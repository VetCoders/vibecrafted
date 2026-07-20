"""Garbage collector for processes that outlive their run.

The control plane already *knows* when a run is dead — ``_reconcile_dead_launcher``
settles it to ``gc``/``stalled`` and records ``pid_gone``. Nothing ever acted on
that knowledge, so a run could reach a terminal state while its monitors, watchers
and helper children kept burning cores for days. This module is the missing actor:
given the control plane's terminal runs, it finds surviving processes that provably
belong to them and takes them down, with a receipt for every decision.

**Ownership must be proven, never inferred.** The reaper runs inside a live
workspace full of processes it must not touch — vc-frame servers, MCP servers, the
operator's own shells and panes. So a pid is a candidate only when it carries one of
two independent proofs tying it to a specific terminal run:

``env_run_id``
    The process environment carries ``SPAWN_RUN_ID=<run>``. Every process in a run's
    tree inherits it (``lib/launcher.sh`` exports it), so this is the strongest
    proof available. It is not universally *readable*, though: macOS strips the
    environment of SIP-protected/hardened binaries, so ``ps eww`` answers for a
    homebrew ``python``/``node`` (what agents actually are) and stays silent for
    ``/bin/sleep``. Absence of the variable therefore proves nothing.

``worker_pgid``
    The process group id matches the run's recorded ``worker_pgid``/``worker_pid``.
    Crucially this survives orphaning — when a parent dies the child is reparented
    to launchd/init but keeps its process group — which is exactly the state the
    survivors we are hunting are in. Where env-reading fails, this still holds.

Anything without one of those is reported as ``unproven`` and left running. A
survivor we failed to prove is a survivor we keep; killing the wrong process in a
live workspace costs far more than missing one.

**We never take ourselves down.** The terminal-seam caller runs *inside* the very
run whose survivors it is reaping, so its own pid and every ancestor are excluded
before anything is signalled. Siblings — the orphaned monitor — remain fair game;
that is the whole point.

Escalation is TERM, then a bounded grace, then KILL, receipted per step. The kill
switch is ``VIBECRAFTED_REAPER=0``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

__all__ = [
    "ProcessEntry",
    "ReapCandidate",
    "ReapPlan",
    "ReapReceipt",
    "PROTECTED_COMMAND_PATTERNS",
    "build_env_index",
    "build_process_table",
    "plan_reap",
    "reap_terminal_runs",
    "main",
]

_TRUTHY_OFF = {"0", "false", "no", "off"}

REAPER_ENABLED_ENV = "VIBECRAFTED_REAPER"
REAPER_GRACE_ENV = "VIBECRAFTED_REAPER_GRACE_SECONDS"
DEFAULT_GRACE_SECONDS = 5.0

#: Never signalled, even when a proof matches. These are workspace infrastructure
#: that can share a process group with a run by accident of how a tab was opened:
#: the terminal multiplexer that *hosts* the run is not part of the run. Killing
#: one takes the operator's window (and every sibling run in it) with it.
PROTECTED_COMMAND_PATTERNS = (
    "vc-frame",
    "zellij",
    "tmux",
    "mcp-server",
    "loctree-mcp",
    "aicx-mcp",
    "sshd",
    "login",
)

_ENV_RUN_ID_PATTERN = re.compile(r"(?:^|\s)SPAWN_RUN_ID=(\S+)")


def reaper_enabled(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return str(env.get(REAPER_ENABLED_ENV, "") or "").strip().lower() not in _TRUTHY_OFF


def grace_seconds(env: Mapping[str, str] | None = None) -> float:
    env = os.environ if env is None else env
    raw = str(env.get(REAPER_GRACE_ENV, "") or "").strip()
    if not raw:
        return DEFAULT_GRACE_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_GRACE_SECONDS
    return value if value >= 0 else DEFAULT_GRACE_SECONDS


@dataclass(frozen=True)
class ProcessEntry:
    """One row of the process table."""

    pid: int
    ppid: int
    pgid: int
    command: str


@dataclass(frozen=True)
class ReapCandidate:
    """A surviving process and what we could (or could not) prove about it."""

    pid: int
    command: str
    run_id: str = ""
    #: "env_run_id" | "worker_pgid" — empty when unproven.
    evidence: str = ""
    detail: str = ""

    @property
    def proven(self) -> bool:
        return bool(self.evidence and self.run_id)

    def row(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "run_id": self.run_id,
            "evidence": self.evidence or "unproven",
            "detail": self.detail,
            "command": self.command[:200],
        }


@dataclass(frozen=True)
class ReapPlan:
    """The decision, taken without side effects so it can be tested directly."""

    should_run: bool
    skip_reason: str = ""
    doomed: tuple[ReapCandidate, ...] = ()
    unproven: tuple[ReapCandidate, ...] = ()
    protected: tuple[ReapCandidate, ...] = ()

    def render(self) -> str:
        """The ``--dry-run`` table: every pid with the evidence behind its verdict."""
        if not self.should_run:
            return f"reaper: skipped ({self.skip_reason})"
        lines: list[str] = []
        for label, rows in (
            ("REAP", self.doomed),
            ("KEEP/unproven", self.unproven),
            ("KEEP/protected", self.protected),
        ):
            for candidate in rows:
                lines.append(
                    f"{label:<15} pid={candidate.pid:<8} run={candidate.run_id or '-':<28} "
                    f"evidence={candidate.evidence or 'unproven':<12} {candidate.command[:80]}"
                )
        if not lines:
            return "reaper: no survivors of terminal runs"
        header = (
            f"reaper: {len(self.doomed)} to reap, {len(self.unproven)} unproven, "
            f"{len(self.protected)} protected"
        )
        return "\n".join([header, *lines])


@dataclass
class ReapReceipt:
    """What actually happened, as written into the run's control-plane record."""

    run_id: str
    reaped: list[dict[str, Any]] = field(default_factory=list)
    unproven: list[dict[str, Any]] = field(default_factory=list)
    skipped_reason: str = ""

    def payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {"reaped": self.reaped}
        if self.unproven:
            data["reap_unproven"] = self.unproven
        if self.skipped_reason:
            data["reap_skipped"] = self.skipped_reason
        return data


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argv is built, never shell-interpolated.
        list(argv),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def build_process_table(
    runner: Callable[..., Any] | None = None,
) -> tuple[ProcessEntry, ...]:
    """Snapshot the process table. Empty on any failure — never raises."""
    runner = _default_runner if runner is None else runner
    try:
        proc = runner(["ps", "-A", "-o", "pid=,ppid=,pgid=,command="])
    except Exception:
        return ()
    if getattr(proc, "returncode", 1) != 0:
        return ()
    entries: list[ProcessEntry] = []
    for line in str(getattr(proc, "stdout", "") or "").splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) < 4:
            continue
        try:
            pid, ppid, pgid = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        entries.append(ProcessEntry(pid=pid, ppid=ppid, pgid=pgid, command=parts[3]))
    return tuple(entries)


def build_env_index(runner: Callable[..., Any] | None = None) -> dict[int, str]:
    """Map pid -> ``SPAWN_RUN_ID`` for every process that exposes one.

    One ``ps axeww`` for the whole machine rather than one probe per pid: the sweep
    runs on every spawn, so hundreds of forks would make it too expensive to be
    opportunistic. ``ww`` disables column truncation, without which a long
    environment is clipped and the variable silently disappears.

    Best-effort by design: macOS refuses the environment of SIP-protected/hardened
    binaries and lists only argv for them. A missing entry means "could not prove",
    never "not owned" — which is why ``worker_pgid`` exists as the second proof.

    The pattern is anchored on a whitespace boundary so a run id merely *mentioned*
    in some other process's command line (``--env SPAWN_RUN_ID:...``) cannot forge
    ownership; only a real ``SPAWN_RUN_ID=<id>`` token counts.
    """
    runner = _default_runner if runner is None else runner
    try:
        proc = runner(["ps", "axeww"])
    except Exception:
        return {}
    if getattr(proc, "returncode", 1) != 0:
        return {}
    index: dict[int, str] = {}
    for line in str(getattr(proc, "stdout", "") or "").splitlines():
        head = line.split(maxsplit=1)
        if not head or not head[0].isdigit():
            continue
        match = _ENV_RUN_ID_PATTERN.search(line)
        if match:
            index[int(head[0])] = match.group(1)
    return index


def _ancestors(pid: int, by_pid: Mapping[int, ProcessEntry]) -> set[int]:
    """Every pid up the parent chain from ``pid``, inclusive."""
    seen: set[int] = set()
    current = pid
    while current > 1 and current not in seen:
        seen.add(current)
        entry = by_pid.get(current)
        if entry is None:
            break
        current = entry.ppid
    return seen


def _is_protected(command: str) -> bool:
    lowered = command.lower()
    return any(pattern in lowered for pattern in PROTECTED_COMMAND_PATTERNS)


def _terminal_run_index(
    runs: Iterable[Mapping[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[int, str],
]:
    """Map terminal runs by id, and their recorded process groups back to run ids."""
    from .control_plane import _coerce_int, _run_is_terminal

    by_run: dict[str, dict[str, Any]] = {}
    pgid_owner: dict[int, str] = {}
    for run in runs:
        run_id = str(run.get("run_id") or "").strip()
        if not run_id or not _run_is_terminal(dict(run)):
            continue
        by_run[run_id] = dict(run)
        for key in ("worker_pgid", "worker_pid"):
            pgid = _coerce_int(run.get(key))
            # pgid 0/1 would match half the machine; only a real group proves ownership.
            if pgid is not None and pgid > 1:
                pgid_owner.setdefault(pgid, run_id)
    return by_run, pgid_owner


def plan_reap(
    runs: Iterable[Mapping[str, Any]],
    table: Sequence[ProcessEntry],
    env_index: Mapping[int, str] | None = None,
    self_pid: int | None = None,
    env: Mapping[str, str] | None = None,
) -> ReapPlan:
    """Decide which survivors may be killed. Pure: signals nothing, touches nothing.

    The process table and env index are injected so unit tests can drive a fake
    machine with no real processes anywhere near the decision.
    """
    env = os.environ if env is None else env
    if not reaper_enabled(env):
        return ReapPlan(should_run=False, skip_reason="disabled")

    by_run, pgid_owner = _terminal_run_index(runs)
    if not by_run:
        return ReapPlan(should_run=True)

    env_index = {} if env_index is None else env_index
    self_pid = os.getpid() if self_pid is None else self_pid
    by_pid = {entry.pid: entry for entry in table}
    # Our own line of descent. The terminal-seam caller is itself a process of the
    # run being reaped; killing an ancestor would kill the reap mid-flight.
    protected_pids = _ancestors(self_pid, by_pid)

    doomed: list[ReapCandidate] = []
    unproven: list[ReapCandidate] = []
    protected: list[ReapCandidate] = []

    for entry in table:
        if entry.pid <= 1 or entry.pid in protected_pids:
            continue

        run_id = ""
        evidence = ""
        detail = ""

        env_run_id = env_index.get(entry.pid, "")
        if env_run_id and env_run_id in by_run:
            run_id, evidence = env_run_id, "env_run_id"
            detail = f"SPAWN_RUN_ID={env_run_id}"
        else:
            owner = pgid_owner.get(entry.pgid)
            if owner:
                run_id, evidence = owner, "worker_pgid"
                detail = f"pgid={entry.pgid} matches run worker_pgid"

        if not evidence:
            # Only surface processes that look run-adjacent; the whole machine is
            # not an interesting "unproven" list.
            if env_run_id:
                unproven.append(
                    ReapCandidate(
                        pid=entry.pid,
                        command=entry.command,
                        run_id=env_run_id,
                        detail="SPAWN_RUN_ID names a run that is not terminal",
                    )
                )
            continue

        candidate = ReapCandidate(
            pid=entry.pid,
            command=entry.command,
            run_id=run_id,
            evidence=evidence,
            detail=detail,
        )
        if _is_protected(entry.command):
            protected.append(candidate)
        else:
            doomed.append(candidate)

    return ReapPlan(
        should_run=True,
        doomed=tuple(doomed),
        unproven=tuple(unproven),
        protected=tuple(protected),
    )


def _signal_pid(pid: int, sig: int) -> str:
    """Send ``sig``; report what the OS said. Never raises."""
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return "already_gone"
    except PermissionError:
        return "permission_denied"
    except OSError as exc:
        return f"error:{exc.errno}"
    return "signalled"


def _pid_alive(pid: int) -> bool:
    from .control_plane import _pid_is_alive

    return _pid_is_alive(pid)


def execute_reap(
    plan: ReapPlan,
    grace: float | None = None,
    sleeper: Callable[[float], None] | None = None,
    alive_check: Callable[[int], bool] | None = None,
    signaller: Callable[[int, int], str] | None = None,
) -> dict[str, ReapReceipt]:
    """Escalate TERM -> grace -> KILL over the plan's doomed pids, receipting each step."""
    grace = grace_seconds() if grace is None else grace
    sleeper = time.sleep if sleeper is None else sleeper
    alive_check = _pid_alive if alive_check is None else alive_check
    signaller = _signal_pid if signaller is None else signaller

    receipts: dict[str, ReapReceipt] = {}

    def _receipt(run_id: str) -> ReapReceipt:
        return receipts.setdefault(run_id, ReapReceipt(run_id=run_id))

    if not plan.should_run:
        return receipts

    # Unproven survivors are reported in the plan (and so in `--dry-run`/`--json`),
    # but deliberately NOT written to a snapshot: by definition they name a run that
    # is still live, and a live run's record is not the place for our indecision.

    termed: list[tuple[ReapCandidate, dict[str, Any]]] = []
    for candidate in plan.doomed:
        row = candidate.row()
        row["term"] = signaller(candidate.pid, signal.SIGTERM)
        termed.append((candidate, row))

    # One shared grace window rather than per-pid: the processes were signalled
    # together, so they get to exit together.
    if termed and grace > 0:
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if not any(alive_check(candidate.pid) for candidate, _ in termed):
                break
            sleeper(min(0.1, max(deadline - time.monotonic(), 0.0)))

    for candidate, row in termed:
        if alive_check(candidate.pid):
            result = signaller(candidate.pid, signal.SIGKILL)
            row["kill"] = result
            # Judge the delivery, not a liveness re-probe. SIGKILL cannot be caught,
            # so once it lands the process is dead — but it stays visible to
            # `kill(pid, 0)` as a zombie until its parent reaps it, and an orphan's
            # parent is by definition gone. Re-checking liveness here would report a
            # successful kill as "survived". Only a signal we failed to DELIVER
            # leaves something actually running.
            if result == "signalled":
                row["outcome"] = "killed"
            elif result == "already_gone":
                row["outcome"] = "exited"
            else:
                row["outcome"] = "survived"
        else:
            row["outcome"] = "exited"
        _receipt(candidate.run_id).reaped.append(row)

    return receipts


def _record_receipts(receipts: Mapping[str, ReapReceipt]) -> None:
    """Append reap receipts to each run's control-plane snapshot.

    Re-reads before writing: the control-plane sync may have touched the snapshot
    since the plan was built. Losing a receipt is acceptable; clobbering a run's
    terminal state to save one is not.
    """
    from .control_plane import _read_json, _snapshot_path, _write_json

    for run_id, receipt in receipts.items():
        if not run_id or run_id == "unknown":
            continue
        path = _snapshot_path(run_id)
        current = _read_json(path)
        if not current:
            continue
        current.update(receipt.payload())
        try:
            _write_json(path, current)
        except OSError:
            pass


def _terminal_run_snapshots() -> list[dict[str, Any]]:
    """All known runs, straight from the snapshot dir.

    Deliberately not ``sync_state()``: that returns only active plus the dozen most
    recent runs, and a two-day-old corpse — precisely our target — is in neither.
    """
    from .control_plane import _load_existing_snapshots

    try:
        return list(_load_existing_snapshots().values())
    except OSError:
        return []


def reap_terminal_runs(
    dry_run: bool = False,
    env: Mapping[str, str] | None = None,
    runs: Iterable[Mapping[str, Any]] | None = None,
    table: Sequence[ProcessEntry] | None = None,
    env_index: Mapping[int, str] | None = None,
) -> ReapPlan:
    """Find and terminate survivors of terminal runs. Never raises.

    Returns the plan so callers can render it; receipts land on the runs' snapshots.
    """
    env = os.environ if env is None else env
    try:
        if not reaper_enabled(env):
            return ReapPlan(should_run=False, skip_reason="disabled")
        run_list = _terminal_run_snapshots() if runs is None else list(runs)
        if not run_list:
            return ReapPlan(should_run=True)
        proc_table = build_process_table() if table is None else table
        if not proc_table:
            return ReapPlan(should_run=False, skip_reason="no_process_table")
        index = build_env_index() if env_index is None else env_index
        plan = plan_reap(run_list, proc_table, env_index=index, env=env)
        if dry_run or not plan.should_run:
            return plan
        receipts = execute_reap(plan, grace=grace_seconds(env))
        _record_receipts(receipts)
        return plan
    except Exception:
        # A garbage collector may never take down the thing it is cleaning up after.
        return ReapPlan(should_run=False, skip_reason="error")


def sweep_quietly(env: Mapping[str, str] | None = None) -> None:
    """Opportunistic pre-flight sweep. Silent, best-effort, never raises."""
    reap_terminal_runs(env=env)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vibecrafted-reap",
        description="Terminate processes that outlived their run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the would-kill table with ownership evidence, signal nothing",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    plan = reap_terminal_runs(dry_run=args.dry_run)
    if args.json:
        print(
            json.dumps(
                {
                    "should_run": plan.should_run,
                    "skip_reason": plan.skip_reason,
                    "dry_run": args.dry_run,
                    "reaped": [c.row() for c in plan.doomed],
                    "unproven": [c.row() for c in plan.unproven],
                    "protected": [c.row() for c in plan.protected],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(plan.render())
    # Always 0: the reaper is maintenance, it never fails its caller.
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    raise SystemExit(main())
