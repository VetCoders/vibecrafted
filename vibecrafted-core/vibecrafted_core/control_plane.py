from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import errno
import fcntl
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from .runtime_paths import vibecrafted_home


ACTIVE_STATES = {
    "created",
    "process_spawned",
    "first_output_seen",
    "active",
    "artifact_seen",
    "report_started",
    "initialized",
    "launching",
    "promise",
    "confirmed",
    "running",
    "paused",
    "stalled",
}
FINAL_STATES = {
    "report_validated",
    "completed",
    "closed",
    "converged",
    "stopped",
    "blocked",
    "failed",
    "report_missing",
    "report_invalid",
    "contract_failed",
    "recovery_required",
    "timed_out",
    "gc",
    "ghost",
}
BLOCKED_STATES = {
    "blocked",
    "stalled",
    "report_missing",
    "report_invalid",
    "contract_failed",
    "recovery_required",
}
SKILL_CODE_MAP = {
    "agnt": "agents",
    "deco": "decorate",
    "delg": "delegate",
    "vdou": "dou",
    "fwup": "followup",
    "hydr": "hydrate",
    "impl": "implement",
    "init": "init",
    "just": "justdo",
    "marb": "marbles",
    "prtn": "partner",
    "plan": "plan",
    "prun": "prune",
    "rels": "release",
    "rsch": "research",
    "rvew": "review",
    "scaf": "scaffold",
    "wflw": "workflow",
}
RUN_STALL_SECONDS = 20 * 60
LIVENESS_STALE_HEARTBEAT_SECONDS = 120
LIVENESS_STALE_HEARTBEAT_ENV = "VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS"
RUN_GC_GRACE_SECONDS = 6 * 60 * 60
RUN_GC_GRACE_ENV = "VIBECRAFTED_RUN_GC_GRACE_SECONDS"
RUN_SNAPSHOT_RETENTION_SECONDS = 7 * 24 * 60 * 60
RUN_SNAPSHOT_RETENTION_SECONDS_ENV = "VIBECRAFTED_RUN_SNAPSHOT_RETENTION_SECONDS"
RUN_SNAPSHOT_RETENTION_COUNT = 2000
RUN_SNAPSHOT_RETENTION_COUNT_ENV = "VIBECRAFTED_RUN_SNAPSHOT_RETENTION_COUNT"
EVENT_TAIL_LIMIT = 16
RECENT_RUN_LIMIT = 12
MISSING_SESSION_IDS = {"", "pending", "none", "null", "unknown"}


@dataclass(frozen=True)
class RunStatus:
    run_id: str
    state: str
    agent: str
    skill: str
    mode: str
    root: str
    operator_session: str
    latest_report: str
    latest_transcript: str
    last_error: str
    updated_at: str
    started_at: str
    health: str
    source: str
    lock_present: bool
    exit_code: int | None = None
    liveness: str = ""
    launcher_pid: int | None = None
    completed_at: str = ""
    session_id: str = ""
    current_loop: int | None = None
    total_loops: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    ts: str
    run_id: str
    kind: str
    message: str
    payload: dict[str, Any]
    cursor: int


def control_plane_home() -> Path:
    return vibecrafted_home() / "control_plane"


def run_snapshot_dir() -> Path:
    return control_plane_home() / "runs"


def event_stream_path() -> Path:
    return control_plane_home() / "events.jsonl"


def _sync_lock_path() -> Path:
    return control_plane_home() / ".sync.lock"


@contextlib.contextmanager
def _sync_lock() -> Iterator[None]:
    control_plane_home().mkdir(parents=True, exist_ok=True)
    lock_path = _sync_lock_path()
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    # Atomic write (tmp + os.replace) so a crash mid-write or a concurrent
    # reader never sees a half-written, unparseable snapshot — _read_json would
    # silently degrade a truncated file to {} and lose the run's metadata.
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _parse_kv_file(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in _read_lines(path):
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def _safe_iso(raw: str | None) -> str:
    return raw or ""


def _parse_iso(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if value and value.lstrip("-").isdigit():
            return int(value)
    return None


def normalize_run_root(
    root: str | Path | None, fallback: str | Path | None = None
) -> str:
    raw = str(root or fallback or "").strip()
    if not raw:
        return ""
    return str(Path(raw).expanduser().resolve())


def ensure_session_id(session_id: Any = "") -> str:
    raw = str(session_id or "").strip()
    if raw.lower() not in MISSING_SESSION_IDS:
        return raw
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _configured_stale_heartbeat_seconds() -> int:
    return _configured_nonnegative_int(
        LIVENESS_STALE_HEARTBEAT_ENV, LIVENESS_STALE_HEARTBEAT_SECONDS
    )


def _configured_run_gc_grace_seconds() -> int:
    return _configured_nonnegative_int(RUN_GC_GRACE_ENV, RUN_GC_GRACE_SECONDS)


def _configured_snapshot_retention_seconds() -> int:
    return _configured_nonnegative_int(
        RUN_SNAPSHOT_RETENTION_SECONDS_ENV, RUN_SNAPSHOT_RETENTION_SECONDS
    )


def _configured_snapshot_retention_count() -> int:
    return _configured_nonnegative_int(
        RUN_SNAPSHOT_RETENTION_COUNT_ENV, RUN_SNAPSHOT_RETENTION_COUNT
    )


def _configured_nonnegative_int(env_name: str, default: int) -> int:
    raw = os.environ.get(env_name)
    if not raw:
        return default
    try:
        return max(int(raw), 0)
    except ValueError:
        return default


def _state_health(state: str, updated_at: str) -> str:
    updated_dt = _parse_iso(updated_at)
    if state in FINAL_STATES:
        return "final"
    if state == "stalled":
        return "stalled"
    if updated_dt is None:
        return "unknown"
    if (_now() - updated_dt).total_seconds() > RUN_STALL_SECONDS:
        return "stalled"
    return "active"


def _operator_state(run: dict[str, Any]) -> str:
    state = str(run.get("state") or "")
    artifact_ok = run.get("artifact_ok")
    artifact_errors = list(run.get("artifact_errors") or [])
    exit_code = _coerce_int(run.get("exit_code"))

    if state == "stopped":
        return "stopped"
    if state in BLOCKED_STATES:
        return "blocked"
    if state in {"failed", "process_dead", "ghost"}:
        return "failed"
    if exit_code not in (None, 0):
        return "failed"
    if state in {"report_validated", "completed", "closed"}:
        if artifact_ok is False or artifact_errors:
            return "blocked"
        return "completed"
    if artifact_ok is False or artifact_errors:
        return "blocked"
    return "running"


def _artifact_projection(
    run: dict[str, Any], previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    report = str(run.get("latest_report") or "")
    transcript = str(run.get("latest_transcript") or "")
    state = str(run.get("state") or "")
    result = dict(run)
    errors = [str(item) for item in (run.get("artifact_errors") or []) if str(item)]
    artifact_ok = run.get("artifact_ok")
    terminal_state = state in {"report_validated", "completed", "closed"}
    has_live_identity = bool(str(run.get("session_id") or "").strip())
    defer_report_gate = state in ACTIVE_STATES and has_live_identity

    if report and not defer_report_gate:
        report_path = Path(report)
        try:
            if not report_path.exists():
                if "report_missing" not in errors:
                    errors.append("report_missing")
            elif report_path.stat().st_size == 0 and "report_invalid" not in errors:
                errors.append("report_invalid")
        except OSError:
            if "report_invalid" not in errors:
                errors.append("report_invalid")
    elif terminal_state:
        if "report_missing" not in errors:
            errors.append("report_missing")

    transcript_bytes: int | None = None
    transcript_growth: int | None = None
    if transcript:
        transcript_path = Path(transcript)
        try:
            if transcript_path.exists():
                transcript_bytes = transcript_path.stat().st_size
                previous_bytes = _coerce_int((previous or {}).get("transcript_bytes"))
                if previous_bytes is not None:
                    transcript_growth = max(transcript_bytes - previous_bytes, 0)
                else:
                    transcript_growth = transcript_bytes
        except OSError:
            transcript_bytes = None
            transcript_growth = None

    if artifact_ok is None:
        artifact_ok = len(errors) == 0
    else:
        artifact_ok = bool(artifact_ok) and len(errors) == 0

    if errors:
        gate = "failed"
    elif state in {"report_validated", "completed", "closed"}:
        gate = "validated"
    else:
        gate = "pending"

    result["artifact_ok"] = artifact_ok
    result["artifact_errors"] = errors
    result["artifact_gate"] = gate
    result["transcript_bytes"] = transcript_bytes
    result["transcript_growth"] = transcript_growth
    result["heartbeat_at"] = str(run.get("heartbeat_at") or run.get("updated_at") or "")
    if terminal_state and artifact_ok and not errors:
        if _coerce_int(result.get("exit_code")) is None:
            result["exit_code"] = 0
        if not str(result.get("completed_at") or ""):
            result["completed_at"] = str(result.get("updated_at") or _now().isoformat())
        result["liveness"] = "terminal"
        result.pop("recovery_required", None)
    result["operator_state"] = _operator_state(result)
    return result


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if exc.errno == errno.EPERM:
            return True
        if exc.errno == errno.ESRCH:
            return False
        return False
    return True


def _heartbeat_age_seconds(run: dict[str, Any], now: dt.datetime) -> float | None:
    heartbeat_at = _parse_iso(
        str(run.get("heartbeat_at") or run.get("updated_at") or "")
    )
    if heartbeat_at is None:
        return None
    if heartbeat_at.tzinfo is None:
        heartbeat_at = heartbeat_at.replace(tzinfo=dt.timezone.utc)
    return (now - heartbeat_at).total_seconds()


def _reconcile_dead_launcher(run: dict[str, Any]) -> dict[str, Any]:
    result = dict(run)
    state = str(result.get("state") or "")
    if state in FINAL_STATES:
        return result
    if _has_success_evidence(result):
        return _reconcile_successful_terminal(result)
    if _run_is_terminal(result):
        return result
    if state not in ACTIVE_STATES - {"paused"}:
        return result
    launcher_pid = _coerce_int(result.get("launcher_pid"))
    liveness = str(result.get("liveness") or "")
    # P0: a dead/absent launcher pid is NOT proof the run died. The launcher is an
    # ephemeral spawn-shell that exits right after forking the detached dispatcher;
    # for headless/detached dispatch it is gone within seconds while the dispatcher
    # and worker keep running and DELIVER. If the worker (or its process group) is
    # still alive, the run is live regardless of the launcher pid — reconciling it
    # to stalled/recovery here false-blocks live, delivering runs.
    if _worker_is_alive(result):
        return result
    if liveness == "pid_alive":
        if launcher_pid is None or _pid_is_alive(launcher_pid):
            return result
    else:
        if launcher_pid is not None and _pid_is_alive(launcher_pid):
            return result
        if launcher_pid is None and _has_signal_target(result):
            return result

    now = _now()
    age_seconds = _heartbeat_age_seconds(result, now)
    threshold = _configured_stale_heartbeat_seconds()
    if age_seconds is None or age_seconds < threshold:
        return result

    artifact_errors = {
        str(item) for item in (result.get("artifact_errors") or []) if str(item)
    }
    artifact_failure_state = ""
    if "report_missing" in artifact_errors:
        artifact_failure_state = "report_missing"
    elif artifact_errors.intersection({"report_invalid", "report_empty"}):
        artifact_failure_state = "report_invalid"

    gc_grace = _configured_run_gc_grace_seconds()
    should_gc = not artifact_failure_state and age_seconds >= gc_grace
    result["state"] = "gc" if should_gc else artifact_failure_state or "stalled"
    result["health"] = "final" if artifact_failure_state or should_gc else "stalled"
    result["liveness"] = "pid_gone"
    result["updated_at"] = now.isoformat()
    if should_gc:
        result["completed_at"] = now.isoformat()
    else:
        result["recovery_required"] = True
    pid_detail = (
        f"launcher_pid {launcher_pid} is not alive"
        if launcher_pid is not None
        else "launcher_pid is missing"
    )
    lock_detail = (
        "; lock file remains present for operator cleanup"
        if result.get("lock_present")
        else ""
    )
    artifact_detail = (
        f"; artifact contract failed ({artifact_failure_state})"
        if artifact_failure_state
        else ""
    )
    if should_gc:
        explanation = (
            f"garbage-collected: dead launcher, heartbeat stale >{gc_grace}s; "
            f"{pid_detail}; heartbeat stale for {int(age_seconds)}s "
            f"(threshold {threshold}s); no live launcher proof{lock_detail}"
        )
    else:
        explanation = (
            f"{pid_detail}; heartbeat stale for {int(age_seconds)}s "
            f"(threshold {threshold}s); no live launcher proof{lock_detail}"
            f"{artifact_detail}; recovery_required"
        )
    previous_error = str(result.get("last_error") or "").strip()
    result["last_error"] = (
        f"{previous_error}; {explanation}" if previous_error else explanation
    )
    return result


def _has_success_evidence(run: dict[str, Any]) -> bool:
    if run.get("artifact_ok") is False or run.get("artifact_errors"):
        return False
    exit_code = _coerce_int(run.get("exit_code"))
    if exit_code not in (None, 0):
        return False
    state = str(run.get("state") or "")
    if state in {"report_validated", "completed", "closed", "converged"}:
        return True
    if exit_code == 0:
        return True
    if str(run.get("completed_at") or "").strip():
        return True
    return str(run.get("liveness") or "") == "terminal"


def _reconcile_successful_terminal(run: dict[str, Any]) -> dict[str, Any]:
    result = dict(run)
    completed_at = str(result.get("completed_at") or result.get("updated_at") or "")
    if not completed_at:
        completed_at = _now().isoformat()
    result["state"] = "completed"
    result["health"] = "final"
    result["liveness"] = "terminal"
    result["completed_at"] = completed_at
    result["updated_at"] = completed_at
    result.pop("recovery_required", None)
    return result


def _failure_card(run: dict[str, Any]) -> dict[str, Any] | None:
    errors = [str(item) for item in (run.get("artifact_errors") or []) if str(item)]
    state = str(run.get("state") or "")
    if not errors and state not in BLOCKED_STATES:
        return None

    return {
        "code": "runtime_contract_failure",
        "summary": "Artifact contract or lifecycle precondition failed.",
        "state": state,
        "run_id": run.get("run_id"),
        "artifact_errors": errors,
        "report": run.get("latest_report") or "",
        "transcript": run.get("latest_transcript") or "",
        "last_error": run.get("last_error") or "",
        "recovery": [
            "Inspect events tail for the run.",
            "Validate report/transcript paths and rerun or retry.",
            "Use vc_run_stop before retry when liveness remains active.",
        ],
    }


def _has_signal_target(run: dict[str, Any]) -> bool:
    for key in ("worker_pgid", "worker_pid", "launcher_pid"):
        raw = run.get(key)
        if _coerce_int(raw):
            return True
    return False


def _worker_is_alive(run: dict[str, Any]) -> bool:
    """True when the run's worker process (or its group leader) is still alive.

    Distinct from ``_has_signal_target`` (which only checks that a pid VALUE is
    present): this checks actual OS liveness. The liveness reconciler uses it so
    a run is never marked recovery_required merely because the ephemeral launcher
    pid died while the worker keeps running and delivering.
    """
    for key in ("worker_pid", "worker_pgid"):
        pid = _coerce_int(run.get(key))
        if pid is not None and _pid_is_alive(pid):
            return True
    return False


def _has_retry_spec(run: dict[str, Any]) -> bool:
    skill = str(run.get("skill") or "")
    if skill == "marbles":
        return True
    return bool(
        str(run.get("prompt") or "").strip() or str(run.get("file") or "").strip()
    )


def _lifecycle_controls(run: dict[str, Any]) -> dict[str, bool]:
    terminal = _run_is_terminal(run)
    liveness = str(run.get("liveness") or "")
    signalable = (
        not terminal
        and liveness not in {"pid_gone", "terminal"}
        and _has_signal_target(run)
    )
    recovery_required = (
        bool(run.get("recovery_required"))
        or liveness == "pid_gone"
        or str(run.get("state") or "") in BLOCKED_STATES
    )
    return {
        "await": not terminal,
        "inspect": True,
        "stop": signalable,
        "cancel": signalable,
        "resume": terminal and _has_retry_spec(run),
        "recovery_required": recovery_required,
    }


def _session_base_name(root: str) -> str:
    base = Path(root or "vibecrafted").name.lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in base).strip("-")
    return cleaned or "vibecrafted"


def operator_session_name(root: str, run_id: str) -> str:
    base = _session_base_name(root)
    return f"{base}-{run_id}" if run_id else base


def _skill_from_code(skill_code: str) -> str:
    return SKILL_CODE_MAP.get(skill_code, skill_code or "unknown")


def _append_event(event: dict[str, Any]) -> None:
    stream_path = event_stream_path()
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    with stream_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _iter_meta_files() -> Iterator[Path]:
    artifacts_root = vibecrafted_home() / "artifacts"
    if not artifacts_root.is_dir():
        return iter(())
    return artifacts_root.rglob("*.meta.json")


def _iter_lock_files() -> Iterator[Path]:
    lock_root = vibecrafted_home() / "locks"
    if not lock_root.is_dir():
        return iter(())
    return lock_root.rglob("*.lock")


def _iter_marbles_state_files() -> Iterator[Path]:
    marbles_root = vibecrafted_home() / "marbles"
    if not marbles_root.is_dir():
        return iter(())
    return marbles_root.rglob("state.json")


def _normalize_agent_meta(path: Path) -> RunStatus | None:
    payload = _read_json(path)
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        return None
    root = str(payload.get("root") or "")
    skill = _skill_from_code(str(payload.get("skill_code") or ""))
    state = str(payload.get("status") or "unknown")
    updated_at = _safe_iso(str(payload.get("updated_at") or ""))
    exit_code = _coerce_int(payload.get("exit_code"))
    liveness = str(payload.get("liveness") or "")
    health = (
        "final"
        if exit_code is not None or liveness == "terminal"
        else _state_health(state, updated_at)
    )
    extra: dict[str, Any] = {}
    for key in (
        "runtime",
        "source_dir",
        "prompt",
        "file",
        "retry_of",
        "worker_command",
        "worker_pid",
        "worker_pgid",
        "heartbeat_at",
        "meta",
        "artifact_ok",
        "artifact_errors",
        "artifact_gate",
        "operator_state",
    ):
        if key in payload and payload.get(key) not in (None, ""):
            extra[key] = payload[key]
    return RunStatus(
        run_id=run_id,
        state=state,
        agent=str(payload.get("agent") or "unknown"),
        skill=skill,
        mode=str(payload.get("mode") or "unknown"),
        root=root,
        operator_session=operator_session_name(root, run_id),
        latest_report=str(payload.get("report") or ""),
        latest_transcript=str(payload.get("transcript") or ""),
        last_error=str(payload.get("message") or payload.get("reason") or ""),
        updated_at=updated_at,
        started_at=_safe_iso(
            str(payload.get("started_at") or payload.get("updated_at") or "")
        ),
        health=health,
        source="agent-meta",
        lock_present=False,
        exit_code=exit_code,
        liveness=liveness,
        launcher_pid=_coerce_int(payload.get("launcher_pid")),
        completed_at=_safe_iso(str(payload.get("completed_at") or "")),
        session_id=str(payload.get("session_id") or ""),
        extra=extra,
    )


def _normalize_lock(path: Path) -> RunStatus | None:
    payload = _parse_kv_file(path)
    run_id = payload.get("run_id", "").strip()
    if not run_id:
        return None
    root = payload.get("root", "")
    state = payload.get("status", "running") or "running"
    started_at = payload.get("started", "")
    return RunStatus(
        run_id=run_id,
        state=state,
        agent=payload.get("agent", "unknown"),
        skill=_skill_from_code(payload.get("skill", "")),
        mode=payload.get("mode", payload.get("runtime", "unknown")),
        root=root,
        operator_session=operator_session_name(root, run_id),
        latest_report="",
        latest_transcript="",
        last_error="",
        updated_at=_safe_iso(started_at),
        started_at=_safe_iso(started_at),
        health=_state_health(state, started_at),
        source="lock",
        lock_present=True,
        liveness="lock_present",
        extra={},
    )


def _normalize_marbles_state(path: Path) -> RunStatus | None:
    payload = _read_json(path)
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        return None
    loops = payload.get("loops") or []
    latest_loop = loops[-1] if loops else {}
    updated_at = _safe_iso(
        str(payload.get("updated_at") or payload.get("started_at") or "")
    )
    state = str(payload.get("status") or "unknown")
    return RunStatus(
        run_id=run_id,
        state=state,
        agent=str(payload.get("agent") or "unknown"),
        skill="marbles",
        mode=str(payload.get("mode") or "steered"),
        root=str(payload.get("root") or ""),
        operator_session=operator_session_name(str(payload.get("root") or ""), run_id),
        latest_report=str(latest_loop.get("report") or ""),
        latest_transcript=str(latest_loop.get("transcript") or ""),
        last_error=str(payload.get("failure_hint") or latest_loop.get("reason") or ""),
        updated_at=updated_at,
        started_at=_safe_iso(str(payload.get("started_at") or "")),
        health=_state_health(state, updated_at),
        source="marbles-state",
        lock_present=False,
        current_loop=int(payload["current_loop"])
        if isinstance(payload.get("current_loop"), int)
        else None,
        total_loops=int(payload["total_loops"])
        if isinstance(payload.get("total_loops"), int)
        else None,
        extra={
            "runtime": str(payload.get("runtime") or "headless"),
        },
    )


def _merge_event_stream(merged: dict[str, RunStatus]) -> dict[str, RunStatus]:
    stream = event_stream_path()
    if not stream.exists():
        return merged

    for line in _read_lines(stream):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        run_id = str(event.get("run_id") or "").strip()
        if not run_id:
            continue

        payload = dict(event.get("payload") or {})
        kind = str(event.get("kind") or "")
        message = str(event.get("message") or "")
        ts = _safe_iso(str(event.get("ts") or ""))
        existing = merged.get(run_id)

        state = str(payload.get("state") or "")
        if not state and kind.startswith("lifecycle:"):
            state = kind.split(":", 1)[1]
        if not state and kind == "launch":
            state = "created"
        if not state and kind == "audit:stop" and payload.get("accepted"):
            state = "stopped"
        if not state:
            state = existing.state if existing is not None else "unknown"

        identity_required = bool(payload.get("identity_required"))
        raw_root = payload.get("root") or (existing.root if existing else "")
        root = (
            normalize_run_root(str(raw_root or ""), Path.cwd())
            if identity_required
            else str(raw_root or "")
        )
        agent = str(payload.get("agent") or (existing.agent if existing else "unknown"))
        skill = str(payload.get("skill") or (existing.skill if existing else "unknown"))
        mode = str(payload.get("mode") or (existing.mode if existing else "unknown"))
        report = str(
            payload.get("report")
            or (existing.latest_report if existing is not None else "")
        )
        transcript = str(
            payload.get("transcript")
            or (existing.latest_transcript if existing is not None else "")
        )
        updated_at = ts or (existing.updated_at if existing else "")
        started_at = str(
            payload.get("started_at")
            or (existing.started_at if existing is not None else "")
            or updated_at
        )
        exit_code = _coerce_int(payload.get("exit_code"))
        if exit_code is None and existing is not None:
            exit_code = existing.exit_code
        liveness = str(
            payload.get("liveness") or (existing.liveness if existing else "")
        )
        launcher_pid = _coerce_int(payload.get("launcher_pid"))
        if launcher_pid is None and existing is not None:
            launcher_pid = existing.launcher_pid
        completed_at = str(
            payload.get("completed_at")
            or (existing.completed_at if existing is not None else "")
        )
        session_id = str(
            payload.get("session_id")
            or (existing.session_id if existing is not None else "")
        )
        if identity_required:
            session_id = ensure_session_id(session_id)

        extra = dict(existing.extra if existing is not None else {})
        for key in (
            "runtime",
            "source_dir",
            "prompt",
            "file",
            "retry_of",
            "worker_command",
            "worker_pid",
            "worker_pgid",
            "heartbeat_at",
            "meta",
            "artifact_ok",
            "artifact_errors",
            "recovery_required",
            "stop_reason",
            "stop_signal",
            "stop_target",
            "stop_target_pid",
            "stop_target_pgid",
            "stop_signal_sent",
            "stop_already_dead",
            "stop_alive_after_grace",
            "stop_grace_seconds",
        ):
            if key in payload and payload.get(key) not in (None, ""):
                extra[key] = payload[key]

        payload_last_error = str(
            payload.get("error") or payload.get("last_error") or ""
        )
        if kind == "state" and payload_last_error == message:
            payload_last_error = ""
        last_error = (
            payload_last_error
            or (existing.last_error if existing is not None else "")
            or (
                message
                if kind != "state"
                and (state in BLOCKED_STATES or state in {"failed", "ghost"})
                else ""
            )
        )

        incoming = RunStatus(
            run_id=run_id,
            state=state,
            agent=agent,
            skill=skill,
            mode=mode,
            root=root,
            operator_session=operator_session_name(root, run_id),
            latest_report=report,
            latest_transcript=transcript,
            last_error=last_error,
            updated_at=updated_at,
            started_at=started_at,
            health=_state_health(state, updated_at),
            source="event-stream",
            lock_present=existing.lock_present if existing is not None else False,
            exit_code=exit_code,
            liveness=liveness,
            launcher_pid=launcher_pid,
            completed_at=completed_at,
            session_id=session_id,
            current_loop=existing.current_loop if existing is not None else None,
            total_loops=existing.total_loops if existing is not None else None,
            extra=extra,
        )
        merged[run_id] = _merge_status(existing, incoming)

    return merged


def _merge_status(existing: RunStatus | None, incoming: RunStatus) -> RunStatus:
    if existing is None:
        return incoming
    existing_dt = _parse_iso(existing.updated_at)
    incoming_dt = _parse_iso(incoming.updated_at) or dt.datetime.min.replace(
        tzinfo=dt.timezone.utc
    )
    latest = (
        existing if existing_dt is not None and existing_dt >= incoming_dt else incoming
    )
    preferred = latest
    return RunStatus(
        run_id=preferred.run_id,
        state=preferred.state,
        agent=preferred.agent or existing.agent,
        skill=preferred.skill or existing.skill,
        mode=preferred.mode or existing.mode,
        root=preferred.root or existing.root,
        operator_session=preferred.operator_session or existing.operator_session,
        latest_report=preferred.latest_report or existing.latest_report,
        latest_transcript=preferred.latest_transcript or existing.latest_transcript,
        last_error=preferred.last_error or existing.last_error,
        updated_at=preferred.updated_at or existing.updated_at,
        started_at=preferred.started_at or existing.started_at,
        health=preferred.health,
        source=preferred.source,
        lock_present=existing.lock_present or incoming.lock_present,
        exit_code=preferred.exit_code
        if preferred.exit_code is not None
        else existing.exit_code,
        liveness=preferred.liveness or existing.liveness,
        launcher_pid=preferred.launcher_pid
        if preferred.launcher_pid is not None
        else existing.launcher_pid,
        completed_at=preferred.completed_at or existing.completed_at,
        session_id=preferred.session_id or existing.session_id,
        current_loop=preferred.current_loop
        if preferred.current_loop is not None
        else existing.current_loop,
        total_loops=preferred.total_loops
        if preferred.total_loops is not None
        else existing.total_loops,
        extra={**existing.extra, **incoming.extra},
    )


def _snapshot_path(run_id: str) -> Path:
    return run_snapshot_dir() / f"{run_id}.json"


def _snapshot_archive_dir() -> Path:
    return run_snapshot_dir() / "archive"


def _load_existing_snapshots() -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for path in run_snapshot_dir().glob("*.json"):
        payload = _read_json(path)
        run_id = str(payload.get("run_id") or "").strip()
        if run_id:
            snapshots[run_id] = payload
    return snapshots


def _status_to_payload(status: RunStatus) -> dict[str, Any]:
    payload = asdict(status)
    extra = payload.pop("extra", {})
    if isinstance(extra, dict):
        payload.update(extra)
    return payload


def _run_is_terminal(run: dict[str, Any]) -> bool:
    if str(run.get("state") or "") in FINAL_STATES:
        return True
    if str(run.get("liveness") or "") == "terminal":
        return True
    return _coerce_int(run.get("exit_code")) is not None


def _snapshot_age_seconds(payload: dict[str, Any], now: dt.datetime) -> float | None:
    timestamp = _parse_iso(
        str(
            payload.get("completed_at")
            or payload.get("updated_at")
            or payload.get("started_at")
            or ""
        )
    )
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
    return (now - timestamp).total_seconds()


def _archive_snapshot(path: Path) -> None:
    archive_dir = _snapshot_archive_dir()
    archive_dir.mkdir(parents=True, exist_ok=True)
    path.replace(archive_dir / path.name)


def _archive_expired_snapshots() -> None:
    now = _now()
    retention_seconds = _configured_snapshot_retention_seconds()
    retention_count = _configured_snapshot_retention_count()
    terminal_snapshots: list[tuple[dt.datetime, Path, dict[str, Any]]] = []
    expired_by_age: set[Path] = set()

    for path in run_snapshot_dir().glob("*.json"):
        payload = _read_json(path)
        if not payload or not _run_is_terminal(payload):
            continue
        age_seconds = _snapshot_age_seconds(payload, now)
        if age_seconds is not None and age_seconds >= retention_seconds:
            expired_by_age.add(path)
        updated_at = _parse_iso(
            str(payload.get("updated_at") or "")
        ) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=dt.timezone.utc)
        terminal_snapshots.append((updated_at, path, payload))

    terminal_snapshots.sort(key=lambda item: item[0], reverse=True)
    expired_by_count = {path for _, path, _ in terminal_snapshots[retention_count:]}
    for path in sorted(expired_by_age | expired_by_count):
        if path.exists():
            _archive_snapshot(path)


def _select_run(snapshot: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    target = str(run_id or "").strip()
    if not target:
        return None
    for key in ("active_runs", "recent_runs"):
        for run in snapshot.get(key) or []:
            if str(run.get("run_id") or "") == target:
                return dict(run)
    payload = _read_json(_snapshot_path(target))
    if str(payload.get("run_id") or "") == target:
        return payload
    return None


# Fields that drift between consecutive sync_state() passes without
# representing a meaningful lifecycle change (timestamps re-derived from the
# event stream, provenance of the winning source, transcript delta counters).
# They must be excluded from the idempotency comparison so re-syncing an
# unchanged run does not emit a spurious "refreshed" event.
_VOLATILE_TRANSITION_KEYS = frozenset(
    {
        "updated_at",
        "heartbeat_at",
        "generated_at",
        "source",
        "transcript_growth",
    }
)


def _stable_transition_view(run: dict[str, Any] | None) -> dict[str, Any]:
    if not run:
        return {}
    return {
        key: value for key, value in run.items() if key not in _VOLATILE_TRANSITION_KEYS
    }


def _record_transition(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> None:
    previous_state = str(previous.get("state") or "") if previous else ""
    current_state = str(current.get("state") or "")
    if previous_state == current_state and _stable_transition_view(
        previous
    ) == _stable_transition_view(current):
        return
    message = (
        f"{current['run_id']} entered {current_state}"
        if previous_state != current_state
        else f"{current['run_id']} refreshed"
    )
    _append_event(
        {
            "ts": _now().isoformat(),
            "run_id": current["run_id"],
            "kind": "state",
            "message": message,
            "payload": {
                "previous_state": previous_state,
                "state": current_state,
                "agent": current.get("agent"),
                "skill": current.get("skill"),
                "mode": current.get("mode"),
                "health": current.get("health"),
                "root": current.get("root"),
                "session_id": current.get("session_id"),
                "liveness": current.get("liveness"),
                "launcher_pid": current.get("launcher_pid"),
                "heartbeat_at": current.get("heartbeat_at"),
                "recovery_required": current.get("recovery_required"),
                "last_error": current.get("last_error"),
            },
        }
    )


def record_stop_transition(
    run_id: str,
    *,
    run: dict[str, Any] | None = None,
    accepted: bool,
    reason: str,
    signal_name: str = "SIGTERM",
    target: str = "",
    target_pid: int | None = None,
    target_pgid: int | None = None,
    signal_sent: bool = False,
    already_dead: bool = False,
    alive_after_grace: bool | None = None,
    grace_seconds: float = 0.0,
    exit_code: int | None = None,
    error: str = "",
) -> dict[str, Any]:
    """Append the canonical control-plane event for an operator stop request."""
    now = _now().isoformat()
    payload: dict[str, Any] = {
        "accepted": accepted,
        "reason": reason,
        "stop_reason": reason,
        "signal": signal_name,
        "stop_signal": signal_name,
        "target": target,
        "stop_target": target,
        "target_pid": target_pid,
        "stop_target_pid": target_pid,
        "target_pgid": target_pgid,
        "stop_target_pgid": target_pgid,
        "signal_sent": signal_sent,
        "stop_signal_sent": signal_sent,
        "already_dead": already_dead,
        "stop_already_dead": already_dead,
        "alive_after_grace": alive_after_grace,
        "stop_alive_after_grace": alive_after_grace,
        "grace_seconds": grace_seconds,
        "stop_grace_seconds": grace_seconds,
        "error": error,
    }
    if run:
        for key in (
            "agent",
            "skill",
            "mode",
            "root",
            "session_id",
            "launcher_pid",
            "worker_pid",
            "worker_pgid",
            "runtime",
            "source_dir",
            "prompt",
            "file",
            "meta",
            "report",
            "transcript",
        ):
            if key in run and run.get(key) not in (None, ""):
                payload[key] = run[key]
        if "report" not in payload and run.get("latest_report"):
            payload["report"] = run["latest_report"]
        if "transcript" not in payload and run.get("latest_transcript"):
            payload["transcript"] = run["latest_transcript"]
    if accepted:
        payload["state"] = "stopped"
        payload["health"] = "final"
        payload["liveness"] = (
            "pid_alive_after_stop" if alive_after_grace else "terminal"
        )
        payload["completed_at"] = now
        if exit_code is not None:
            payload["exit_code"] = exit_code

    event = {
        "ts": now,
        "run_id": str(run_id or ""),
        "kind": "audit:stop",
        "message": (
            "run stopped" if accepted else f"stop rejected: {reason.replace('_', ' ')}"
        ),
        "payload": payload,
    }
    with _sync_lock():
        _append_event(event)
    return event


def _warnings_for_runs(runs: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for run in runs:
        if run.get("health") == "stalled":
            warnings.append(f"{run['run_id']} looks stalled ({run.get('state')}).")
        if (
            run.get("lock_present")
            and not run.get("latest_report")
            and run.get("state") not in FINAL_STATES
        ):
            warnings.append(
                f"{run['run_id']} still has a live lock but no report artifact yet."
            )
        failure_card = run.get("failure_card")
        if isinstance(failure_card, dict) and failure_card.get("code"):
            warnings.append(
                f"{run['run_id']} contract failure: {failure_card.get('code')}"
            )
    return warnings[:6]


def read_event_tail(limit: int = EVENT_TAIL_LIMIT) -> list[dict[str, Any]]:
    stream = event_stream_path()
    if not stream.exists():
        return []
    events = []
    for line in stream.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(events))


def subscribe_events(
    since_cursor: int | None = None,
    kinds: set[str] | list[str] | tuple[str, ...] | None = None,
    callback=None,
) -> Iterator[Event]:
    """Yield control-plane events from events.jsonl, polling when needed."""
    stream = event_stream_path()
    cursor = max(int(since_cursor or 0), 0)
    kinds_filter = set(kinds or [])

    while True:
        emitted = False
        if stream.exists():
            with stream.open("r", encoding="utf-8") as handle:
                handle.seek(cursor)
                while True:
                    line = handle.readline()
                    if not line:
                        break
                    cursor = handle.tell()
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    kind = str(payload.get("kind") or "")
                    if kinds_filter and kind not in kinds_filter:
                        continue
                    event = Event(
                        ts=str(payload.get("ts") or ""),
                        run_id=str(payload.get("run_id") or ""),
                        kind=kind,
                        message=str(payload.get("message") or ""),
                        payload=dict(payload.get("payload") or {}),
                        cursor=cursor,
                    )
                    if callback is not None:
                        callback(event)
                    emitted = True
                    yield event
        if callback is None and not emitted:
            return
        time.sleep(1.0)


def sync_state() -> dict[str, Any]:
    with _sync_lock():
        previous_snapshots = _load_existing_snapshots()
        merged: dict[str, RunStatus] = {}

        for path in _iter_meta_files():
            status = _normalize_agent_meta(path)
            if status is None:
                continue
            merged[status.run_id] = _merge_status(merged.get(status.run_id), status)

        for path in _iter_lock_files():
            status = _normalize_lock(path)
            if status is None:
                continue
            merged[status.run_id] = _merge_status(merged.get(status.run_id), status)

        for path in _iter_marbles_state_files():
            status = _normalize_marbles_state(path)
            if status is None:
                continue
            merged[status.run_id] = _merge_status(merged.get(status.run_id), status)

        merged = _merge_event_stream(merged)

        payload_runs = []
        run_snapshot_dir().mkdir(parents=True, exist_ok=True)
        for run_id, status in merged.items():
            previous = previous_snapshots.get(run_id)
            payload = _artifact_projection(_status_to_payload(status), previous)
            payload = _reconcile_dead_launcher(payload)
            payload["failure_card"] = _failure_card(payload)
            payload["health"] = _state_health(
                str(payload.get("state") or ""), str(payload.get("updated_at") or "")
            )
            if not payload.get("liveness"):
                payload["liveness"] = (
                    "terminal" if _run_is_terminal(payload) else "heartbeat"
                )
            payload["lifecycle"] = _lifecycle_controls(payload)
            _record_transition(previous, payload)
            _write_json(_snapshot_path(run_id), payload)
            payload_runs.append(payload)
        _archive_expired_snapshots()

    payload_runs.sort(
        key=lambda item: (
            _parse_iso(item.get("updated_at"))
            or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        ),
        reverse=True,
    )
    active_runs = [
        run
        for run in payload_runs
        if run.get("health") in {"active", "stalled"}
        and run.get("state") not in FINAL_STATES
    ]
    recent_runs = payload_runs[:RECENT_RUN_LIMIT]
    return {
        "generated_at": _now().isoformat(),
        "active_runs": active_runs,
        "recent_runs": recent_runs,
        "warnings": _warnings_for_runs(payload_runs),
        "events": read_event_tail(),
    }


def lookup_run(run_id: str) -> dict[str, Any] | None:
    """Return the current control-plane projection for one run id."""
    snapshot = sync_state()
    return _select_run(snapshot, run_id)


class RunNotResolved(Exception):
    """Raised when a run id maps to no on-disk artifacts yet.

    The actionable case is "still launching" — the dispatcher has accepted the
    run but the worker has not produced its run directory yet. Point the caller
    at ``await`` instead of failing silently.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(
            f"run {run_id!r} not found in runtime_runs/ or artifacts/ — it may "
            f"still be launching. Wait with: vibecrafted await --run-id {run_id}"
        )


@dataclass(frozen=True)
class ResolvedRun:
    """On-disk location of a run, resolved read-follows-write.

    ``runtime_runs/`` is where the core runtime *writes*; ``artifacts/`` is the
    legacy location older readers expect. One resolver so observe / await / CLI /
    app / MCP read from the same place the runtime wrote (Niezmiennik 3).
    """

    run_id: str
    source: str  # "runtime_runs" | "artifacts"
    run_dir: Path
    meta: Path | None
    transcript: Path | None
    report: Path | None


def _runtime_run_dir(run_id: str) -> Path:
    return control_plane_home() / "runtime_runs" / run_id


def _report_from_meta(meta: Path) -> Path | None:
    try:
        payload = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    raw = str(payload.get("report") or payload.get("latest_report") or "")
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    return candidate if candidate.is_file() else None


def _resolve_run_in_artifacts(run_id: str) -> ResolvedRun | None:
    artifacts_root = vibecrafted_home() / "artifacts"
    if not artifacts_root.is_dir():
        return None
    for meta in sorted(artifacts_root.rglob(f"*{run_id}*.meta.json")):
        transcript = meta.with_suffix("").with_suffix(".transcript.log")
        return ResolvedRun(
            run_id=run_id,
            source="artifacts",
            run_dir=meta.parent,
            meta=meta,
            transcript=transcript if transcript.is_file() else None,
            report=_report_from_meta(meta),
        )
    return None


def resolve_run(run_id: str) -> ResolvedRun:
    """Resolve a run id to its on-disk artifacts, read-follows-write.

    Probes ``runtime_runs/<id>/`` (where the core runtime writes) first, then the
    legacy ``artifacts/`` location, then raises :class:`RunNotResolved` loudly so
    a still-launching run is sent to ``await`` instead of a silent "no metadata".
    This is the single resolver that closes the observe/await split-brain.
    """
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run_dir = _runtime_run_dir(target)
    if run_dir.is_dir():
        meta = run_dir / "meta.json"
        transcript = run_dir / "transcript.log"
        return ResolvedRun(
            run_id=target,
            source="runtime_runs",
            run_dir=run_dir,
            meta=meta if meta.is_file() else None,
            transcript=transcript if transcript.is_file() else None,
            report=_report_from_meta(meta) if meta.is_file() else None,
        )

    legacy = _resolve_run_in_artifacts(target)
    if legacy is not None:
        return legacy

    raise RunNotResolved(target)


def _await_progress_fingerprint(run: dict[str, Any] | None) -> tuple[Any, ...]:
    """Cheap movement signal for liveness-aware waits.

    Any change between two polls is proof the worker is doing real work:
    transcript bytes grew (session-file growth), the lifecycle state advanced,
    a fresh heartbeat landed, or new tokens/commits were recorded. Used by
    :func:`await_run` to RESET its idle deadline instead of abandoning a run on
    a blind wall clock while the agent is demonstrably alive.
    """
    if not run:
        return ()
    return (
        str(run.get("state") or ""),
        str(run.get("liveness") or ""),
        _coerce_int(run.get("transcript_bytes")),
        str(run.get("heartbeat_at") or run.get("updated_at") or ""),
        _coerce_int(run.get("tokens_output")),
        str(run.get("commit") or run.get("commit_sha") or run.get("head_sha") or ""),
    )


def _await_child_runs(snapshot: dict[str, Any], target: str) -> list[dict[str, Any]]:
    """Child runs of a loop parent (marbles/polarize ``<parent>-<kind>-L<n>``).

    Loop parents write almost nothing themselves — the children carry the real
    transcripts and pids, yet they are separate run records linked only by the
    id prefix. An await that fingerprints the parent alone sees a frozen record
    (and possibly a gone pid between rounds) while a child is demonstrably
    working, then fires a false ``idle_stall`` mid-loop.
    """
    prefix = f"{target}-"
    children: list[dict[str, Any]] = []
    for key in ("active_runs", "recent_runs"):
        for run in snapshot.get(key) or []:
            if not isinstance(run, dict):
                continue
            if str(run.get("run_id") or "").startswith(prefix):
                children.append(run)
    return children


def _report_file_written(path: str) -> bool:
    try:
        return Path(str(path)).stat().st_size > 0
    except OSError:
        return False


def _resolve_await_hard_cap(hard_cap_seconds: float | None) -> float | None:
    """Optional absolute ceiling for :func:`await_run`.

    Liveness governs by default (``None`` → no wall-clock kill of a live run).
    A hard cap, when set, is the only thing that stops a worker that stays alive
    but never finishes; the operator keeps it far above realistic single-marble
    work. Explicit argument wins; otherwise ``VIBECRAFTED_AWAIT_HARD_CAP_S``.
    """
    if hard_cap_seconds is not None:
        cap = float(hard_cap_seconds)
        return cap if cap > 0 else None
    raw = str(os.environ.get("VIBECRAFTED_AWAIT_HARD_CAP_S") or "").strip()
    if not raw:
        return None
    try:
        cap = float(raw)
    except ValueError:
        return None
    return cap if cap > 0 else None


def await_run(
    run_id: str,
    *,
    timeout_seconds: float = 300,
    interval_seconds: float = 5,
    hard_cap_seconds: float | None = None,
    report_path: str | None = None,
    on_poll: Callable[[dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    """Liveness-aware bounded wait for a run using control-plane state only.

    ``timeout_seconds`` is an IDLE deadline, not a blind wall clock: it RESETS
    whenever the run shows movement (transcript growth, state/heartbeat/token
    advance) or the worker process is demonstrably alive (``_worker_is_alive``).
    A run is only abandoned (``timed_out``) on a genuine stall — the idle window
    elapsing with zero movement AND no live worker — or, when configured, the
    optional ``hard_cap_seconds`` absolute ceiling. This stops the orchestrator
    from killing a marbles loop that is still doing real work (~13 min single
    marble) just because a fixed wall-clock budget expired.

    Two more truths keep this the ONE await nobody has to second-guess:

    - A non-empty report file (``report_path`` argument, else the run's own
      ``latest_report``) from a worker that is GONE is the handoff itself —
      return ``completed`` with ``reason: report_delivered`` immediately
      instead of idling out a full window on the corpse. While the worker is
      alive the report alone never completes the wait: it may be mid-write,
      or a stale leftover from a previous attempt on the same announced path.
    - Movement and liveness aggregate the run's CHILD runs (marbles/polarize
      loop rounds live in separate ``<parent>-…-L<n>`` records), so a working
      child keeps the parent's await open even while the parent record is
      frozen between rounds.

    ``on_poll`` (when given) is called once per poll with the latest run
    projection — for callers that print progress while blocking.
    """
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    idle_window = max(float(timeout_seconds), 0.0)
    interval_seconds = max(float(interval_seconds), 0.1)
    hard_cap = _resolve_await_hard_cap(hard_cap_seconds)

    start = time.monotonic()
    idle_deadline = start + idle_window
    hard_deadline = start + hard_cap if hard_cap is not None else None
    previous_fingerprint: tuple[Any, ...] | None = None
    attempts = 0
    last_run: dict[str, Any] | None = None

    while True:
        attempts += 1
        snapshot = sync_state()
        last_run = _select_run(snapshot, target)
        if on_poll is not None:
            on_poll(last_run)
        if last_run is not None and _run_is_terminal(last_run):
            return {
                "run_id": target,
                "found": True,
                "completed": True,
                "timed_out": False,
                "reason": "terminal",
                "worker_alive": _worker_is_alive(last_run),
                "attempts": attempts,
                "run": last_run,
            }

        delivered_report = str(
            report_path or (last_run.get("latest_report") if last_run else "") or ""
        ).strip()
        # Worker death is the handoff seal: a LIVE worker may still be
        # mid-write, and the announced path can hold a stale report from a
        # previous attempt (stage retries reuse artifact paths) — returning
        # `completed` on it reported exit 0 for a still-working run.
        if (
            delivered_report
            and _report_file_written(delivered_report)
            and not (last_run is not None and _worker_is_alive(last_run))
        ):
            return {
                "run_id": target,
                "found": last_run is not None,
                "completed": True,
                "timed_out": False,
                "reason": "report_delivered",
                "worker_alive": False,
                "attempts": attempts,
                "run": last_run,
            }

        now = time.monotonic()
        children = _await_child_runs(snapshot, target)
        worker_alive = bool(
            (last_run is not None and _worker_is_alive(last_run))
            or any(_worker_is_alive(child) for child in children)
        )
        fingerprint = (
            _await_progress_fingerprint(last_run),
            tuple(
                sorted(
                    (str(child.get("run_id") or ""),)
                    + _await_progress_fingerprint(child)
                    for child in children
                )
            ),
        )
        moved = fingerprint != previous_fingerprint
        previous_fingerprint = fingerprint
        # Real activity or a live worker keeps the idle window open: never
        # abandon a run that is demonstrably making progress or alive.
        if moved or worker_alive:
            idle_deadline = now + idle_window

        if hard_deadline is not None and now >= hard_deadline:
            return {
                "run_id": target,
                "found": last_run is not None,
                "completed": False,
                "timed_out": True,
                "reason": "hard_cap",
                "worker_alive": worker_alive,
                "attempts": attempts,
                "run": last_run,
            }
        if now >= idle_deadline and not worker_alive:
            return {
                "run_id": target,
                "found": last_run is not None,
                "completed": False,
                "timed_out": True,
                "reason": "idle_stall",
                "worker_alive": worker_alive,
                "attempts": attempts,
                "run": last_run,
            }

        sleep_for = interval_seconds
        if hard_deadline is not None:
            sleep_for = min(sleep_for, max(hard_deadline - now, 0.0))
        if not worker_alive:
            sleep_for = min(sleep_for, max(idle_deadline - now, 0.0))
        time.sleep(max(sleep_for, 0.0))


def run_liveness(run_id: str) -> dict[str, Any]:
    """Bounded, reconciled liveness projection for a single run.

    Closes the report-on-death gap (docs/runtime/AGENT_OPS.md, Class 2): in
    no-await mode a worker that dies at startup emits no report and no
    terminal state, so passive readers wait on a corpse. This runs the same
    sync/reconcile pass the dispatch verbs use and answers the one question a
    supervisor needs before trusting silence: is the worker demonstrably
    alive, and what state did reconciliation settle on.
    """
    target = str(run_id or "").strip()
    if not target:
        return {"run_id": "", "found": False}
    try:
        snapshot = sync_state()
    except OSError:
        return {"run_id": target, "found": False}
    run = _select_run(snapshot, target)
    if run is None:
        return {"run_id": target, "found": False}
    return {
        "run_id": target,
        "found": True,
        "state": str(run.get("state") or ""),
        "liveness": str(run.get("liveness") or ""),
        "worker_alive": _worker_is_alive(run),
        "recovery_required": bool(run.get("recovery_required")),
    }


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync and inspect Vibecrafted control-plane state."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="sync",
        choices=("sync", "status"),
        help="sync writes snapshots and prints the aggregate payload; status is an alias.",
    )
    parser.parse_args(argv)
    payload = sync_state()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(cli())
