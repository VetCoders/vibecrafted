from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .artifacts import validate_artifacts
from .control_plane import (
    await_run,
    control_plane_home,
    ensure_session_id,
    lookup_run,
    normalize_run_root,
    operator_session_name,
    record_stop_transition,
    sync_state,
)
from .events import append_event
from .spawn import _default_command


SUPPORTED_WORKFLOWS = {"workflow", "implement", "research", "review", "marbles"}
SUPPORTED_AGENTS = {"claude", "codex", "gemini", "agy", "junie", "grok", "swarm"}
SUPPORTED_RUNTIMES = {"headless", "terminal", "visible"}
TERMINAL_STATES = {
    "completed",
    "failed",
    "report_validated",
    "report_missing",
    "report_invalid",
    "contract_failed",
    "closed",
    "stopped",
    "timed_out",
    "ghost",
}


@dataclass(frozen=True)
class WorkflowLaunchSpec:
    agent: str
    mode: str
    skill: str
    prompt: str
    file: str
    runtime: str
    root: str
    count: int | None = None
    depth: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def vibecrafted_launcher(source_dir: str | Path) -> Path:
    return Path(source_dir).resolve() / "scripts" / "vibecrafted"


def _run_id(skill: str) -> str:
    stamp = time.strftime("%y%m%d-%H%M%S")
    code = (skill or "run")[:4].ljust(4, "x")
    entropy = int(time.time_ns() % 100000)
    return f"{code}-{stamp}-{entropy:05d}"


def _run_artifact_paths(run_id: str) -> dict[str, Path]:
    run_dir = control_plane_home() / "runtime_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return {
        "meta": run_dir / "meta.json",
        "report": run_dir / "report.md",
        "transcript": run_dir / "transcript.log",
    }


def _core_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _prepend_pythonpath(env: dict[str, str], path: Path) -> None:
    existing = env.get("PYTHONPATH", "")
    entries = [str(path)]
    entries.extend(item for item in existing.split(os.pathsep) if item)
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(entries))


def _dispatcher_command(
    *,
    run_id: str,
    root: str,
    meta_path: Path,
    report_path: Path,
    transcript_path: Path,
    worker_command: list[str],
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "vibecrafted_core.dispatcher",
        "run",
        "--run-id",
        run_id,
        "--root",
        root,
        "--meta",
        str(meta_path),
        "--report",
        str(report_path),
        "--transcript",
        str(transcript_path),
        "--json",
        "--",
    ]
    command.extend(worker_command)
    return command


def _run_is_terminal(run: dict[str, Any]) -> bool:
    if str(run.get("state") or "") in TERMINAL_STATES:
        return True
    if str(run.get("liveness") or "") == "terminal":
        return True
    return run.get("exit_code") is not None


def _path_exists(path: str) -> bool:
    if not path:
        return False
    try:
        return Path(path).is_file()
    except OSError:
        return False


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _terminal_meta_payload(
    *,
    run_id: str,
    run: dict[str, Any],
    report_path: str,
    transcript_path: str,
    meta_path: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "state": str(run.get("state") or ""),
        "liveness": str(run.get("liveness") or ""),
        "operator_state": str(run.get("operator_state") or ""),
        "terminal": _run_is_terminal(run),
        "exit_code": run.get("exit_code"),
        "session_id": str(run.get("session_id") or ""),
        "root": str(run.get("root") or ""),
        "agent": str(run.get("agent") or ""),
        "skill": str(run.get("skill") or ""),
        "mode": str(run.get("mode") or ""),
        "report": report_path,
        "transcript": transcript_path,
        "meta": meta_path,
        "artifact_ok": bool(run.get("artifact_ok")),
        "artifact_errors": list(run.get("artifact_errors") or []),
        "updated_at": str(run.get("updated_at") or ""),
        "completed_at": str(run.get("completed_at") or ""),
    }


def _write_terminal_meta(
    *,
    run_id: str,
    run: dict[str, Any],
    report_path: str,
    transcript_path: str,
    meta_path: str,
) -> dict[str, Any]:
    if not meta_path:
        return {}
    path = Path(meta_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_json_object(path)
    payload = {
        **existing,
        **_terminal_meta_payload(
            run_id=run_id,
            run=run,
            report_path=report_path,
            transcript_path=transcript_path,
            meta_path=meta_path,
        ),
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def await_launch_truth(
    launch: dict[str, Any] | str,
    *,
    timeout_seconds: float = 300,
    interval_seconds: float = 5,
    require_report: bool = True,
    require_transcript_output: bool = False,
) -> dict[str, Any]:
    """Await a launched workflow and verify its announced artifact paths.

    This is intentionally separate from :func:`launch_workflow` so callers can
    keep launch acceptance asynchronous while dispatch engines can later prove
    terminal run truth for returned run ids.
    """
    launch_payload: dict[str, Any]
    if isinstance(launch, dict):
        launch_payload = dict(launch)
        run_id = str(launch_payload.get("run_id") or "").strip()
    else:
        launch_payload = {}
        run_id = str(launch or "").strip()
    if not run_id:
        raise ValueError("run_id is required")

    awaited = await_run(
        run_id,
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
    )
    run = dict(awaited.get("run") or {})
    report_path = str(launch_payload.get("report") or run.get("latest_report") or "")
    transcript_path = str(
        launch_payload.get("transcript") or run.get("latest_transcript") or ""
    )
    meta_path = str(launch_payload.get("meta") or run.get("meta") or "")
    terminal = bool(awaited.get("completed")) and _run_is_terminal(run)

    meta_payload: dict[str, Any] = {}
    if terminal:
        meta_payload = _write_terminal_meta(
            run_id=run_id,
            run=run,
            report_path=report_path,
            transcript_path=transcript_path,
            meta_path=meta_path,
        )

    validation = validate_artifacts(
        meta_path=meta_path or None,
        report_path=report_path or None,
        transcript_path=transcript_path or None,
        require_report=require_report,
        require_transcript_output=require_transcript_output,
    )
    paths_exist = {
        "report": _path_exists(report_path),
        "transcript": _path_exists(transcript_path),
        "meta": _path_exists(meta_path),
    }
    path_errors = [
        f"{name}_missing" for name, exists in paths_exist.items() if not exists
    ]

    return {
        "run_id": run_id,
        "found": bool(awaited.get("found")),
        "completed": bool(awaited.get("completed")),
        "timed_out": bool(awaited.get("timed_out")),
        "terminal": terminal,
        "attempts": awaited.get("attempts"),
        "run": run,
        "report": report_path,
        "transcript": transcript_path,
        "meta": meta_path,
        "paths_exist": paths_exist,
        "artifact_ok": validation.ok and not path_errors,
        "artifact_errors": list(validation.errors) + path_errors,
        "artifact_warnings": list(validation.warnings),
        "meta_payload": meta_payload or validation.meta_payload,
    }


def _stop_signal_target(run: dict[str, Any]) -> tuple[str, int] | None:
    for key in ("launcher_pid", "worker_pgid", "worker_pid"):
        raw = run.get(key)
        if isinstance(raw, int) and raw > 0:
            return key, raw
        if isinstance(raw, str) and raw.strip().isdigit():
            return key, int(raw.strip())
    return None


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _wait_for_pid_exit(pid: int, grace_seconds: float) -> bool:
    deadline = time.monotonic() + max(float(grace_seconds), 0.0)
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            return False
        time.sleep(min(0.05, max(deadline - time.monotonic(), 0.0)))
    return _pid_is_alive(pid)


def _normalized_runtime(raw: str) -> str:
    return raw if raw in SUPPORTED_RUNTIMES else "headless"


def _coerce_positive_int(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        result = int(str(value))
    except ValueError:
        return default
    return result if result > 0 else default


def normalize_launch_spec(
    payload: dict[str, Any], source_dir: str | Path
) -> WorkflowLaunchSpec:
    skill = str(payload.get("skill") or "workflow").strip()
    if skill not in SUPPORTED_WORKFLOWS:
        raise ValueError(f"Unsupported workflow: {skill}")

    default_agent = "swarm" if skill == "research" else "claude"
    agent = str(payload.get("agent") or default_agent).strip()
    if skill == "research":
        agent = "swarm"
    if agent not in SUPPORTED_AGENTS:
        raise ValueError(f"Unsupported agent: {agent}")

    prompt = str(payload.get("prompt") or "").strip()
    file_path = str(payload.get("file") or "").strip()
    root = normalize_run_root(payload.get("root"), source_dir)
    runtime = _normalized_runtime(str(payload.get("runtime") or "headless").strip())
    mode = str(payload.get("mode") or skill).strip() or skill
    count = _coerce_positive_int(
        payload.get("count"), 3 if skill == "marbles" else None
    )
    depth = _coerce_positive_int(
        payload.get("depth"), 3 if skill == "marbles" else None
    )

    if skill != "marbles" and not prompt and not file_path:
        raise ValueError("Launch requires either prompt text or a file path.")

    return WorkflowLaunchSpec(
        agent=agent,
        mode=mode,
        skill=skill,
        prompt=prompt,
        file=file_path,
        runtime=runtime,
        root=root,
        count=count,
        depth=depth,
    )


def _source_prompt(spec: WorkflowLaunchSpec) -> str:
    if spec.file:
        try:
            return (
                Path(spec.file)
                .expanduser()
                .read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            return f"Read the requested prompt file yourself: {spec.file}"
    return spec.prompt


def _runtime_prompt(spec: WorkflowLaunchSpec) -> str:
    report_hint = "${VIBECRAFTED_REPORT_PATH}"
    transcript_hint = "${VIBECRAFTED_TRANSCRIPT_PATH}"
    source_prompt = _source_prompt(spec)
    return f"""You are running under Vibecrafted core runtime.

Contract:
- Work in repository root: {spec.root}
- Skill: vc-{spec.skill}
- Agent request: {spec.agent}
- Mode: {spec.mode}
- Runtime request: {spec.runtime}
- Count: {spec.count or ""}
- Depth: {spec.depth or ""}
- Do not launch or delegate to external agent fleets.
- Do not call legacy Vibecrafted skill launchers or runtime/scripts launchers.
- Write your final report to the path in VIBECRAFTED_REPORT_PATH ({report_hint}).
- Let stdout/stderr form the transcript captured at VIBECRAFTED_TRANSCRIPT_PATH ({transcript_hint}).
- Do not create, overwrite, or summarize run metadata yourself. The runtime owns VIBECRAFTED_META_PATH.

Operator prompt:
{source_prompt}
"""


def build_launch_command(
    spec: WorkflowLaunchSpec, _source_dir: str | Path
) -> list[str]:
    source_prompt = _source_prompt(spec)
    if spec.skill == "research":
        return [
            sys.executable,
            "-m",
            "vibecrafted_core.workflow_runtime",
            "research",
            "--root",
            spec.root,
            "--prompt",
            source_prompt,
        ]
    if spec.skill == "marbles":
        return [
            sys.executable,
            "-m",
            "vibecrafted_core.workflow_runtime",
            "marbles",
            "--agent",
            spec.agent if spec.agent != "swarm" else "codex",
            "--root",
            spec.root,
            "--prompt",
            source_prompt,
            "--count",
            str(spec.count or 3),
            "--depth",
            str(spec.depth or 3),
        ]

    worker_agent = spec.agent
    return _default_command(worker_agent, _runtime_prompt(spec))


def launch_workflow(
    spec: WorkflowLaunchSpec,
    source_dir: str | Path,
    *,
    env: dict[str, str] | None = None,
    retry_of: str = "",
) -> dict[str, Any]:
    run_id = _run_id(spec.skill)
    worker_command = build_launch_command(spec, source_dir)
    artifacts = _run_artifact_paths(run_id)
    command = _dispatcher_command(
        run_id=run_id,
        root=spec.root,
        meta_path=artifacts["meta"],
        report_path=artifacts["report"],
        transcript_path=artifacts["transcript"],
        worker_command=worker_command,
    )
    launch_dir = control_plane_home() / "launches"
    launch_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    launch_log = launch_dir / f"{stamp}_{spec.skill}.log"
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    _prepend_pythonpath(merged_env, _core_package_root())
    session_id = ensure_session_id(merged_env.get("VIBECRAFTED_SESSION_ID"))
    merged_env["VIBECRAFTED_RUN_ID"] = run_id
    merged_env["VIBECRAFTED_SESSION_ID"] = session_id
    merged_env["VIBECRAFTED_REPORT_PATH"] = str(artifacts["report"])
    merged_env["VIBECRAFTED_TRANSCRIPT_PATH"] = str(artifacts["transcript"])
    merged_env["VIBECRAFTED_META_PATH"] = str(artifacts["meta"])
    merged_env["VIBECRAFTED_AGENT"] = spec.agent
    merged_env["VIBECRAFTED_SKILL"] = spec.skill
    merged_env["VIBECRAFTED_RUNTIME"] = spec.runtime
    operator_session = operator_session_name(spec.root, run_id)
    merged_env["VIBECRAFTED_OPERATOR_SESSION"] = operator_session

    append_event(
        kind="launch",
        run_id=run_id,
        message=f"launch accepted for {spec.skill}",
        payload={
            "state": "created",
            "agent": spec.agent,
            "skill": spec.skill,
            "mode": spec.mode,
            "runtime": spec.runtime,
            "root": spec.root,
            "operator_session": operator_session,
            "session_id": session_id,
            "identity_required": True,
            "source_dir": str(Path(source_dir).resolve()),
            "prompt": spec.prompt,
            "file": spec.file,
            "report": str(artifacts["report"]),
            "transcript": str(artifacts["transcript"]),
            "meta": str(artifacts["meta"]),
            "worker_command": worker_command,
            "retry_of": retry_of,
        },
    )
    with launch_log.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": stamp,
                    "run_id": run_id,
                    "spec": spec.to_payload(),
                    "worker_command": worker_command,
                    "dispatch_command": command,
                    "retry_of": retry_of,
                    "session_id": session_id,
                    "operator_session": operator_session,
                }
            )
            + "\n"
        )
        try:
            proc = subprocess.Popen(
                command,
                cwd=Path(source_dir).resolve(),
                env=merged_env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                text=True,
            )
        except OSError as exc:
            handle.write(
                json.dumps(
                    {
                        "ts": stamp,
                        "event": "spawn_error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                + "\n"
            )
            return {
                "accepted": False,
                "message": f"Failed to launch {spec.skill}: {exc}",
                "command": command,
                "worker_command": worker_command,
                "launch_log": str(launch_log),
                "spec": spec.to_payload(),
                "error": f"{type(exc).__name__}: {exc}",
                "run_id": run_id,
                "retry_of": retry_of,
                "control_plane": sync_state(),
            }
        append_event(
            kind="launch",
            run_id=run_id,
            message="dispatcher process spawned",
            payload={
                "state": "process_spawned",
                "launcher_pid": proc.pid,
                "agent": spec.agent,
                "skill": spec.skill,
                "mode": spec.mode,
                "runtime": spec.runtime,
                "root": spec.root,
                "operator_session": operator_session,
                "session_id": session_id,
                "identity_required": True,
                "source_dir": str(Path(source_dir).resolve()),
                "prompt": spec.prompt,
                "file": spec.file,
                "report": str(artifacts["report"]),
                "transcript": str(artifacts["transcript"]),
                "meta": str(artifacts["meta"]),
                "worker_command": worker_command,
                "retry_of": retry_of,
            },
        )
        handle.write(
            json.dumps({"ts": stamp, "event": "spawned", "pid": proc.pid}) + "\n"
        )

    snapshot = sync_state()
    return {
        "accepted": True,
        "message": f"Launched {spec.skill} via Vibecrafted core runtime.",
        "command": command,
        "worker_command": worker_command,
        "pid": proc.pid,
        "run_id": run_id,
        "report": str(artifacts["report"]),
        "transcript": str(artifacts["transcript"]),
        "meta": str(artifacts["meta"]),
        "session_id": session_id,
        "operator_session": operator_session,
        "control_plane_identity": {
            "run_id": run_id,
            "session_id": session_id,
            "operator_session": operator_session,
        },
        "retry_of": retry_of,
        "launch_log": str(launch_log),
        "spec": spec.to_payload(),
        "control_plane": snapshot,
    }


def stop_run(
    run_id: str,
    *,
    reason: str = "operator stop request",
    grace_seconds: float = 2.0,
) -> dict[str, Any]:
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run = lookup_run(target)
    if run is None:
        record_stop_transition(
            target,
            accepted=False,
            reason="run_not_found",
        )
        return {"accepted": False, "run_id": target, "reason": "run_not_found"}

    if _run_is_terminal(run):
        record_stop_transition(
            target,
            run=run,
            accepted=False,
            reason="run_terminal",
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "run_terminal",
            "run": run,
        }

    signal_target = _stop_signal_target(run)
    if signal_target is None:
        record_stop_transition(
            target,
            run=run,
            accepted=False,
            reason="missing_signal_target",
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "missing_signal_target",
            "run": run,
        }

    target_kind, target_pid = signal_target
    target_pgid: int | None = None
    signal_sent = False
    already_dead = False
    alive_after_grace: bool | None = None
    stop_reason = reason
    stop_error = ""
    try:
        if target_kind == "launcher_pid":
            target_pgid = os.getpgid(target_pid)
            os.killpg(target_pgid, signal.SIGTERM)
        elif target_kind == "worker_pgid":
            target_pgid = target_pid
            os.killpg(target_pgid, signal.SIGTERM)
        else:
            os.kill(target_pid, signal.SIGTERM)
        signal_sent = True
    except ProcessLookupError:
        already_dead = True
        stop_reason = "pid_gone_before_stop"
    except OSError as exc:
        stop_error = f"{type(exc).__name__}: {exc}"

    accepted = not stop_error
    if signal_sent:
        alive_after_grace = _wait_for_pid_exit(target_pid, grace_seconds)
    elif already_dead:
        alive_after_grace = False

    record_stop_transition(
        target,
        run=run,
        accepted=accepted,
        reason=stop_reason if accepted else "signal_failed",
        signal_name="SIGTERM",
        target=target_kind,
        target_pid=target_pid,
        target_pgid=target_pgid,
        signal_sent=signal_sent,
        already_dead=already_dead,
        alive_after_grace=alive_after_grace,
        grace_seconds=grace_seconds,
        exit_code=143 if signal_sent else None,
        error=stop_error,
    )
    return {
        "accepted": accepted,
        "run_id": target,
        "target": target_kind,
        "target_pid": target_pid,
        "target_pgid": target_pgid,
        "signal_sent": signal_sent,
        "already_dead": already_dead,
        "alive_after_grace": alive_after_grace,
        "reason": stop_reason if accepted else "signal_failed",
        "error": stop_error,
        "run": lookup_run(target),
    }


def retry_run(
    run_id: str,
    source_dir: str | Path = ".",
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run = lookup_run(target)
    if run is None:
        append_event(
            kind="audit:retry",
            run_id=target,
            message="retry rejected: run not found",
            payload={"accepted": False, "reason": "run_not_found"},
        )
        return {"accepted": False, "run_id": target, "reason": "run_not_found"}

    if not _run_is_terminal(run):
        append_event(
            kind="audit:retry",
            run_id=target,
            message="retry rejected: run not terminal",
            payload={
                "accepted": False,
                "reason": "run_not_terminal",
                "state": run.get("state"),
            },
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "run_not_terminal",
            "run": run,
        }

    payload: dict[str, Any] = {
        "skill": str(run.get("skill") or "workflow"),
        "agent": str(run.get("agent") or "claude"),
        "prompt": str(run.get("prompt") or ""),
        "file": str(run.get("file") or ""),
        "runtime": str(run.get("runtime") or "headless"),
        "root": str(run.get("root") or Path(source_dir).resolve()),
    }
    mode = str(run.get("mode") or "").strip()
    if mode:
        payload["mode"] = mode

    try:
        spec = normalize_launch_spec(payload, source_dir)
    except ValueError as exc:
        append_event(
            kind="audit:retry",
            run_id=target,
            message="retry rejected: launch spec invalid",
            payload={
                "accepted": False,
                "reason": "invalid_retry_spec",
                "error": str(exc),
            },
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "invalid_retry_spec",
            "error": str(exc),
            "run": run,
        }

    launched = launch_workflow(spec, source_dir, env=env, retry_of=target)
    append_event(
        kind="audit:retry",
        run_id=target,
        message="retry dispatched" if launched.get("accepted") else "retry failed",
        payload={
            "accepted": bool(launched.get("accepted")),
            "new_run_id": launched.get("run_id"),
            "error": launched.get("error", ""),
        },
    )
    return {
        "accepted": bool(launched.get("accepted")),
        "run_id": target,
        "retry_run_id": str(launched.get("run_id") or ""),
        "launch": launched,
    }


def block_run(
    run_id: str,
    *,
    reason: str = "operator block request",
    note: str = "",
) -> dict[str, Any]:
    """Mark an in-flight run as ``blocked`` with an audited lifecycle event.

    Blocking is an operator lever, not a signal: it records that the run needs
    human intervention and pins it to the terminal ``blocked`` state so the
    control plane stops treating it as active. A blocked run can later be
    resumed through :func:`retry_run` (which requires a terminal state).
    """
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run = lookup_run(target)
    if run is None:
        append_event(
            kind="audit:block",
            run_id=target,
            message="block rejected: run not found",
            payload={"accepted": False, "reason": "run_not_found"},
        )
        return {"accepted": False, "run_id": target, "reason": "run_not_found"}

    if _run_is_terminal(run):
        append_event(
            kind="audit:block",
            run_id=target,
            message="block rejected: run already terminal",
            payload={
                "accepted": False,
                "reason": "run_terminal",
                "state": run.get("state"),
            },
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "run_terminal",
            "run": run,
        }

    append_event(
        kind="audit:block",
        run_id=target,
        message="run marked blocked",
        payload={
            "accepted": True,
            "reason": reason,
            "note": note,
            "state": "blocked",
        },
    )
    return {
        "accepted": True,
        "run_id": target,
        "reason": reason,
        "note": note,
        "run": lookup_run(target),
    }
