from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

try:
    from runtime_paths import vibecrafted_home
except ModuleNotFoundError:  # pragma: no cover - import path depends on entrypoint
    from scripts.runtime_paths import vibecrafted_home


ACTIVE_STATES = {
    "initialized",
    "launching",
    "promise",
    "confirmed",
    "running",
    "paused",
    "stalled",
}
FINAL_STATES = {"completed", "converged", "stopped", "failed", "timed_out", "gc"}
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
EVENT_TAIL_LIMIT = 16
RECENT_RUN_LIMIT = 12


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
    current_loop: int | None = None
    total_loops: int | None = None


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
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


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


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _state_health(state: str, updated_at: str) -> str:
    updated_dt = _parse_iso(updated_at)
    if state in FINAL_STATES:
        return "final"
    if updated_dt is None:
        return "unknown"
    if (_now() - updated_dt).total_seconds() > RUN_STALL_SECONDS:
        return "stalled"
    return "active"


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
        health=_state_health(state, updated_at),
        source="agent-meta",
        lock_present=False,
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
    )


def _merge_status(existing: RunStatus | None, incoming: RunStatus) -> RunStatus:
    if existing is None:
        return incoming
    latest = (
        existing
        if _parse_iso(existing.updated_at)
        and _parse_iso(existing.updated_at)
        >= (
            _parse_iso(incoming.updated_at)
            or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        )
        else incoming
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
        current_loop=preferred.current_loop
        if preferred.current_loop is not None
        else existing.current_loop,
        total_loops=preferred.total_loops
        if preferred.total_loops is not None
        else existing.total_loops,
    )


def _snapshot_path(run_id: str) -> Path:
    return run_snapshot_dir() / f"{run_id}.json"


def _load_existing_snapshots() -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for path in run_snapshot_dir().glob("*.json"):
        payload = _read_json(path)
        run_id = str(payload.get("run_id") or "").strip()
        if run_id:
            snapshots[run_id] = payload
    return snapshots


def _status_to_payload(status: RunStatus) -> dict[str, Any]:
    return asdict(status)


def _record_transition(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> None:
    previous_state = str(previous.get("state") or "") if previous else ""
    current_state = str(current.get("state") or "")
    if previous_state == current_state and previous == current:
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
            },
        }
    )


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

        payload_runs = []
        run_snapshot_dir().mkdir(parents=True, exist_ok=True)
        for run_id, status in merged.items():
            payload = _status_to_payload(status)
            previous = previous_snapshots.get(run_id)
            _record_transition(previous, payload)
            _write_json(_snapshot_path(run_id), payload)
            payload_runs.append(payload)

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
