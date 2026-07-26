from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest
from vibecrafted_core import control_plane
from vibecrafted_core.settlement_history import (
    MAX_U64,
    SETTLEMENT_COUNTS_PIPE,
    SETTLEMENT_HISTORY_GENERATION_SCHEMA,
    SETTLEMENT_REPLAY_INTERVAL_SECONDS,
    RunSettlementHistory,
    SettlementCounts,
    SettlementHistoryError,
    SettlementHistoryPublisher,
    SettlementHistorySnapshot,
    advance_run_settlement_history,
    reconcile_settlement_history,
)

GENERATION = "019f9c72-6ed3-7a41-8cf0-df0b7bff80fe"
NEXT_GENERATION = "019f9c72-6ed3-7a41-8cf0-df0b7bff80ff"


def write_generation(
    root: Path,
    generation: str = GENERATION,
    *,
    continuity_gaps: int = 0,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "settlement_history_generation.json").write_text(
        json.dumps(
            {
                "schema": SETTLEMENT_HISTORY_GENERATION_SCHEMA,
                "generation": generation,
                "continuity_gaps": continuity_gaps,
            }
        ),
        encoding="utf-8",
    )


def settled(run_id: str, revision: int, tui: str) -> dict[str, Any]:
    verdict = {
        "f": "finalized",
        "x": "failed",
        "n": "needs_attention",
    }[tui]
    return {
        "run_id": run_id,
        "state": "completed",
        "settlement_verdict": verdict,
        "settlement_tui": tui,
        "settlement_revision": revision,
        "settlement_reason": "test",
        "settlement_at": "2026-07-26T06:00:00+00:00",
        "settlement_source": "test",
        "settlement_claim_digest": "",
        "settlement_waived": False,
        "settlement": {
            "verdict": verdict,
            "tui": tui,
            "reason": "test",
            "settled_at": "2026-07-26T06:00:00+00:00",
            "source": "test",
            "claim_digest": "",
            "waived": False,
        },
    }


def settlement_event(run_id: str, revision: int, tui: str) -> dict[str, Any]:
    return {
        "schema": "vibecrafted.settlement-event.v1",
        "run_id": run_id,
        "revision": revision,
        "current": {"tui": tui},
    }


def test_per_run_history_counts_each_revision_and_replay_is_idempotent() -> None:
    first = settled("run-1", 1, "n")
    first["settlement_history"] = advance_run_settlement_history(
        None,
        first,
        settlement_event("run-1", 1, "n"),
    )
    second = settled("run-1", 2, "f")
    event = settlement_event("run-1", 2, "f")

    advanced = advance_run_settlement_history(first, second, event)
    replay = advance_run_settlement_history(
        {**second, "settlement_history": advanced},
        second,
        event,
    )
    history = RunSettlementHistory.from_payload(advanced)

    assert history.historical_transitions.to_payload() == {
        "f": 1,
        "x": 0,
        "n": 1,
        "total": 2,
    }
    assert (history.latest_revision, history.latest_tui) == (2, "f")
    assert history.gaps == 0
    assert history.complete_from == 1
    assert replay == advanced


def test_legacy_revision_hole_is_an_honest_lower_bound() -> None:
    history = RunSettlementHistory.from_payload(
        advance_run_settlement_history(None, settled("legacy", 3, "x"))
    )

    assert history.historical_transitions.to_payload() == {
        "f": 0,
        "x": 1,
        "n": 0,
        "total": 1,
    }
    assert history.gaps == 2
    assert history.complete_from is None


def test_legacy_revision_one_without_a_ledger_is_still_incomplete() -> None:
    history = RunSettlementHistory.from_payload(
        advance_run_settlement_history(None, settled("legacy", 1, "f"))
    )

    assert history.gaps == 1
    assert history.complete_from is None


def test_snapshot_carries_history_even_when_event_publish_crashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path))
    path = control_plane.run_snapshot_dir() / "run-crash.json"

    def crash_after_snapshot(_event: object) -> None:
        raise OSError("injected event append crash")

    monkeypatch.setattr(control_plane, "emit_settlement_event", crash_after_snapshot)
    with pytest.raises(OSError, match="injected event append crash"):
        control_plane._write_run_snapshot(
            path,
            None,
            settled("run-crash", 1, "n"),
        )

    persisted = json.loads(path.read_text(encoding="utf-8"))
    history = RunSettlementHistory.from_payload(persisted["settlement_history"])
    assert history.latest_tui == "n"
    assert history.historical_transitions.n == 1


def test_reconcile_dedupes_active_archive_and_is_restart_idempotent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "control_plane"
    active = root / "runs" / "run-one.json"
    archive = root / "runs" / "archive" / "run-one.json"
    active.parent.mkdir(parents=True)
    archive.parent.mkdir(parents=True)

    first = settled("run-one", 1, "n")
    first["settlement_history"] = advance_run_settlement_history(
        None,
        first,
        settlement_event("run-one", 1, "n"),
    )
    current = settled("run-one", 2, "f")
    current["settlement_history"] = advance_run_settlement_history(
        first,
        current,
        settlement_event("run-one", 2, "f"),
    )
    encoded = json.dumps(current)
    active.write_text(encoded, encoding="utf-8")
    archive.write_text(encoded, encoding="utf-8")
    legacy = settled("run-two", 3, "x")
    (archive.parent / "run-two.json").write_text(
        json.dumps(legacy),
        encoding="utf-8",
    )

    first_projection = reconcile_settlement_history(control_plane_root=root)
    replay_projection = reconcile_settlement_history(control_plane_root=root)

    assert first_projection == replay_projection
    assert first_projection.to_payload() == {
        "schema": "vibecrafted.settlement-history.v1",
        "generation": first_projection.generation,
        "sequence": 3,
        "historical_transitions": {"f": 1, "x": 1, "n": 1, "total": 3},
        "latest_by_run": {"f": 1, "x": 1, "n": 0, "total": 2},
        "gaps": 2,
        "complete_from": None,
    }


def test_reconcile_rejects_same_revision_active_archive_divergence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "control_plane"
    active = root / "runs" / "run-one.json"
    archive = root / "runs" / "archive" / "run-one.json"
    active.parent.mkdir(parents=True)
    archive.parent.mkdir(parents=True)
    active.write_text(json.dumps(settled("run-one", 1, "f")), encoding="utf-8")
    archive.write_text(json.dumps(settled("run-one", 1, "x")), encoding="utf-8")

    with pytest.raises(SettlementHistoryError, match="divergent active/archive"):
        reconcile_settlement_history(control_plane_root=root)


def test_generation_is_stable_until_its_durable_store_id_is_reset(
    tmp_path: Path,
) -> None:
    root = tmp_path / "control_plane"
    run = root / "runs" / "run-one.json"
    run.parent.mkdir(parents=True)
    payload = settled("run-one", 1, "f")
    payload["settlement_history"] = advance_run_settlement_history(
        None,
        payload,
        settlement_event("run-one", 1, "f"),
    )
    run.write_text(json.dumps(payload), encoding="utf-8")

    first = reconcile_settlement_history(control_plane_root=root)
    replay = reconcile_settlement_history(control_plane_root=root)
    assert replay.generation == first.generation

    (root / "settlement_history_generation.json").unlink()
    reset = reconcile_settlement_history(control_plane_root=root)
    reset_replay = reconcile_settlement_history(control_plane_root=root)

    assert reset.generation != first.generation
    assert reset_replay == reset
    assert reset.sequence == first.sequence
    assert reset.gaps == 1
    assert reset.complete_from is None


def test_reset_to_empty_store_is_partial_not_an_exact_zero(tmp_path: Path) -> None:
    root = tmp_path / "control_plane"
    run = root / "runs" / "run-one.json"
    run.parent.mkdir(parents=True)
    payload = settled("run-one", 1, "f")
    payload["settlement_history"] = advance_run_settlement_history(
        None,
        payload,
        settlement_event("run-one", 1, "f"),
    )
    run.write_text(json.dumps(payload), encoding="utf-8")
    first = reconcile_settlement_history(control_plane_root=root)

    run.unlink()
    (root / "settlement_history_generation.json").unlink()
    reset = reconcile_settlement_history(control_plane_root=root)

    assert reset.generation != first.generation
    assert reset.sequence == 0
    assert reset.historical_transitions.total == 0
    assert reset.latest_by_run.total == 0
    assert reset.gaps == 1
    assert reset.complete_from is None


def test_public_schema_rejects_latest_bucket_without_historical_transition() -> None:
    with pytest.raises(SettlementHistoryError, match="bucket exceeds"):
        SettlementHistorySnapshot.from_payload(
            {
                "schema": "vibecrafted.settlement-history.v1",
                "generation": GENERATION,
                "sequence": 1,
                "historical_transitions": {"f": 0, "x": 0, "n": 1, "total": 1},
                "latest_by_run": {"f": 1, "x": 0, "n": 0, "total": 1},
                "gaps": 0,
                "complete_from": 1,
            }
        )


def test_public_schema_is_exactly_u64_width() -> None:
    maximum = SettlementHistorySnapshot.from_payload(
        {
            "schema": "vibecrafted.settlement-history.v1",
            "generation": GENERATION,
            "sequence": MAX_U64,
            "historical_transitions": {
                "f": MAX_U64,
                "x": 0,
                "n": 0,
                "total": MAX_U64,
            },
            "latest_by_run": {
                "f": MAX_U64,
                "x": 0,
                "n": 0,
                "total": MAX_U64,
            },
            "gaps": MAX_U64,
            "complete_from": None,
        }
    )
    assert maximum.sequence == MAX_U64

    too_wide = maximum.to_payload()
    too_wide["gaps"] = MAX_U64 + 1
    with pytest.raises(SettlementHistoryError, match="gaps are invalid"):
        SettlementHistorySnapshot.from_payload(too_wide)

    with pytest.raises(SettlementHistoryError, match="total exceeds u64"):
        SettlementCounts(f=MAX_U64, x=1)

    with pytest.raises(SettlementHistoryError, match="revision exceeds u64"):
        advance_run_settlement_history(
            None,
            settled("too-wide", MAX_U64 + 1, "f"),
            settlement_event("too-wide", MAX_U64 + 1, "f"),
        )


def test_publisher_broadcasts_only_to_running_sessions_without_plugin_launch(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "vc-frame"
    binary.touch()
    calls: list[list[str]] = []

    def runner(
        argv: list[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        assert timeout == 2.0
        calls.append(argv)
        if "list-sessions" in argv:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=(
                    "live-one [Created 1s ago] \n"
                    "dead-one [Created 2s ago] (EXITED - attach to resurrect)\n"
                    "live-two [Created 3s ago] \n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    publisher = SettlementHistoryPublisher(
        control_plane_root=tmp_path / "control_plane",
        runner=runner,
        env={"VIBECRAFTED_VC_FRAME_BIN": str(binary)},
        timeout=2.0,
    )
    write_generation(publisher.root)
    snapshot = SettlementHistorySnapshot.from_payload(
        {
            "schema": "vibecrafted.settlement-history.v1",
            "generation": GENERATION,
            "sequence": 1,
            "historical_transitions": {"f": 1, "x": 0, "n": 0, "total": 1},
            "latest_by_run": {"f": 1, "x": 0, "n": 0, "total": 1},
            "gaps": 0,
            "complete_from": 1,
        }
    )
    publisher.stage(snapshot)

    report = publisher.flush()

    assert report.delivered_sessions == ("live-one", "live-two")
    assert not publisher.outbox_path.exists()
    pipe_calls = calls[1:]
    assert [call[2] for call in pipe_calls] == ["live-one", "live-two"]
    assert all(
        call[3:8]
        == ["pipe", "--name", SETTLEMENT_COUNTS_PIPE, "--", snapshot.to_json()]
        for call in pipe_calls
    )
    assert all("--plugin" not in call for call in pipe_calls)


def test_publisher_failure_retains_only_the_newest_snapshot(tmp_path: Path) -> None:
    binary = tmp_path / "vc-frame"
    binary.touch()

    def runner(
        argv: list[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        if "list-sessions" in argv:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="live [Created 1s ago] \n",
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="busy")

    publisher = SettlementHistoryPublisher(
        control_plane_root=tmp_path / "control_plane",
        runner=runner,
        env={"VIBECRAFTED_VC_FRAME_BIN": str(binary)},
    )
    write_generation(publisher.root)
    first = SettlementHistorySnapshot(
        generation=GENERATION,
        sequence=1,
        historical_transitions=RunSettlementHistory.from_payload(
            advance_run_settlement_history(
                None,
                settled("one", 1, "f"),
                settlement_event("one", 1, "f"),
            )
        ).historical_transitions,
        latest_by_run=RunSettlementHistory.from_payload(
            advance_run_settlement_history(
                None,
                settled("one", 1, "f"),
                settlement_event("one", 1, "f"),
            )
        ).historical_transitions,
        gaps=0,
        complete_from=1,
    )
    second_payload = first.to_payload()
    second_payload.update(
        {
            "sequence": 2,
            "historical_transitions": {"f": 1, "x": 1, "n": 0, "total": 2},
            "latest_by_run": {"f": 1, "x": 1, "n": 0, "total": 2},
        }
    )
    second = SettlementHistorySnapshot.from_payload(second_payload)

    publisher.stage(first)
    assert publisher.flush().pending is True
    publisher.stage(second)

    pending = json.loads(publisher.outbox_path.read_text(encoding="utf-8"))
    assert pending["sequence"] == 2
    assert pending["payload"] == second.to_payload()


def test_publisher_fences_retired_generation_after_reset(tmp_path: Path) -> None:
    root = tmp_path / "control_plane"
    write_generation(root)
    publisher = SettlementHistoryPublisher(control_plane_root=root)
    first = SettlementHistorySnapshot.from_payload(
        {
            "schema": "vibecrafted.settlement-history.v1",
            "generation": GENERATION,
            "sequence": 1,
            "historical_transitions": {"f": 1, "x": 0, "n": 0, "total": 1},
            "latest_by_run": {"f": 1, "x": 0, "n": 0, "total": 1},
            "gaps": 0,
            "complete_from": 1,
        }
    )
    reset = SettlementHistorySnapshot.from_payload(
        {
            "schema": "vibecrafted.settlement-history.v1",
            "generation": NEXT_GENERATION,
            "sequence": 0,
            "historical_transitions": {"f": 0, "x": 0, "n": 0, "total": 0},
            "latest_by_run": {"f": 0, "x": 0, "n": 0, "total": 0},
            "gaps": 1,
            "complete_from": None,
        }
    )
    publisher.stage(first)

    write_generation(root, NEXT_GENERATION, continuity_gaps=1)
    assert publisher.flush().reason == "stale settlement history generation"
    publisher.stage(reset)
    with pytest.raises(SettlementHistoryError, match="stale"):
        publisher.stage(first)

    pending = json.loads(publisher.outbox_path.read_text(encoding="utf-8"))
    assert pending["payload"] == reset.to_payload()


def test_background_refresh_is_nonblocking_and_coalesces_latest_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = SettlementHistoryPublisher(
        control_plane_root=tmp_path / "control_plane"
    )
    started = threading.Event()
    release = threading.Event()
    calls: list[int] = []

    def refresh() -> object:
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            started.set()
            assert release.wait(timeout=2)
        return object()

    monkeypatch.setattr(publisher, "refresh_and_flush", refresh)

    assert publisher.request_refresh() is True
    assert started.wait(timeout=2)
    assert publisher.request_refresh() is False
    assert publisher.request_refresh() is False
    release.set()

    assert publisher.wait_for_idle(timeout=2)
    assert calls == [1, 2]


def test_periodic_refresh_replays_for_new_plugins_within_five_seconds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = SettlementHistoryPublisher(
        control_plane_root=tmp_path / "control_plane"
    )
    refreshed = threading.Event()
    calls: list[int] = []

    def refresh() -> object:
        calls.append(len(calls) + 1)
        if len(calls) >= 2:
            refreshed.set()
        return object()

    monkeypatch.setattr(publisher, "refresh_and_flush", refresh)

    assert 0 < SETTLEMENT_REPLAY_INTERVAL_SECONDS <= 5
    try:
        assert publisher.start_periodic_refresh(interval=0.01) is True
        assert publisher.start_periodic_refresh(interval=0.01) is False
        assert refreshed.wait(timeout=0.5)
    finally:
        assert publisher.stop_periodic_refresh(timeout=1)
        assert publisher.wait_for_idle(timeout=1)

    delivered = len(calls)
    assert delivered >= 2
    threading.Event().wait(0.03)
    assert len(calls) == delivered
