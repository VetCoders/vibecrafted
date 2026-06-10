from __future__ import annotations

import datetime as dt
import json
import os
import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .agent_dispatch import extract_session_id, sandbox_supported
from .control_plane import ensure_session_id, normalize_run_root
from .events import append_event

EventCallback = Callable[[dict[str, Any]], None]


@dataclass
class SpawnHandle:
    run_id: str
    agent: str
    skill: str
    mode: str
    root: Path
    process: Any
    pgid: int | None
    started_at: str
    command: list[str]
    meta_path: Path | None = None
    transcript_path: Path | None = None
    exit_code: int | None = None
    completed_at: str = ""
    session_id: str = ""
    _done: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    @property
    def pid(self) -> int:
        return self.process.pid

    def wait(self, timeout: float | None = None) -> int:
        if not self._done.wait(timeout):
            raise TimeoutError(f"spawn {self.run_id} still running")
        return int(self.exit_code if self.exit_code is not None else 1)


class _SandboxProcess:
    def __init__(self) -> None:
        self.pid = os.getpid()

    def wait(self) -> int:
        return 0


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _set_child_pgid() -> None:
    try:
        os.setpgid(0, 0)
    except OSError:
        pass


def _default_command(agent: str, prompt: str) -> list[str]:
    if agent == "claude":
        return [
            "claude",
            "--print",
            "--verbose",
            "--dangerously-skip-permissions",
            prompt,
        ]
    if agent == "codex":
        return ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", prompt]
    if agent == "gemini":
        return ["gemini", "--yolo", "--prompt", prompt]
    if agent == "agy":
        return [
            "bash",
            "-lc",
            "agy --print --dangerously-skip-permissions --add-dir . --print-timeout 30m '' <<< \"$1\"",
            "agy",
            prompt,
        ]
    if agent == "junie":
        return ["junie", "--task", prompt, "--project", ".", "--skip-update-check"]
    if agent == "grok":
        return [
            "grok",
            "--cwd",
            ".",
            "--permission-mode",
            "bypassPermissions",
            "--no-alt-screen",
            "--single",
            prompt,
        ]
    raise ValueError(f"unsupported agent: {agent}")


def _parse_launcher_assignment(path: Path, key: str) -> str:
    if not path.is_file():
        return ""
    prefix = f"{key}="
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(prefix):
            continue
        raw = line.split("=", 1)[1].strip()
        try:
            parts = shlex.split(raw)
        except ValueError:
            return raw.strip("'\"")
        return parts[0] if parts else ""
    return ""


def _read_meta(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _maybe_extract_session_id(handle: SpawnHandle) -> str:
    meta = _read_meta(handle.meta_path)
    if meta.get("session_id"):
        return str(meta["session_id"])

    transcript = handle.transcript_path
    if transcript is None and meta.get("transcript"):
        transcript = Path(str(meta["transcript"]))
    if transcript is None or not transcript.is_file():
        return ""

    text = transcript.read_text(encoding="utf-8", errors="replace")
    session_id = extract_session_id(handle.agent, text) or ""
    if session_id and handle.meta_path is not None and handle.meta_path.is_file():
        meta["session_id"] = session_id
        _write_meta(handle.meta_path, meta)
    return session_id


class Supervisor:
    """Small UNIX process supervisor for Vibecrafted agent launchers."""

    def spawn(
        self,
        agent: str,
        prompt: str,
        *,
        skill: str,
        mode: str,
        root: str | os.PathLike[str],
        on_event: EventCallback | None = None,
        command: Sequence[str] | None = None,
        env: dict[str, str] | None = None,
        run_id: str | None = None,
        meta_path: str | os.PathLike[str] | None = None,
        transcript_path: str | os.PathLike[str] | None = None,
        sandbox: bool = False,
        sandbox_policy: str | os.PathLike[str] | None = None,
        sandbox_config: dict[str, Any] | None = None,
    ) -> SpawnHandle:
        root_path = Path(normalize_run_root(root))
        command_list = (
            list(command) if command is not None else _default_command(agent, prompt)
        )
        effective_run_id = (
            run_id or os.environ.get("VIBECRAFTED_RUN_ID") or f"{skill}-manual"
        )

        launcher = Path(command_list[-1]).expanduser() if command_list else Path()
        inferred_meta = Path(meta_path).expanduser() if meta_path is not None else None
        inferred_transcript = (
            Path(transcript_path).expanduser() if transcript_path is not None else None
        )
        if inferred_meta is None and launcher.suffix == ".sh":
            parsed = _parse_launcher_assignment(launcher, "meta")
            inferred_meta = Path(parsed).expanduser() if parsed else None
        if inferred_transcript is None and launcher.suffix == ".sh":
            parsed = _parse_launcher_assignment(launcher, "transcript")
            inferred_transcript = Path(parsed).expanduser() if parsed else None

        child_env = os.environ.copy()
        if env:
            child_env.update(env)
        session_id = ensure_session_id(child_env.get("VIBECRAFTED_SESSION_ID"))
        child_env.setdefault("VIBECRAFTED_RUN_ID", effective_run_id)
        child_env["VIBECRAFTED_SESSION_ID"] = session_id

        if sandbox:
            if not sandbox_supported(agent):
                raise ValueError(f"agent does not support sandbox dispatch: {agent}")
            process = _SandboxProcess()
            handle = SpawnHandle(
                run_id=effective_run_id,
                agent=agent,
                skill=skill,
                mode=mode,
                root=root_path,
                process=process,
                pgid=None,
                started_at=_now_iso(),
                command=command_list,
                meta_path=inferred_meta,
                transcript_path=inferred_transcript,
                session_id=session_id,
            )
            self._emit(
                "spawn-started",
                handle,
                "supervisor spawned sandbox child",
                {"pid": process.pid, "pgid": None, "command": command_list},
                on_event,
            )
            thread = threading.Thread(
                target=self._run_sandbox,
                args=(
                    handle,
                    child_env,
                    sandbox_policy,
                    sandbox_config or {},
                    on_event,
                ),
                daemon=True,
            )
            handle._thread = thread
            thread.start()
            return handle

        process = subprocess.Popen(
            command_list,
            cwd=str(root_path),
            env=child_env,
            text=True,
            preexec_fn=_set_child_pgid if hasattr(os, "setpgid") else None,
        )
        try:
            pgid = os.getpgid(process.pid)
        except OSError:
            pgid = None

        handle = SpawnHandle(
            run_id=effective_run_id,
            agent=agent,
            skill=skill,
            mode=mode,
            root=root_path,
            process=process,
            pgid=pgid,
            started_at=_now_iso(),
            command=command_list,
            meta_path=inferred_meta,
            transcript_path=inferred_transcript,
            session_id=session_id,
        )
        self._emit(
            "spawn-started",
            handle,
            "supervisor spawned child",
            {"pid": process.pid, "pgid": pgid, "command": command_list},
            on_event,
        )
        thread = threading.Thread(
            target=self._wait_owner, args=(handle, on_event), daemon=True
        )
        handle._thread = thread
        thread.start()
        return handle

    def _run_sandbox(
        self,
        handle: SpawnHandle,
        env: dict[str, str],
        sandbox_policy: str | os.PathLike[str] | None,
        sandbox_config: dict[str, Any],
        on_event: EventCallback | None,
    ) -> None:
        try:
            from .sandbox import SandboxAdapter, SandboxPolicy

            policy = SandboxPolicy.load(sandbox_policy, root=handle.root)
            adapter = SandboxAdapter(
                policy=policy,
                server_url=sandbox_config.get("server_url"),
                api_key_path=sandbox_config.get("api_key_path"),
            )
            result = adapter.execute_sync(
                handle.command,
                env=env,
                cwd=handle.root,
                timeout=sandbox_config.get("timeout"),
                run_id=handle.run_id,
                agent=handle.agent,
                skill=handle.skill,
                mode=handle.mode,
                on_event=on_event,
            )
            handle.exit_code = result.exit_code
        except Exception as exc:  # pragma: no cover - defensive event path
            handle.exit_code = 1
            self._emit(
                "spawn-failed",
                handle,
                f"sandbox execution failed: {exc}",
                {"pid": handle.pid, "pgid": handle.pgid, "exit_code": 1},
                on_event,
            )
            handle._done.set()
            return

        handle.completed_at = _now_iso()
        extracted_session_id = _maybe_extract_session_id(handle)
        if extracted_session_id:
            handle.session_id = extracted_session_id
        kind = "spawn-completed" if handle.exit_code == 0 else "spawn-failed"
        self._emit(
            kind,
            handle,
            f"sandbox child exited with {handle.exit_code}",
            {
                "pid": handle.pid,
                "pgid": handle.pgid,
                "exit_code": handle.exit_code,
                "session_id": handle.session_id,
                "meta": str(handle.meta_path or ""),
                "transcript": str(handle.transcript_path or ""),
                "substrate": "microsandbox",
            },
            on_event,
        )
        handle._done.set()

    def _wait_owner(self, handle: SpawnHandle, on_event: EventCallback | None) -> None:
        exit_code = handle.process.wait()
        handle.exit_code = exit_code
        handle.completed_at = _now_iso()
        extracted_session_id = _maybe_extract_session_id(handle)
        if extracted_session_id:
            handle.session_id = extracted_session_id
        kind = "spawn-completed" if exit_code == 0 else "spawn-failed"
        self._emit(
            kind,
            handle,
            f"supervisor child exited with {exit_code}",
            {
                "pid": handle.pid,
                "pgid": handle.pgid,
                "exit_code": exit_code,
                "session_id": handle.session_id,
                "meta": str(handle.meta_path or ""),
                "transcript": str(handle.transcript_path or ""),
            },
            on_event,
        )
        if handle.transcript_path and not handle.session_id:
            self._emit(
                "session_id_extraction_failed",
                handle,
                "could not extract agent session_id from transcript",
                {"agent": handle.agent, "transcript": str(handle.transcript_path)},
                on_event,
            )
        handle._done.set()

    def _emit(
        self,
        kind: str,
        handle: SpawnHandle,
        message: str,
        payload: dict[str, Any],
        on_event: EventCallback | None,
    ) -> None:
        event = append_event(
            kind,
            handle.run_id,
            message,
            {
                "agent": handle.agent,
                "skill": handle.skill,
                "mode": handle.mode,
                "root": str(handle.root),
                "session_id": handle.session_id,
                "identity_required": True,
                **payload,
            },
        )
        if on_event is not None:
            on_event(event)
