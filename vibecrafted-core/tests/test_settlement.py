"""Settlement layer contract — typed terminals, gc gate, await persistence, orphans."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from vibecrafted_core import control_plane
from vibecrafted_core.settlement import (
    SettlementVerdict,
    board_fxn_counts,
    can_archive,
    claim_digest_from_payload,
    orphan_markdown_paths,
    persist_await_verdict,
    settle_payload,
    tui_key_for,
)


def _write_meta(home: Path, payload: dict[str, object]) -> Path:
    reports = home / "artifacts" / "Vetcoders" / "vibecrafted" / "2026_0721" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"{payload['run_id']}.meta.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_tui_key_mapping() -> None:
    assert tui_key_for(SettlementVerdict.FINALIZED) == "f"
    assert tui_key_for(SettlementVerdict.FAILED) == "x"
    assert tui_key_for(SettlementVerdict.INVALID) == "x"
    assert tui_key_for(SettlementVerdict.NEEDS_ATTENTION) == "n"
    assert tui_key_for("unknown") == "n"


def test_exit_zero_without_report_is_needs_attention() -> None:
    settlement = settle_payload(
        {
            "state": "completed",
            "exit_code": 0,
            "report": "",
            "agent": "codex",
            "skill": "workflow",
        }
    )
    assert settlement is not None
    assert settlement.verdict is SettlementVerdict.NEEDS_ATTENTION
    assert settlement.tui_key == "n"
    assert "without_report" in settlement.reason


def test_report_without_seal_is_needs_attention(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text("# done\n", encoding="utf-8")
    settlement = settle_payload(
        {
            "state": "report_validated",
            "exit_code": 0,
            "report": str(report),
            "agent": "codex",
            "skill": "workflow",
            "prompt": "settle the layer",
            "proof_state": "undeclared",
            "delivery_state": "unverified",
        }
    )
    assert settlement is not None
    assert settlement.verdict is SettlementVerdict.NEEDS_ATTENTION
    assert settlement.reason == "report_without_seal"
    assert settlement.claim_digest


def test_claim_report_and_seal_is_finalized(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text("# done\n", encoding="utf-8")
    settlement = settle_payload(
        {
            "state": "report_validated",
            "exit_code": 0,
            "report": str(report),
            "agent": "codex",
            "skill": "workflow",
            "prompt": "settle the layer",
            "proof_state": "passed",
            "delivery_state": "sealed",
        }
    )
    assert settlement is not None
    assert settlement.verdict is SettlementVerdict.FINALIZED
    assert settlement.tui_key == "f"
    assert settlement.reason == "claim_report_and_seal"


def test_operator_waive_finalizes_without_seal(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text("# done\n", encoding="utf-8")
    settlement = settle_payload(
        {
            "state": "completed",
            "exit_code": 0,
            "report": str(report),
            "agent": "codex",
            "skill": "workflow",
            "operator_waive": True,
        }
    )
    assert settlement is not None
    assert settlement.verdict is SettlementVerdict.FINALIZED
    assert settlement.waived is True
    assert settlement.source == "operator_waive"


def test_proof_failed_is_failed_or_invalid() -> None:
    failed = settle_payload(
        {
            "state": "completed",
            "exit_code": 0,
            "proof_state": "failed",
            "delivery_state": "unverified",
            "agent": "x",
            "skill": "y",
        }
    )
    assert failed is not None
    assert failed.verdict is SettlementVerdict.FAILED
    assert failed.tui_key == "x"

    invalid = settle_payload(
        {
            "state": "completed",
            "exit_code": 0,
            "proof_state": "invalid",
            "agent": "x",
            "skill": "y",
        }
    )
    assert invalid is not None
    assert invalid.verdict is SettlementVerdict.INVALID
    assert invalid.tui_key == "x"


def test_live_run_has_no_settlement() -> None:
    assert settle_payload({"state": "running", "agent": "codex"}) is None


def test_unsettled_terminal_counts_as_n_on_board() -> None:
    counts = board_fxn_counts(
        [
            {"settlement_verdict": "finalized"},
            {"settlement_verdict": "failed"},
            {"settlement_verdict": "invalid"},
            {"settlement_verdict": "needs_attention"},
            {"state": "completed"},  # unsettled terminal → n, never silence
            {"state": "running"},  # live ignored
        ]
    )
    assert counts == {"f": 1, "x": 2, "n": 2}


def test_can_archive_requires_settlement() -> None:
    assert can_archive({}) is False
    assert can_archive({"state": "completed"}) is False
    assert can_archive({"settlement_verdict": "needs_attention"}) is True
    assert can_archive({"settlement_verdict": "finalized"}) is True


def test_orphan_markdown_scan(tmp_path: Path) -> None:
    (tmp_path / "Untitled.md").write_text("", encoding="utf-8")
    (tmp_path / "Untitled 1.md").write_text("x", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "Untitled-final.md").write_text("y", encoding="utf-8")
    (tmp_path / "real-report.md").write_text("ok", encoding="utf-8")
    orphans = orphan_markdown_paths(tmp_path)
    names = {p.name for p in orphans}
    assert "Untitled.md" in names
    assert "Untitled 1.md" in names
    assert "Untitled-final.md" in names
    assert "real-report.md" not in names


def test_claim_digest_stable() -> None:
    a = claim_digest_from_payload(
        {"prompt": "same", "skill": "workflow", "agent": "codex"}
    )
    b = claim_digest_from_payload(
        {"prompt": "same", "skill": "workflow", "agent": "codex"}
    )
    assert a and a == b
    c = claim_digest_from_payload(
        {"prompt": "other", "skill": "workflow", "agent": "codex"}
    )
    assert a != c


def test_sync_state_writes_settlement_on_terminal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_RUN_GC_GRACE_SECONDS", "999999999")
    report = home / "artifacts" / "r.md"
    report.parent.mkdir(parents=True)
    report.write_text("# report\n", encoding="utf-8")
    _write_meta(
        home,
        {
            "run_id": "work-settle-1",
            "status": "report_validated",
            "agent": "grok",
            "mode": "workflow",
            "root": str(tmp_path),
            "updated_at": "2026-07-21T00:00:00+00:00",
            "skill_code": "wflw",
            "exit_code": 0,
            "report": str(report),
            "prompt": "implement settlement",
            "liveness": "terminal",
        },
    )

    snapshot = control_plane.sync_state()
    run = next(r for r in snapshot["recent_runs"] if r["run_id"] == "work-settle-1")

    assert run["settlement_verdict"] == "needs_attention"
    assert run["settlement_reason"] == "report_without_seal"
    assert run["settlement_tui"] == "n"
    assert "settlement_counts" in snapshot
    assert snapshot["settlement_counts"]["n"] >= 1
    assert snapshot["settlement_counts"]["f"] == 0


def test_sync_state_gc_parks_with_settlement(
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
            "run_id": "just-old-stalled-settle",
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
    run = next(
        r for r in snapshot["recent_runs"] if r["run_id"] == "just-old-stalled-settle"
    )

    assert run["state"] == "gc"
    assert run["settlement_verdict"] == "needs_attention"
    assert run["settlement_tui"] == "n"
    assert "settlement parks as needs_attention" in run["last_error"]


def test_archive_settles_then_archives(
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
    terminal_path.write_text(
        json.dumps(
            {
                "run_id": "old-terminal",
                "state": "completed",
                "health": "final",
                "exit_code": 0,
                "updated_at": "2026-05-19T00:00:00+00:00",
                "completed_at": "2026-05-19T00:00:00+00:00",
                "agent": "codex",
                "skill": "workflow",
            }
        ),
        encoding="utf-8",
    )

    control_plane.sync_state()

    archived = runs_dir / "archive" / "old-terminal.json"
    assert archived.exists()
    body = json.loads(archived.read_text(encoding="utf-8"))
    assert body["settlement_verdict"] in {
        "finalized",
        "failed",
        "needs_attention",
        "invalid",
    }
    assert not terminal_path.exists()


def test_await_persists_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    run_id = "work-await-settle"
    run_dir = home / "control_plane" / "runtime_runs" / run_id
    run_dir.mkdir(parents=True)
    meta = run_dir / "meta.json"
    meta.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "exit_code": 0,
                "agent": "grok",
                "skill_code": "wflw",
                "liveness": "terminal",
            }
        ),
        encoding="utf-8",
    )
    _write_meta(
        home,
        {
            "run_id": run_id,
            "status": "completed",
            "agent": "grok",
            "mode": "workflow",
            "root": str(tmp_path),
            "updated_at": "2026-07-21T00:00:00+00:00",
            "skill_code": "wflw",
            "exit_code": 0,
            "liveness": "terminal",
            "meta": str(meta),
        },
    )

    payload = control_plane.await_run(run_id, timeout_seconds=0, interval_seconds=0.05)

    assert payload["completed"] is True
    assert payload["await_outcome"] == "completed"
    assert payload["await_rc"] == 0
    meta_body = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_body["await_outcome"] == "completed"
    assert meta_body["await_rc"] == 0
    assert "await_settled_at" in meta_body


def test_persist_await_verdict_standalone(tmp_path: Path) -> None:
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"run_id": "x"}), encoding="utf-8")
    fields = persist_await_verdict(
        meta, rc=1, outcome="timed_out", worker_alive=False, reason="idle_stall"
    )
    body = json.loads(meta.read_text(encoding="utf-8"))
    assert body["await_rc"] == 1
    assert body["await_outcome"] == "timed_out"
    assert fields["await_reason"] == "idle_stall"
