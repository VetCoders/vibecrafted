from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from .agent_stream import AgentStreamParser
from .artifacts import ArtifactValidation, validate_artifacts
from .control_plane import ensure_session_id, normalize_run_root
from .events import append_event
from .lifecycle import EventKind, RunState


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _infer_agent(command: Sequence[str]) -> str:
    if not command:
        return "agent"
    name = Path(str(command[0])).name
    if name in {"claude", "codex", "gemini", "agy", "junie", "grok"}:
        return name
    if name in {"python", "python3"}:
        return "python"
    return name or "agent"


@dataclass
class AsyncRunHandle:
    run_id: str
    command: tuple[str, ...]
    root: Path
    process: asyncio.subprocess.Process
    started_at: datetime
    meta_path: Path | None = None
    report_path: Path | None = None
    transcript_path: Path | None = None
    pgid: int | None = None
    states: list[RunState] = field(default_factory=lambda: [RunState.CREATED])
    exit_code: int | None = None
    completed_at: datetime | None = None
    artifact_validation: ArtifactValidation | None = None
    first_output_seen: bool = False
    session_id: str = ""
    agent: str = ""
    agent_session_id: str = ""
    agent_model: str = ""
    tokens_input: int = 0
    tokens_cached_input: int = 0
    tokens_output: int = 0
    cost_usd: float | None = None
    resume_command: str = ""

    @property
    def state(self) -> RunState:
        return self.states[-1]


class AsyncSupervisor:
    def __init__(self) -> None:
        self._runs: dict[str, AsyncRunHandle] = {}

    def get(self, run_id: str) -> AsyncRunHandle | None:
        return self._runs.get(run_id)

    async def spawn(
        self,
        *,
        run_id: str,
        command: Sequence[str],
        root: str | Path = ".",
        env: Mapping[str, str] | None = None,
        meta_path: str | Path | None = None,
        report_path: str | Path | None = None,
        transcript_path: str | Path | None = None,
        prompt_file_path: str | Path | None = None,
    ) -> AsyncRunHandle:
        if not command:
            raise ValueError("command must not be empty")
        cwd = Path(normalize_run_root(root))
        transcript = Path(transcript_path) if transcript_path is not None else None
        if transcript is not None:
            transcript.parent.mkdir(parents=True, exist_ok=True)
        prompt_file = Path(prompt_file_path).expanduser() if prompt_file_path else None

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        session_id = ensure_session_id(merged_env.get("VIBECRAFTED_SESSION_ID"))
        merged_env["VIBECRAFTED_SESSION_ID"] = session_id
        if meta_path is not None:
            merged_env["VIBECRAFTED_META_PATH"] = str(meta_path)
        if report_path is not None:
            merged_env["VIBECRAFTED_REPORT_PATH"] = str(report_path)
        if transcript_path is not None:
            merged_env["VIBECRAFTED_TRANSCRIPT_PATH"] = str(transcript_path)
        if prompt_file is not None:
            merged_env["VIBECRAFTED_PROMPT_PATH"] = str(prompt_file)
        agent = str(merged_env.get("VIBECRAFTED_AGENT") or _infer_agent(command))
        started_at = _utc_now()

        await self._emit(
            run_id,
            RunState.CREATED,
            "async supervisor run created",
            payload={
                "root": str(cwd),
                "command": list(command),
                "meta": str(meta_path or ""),
                "report": str(report_path or ""),
                "transcript": str(transcript_path or ""),
                "prompt_file": str(prompt_file or ""),
                "started_at": started_at.isoformat(),
                "session_id": session_id,
                "identity_required": True,
                "agent": agent,
            },
        )

        stdin_handle = None
        try:
            if prompt_file is not None:
                stdin_handle = prompt_file.open("rb")
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd),
                env=merged_env,
                stdin=stdin_handle,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            if stdin_handle is not None:
                stdin_handle.close()
        handle = AsyncRunHandle(
            run_id=run_id,
            command=tuple(command),
            root=cwd,
            process=process,
            started_at=started_at,
            meta_path=Path(meta_path) if meta_path is not None else None,
            report_path=Path(report_path) if report_path is not None else None,
            transcript_path=transcript,
            session_id=session_id,
            agent=agent,
        )
        try:
            handle.pgid = os.getpgid(process.pid)
        except ProcessLookupError:
            handle.pgid = None
        self._runs[run_id] = handle
        await self._transition(
            handle,
            RunState.PROCESS_SPAWNED,
            "process spawned",
            payload={
                "worker_pid": handle.process.pid,
                "worker_pgid": handle.pgid,
                "meta": str(handle.meta_path or ""),
                "report": str(handle.report_path or ""),
                "transcript": str(handle.transcript_path or ""),
            },
        )
        return handle

    async def run(
        self,
        *,
        run_id: str,
        command: Sequence[str],
        root: str | Path = ".",
        env: Mapping[str, str] | None = None,
        meta_path: str | Path | None = None,
        report_path: str | Path | None = None,
        transcript_path: str | Path | None = None,
        prompt_file_path: str | Path | None = None,
        timeout: float | None = None,
        require_report: bool = True,
        require_transcript_output: bool = False,
        tee_output: bool = False,
    ) -> AsyncRunHandle:
        handle = await self.spawn(
            run_id=run_id,
            command=command,
            root=root,
            env=env,
            meta_path=meta_path,
            report_path=report_path,
            transcript_path=transcript_path,
            prompt_file_path=prompt_file_path,
        )
        try:
            if timeout is None:
                await self._watch_process(handle, tee_output=tee_output)
            else:
                await asyncio.wait_for(
                    self._watch_process(handle, tee_output=tee_output),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            await self._terminate(handle)
            handle.exit_code = handle.process.returncode
            handle.completed_at = _utc_now()
            await self._transition(
                handle,
                RunState.STALLED,
                "process timed out",
                payload={
                    "exit_code": handle.exit_code,
                    "completed_at": handle.completed_at.isoformat(),
                    "liveness": "terminal",
                },
            )
            return handle

        handle.exit_code = handle.process.returncode
        handle.completed_at = _utc_now()
        if handle.exit_code == 0:
            await self._transition(
                handle,
                RunState.COMPLETED,
                "process completed",
                payload={
                    "exit_code": handle.exit_code,
                    "completed_at": handle.completed_at.isoformat(),
                    "liveness": "terminal",
                },
            )
        else:
            await self._transition(
                handle,
                RunState.FAILED,
                f"process failed with exit code {handle.exit_code}",
                payload={
                    "exit_code": handle.exit_code,
                    "completed_at": handle.completed_at.isoformat(),
                    "liveness": "terminal",
                },
            )

        handle.artifact_validation = validate_artifacts(
            meta_path=handle.meta_path,
            report_path=handle.report_path,
            transcript_path=handle.transcript_path,
            require_report=require_report,
            require_transcript_output=require_transcript_output,
        )
        await self._emit(
            handle.run_id,
            RunState.ARTIFACT_SEEN,
            "artifacts inspected",
            payload={
                "event_kind": EventKind.ARTIFACT.value,
                "meta": str(handle.meta_path or ""),
                "report": str(handle.report_path or ""),
                "transcript": str(handle.transcript_path or ""),
                "agent": handle.agent,
                "agent_session_id": handle.agent_session_id,
                "agent_model": handle.agent_model,
                "tokens_input": handle.tokens_input,
                "tokens_cached_input": handle.tokens_cached_input,
                "tokens_output": handle.tokens_output,
                "tokens_total": handle.tokens_input + handle.tokens_output,
                "cost_usd": handle.cost_usd,
                "resume_command": handle.resume_command,
                **handle.artifact_validation.as_payload(),
            },
        )
        if handle.artifact_validation.ok:
            await self._transition(
                handle, RunState.REPORT_VALIDATED, "artifact contract validated"
            )
        else:
            failed_state = (
                RunState.REPORT_MISSING
                if "report_missing" in handle.artifact_validation.errors
                else RunState.REPORT_INVALID
            )
            await self._transition(
                handle,
                failed_state,
                "artifact contract failed",
                payload={
                    **handle.artifact_validation.as_payload(),
                    "liveness": "terminal",
                },
            )
        return handle

    async def _watch_process(
        self, handle: AsyncRunHandle, *, tee_output: bool = False
    ) -> None:
        assert handle.process.stdout is not None
        parser = AgentStreamParser(handle.agent)
        while True:
            chunk = await handle.process.stdout.readline()
            if not chunk:
                break
            if handle.transcript_path is not None:
                with handle.transcript_path.open("ab") as transcript:
                    transcript.write(chunk)
            display_text = parser.feed_line(chunk)
            self._sync_stream_summary(handle, parser)
            if tee_output:
                if display_text:
                    sys.stdout.buffer.write(display_text.encode("utf-8"))
                    sys.stdout.buffer.flush()
            if not handle.first_output_seen:
                handle.first_output_seen = True
                await self._transition(
                    handle,
                    RunState.FIRST_OUTPUT_SEEN,
                    "first output observed",
                    payload={
                        "heartbeat_at": _utc_now().isoformat(),
                    },
                )
                await self._transition(
                    handle,
                    RunState.ACTIVE,
                    "process active",
                    payload={
                        "liveness": "pid_alive",
                        "heartbeat_at": _utc_now().isoformat(),
                    },
                )
        await handle.process.wait()
        self._sync_stream_summary(handle, parser)
        self._write_meta_summary(handle)

    def _sync_stream_summary(
        self, handle: AsyncRunHandle, parser: AgentStreamParser
    ) -> None:
        handle.agent_session_id = parser.session_id
        handle.agent_model = parser.model_id
        handle.tokens_input = parser.tokens_input
        handle.tokens_cached_input = parser.tokens_cached_input
        handle.tokens_output = parser.tokens_output
        handle.cost_usd = parser.cost_usd
        handle.resume_command = parser.resume_command(handle.root)

    def _write_meta_summary(self, handle: AsyncRunHandle) -> None:
        if handle.meta_path is None:
            return
        payload: dict[str, object] = {}
        if handle.meta_path.exists():
            try:
                loaded = json.loads(handle.meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                payload.update(loaded)
        payload.update(
            {
                "run_id": handle.run_id,
                "agent": handle.agent,
                "session_id": handle.agent_session_id,
                "agent_session_id": handle.agent_session_id,
                "agent_model": handle.agent_model,
                "runtime_session_id": handle.session_id,
                "root": str(handle.root),
                "report": str(handle.report_path or ""),
                "transcript": str(handle.transcript_path or ""),
                "tokens_input": handle.tokens_input,
                "tokens_cached_input": handle.tokens_cached_input,
                "tokens_output": handle.tokens_output,
                "tokens_total": handle.tokens_input + handle.tokens_output,
                "cost_usd": handle.cost_usd
                if handle.cost_usd is not None
                else "unknown",
                "resume_command": handle.resume_command,
            }
        )
        handle.meta_path.parent.mkdir(parents=True, exist_ok=True)
        handle.meta_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    async def _terminate(self, handle: AsyncRunHandle) -> None:
        if handle.process.returncode is not None:
            return
        try:
            if handle.pgid is not None:
                os.killpg(handle.pgid, signal.SIGTERM)
            else:
                handle.process.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(handle.process.wait(), timeout=3)
        except asyncio.TimeoutError:
            try:
                if handle.pgid is not None:
                    os.killpg(handle.pgid, signal.SIGKILL)
                else:
                    handle.process.kill()
            except ProcessLookupError:
                pass
            await handle.process.wait()

    async def _transition(
        self,
        handle: AsyncRunHandle,
        state: RunState,
        message: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> None:
        handle.states.append(state)
        event_payload: dict[str, object] = {
            "root": str(handle.root),
            "session_id": handle.session_id,
            "identity_required": True,
        }
        if payload:
            event_payload.update(payload)
        await self._emit(handle.run_id, state, message, payload=event_payload)

    async def _emit(
        self,
        run_id: str,
        state: RunState,
        message: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> None:
        event_payload: dict[str, object] = {
            "event_kind": EventKind.LIFECYCLE.value,
            "state": state.value,
        }
        if payload:
            event_payload.update(payload)
        await asyncio.to_thread(
            append_event,
            kind=f"{EventKind.LIFECYCLE.value}:{state.value}",
            run_id=run_id,
            message=message,
            payload=event_payload,
        )
