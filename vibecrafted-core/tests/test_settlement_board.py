from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from vibecrafted_core.settlement_board import (
    SETTLEMENT_BOARD_SCOPE,
    SETTLEMENT_COUNTS_PIPE,
    ServerSettlementBoard,
    SettlementBoardError,
    SettlementBoardPublisher,
)


def server_state(f: int = 158, x: int = 30, n: int = 80) -> dict[str, object]:
    return {
        "generated_at": "2026-08-10T19:59:44+00:00",
        "settlement_counts": {
            "scope": SETTLEMENT_BOARD_SCOPE,
            "active": 4,
            "f": f,
            "x": x,
            "n": n,
            "invalid": 0,
            "unclassified": 13,
            "total_settled": f + x + n,
        },
    }


def ledger_state(f: int = 118, x: int = 435, n: int = 2247) -> dict[str, object]:
    return {
        "counts": {
            "historical_transitions": {
                "f": f,
                "x": x,
                "n": n,
                "total": f + x + n,
            }
        }
    }


def test_server_board_requires_canonical_scope_and_consistent_totals() -> None:
    board = ServerSettlementBoard.from_state(server_state())
    assert (board.f, board.x, board.n) == (158, 30, 80)

    wrong_scope = server_state()
    assert isinstance(wrong_scope["settlement_counts"], dict)
    wrong_scope["settlement_counts"]["scope"] = "all_time"
    with pytest.raises(SettlementBoardError, match="scope"):
        ServerSettlementBoard.from_state(wrong_scope)

    wrong_total = server_state()
    assert isinstance(wrong_total["settlement_counts"], dict)
    wrong_total["settlement_counts"]["total_settled"] = 999
    with pytest.raises(SettlementBoardError, match="inconsistent"):
        ServerSettlementBoard.from_state(wrong_total)


def test_wire_displays_server_counts_not_local_historical_mountain(
    tmp_path: Path,
) -> None:
    publisher = SettlementBoardPublisher(
        server_url="http://100.82.232.70:3025",
        control_plane_root=tmp_path,
        board_reader=lambda _url, _timeout: server_state(),
        ledger_reader=lambda _path: ledger_state(),
        env={},
    )

    payload = json.loads(publisher._compatibility_payload())

    assert payload["latest_by_run"] == {"f": 158, "x": 30, "n": 80, "total": 268}
    assert payload["historical_transitions"] == {
        "f": 158,
        "x": 435,
        "n": 2247,
        "total": 2840,
    }
    assert payload["gaps"] == 0
    assert payload["complete_from"] == 1
    assert not (tmp_path / "settlement_history.json").exists()


def test_payload_identity_is_stable_until_canonical_board_changes(
    tmp_path: Path,
) -> None:
    states = [server_state(), server_state(), server_state(f=157)]

    def read_board(_url: str, _timeout: float) -> dict[str, object]:
        return states.pop(0)

    publisher = SettlementBoardPublisher(
        server_url="http://server.example:3025",
        control_plane_root=tmp_path,
        board_reader=read_board,
        ledger_reader=lambda _path: ledger_state(),
        env={},
    )

    first = json.loads(publisher._compatibility_payload())
    replay = json.loads(publisher._compatibility_payload())
    changed = json.loads(publisher._compatibility_payload())

    assert replay == first
    assert changed["generation"] != first["generation"]
    assert changed["sequence"] == first["sequence"]
    assert changed["latest_by_run"]["f"] == 157


def test_transport_carrier_stays_monotonic_across_guardian_restart(
    tmp_path: Path,
) -> None:
    first = SettlementBoardPublisher(
        server_url="http://server.example:3025",
        control_plane_root=tmp_path,
        board_reader=lambda _url, _timeout: server_state(f=158),
        ledger_reader=lambda _path: ledger_state(),
        env={},
    )
    first_payload = json.loads(first._compatibility_payload())

    restarted = SettlementBoardPublisher(
        server_url="http://server.example:3025",
        control_plane_root=tmp_path,
        board_reader=lambda _url, _timeout: server_state(f=157),
        ledger_reader=lambda _path: ledger_state(),
        env={},
    )
    restarted_payload = json.loads(restarted._compatibility_payload())

    assert (
        restarted_payload["historical_transitions"]
        == first_payload["historical_transitions"]
    )
    assert restarted_payload["latest_by_run"]["f"] == 157


def test_refresh_pipes_canonical_board_only_to_plugin_sessions(tmp_path: Path) -> None:
    binary = tmp_path / "vc-frame"
    binary.touch()
    calls: list[list[str]] = []

    def runner(argv: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        assert timeout == 2.0
        calls.append(argv)
        if "list-sessions" in argv:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=(
                    "Finalized runs [Created now]\n"
                    "live-one [Created now]\n"
                    "dead [Created now] (EXITED - attach to resurrect)\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    publisher = SettlementBoardPublisher(
        server_url="http://server.example:3025",
        control_plane_root=tmp_path / "control_plane",
        board_reader=lambda _url, _timeout: server_state(),
        ledger_reader=lambda _path: ledger_state(),
        runner=runner,
        env={"VIBECRAFTED_VC_FRAME_BIN": str(binary)},
        timeout=2.0,
    )

    report = publisher.refresh_and_flush()

    assert report.delivered_sessions == ("live-one",)
    assert len(calls) == 2
    pipe = calls[1]
    assert pipe[1:7] == [
        "--session",
        "live-one",
        "pipe",
        "--name",
        SETTLEMENT_COUNTS_PIPE,
        "--",
    ]
    assert json.loads(pipe[7])["latest_by_run"] == {
        "f": 158,
        "x": 30,
        "n": 80,
        "total": 268,
    }


def test_delivery_failure_is_backed_off_without_blocking_new_snapshot(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "vc-frame"
    binary.touch()
    now = [10.0]
    pipe_attempts = 0

    def runner(argv: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        nonlocal pipe_attempts
        del timeout
        if "list-sessions" in argv:
            return subprocess.CompletedProcess(
                argv, 0, stdout="live [Created now]\n", stderr=""
            )
        pipe_attempts += 1
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="busy")

    publisher = SettlementBoardPublisher(
        server_url="http://server.example:3025",
        control_plane_root=tmp_path / "control_plane",
        board_reader=lambda _url, _timeout: server_state(),
        ledger_reader=lambda _path: ledger_state(),
        runner=runner,
        env={"VIBECRAFTED_VC_FRAME_BIN": str(binary)},
        retry_backoff=300.0,
        clock=lambda: now[0],
    )

    assert publisher.refresh_and_flush().failed_sessions == ("live",)
    assert publisher.refresh_and_flush().deferred_sessions == ("live",)
    assert pipe_attempts == 1
