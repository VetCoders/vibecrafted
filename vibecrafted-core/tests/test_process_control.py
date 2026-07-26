"""Identity-qualified process control (vc-procs authority)."""

from __future__ import annotations

import signal

from vibecrafted_core import process_control as pc
from vibecrafted_core import run_reaper


def entry(
    pid: int,
    ppid: int = 1,
    pgid: int | None = None,
    command: str = "node agent",
    start_token: str | None = None,
) -> run_reaper.ProcessEntry:
    return run_reaper.ProcessEntry(
        pid=pid,
        ppid=ppid,
        pgid=pid if pgid is None else pgid,
        command=command,
        start_token=start_token or f"birth:{pid}",
    )


TERMINAL_RUN = {
    "run_id": "impl-test-0001",
    "session_id": "019fa010-1010-7010-8010-101010101010",
    "state": "completed",
    "exit_code": 0,
    "worker_pgid": 4242,
}


def identity() -> run_reaper.ProcessEnvIdentity:
    return run_reaper.ProcessEnvIdentity(
        run_id=str(TERMINAL_RUN["run_id"]),
        session_id=str(TERMINAL_RUN["session_id"]),
    )


def test_snapshot_marks_owned_process_killable():
    table = [entry(900, pgid=4242, command="node worker")]
    snap = pc.snapshot_processes(
        table=table,
        runs=[TERMINAL_RUN],
        env_index={900: identity()},
        self_pid=1000,
        env={},
    )
    assert snap["schema"] == pc.SCHEMA_VERSION
    rows = {r["pid"]: r for r in snap["processes"]}
    assert 900 in rows
    assert rows[900]["killable"] is True
    assert rows[900]["ownership"] == "proven"
    assert rows[900]["run_id"] == TERMINAL_RUN["run_id"]
    assert len(rows[900]["command_sha256"]) == 64
    assert rows[900]["start_token"]


def test_snapshot_protects_vc_frame():
    table = [entry(901, pgid=4242, command="/usr/local/bin/vc-frame attach foo")]
    snap = pc.snapshot_processes(
        table=table,
        runs=[TERMINAL_RUN],
        env_index={901: identity()},
        self_pid=1000,
        env={},
    )
    row = next(r for r in snap["processes"] if r["pid"] == 901)
    assert row["killable"] is False
    assert row["ownership"] == "protected"


def test_terminate_rejects_stale_start_token():
    table = [entry(902, pgid=4242, command="node worker")]
    live_hash = pc.command_sha256("node worker")
    signals: list[tuple[int, int]] = []

    def signaller(pid: int, sig: int) -> str:
        signals.append((pid, sig))
        return "signalled"

    outcome = pc.terminate_process(
        pid=902,
        expected_start="start:WRONG",
        expected_command_sha256=live_hash,
        expected_run_id=TERMINAL_RUN["run_id"],
        table=table,
        runs=[TERMINAL_RUN],
        env_index={902: identity()},
        self_pid=1000,
        env={},
        signaller=signaller,
        alive_check=lambda _pid: True,
        sleeper=lambda _s: None,
        start_reader=lambda pid: f"birth:{pid}",
        grace=0,
    )
    assert outcome.ok is False
    assert outcome.outcome == "stale_selection"
    assert signals == []


def test_terminate_allows_owned_process():
    cmd = "node worker"
    table = [entry(903, pgid=4242, command=cmd)]
    start = table[0].start_token
    cmd_hash = pc.command_sha256(cmd)
    signals: list[tuple[int, int]] = []

    def signaller(pid: int, sig: int) -> str:
        signals.append((pid, sig))
        return "signalled"

    alive = {903: True}

    def alive_check(pid: int) -> bool:
        return alive.get(pid, False)

    def sleeper(_s: float) -> None:
        alive[903] = False

    outcome = pc.terminate_process(
        pid=903,
        expected_start=start,
        expected_command_sha256=cmd_hash,
        expected_run_id=TERMINAL_RUN["run_id"],
        table=table,
        runs=[TERMINAL_RUN],
        env_index={903: identity()},
        self_pid=1000,
        env={},
        signaller=signaller,
        alive_check=alive_check,
        sleeper=sleeper,
        start_reader=lambda pid: f"birth:{pid}",
        grace=0.01,
    )
    assert outcome.ok is True
    assert outcome.outcome in {"terminated", "killed"}
    assert signals[0] == (903, signal.SIGTERM)


def test_terminate_blocks_pid_reuse_between_term_and_kill():
    cmd = "node worker"
    table = [entry(904, pgid=4242, command=cmd)]
    births = iter(("birth:904", "birth:904", "birth:REUSED"))
    signals: list[tuple[int, int]] = []

    def signaller(pid: int, sig: int) -> str:
        signals.append((pid, sig))
        return "signalled"

    outcome = pc.terminate_process(
        pid=904,
        expected_start="birth:904",
        expected_command_sha256=pc.command_sha256(cmd),
        expected_run_id=TERMINAL_RUN["run_id"],
        table=table,
        runs=[TERMINAL_RUN],
        env_index={904: identity()},
        self_pid=1000,
        env={},
        signaller=signaller,
        alive_check=lambda _pid: True,
        sleeper=lambda _seconds: None,
        start_reader=lambda _pid: next(births),
        grace=0,
    )

    assert outcome.ok is False
    assert outcome.outcome == "stale_selection"
    assert outcome.detail == "birth_identity_changed_before_kill"
    assert signals == [(904, signal.SIGTERM)]
