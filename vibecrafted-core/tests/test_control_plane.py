from __future__ import annotations

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
        "recovery_required": False,
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
