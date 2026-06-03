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

from .control_plane import control_plane_home, lookup_run, sync_state
from .events import append_event


SUPPORTED_WORKFLOWS = {"workflow", "research", "review", "marbles"}
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


def _stop_signal_target(run: dict[str, Any]) -> tuple[str, int] | None:
    for key in ("worker_pgid", "worker_pid", "launcher_pid"):
        raw = run.get(key)
        if isinstance(raw, int) and raw > 0:
            return key, raw
        if isinstance(raw, str) and raw.strip().isdigit():
            return key, int(raw.strip())
    return None


def _normalized_runtime(raw: str) -> str:
    return raw if raw in SUPPORTED_RUNTIMES else "headless"


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
    root = str(payload.get("root") or Path(source_dir).resolve()).strip()
    runtime = _normalized_runtime(str(payload.get("runtime") or "headless").strip())
    mode = str(payload.get("mode") or skill).strip() or skill

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
    )


def build_launch_command(spec: WorkflowLaunchSpec, source_dir: str | Path) -> list[str]:
    launcher = vibecrafted_launcher(source_dir)
    if not launcher.exists():
        raise FileNotFoundError(f"Command deck not found at {launcher}")

    command = ["bash", str(launcher), spec.skill]
    if spec.skill != "research":
        command.append(spec.agent)

    command.extend(["--runtime", spec.runtime])
    if spec.root:
        command.extend(["--root", spec.root])
    if spec.file:
        command.extend(["--file", spec.file])
    elif spec.prompt:
        command.extend(["--prompt", spec.prompt])
    elif spec.skill == "marbles":
        command.extend(["--depth", "3"])

    return command


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
    merged_env["VIBECRAFTED_RUN_ID"] = run_id
    merged_env["VIBECRAFTED_REPORT_PATH"] = str(artifacts["report"])
    merged_env["VIBECRAFTED_TRANSCRIPT_PATH"] = str(artifacts["transcript"])
    merged_env["VIBECRAFTED_META_PATH"] = str(artifacts["meta"])

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
        "message": f"Launched {spec.skill} via the existing command deck.",
        "command": command,
        "worker_command": worker_command,
        "pid": proc.pid,
        "run_id": run_id,
        "report": str(artifacts["report"]),
        "transcript": str(artifacts["transcript"]),
        "meta": str(artifacts["meta"]),
        "retry_of": retry_of,
        "launch_log": str(launch_log),
        "spec": spec.to_payload(),
        "control_plane": snapshot,
    }


def stop_run(run_id: str, *, reason: str = "operator stop request") -> dict[str, Any]:
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run = lookup_run(target)
    if run is None:
        append_event(
            kind="audit:stop",
            run_id=target,
            message="stop rejected: run not found",
            payload={"accepted": False, "reason": "run_not_found"},
        )
        return {"accepted": False, "run_id": target, "reason": "run_not_found"}

    if _run_is_terminal(run):
        append_event(
            kind="audit:stop",
            run_id=target,
            message="stop rejected: run already terminal",
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

    signal_target = _stop_signal_target(run)
    if signal_target is None:
        append_event(
            kind="audit:stop",
            run_id=target,
            message="stop rejected: no signal target",
            payload={"accepted": False, "reason": "missing_signal_target"},
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "missing_signal_target",
            "run": run,
        }

    target_kind, target_pid = signal_target
    try:
        if target_kind == "worker_pgid":
            os.killpg(target_pid, signal.SIGTERM)
        else:
            os.kill(target_pid, signal.SIGTERM)
        accepted = True
        stop_error = ""
    except OSError as exc:
        accepted = False
        stop_error = f"{type(exc).__name__}: {exc}"

    append_event(
        kind="audit:stop",
        run_id=target,
        message="stop signal dispatched" if accepted else "stop signal failed",
        payload={
            "accepted": accepted,
            "reason": reason,
            "signal": "SIGTERM",
            "target": target_kind,
            "target_pid": target_pid,
            "error": stop_error,
        },
    )
    time.sleep(0.05)
    return {
        "accepted": accepted,
        "run_id": target,
        "target": target_kind,
        "target_pid": target_pid,
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
