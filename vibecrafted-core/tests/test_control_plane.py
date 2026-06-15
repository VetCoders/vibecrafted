from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from pathlib import Path

import pytest

from vibecrafted_core import control_plane


def _write_meta(home: Path, payload: dict[str, object]) -> Path:
    reports = home / "artifacts" / "VetCoders" / "vibecrafted" / "2026_0519" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"{payload['run_id']}.meta.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_lock(home: Path, payload: dict[str, object]) -> Path:
    locks = home / "locks" / ".vibecrafted"
    locks.mkdir(parents=True, exist_ok=True)
    path = locks / f"{payload['run_id']}.lock"
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in payload.items()) + "\n",
        encoding="utf-8",
    )
    return path


def test_sync_state_preserves_runtime_observe_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    completed_at = "2026-05-19T00:01:00+00:00"
    _write_meta(
        home,
        {
            "run_id": "impl-010101-42",
            "status": "completed",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "report": "/tmp/report.md",
            "transcript": "/tmp/transcript.log",
            "updated_at": completed_at,
            "started_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "impl",
            "exit_code": 0,
            "liveness": "terminal",
            "launcher_pid": 12345,
            "completed_at": completed_at,
            "session_id": "session-abc",
        },
    )

    snapshot = control_plane.sync_state()

    run = snapshot["recent_runs"][0]
    assert run["run_id"] == "impl-010101-42"
    assert run["exit_code"] == 0
    assert run["liveness"] == "terminal"
    assert run["launcher_pid"] == 12345
    assert run["completed_at"] == completed_at
    assert run["session_id"] == "session-abc"


def test_sync_state_enforces_identity_on_fresh_creation_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.chdir(tmp_path)
    events = home / "control_plane" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": "2026-05-19T00:00:00+00:00",
                        "run_id": "wflw-known-identity",
                        "kind": "launch",
                        "message": "launch accepted",
                        "payload": {
                            "state": "created",
                            "agent": "codex",
                            "skill": "workflow",
                            "mode": "workflow",
                            "root": str(repo),
                            "session_id": "session-real",
                            "identity_required": True,
                        },
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-05-19T00:00:01+00:00",
                        "run_id": "wflw-fallback-identity",
                        "kind": "launch",
                        "message": "launch accepted",
                        "payload": {
                            "state": "created",
                            "agent": "claude",
                            "skill": "workflow",
                            "mode": "workflow",
                            "root": "repo",
                            "session_id": "pending",
                            "identity_required": True,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = control_plane.sync_state()
    runs = {run["run_id"]: run for run in snapshot["recent_runs"]}

    known = runs["wflw-known-identity"]
    assert known["session_id"] == "session-real"
    assert known["root"] == str(repo.resolve())

    fallback = runs["wflw-fallback-identity"]
    assert fallback["root"] == str(repo.resolve())
    assert fallback["session_id"] != "pending"
    uuid.UUID(fallback["session_id"])


def test_sync_state_publishes_lifecycle_control_availability(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_RUN_GC_GRACE_SECONDS", "999999999")
    _write_meta(
        home,
        {
            "run_id": "wflw-010102-42",
            "status": "running",
            "agent": "codex",
            "mode": "workflow",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "wflw",
            "worker_pgid": 23456,
            "prompt": "continue",
        },
    )
    _write_meta(
        home,
        {
            "run_id": "impl-010103-42",
            "status": "completed",
            "agent": "claude",
            "mode": "implement",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:01:00+00:00",
            "skill_code": "impl",
            "exit_code": 0,
            "liveness": "terminal",
            "prompt": "continue",
        },
    )
    _write_meta(
        home,
        {
            "run_id": "rvew-010104-42",
            "status": "running",
            "agent": "gemini",
            "mode": "review",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:02:00+00:00",
            "skill_code": "rvew",
        },
    )

    snapshot = control_plane.sync_state()
    runs = {run["run_id"]: run for run in snapshot["recent_runs"]}

    assert runs["wflw-010102-42"]["lifecycle"] == {
        "await": True,
        "inspect": True,
        "stop": True,
        "cancel": True,
        "resume": False,
        "recovery_required": False,
    }
    assert runs["impl-010103-42"]["lifecycle"] == {
        "await": False,
        "inspect": True,
        "stop": False,
        "cancel": False,
        "resume": True,
        "recovery_required": False,
    }
    assert runs["rvew-010104-42"]["lifecycle"] == {
        "await": True,
        "inspect": True,
        "stop": False,
        "cancel": False,
        "resume": False,
        "recovery_required": True,
    }


def test_lookup_run_uses_synced_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    _write_meta(
        home,
        {
            "run_id": "rvew-020202-42",
            "status": "running",
            "agent": "claude",
            "mode": "review",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "rvew",
            "launcher_pid": os.getpid(),
            "liveness": "pid_alive",
        },
    )

    run = control_plane.lookup_run("rvew-020202-42")

    assert run is not None
    assert run["agent"] == "claude"
    assert run["launcher_pid"] == os.getpid()
    assert run["liveness"] == "pid_alive"


def test_sync_state_reconciles_dead_launcher_to_stalled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "1")
    monkeypatch.setenv("VIBECRAFTED_RUN_GC_GRACE_SECONDS", "999999999")
    _write_meta(
        home,
        {
            "run_id": "just-dead-pid",
            "status": "running",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:02:00+00:00",
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "just",
            "launcher_pid": 999999999,
            "liveness": "pid_alive",
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert run["state"] == "stalled"
    assert run["health"] == "stalled"
    assert run["liveness"] == "pid_gone"
    assert run["recovery_required"] is True
    assert run["lifecycle"]["recovery_required"] is True
    assert run["lifecycle"]["stop"] is False
    assert "recovery_required" in run["last_error"]

    persisted = json.loads(
        (home / "control_plane" / "runs" / "just-dead-pid.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["state"] == "stalled"
    assert persisted["liveness"] == "pid_gone"

    refreshed = control_plane.lookup_run("just-dead-pid")
    assert refreshed is not None
    assert refreshed["state"] == "stalled"
    assert refreshed["liveness"] == "pid_gone"
    assert refreshed["recovery_required"] is True
    assert refreshed["lifecycle"]["recovery_required"] is True
    assert "recovery_required" in refreshed["last_error"]


def test_sync_state_gc_terminalizes_old_stalled_dead_launcher(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "60")
    monkeypatch.setenv("VIBECRAFTED_RUN_GC_GRACE_SECONDS", "3600")
    now = dt.datetime(2026, 5, 19, 6, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(control_plane, "_now", lambda: now)
    _write_meta(
        home,
        {
            "run_id": "just-old-stalled",
            "status": "stalled",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:00:00+00:00",
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "just",
            "launcher_pid": 999999999,
            "liveness": "pid_alive",
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert run["state"] == "gc"
    assert run["health"] == "final"
    assert run["liveness"] == "pid_gone"
    assert run["completed_at"] == now.isoformat()
    assert (
        "garbage-collected: dead launcher, heartbeat stale >3600s" in run["last_error"]
    )
    assert all(item["run_id"] != "just-old-stalled" for item in snapshot["active_runs"])

    persisted = json.loads(
        (home / "control_plane" / "runs" / "just-old-stalled.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["state"] == "gc"


def test_sync_state_keeps_stalled_dead_launcher_active_before_gc_grace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "60")
    monkeypatch.setenv("VIBECRAFTED_RUN_GC_GRACE_SECONDS", "3600")
    now = dt.datetime(2026, 5, 19, 0, 30, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(control_plane, "_now", lambda: now)
    _write_meta(
        home,
        {
            "run_id": "just-fresh-stalled",
            "status": "stalled",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:00:00+00:00",
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "just",
            "launcher_pid": 999999999,
            "liveness": "pid_alive",
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert run["state"] == "stalled"
    assert run["health"] == "stalled"
    assert run["liveness"] == "pid_gone"
    assert run["run_id"] in {item["run_id"] for item in snapshot["active_runs"]}
    assert "garbage-collected" not in run["last_error"]


def test_sync_state_reconciles_dead_launcher_success_evidence_to_completed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "1")
    completed_at = "2026-05-19T00:02:00+00:00"
    _write_meta(
        home,
        {
            "run_id": "just-success-pid-gone",
            "status": "running",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:02:00+00:00",
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "just",
            "exit_code": 0,
            "launcher_pid": 999999999,
            "liveness": "pid_alive",
            "completed_at": completed_at,
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert run["state"] == "completed"
    assert run["health"] == "final"
    assert run["liveness"] == "terminal"
    assert run["completed_at"] == completed_at
    assert all(
        item["run_id"] != "just-success-pid-gone" for item in snapshot["active_runs"]
    )


def test_sync_state_reconciles_dead_launcher_with_missing_report_to_terminal_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "1")
    _write_meta(
        home,
        {
            "run_id": "just-missing-report",
            "status": "running",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "report": str(tmp_path / "missing-report.md"),
            "transcript": str(tmp_path / "transcript.log"),
            "updated_at": "2026-05-19T00:02:00+00:00",
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "just",
            "launcher_pid": 999999999,
            "liveness": "pid_alive",
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert run["state"] == "report_missing"
    assert run["health"] == "final"
    assert run["operator_state"] == "blocked"
    assert run["artifact_gate"] == "failed"
    assert run["liveness"] == "pid_gone"
    assert run["recovery_required"] is True
    assert run["lifecycle"]["await"] is False
    assert run["lifecycle"]["recovery_required"] is True
    assert "report_missing" in run["artifact_errors"]
    assert "artifact contract failed (report_missing)" in run["last_error"]

    refreshed = control_plane.lookup_run("just-missing-report")
    assert refreshed is not None
    assert refreshed["state"] == "report_missing"
    assert refreshed["health"] == "final"


def test_sync_state_reaps_stale_lock_present_run_without_launcher_pid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_RUN_GC_GRACE_SECONDS", "999999999")
    lock = _write_lock(
        home,
        {
            "run_id": "just-233141-77774",
            "status": "running",
            "agent": "codex",
            "mode": "justdo",
            "root": str(tmp_path),
            "skill": "just",
            "started": "2026-06-11T06:31:41Z",
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert lock.exists()
    assert run["state"] == "stalled"
    assert run["health"] == "stalled"
    assert run["liveness"] == "pid_gone"
    assert run["launcher_pid"] is None
    assert run["heartbeat_at"] == "2026-06-11T06:31:41Z"
    assert run["lock_present"] is True
    assert run["recovery_required"] is True
    assert run["lifecycle"]["recovery_required"] is True
    assert "launcher_pid is missing" in run["last_error"]
    assert "no live launcher proof" in run["last_error"]
    assert "lock file remains present" in run["last_error"]


def test_sync_state_leaves_fresh_lock_present_run_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "3600")
    started_at = control_plane._now().isoformat()
    lock = _write_lock(
        home,
        {
            "run_id": "just-fresh-lock",
            "status": "running",
            "agent": "codex",
            "mode": "justdo",
            "root": str(tmp_path),
            "skill": "just",
            "started": started_at,
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert lock.exists()
    assert run["state"] == "running"
    assert run["health"] == "active"
    assert run["liveness"] == "lock_present"
    assert run["launcher_pid"] is None
    assert run["heartbeat_at"] == started_at
    assert run["lock_present"] is True
    assert "recovery_required" not in run
    assert run["lifecycle"]["recovery_required"] is False


def test_sync_state_leaves_live_launcher_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "1")
    _write_meta(
        home,
        {
            "run_id": "just-live-pid",
            "status": "running",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:02:00+00:00",
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "just",
            "launcher_pid": os.getpid(),
            "liveness": "pid_alive",
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert run["state"] == "running"
    assert run["liveness"] == "pid_alive"
    assert run["lifecycle"]["recovery_required"] is False


def test_sync_state_leaves_terminal_dead_launcher_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "1")
    completed_at = "2026-05-19T00:02:00+00:00"
    _write_meta(
        home,
        {
            "run_id": "just-terminal-pid",
            "status": "completed",
            "agent": "codex",
            "mode": "implement",
            "root": str(tmp_path),
            "updated_at": completed_at,
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "just",
            "exit_code": 0,
            "launcher_pid": 999999999,
            "liveness": "terminal",
            "completed_at": completed_at,
        },
    )

    snapshot = control_plane.sync_state()
    run = snapshot["recent_runs"][0]

    assert run["state"] == "completed"
    assert run["health"] == "final"
    assert run["liveness"] == "terminal"
    assert "recovery_required" not in run


def test_sync_state_archives_old_terminal_snapshots_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_RUN_SNAPSHOT_RETENTION_SECONDS", "3600")
    monkeypatch.setenv("VIBECRAFTED_RUN_SNAPSHOT_RETENTION_COUNT", "100")
    now = dt.datetime(2026, 5, 19, 6, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(control_plane, "_now", lambda: now)
    runs_dir = home / "control_plane" / "runs"
    runs_dir.mkdir(parents=True)
    terminal_path = runs_dir / "old-terminal.json"
    active_path = runs_dir / "old-active.json"
    terminal_path.write_text(
        json.dumps(
            {
                "run_id": "old-terminal",
                "state": "completed",
                "health": "final",
                "updated_at": "2026-05-19T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    active_path.write_text(
        json.dumps(
            {
                "run_id": "old-active",
                "state": "running",
                "health": "active",
                "updated_at": "2026-05-19T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    control_plane.sync_state()
    control_plane.sync_state()

    archived = runs_dir / "archive" / "old-terminal.json"
    assert archived.exists()
    assert not terminal_path.exists()
    assert active_path.exists()
    assert json.loads(archived.read_text(encoding="utf-8"))["run_id"] == "old-terminal"


def test_await_run_completes_from_metadata_without_transcript(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    _write_meta(
        home,
        {
            "run_id": "wflw-030303-42",
            "status": "running",
            "agent": "codex",
            "mode": "workflow",
            "root": str(tmp_path),
            "updated_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "wflw",
            "exit_code": "0",
            "liveness": "terminal",
        },
    )

    payload = control_plane.await_run(
        "wflw-030303-42", timeout_seconds=0, interval_seconds=0.1
    )

    assert payload["completed"] is True
    assert payload["timed_out"] is False
    assert payload["run"]["exit_code"] == 0


def test_await_run_completes_when_dead_worker_missing_report_is_terminal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_LIVENESS_STALE_HEARTBEAT_SECONDS", "1")
    _write_meta(
        home,
        {
            "run_id": "wflw-missing-report",
            "status": "running",
            "agent": "codex",
            "mode": "workflow",
            "root": str(tmp_path),
            "report": str(tmp_path / "missing-report.md"),
            "transcript": str(tmp_path / "transcript.log"),
            "updated_at": "2026-05-19T00:02:00+00:00",
            "heartbeat_at": "2026-05-19T00:00:00+00:00",
            "skill_code": "wflw",
            "launcher_pid": 999999999,
            "liveness": "pid_alive",
        },
    )

    payload = control_plane.await_run(
        "wflw-missing-report", timeout_seconds=0, interval_seconds=0.1
    )

    assert payload["found"] is True
    assert payload["completed"] is True
    assert payload["timed_out"] is False
    assert payload["run"]["state"] == "report_missing"
    assert "report_missing" in payload["run"]["artifact_errors"]


def test_await_run_times_out_when_metadata_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))

    payload = control_plane.await_run(
        "missing-040404-42", timeout_seconds=0, interval_seconds=0.1
    )

    assert payload["found"] is False
    assert payload["completed"] is False
    assert payload["timed_out"] is True


def test_sync_state_projects_event_stream_lifecycle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    events = home / "control_plane" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": "2026-05-19T00:00:00+00:00",
                        "run_id": "wflw-111111-1111",
                        "kind": "launch",
                        "message": "launch accepted",
                        "payload": {
                            "state": "created",
                            "agent": "claude",
                            "skill": "workflow",
                            "mode": "workflow",
                            "runtime": "headless",
                            "root": str(tmp_path),
                            "prompt": "go",
                            "report": str(tmp_path / "report.md"),
                            "transcript": str(tmp_path / "run.log"),
                        },
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-05-19T00:00:05+00:00",
                        "run_id": "wflw-111111-1111",
                        "kind": "lifecycle:active",
                        "message": "process active",
                        "payload": {"state": "active", "liveness": "pid_alive"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = control_plane.sync_state()

    run = snapshot["recent_runs"][0]
    assert run["run_id"] == "wflw-111111-1111"
    assert run["state"] == "active"
    assert run["operator_state"] == "blocked"
    assert run["artifact_gate"] == "failed"
    assert "report_missing" in run["artifact_errors"]


def test_sync_state_surfaces_failure_card_on_contract_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    events = home / "control_plane" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(
        json.dumps(
            {
                "ts": "2026-05-19T00:01:00+00:00",
                "run_id": "wflw-222222-2222",
                "kind": "lifecycle:report_missing",
                "message": "artifact contract failed",
                "payload": {
                    "state": "report_missing",
                    "agent": "codex",
                    "skill": "workflow",
                    "mode": "workflow",
                    "root": str(tmp_path),
                    "artifact_errors": ["report_missing"],
                    "liveness": "terminal",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = control_plane.sync_state()

    run = snapshot["recent_runs"][0]
    assert run["run_id"] == "wflw-222222-2222"
    assert run["operator_state"] == "blocked"
    card = run["failure_card"]
    assert card is not None
    assert card["code"] == "runtime_contract_failure"
    assert any("contract failure" in warning for warning in snapshot["warnings"])


def test_block_run_lever_pins_terminal_blocked_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vibecrafted_core import workflow

    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    events = home / "control_plane" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(
        json.dumps(
            {
                "ts": "2026-05-19T00:02:00+00:00",
                "run_id": "wflw-333333-3333",
                "kind": "lifecycle:active",
                "message": "process active",
                "payload": {
                    "state": "active",
                    "agent": "claude",
                    "skill": "workflow",
                    "mode": "workflow",
                    "root": str(tmp_path),
                    "liveness": "pid_alive",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = workflow.block_run(
        "wflw-333333-3333", reason="waiting on operator", note="needs api key"
    )
    assert result["accepted"] is True

    snapshot = control_plane.sync_state()
    run = next(
        item
        for bucket in ("active_runs", "recent_runs")
        for item in (snapshot.get(bucket) or [])
        if item["run_id"] == "wflw-333333-3333"
    )
    assert run["state"] == "blocked"
    assert run["operator_state"] == "blocked"
    assert run["health"] == "final"
    assert run["failure_card"] is not None
