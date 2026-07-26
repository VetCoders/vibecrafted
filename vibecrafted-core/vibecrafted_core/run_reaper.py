"""Garbage collector for processes that outlive their run.

The control plane already *knows* when a run is dead — ``_reconcile_dead_launcher``
settles it to ``gc``/``stalled`` and records ``pid_gone``. Nothing ever acted on
that knowledge, so a run could reach a terminal state while its monitors, watchers
and helper children kept burning cores for days. This module is the missing actor:
given the control plane's terminal runs, it finds surviving processes that provably
belong to them and takes them down, with a receipt for every decision.

**Ownership must be proven, never inferred.** The reaper runs inside a live
workspace full of processes it must not touch — vc-frame servers, MCP servers, the
operator's own shells and panes. PID, PGID, command text and a run id in ``ps``
output are all reusable or forgeable hints; none is authority by itself.

A process is signalable only when all four witnesses agree:

``run birth identity``
    The terminal snapshot carries the immutable ``session_id`` created at launch.

``environment lineage``
    The process exposes both that ``session_id`` and the matching run id.

``process-group lineage``
    Its current PGID matches the run's launch-recorded worker PGID.

``process birth token``
    The kernel start token captured in the plan is re-read immediately before
    TERM and again before KILL. Missing or changed identity fails closed.

Anything missing one witness is reported as ``unproven`` and left running. A
survivor we failed to prove is a survivor we keep; killing the wrong process in a
live workspace costs far more than missing one. The opportunistic launch-time
sweep is audit-only; signalling is an explicit operator action.

**Three ownership buckets** (run-level inventory + process verdicts):

``provable``
    Terminal run carries both a launch ``session_id`` and a recorded
    ``worker_pgid``/``worker_pid``. Kill candidates only come from this bucket,
    and still need matching process environment plus a revalidated birth token.

``legacy``
    Historical terminal run without a recorded pgid, explicitly marked by the
    one-shot migration (``reaper_ownership: legacy``). The reaper never treats
    these as kill sources — even if a lingering process still carries their
    ``SPAWN_RUN_ID``.

``undecidable``
    Terminal run with neither a recorded pgid nor a legacy mark, and no positive
    env proof on a live process. Fail-closed: never killed.

Migration lives at ``quarantine_legacy_runs`` (doctor: ``--quarantine-legacy-runs``):
marks terminal-no-pgid as legacy; best-effort recovers pgid for *live* runs only
when ``SPAWN_RUN_ID`` is positively visible in ``ps``.

**We never take ourselves down.** The terminal-seam caller's own pid, ancestors,
and every process in its current process group are excluded before anything is
signalled. This protects operator/control-plane siblings sharing a terminal group.

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
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "OWNERSHIP_LEGACY",
    "OWNERSHIP_PROVABLE",
    "OWNERSHIP_UNDECIDABLE",
    "PROTECTED_COMMAND_PATTERNS",
    "REAPER_OWNERSHIP_KEY",
    "OwnershipBuckets",
    "ProcessEntry",
    "ProcessEnvIdentity",
    "QuarantineResult",
    "ReapCandidate",
    "ReapPlan",
    "ReapReceipt",
    "RunBirthIdentity",
    "build_env_index",
    "build_process_table",
    "classify_run_ownership",
    "main",
    "plan_json_payload",
    "plan_reap",
    "quarantine_legacy_runs",
    "read_process_start_token",
    "reap_terminal_runs",
    "recorded_run_identity",
    "recorded_worker_pgid",
    "verify_run_process",
]

_TRUTHY_OFF = {"0", "false", "no", "off"}

REAPER_ENABLED_ENV = "VIBECRAFTED_REAPER"
REAPER_GRACE_ENV = "VIBECRAFTED_REAPER_GRACE_SECONDS"
DEFAULT_GRACE_SECONDS = 5.0

#: Field written by the one-shot legacy quarantine migration.
REAPER_OWNERSHIP_KEY = "reaper_ownership"
OWNERSHIP_LEGACY = "legacy"
OWNERSHIP_PROVABLE = "provable"
OWNERSHIP_UNDECIDABLE = "undecidable"

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
    "vibecrafted-server",
    "control-core",
    "vibecrafted-reap",
    "vibecrafted procs",
    "sshd",
    "login",
)

_ENV_RUN_ID_PATTERNS = (
    re.compile(r"(?:^|\s)SPAWN_RUN_ID=(\S+)"),
    re.compile(r"(?:^|\s)VIBECRAFTED_RUN_ID=(\S+)"),
)
_ENV_SESSION_ID_PATTERN = re.compile(r"(?:^|\s)VIBECRAFTED_SESSION_ID=(\S+)")
_MISSING_BIRTH_IDS = {"", "none", "null", "pending", "pending-unset", "unknown"}


@dataclass(frozen=True)
class ProcessEnvIdentity:
    """Immutable run lineage exposed by a process environment."""

    run_id: str = ""
    session_id: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.run_id and self.session_id)


@dataclass(frozen=True)
class RunBirthIdentity:
    """Launch-recorded identity required before a run can own a process group."""

    run_id: str
    session_id: str
    pgid: int


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


def read_process_start_token(pid: int) -> str | None:
    """Return an OS birth token for ``pid`` or ``None`` when it is unavailable.

    A command hash is deliberately not a fallback: a recycled PID can execute
    the same command. Linux exposes the monotonic birth tick in ``/proc``.
    Darwin's libproc exposes the kernel ``timeval`` with microsecond precision.
    Unsupported or unreadable platforms fail closed.
    """
    if pid <= 1:
        return None
    try:
        proc_stat = f"/proc/{pid}/stat"
        if os.path.isfile(proc_stat):
            with open(proc_stat, encoding="utf-8", errors="replace") as handle:
                raw = handle.read()
            closing = raw.rfind(")")
            if closing < 0:
                return None
            fields = raw[closing + 2 :].split()
            if len(fields) < 20:
                return None
            return f"proc:{fields[19]}"
    except (OSError, ValueError, IndexError):
        return None

    if sys.platform != "darwin":
        return None

    try:
        import ctypes
        import ctypes.util

        class _ProcBsdInfo(ctypes.Structure):
            _fields_ = [
                ("pbi_flags", ctypes.c_uint32),
                ("pbi_status", ctypes.c_uint32),
                ("pbi_xstatus", ctypes.c_uint32),
                ("pbi_pid", ctypes.c_uint32),
                ("pbi_ppid", ctypes.c_uint32),
                ("pbi_uid", ctypes.c_uint32),
                ("pbi_gid", ctypes.c_uint32),
                ("pbi_ruid", ctypes.c_uint32),
                ("pbi_rgid", ctypes.c_uint32),
                ("pbi_svuid", ctypes.c_uint32),
                ("pbi_svgid", ctypes.c_uint32),
                ("rfu_1", ctypes.c_uint32),
                ("pbi_comm", ctypes.c_char * 16),
                ("pbi_name", ctypes.c_char * 32),
                ("pbi_nfiles", ctypes.c_uint32),
                ("pbi_pgid", ctypes.c_uint32),
                ("pbi_pjobc", ctypes.c_uint32),
                ("e_tdev", ctypes.c_uint32),
                ("e_tpgid", ctypes.c_uint32),
                ("pbi_nice", ctypes.c_int32),
                ("pbi_start_tvsec", ctypes.c_uint64),
                ("pbi_start_tvusec", ctypes.c_uint64),
            ]

        library_path = ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib"
        libproc = ctypes.CDLL(library_path, use_errno=True)
        proc_pidinfo = libproc.proc_pidinfo
        proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        proc_pidinfo.restype = ctypes.c_int
        info = _ProcBsdInfo()
        size = ctypes.sizeof(info)
        written = proc_pidinfo(pid, 3, 0, ctypes.byref(info), size)
        if written != size or info.pbi_pid != pid or info.pbi_start_tvsec <= 0:
            return None
        return f"darwin:{info.pbi_start_tvsec}:{info.pbi_start_tvusec}"
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def recorded_worker_pgid(run: Mapping[str, Any]) -> int | None:
    """Return the run's recorded process-group hint.

    This is never sufficient ownership proof by itself. pgid 0/1 would match
    half the machine, so only a real group (>1) is returned.
    """
    from .control_plane import _coerce_int

    for key in ("worker_pgid", "worker_pid"):
        pgid = _coerce_int(run.get(key))
        if pgid is not None and pgid > 1:
            return pgid
    return None


def recorded_run_identity(run: Mapping[str, Any]) -> RunBirthIdentity | None:
    """Return complete launch identity or ``None`` for stale/legacy metadata."""
    run_id = str(run.get("run_id") or "").strip()
    session_id = str(
        run.get("runtime_session_id") or run.get("session_id") or ""
    ).strip()
    pgid = recorded_worker_pgid(run)
    if (
        not run_id
        or session_id.lower() in _MISSING_BIRTH_IDS
        or pgid is None
    ):
        return None
    return RunBirthIdentity(run_id=run_id, session_id=session_id, pgid=pgid)


def classify_run_ownership(run: Mapping[str, Any]) -> str:
    """Classify a run into provable / legacy / undecidable.

    ``legacy`` is an explicit field written by the quarantine migration — it
    wins over a spurious recorded pgid so a marked historical run can never be
    treated as a kill source.
    """
    if str(run.get(REAPER_OWNERSHIP_KEY) or "").strip() == OWNERSHIP_LEGACY:
        return OWNERSHIP_LEGACY
    if recorded_run_identity(run) is not None:
        return OWNERSHIP_PROVABLE
    return OWNERSHIP_UNDECIDABLE


@dataclass(frozen=True)
class OwnershipBuckets:
    """Terminal-run inventory for the reaper report: three exclusive buckets."""

    provable: tuple[str, ...] = ()
    legacy: tuple[str, ...] = ()
    undecidable: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, list[str]]:
        return {
            OWNERSHIP_PROVABLE: list(self.provable),
            OWNERSHIP_LEGACY: list(self.legacy),
            OWNERSHIP_UNDECIDABLE: list(self.undecidable),
        }


@dataclass
class QuarantineResult:
    """Outcome of the one-shot ``reaper_ownership: legacy`` migration."""

    marked_legacy: list[str] = field(default_factory=list)
    recovered_pgid: list[dict[str, Any]] = field(default_factory=list)
    skipped_live: list[str] = field(default_factory=list)
    skipped_has_pgid: list[str] = field(default_factory=list)
    already_legacy: list[str] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    changed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "marked_legacy": list(self.marked_legacy),
            "recovered_pgid": list(self.recovered_pgid),
            "skipped_live": list(self.skipped_live),
            "skipped_has_pgid": list(self.skipped_has_pgid),
            "already_legacy": list(self.already_legacy),
            "parse_errors": list(self.parse_errors),
            "changed": self.changed,
        }


@dataclass(frozen=True)
class ProcessEntry:
    """One row of the process table."""

    pid: int
    ppid: int
    pgid: int
    command: str
    start_token: str = ""


@dataclass(frozen=True)
class ReapCandidate:
    """A surviving process and what we could (or could not) prove about it."""

    pid: int
    command: str
    run_id: str = ""
    #: "env_run_id" | "worker_pgid" — empty when unproven.
    evidence: str = ""
    detail: str = ""
    session_id: str = ""
    start_token: str = ""

    @property
    def proven(self) -> bool:
        return bool(
            self.evidence and self.run_id and self.session_id and self.start_token
        )

    def row(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "run_id": self.run_id,
            "evidence": self.evidence or "unproven",
            "detail": self.detail,
            "session_id": self.session_id,
            "start_token": self.start_token,
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
    #: Processes tied to a ``reaper_ownership: legacy`` run — never killed.
    legacy: tuple[ReapCandidate, ...] = ()
    #: Terminal-run inventory: provable / legacy / undecidable.
    ownership: OwnershipBuckets = field(default_factory=OwnershipBuckets)

    def render(self) -> str:
        """The ``--dry-run`` table: every pid with the evidence behind its verdict."""
        if not self.should_run:
            return f"reaper: skipped ({self.skip_reason})"
        lines: list[str] = []
        for label, rows in (
            ("REAP", self.doomed),
            ("KEEP/legacy", self.legacy),
            ("KEEP/unproven", self.unproven),
            ("KEEP/protected", self.protected),
        ):
            for candidate in rows:
                lines.append(
                    f"{label:<15} pid={candidate.pid:<8} run={candidate.run_id or '-':<28} "
                    f"evidence={candidate.evidence or 'unproven':<12} {candidate.command[:80]}"
                )
        if not lines:
            buckets = self.ownership
            if buckets.legacy or buckets.undecidable or buckets.provable:
                return (
                    "reaper: no survivors of terminal runs "
                    f"(ownership provable={len(buckets.provable)} "
                    f"legacy={len(buckets.legacy)} "
                    f"undecidable={len(buckets.undecidable)})"
                )
            return "reaper: no survivors of terminal runs"
        header = (
            f"reaper: {len(self.doomed)} to reap, {len(self.legacy)} legacy, "
            f"{len(self.unproven)} unproven, {len(self.protected)} protected"
        )
        return "\n".join([header, *lines])


def plan_json_payload(plan: ReapPlan, dry_run: bool = False) -> dict[str, Any]:
    """Machine-readable reap plan: explicit ownership buckets + process rows."""
    return {
        "should_run": plan.should_run,
        "skip_reason": plan.skip_reason,
        "dry_run": dry_run,
        "ownership": plan.ownership.as_dict(),
        "reaped": [c.row() for c in plan.doomed],
        "legacy": [c.row() for c in plan.legacy],
        "unproven": [c.row() for c in plan.unproven],
        "protected": [c.row() for c in plan.protected],
    }


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
    return subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def build_process_table(
    runner: Callable[..., Any] | None = None,
    start_reader: Callable[[int], str | None] | None = None,
) -> tuple[ProcessEntry, ...]:
    """Snapshot the process table. Empty on any failure — never raises."""
    runner = _default_runner if runner is None else runner
    start_reader = read_process_start_token if start_reader is None else start_reader
    try:
        proc = runner(["ps", "-A", "-o", "pid=,ppid=,pgid=,command="])
    except Exception:  # noqa: BLE001
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
        try:
            start_token = str(start_reader(pid) or "")
        except Exception:  # noqa: BLE001
            start_token = ""
        entries.append(
            ProcessEntry(
                pid=pid,
                ppid=ppid,
                pgid=pgid,
                command=parts[3],
                start_token=start_token,
            )
        )
    return tuple(entries)


def _single_env_value(line: str, patterns: Sequence[re.Pattern[str]]) -> str:
    values = {
        match.group(1)
        for pattern in patterns
        for match in pattern.finditer(line)
        if match.group(1)
    }
    return next(iter(values)) if len(values) == 1 else ""


def build_env_index(
    runner: Callable[..., Any] | None = None,
) -> dict[int, ProcessEnvIdentity]:
    """Map pid -> run birth identity for processes that expose both fields.

    One ``ps axeww`` for the whole machine rather than one probe per pid: the sweep
    runs on every spawn, so hundreds of forks would make it too expensive to be
    opportunistic. ``ww`` disables column truncation, without which a long
    environment is clipped and the variable silently disappears.

    Best-effort by design: macOS refuses the environment of SIP-protected/hardened
    binaries and lists only argv for them. A missing field means "could not prove",
    never "not owned". Even a complete pair is still only one witness: plan_reap
    additionally requires the launch-recorded PGID and a kernel birth token.
    """
    runner = _default_runner if runner is None else runner
    try:
        proc = runner(["ps", "axeww"])
    except Exception:  # noqa: BLE001
        return {}
    if getattr(proc, "returncode", 1) != 0:
        return {}
    index: dict[int, ProcessEnvIdentity] = {}
    for line in str(getattr(proc, "stdout", "") or "").splitlines():
        head = line.split(maxsplit=1)
        if not head or not head[0].isdigit():
            continue
        run_id = _single_env_value(line, _ENV_RUN_ID_PATTERNS)
        session_id = _single_env_value(line, (_ENV_SESSION_ID_PATTERN,))
        if run_id or session_id:
            index[int(head[0])] = ProcessEnvIdentity(
                run_id=run_id,
                session_id=session_id,
            )
    return index


def _coerce_env_identity(value: Any) -> ProcessEnvIdentity:
    if isinstance(value, ProcessEnvIdentity):
        return value
    if isinstance(value, Mapping):
        return ProcessEnvIdentity(
            run_id=str(value.get("run_id") or "").strip(),
            session_id=str(value.get("session_id") or "").strip(),
        )
    # Compatibility for old callers: a bare run id remains visible for
    # diagnostics but is intentionally incomplete and can never authorize.
    return ProcessEnvIdentity(run_id=str(value or "").strip())


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


def verify_run_process(
    run: Mapping[str, Any],
    target_pid: int,
    table: Sequence[ProcessEntry],
    env_index: Mapping[int, Any],
    *,
    self_pid: int | None = None,
) -> tuple[ProcessEntry | None, str]:
    """Verify one explicit signal target against launch identity.

    Unlike the terminal reaper this helper may verify a live run, but it never
    authorizes a group signal. The caller gets one exact PID plus its birth
    token and must re-read that token immediately before signalling.
    """
    run_id = str(run.get("run_id") or "").strip()
    session_id = str(
        run.get("runtime_session_id") or run.get("session_id") or ""
    ).strip()
    if not run_id or session_id.lower() in _MISSING_BIRTH_IDS:
        return None, "missing_run_birth_identity"

    by_pid = {entry.pid: entry for entry in table}
    entry = by_pid.get(target_pid)
    if entry is None:
        return None, "pid_not_in_process_table"
    if not entry.start_token:
        return None, "process_birth_unavailable"

    identity = _coerce_env_identity(env_index.get(target_pid))
    if identity.run_id != run_id or identity.session_id != session_id:
        return None, "environment_birth_mismatch"

    recorded_pgid = recorded_worker_pgid(run)
    if recorded_pgid is None:
        return None, "missing_recorded_pgid"
    if entry.pgid != recorded_pgid:
        return None, "recorded_pgid_mismatch"

    self_pid = os.getpid() if self_pid is None else self_pid
    protected_pids = _ancestors(self_pid, by_pid)
    self_entry = by_pid.get(self_pid)
    if self_entry is not None and self_entry.pgid > 1:
        protected_pids.update(
            row.pid for row in table if row.pgid == self_entry.pgid
        )
    if entry.pid in protected_pids:
        return None, "operator_lineage_protected"
    if _is_protected(entry.command):
        return None, "infrastructure_command_protected"
    return entry, ""


def _terminal_run_index(
    runs: Iterable[Mapping[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[int, RunBirthIdentity],
    dict[int, str],
    set[str],
    OwnershipBuckets,
]:
    """Map terminal runs by id, pgid ownership, legacy set, and ownership inventory.

    Legacy runs are inventoried and tracked in ``legacy_pgid_owner`` for KEEP
    reporting only — never in ``pgid_owner`` (kill source). A process that still
    carries their ``SPAWN_RUN_ID`` or matches a legacy-recorded pgid is reported
    in the legacy process bucket instead of doomed.
    """
    from .control_plane import _run_is_terminal

    by_run: dict[str, dict[str, Any]] = {}
    pgid_owner: dict[int, RunBirthIdentity] = {}
    legacy_pgid_owner: dict[int, str] = {}
    legacy_runs: set[str] = set()
    provable: list[str] = []
    legacy_ids: list[str] = []
    undecidable: list[str] = []

    for run in runs:
        run_id = str(run.get("run_id") or "").strip()
        if not run_id or not _run_is_terminal(dict(run)):
            continue
        payload = dict(run)
        by_run[run_id] = payload
        bucket = classify_run_ownership(payload)
        if bucket == OWNERSHIP_LEGACY:
            legacy_runs.add(run_id)
            legacy_ids.append(run_id)
            pgid = recorded_worker_pgid(payload)
            if pgid is not None:
                legacy_pgid_owner.setdefault(pgid, run_id)
            continue
        if bucket == OWNERSHIP_PROVABLE:
            provable.append(run_id)
            identity = recorded_run_identity(payload)
            if identity is not None:
                pgid_owner.setdefault(identity.pgid, identity)
            continue
        undecidable.append(run_id)

    ownership = OwnershipBuckets(
        provable=tuple(provable),
        legacy=tuple(legacy_ids),
        undecidable=tuple(undecidable),
    )
    return by_run, pgid_owner, legacy_pgid_owner, legacy_runs, ownership


def plan_reap(
    runs: Iterable[Mapping[str, Any]],
    table: Sequence[ProcessEntry],
    env_index: Mapping[int, Any] | None = None,
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

    by_run, pgid_owner, legacy_pgid_owner, legacy_runs, ownership = _terminal_run_index(
        runs
    )
    if not by_run:
        return ReapPlan(should_run=True, ownership=ownership)

    env_index = {} if env_index is None else env_index
    self_pid = os.getpid() if self_pid is None else self_pid
    by_pid = {entry.pid: entry for entry in table}
    # Our own lineage and process-group siblings. A terminal invocation may run
    # inside the same terminal group as the operator/control plane.
    protected_pids = _ancestors(self_pid, by_pid)
    self_entry = by_pid.get(self_pid)
    if self_entry is not None and self_entry.pgid > 1:
        protected_pids.update(
            entry.pid for entry in table if entry.pgid == self_entry.pgid
        )
    current_identity = ProcessEnvIdentity(
        run_id=str(env.get("VIBECRAFTED_RUN_ID") or "").strip(),
        session_id=str(env.get("VIBECRAFTED_SESSION_ID") or "").strip(),
    )

    doomed: list[ReapCandidate] = []
    unproven: list[ReapCandidate] = []
    protected: list[ReapCandidate] = []
    legacy_candidates: list[ReapCandidate] = []

    for entry in table:
        if entry.pid <= 1:
            continue

        proc_identity = _coerce_env_identity(env_index.get(entry.pid))
        legacy_owner = legacy_pgid_owner.get(entry.pgid)
        if legacy_owner or proc_identity.run_id in legacy_runs:
            run_id = legacy_owner or proc_identity.run_id
            legacy_candidates.append(
                ReapCandidate(
                    pid=entry.pid,
                    command=entry.command,
                    run_id=run_id,
                    evidence=OWNERSHIP_LEGACY,
                    detail=f"reaper_ownership=legacy pgid={entry.pgid}",
                    session_id=proc_identity.session_id,
                    start_token=entry.start_token,
                )
            )
            continue

        owner = pgid_owner.get(entry.pgid)
        exact_identity = bool(
            owner is not None
            and proc_identity.complete
            and proc_identity.run_id == owner.run_id
            and proc_identity.session_id == owner.session_id
        )

        if owner is None and not proc_identity.run_id:
            # The whole machine is not an interesting unproven list.
            continue

        run_id = owner.run_id if owner is not None else proc_identity.run_id
        session_id = (
            owner.session_id if owner is not None else proc_identity.session_id
        )
        evidence = "run_birth_identity" if exact_identity else ""
        if exact_identity and entry.start_token:
            detail = (
                f"run_id+session_id+pgid={entry.pgid} match; "
                f"birth={entry.start_token}"
            )
        elif exact_identity:
            detail = "process birth token unavailable"
        elif owner is not None:
            detail = (
                "stale or reused pgid identity: "
                "run_id/session_id environment does not match launch record"
            )
        elif proc_identity.run_id in by_run:
            detail = "run birth environment matched but recorded pgid did not"
        else:
            detail = "run birth environment names a non-terminal or unknown run"

        candidate = ReapCandidate(
            pid=entry.pid,
            command=entry.command,
            run_id=run_id,
            evidence=evidence,
            detail=detail,
            session_id=session_id,
            start_token=entry.start_token,
        )
        is_current_run = bool(
            current_identity.complete and proc_identity == current_identity
        )
        if entry.pid in protected_pids or is_current_run or _is_protected(entry.command):
            protected.append(candidate)
        elif not candidate.proven:
            unproven.append(candidate)
        else:
            doomed.append(candidate)

    return ReapPlan(
        should_run=True,
        doomed=tuple(doomed),
        unproven=tuple(unproven),
        protected=tuple(protected),
        legacy=tuple(legacy_candidates),
        ownership=ownership,
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
    birth_reader: Callable[[int], str | None] | None = None,
) -> dict[str, ReapReceipt]:
    """Escalate TERM -> grace -> KILL after identity revalidation at each edge."""
    grace = grace_seconds() if grace is None else grace
    sleeper = time.sleep if sleeper is None else sleeper
    alive_check = _pid_alive if alive_check is None else alive_check
    signaller = _signal_pid if signaller is None else signaller
    birth_reader = read_process_start_token if birth_reader is None else birth_reader

    receipts: dict[str, ReapReceipt] = {}

    def _receipt(run_id: str) -> ReapReceipt:
        return receipts.setdefault(run_id, ReapReceipt(run_id=run_id))

    def _safe_birth(pid: int) -> str:
        try:
            return str(birth_reader(pid) or "")
        except Exception:  # noqa: BLE001
            return ""

    if not plan.should_run:
        return receipts

    # Unproven survivors are reported in the plan (and so in `--dry-run`/`--json`),
    # but deliberately NOT written to a snapshot: by definition they name a run that
    # is still live, and a live run's record is not the place for our indecision.

    termed: list[tuple[ReapCandidate, dict[str, Any]]] = []
    for candidate in plan.doomed:
        row = candidate.row()
        live_birth = _safe_birth(candidate.pid)
        row["birth_before_term"] = live_birth or "unavailable"
        if not live_birth or live_birth != candidate.start_token:
            row["term"] = "not_signalled"
            row["outcome"] = "identity_changed"
            _receipt(candidate.run_id).reaped.append(row)
            continue
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
            live_birth = _safe_birth(candidate.pid)
            row["birth_before_kill"] = live_birth or "unavailable"
            if not live_birth or live_birth != candidate.start_token:
                row["kill"] = "not_signalled"
                row["outcome"] = "identity_changed"
                _receipt(candidate.run_id).reaped.append(row)
                continue
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


def quarantine_legacy_runs(
    runs: Iterable[Mapping[str, Any]] | None = None,
    table: Sequence[ProcessEntry] | None = None,
    env_index: Mapping[int, Any] | None = None,
    *,
    dry_run: bool = False,
    writer: Callable[[str, dict[str, Any]], None] | None = None,
) -> QuarantineResult:
    """Mark terminal runs without complete birth identity as legacy.

    Rules (fail-closed, no fiction):

    * Terminal + missing session id or missing valid pgid →
      ``reaper_ownership: legacy``.
    * Terminal + complete launch identity → untouched (already provable).
    * Already ``reaper_ownership: legacy`` → no write (idempotent).
    * Live (non-terminal) → never marked legacy; best-effort recover
      ``worker_pgid`` from the process table only when run id and launch session
      id are both visible and match. A bare pgid or run id is not enough.

    Historical JSON variants that break parsing are listed in ``parse_errors``
    and skipped rather than crashing the migration.
    """
    from .control_plane import (
        _run_is_terminal,
        _snapshot_path,
        _write_json,
    )

    result = QuarantineResult()

    if runs is None:
        try:
            run_list: list[dict[str, Any]] = _terminal_run_snapshots()
        except Exception as exc:  # pragma: no cover - defensive  # noqa: BLE001
            result.parse_errors.append(f"load_snapshots:{exc}")
            return result
    else:
        run_list = []
        for raw in runs:
            try:
                run_list.append(dict(raw))
            except Exception as exc:  # noqa: BLE001
                result.parse_errors.append(f"coerce:{exc}")

    proc_table = () if table is None else table
    # When the caller did not inject a table, only build one if we need live recovery.
    need_recovery = any(
        (not _run_is_terminal(r)) and recorded_worker_pgid(r) is None for r in run_list
    )
    if table is None and need_recovery:
        proc_table = build_process_table()
    index: dict[int, Any] = {} if env_index is None else dict(env_index)
    if env_index is None and need_recovery:
        index = build_env_index()

    by_pid = {entry.pid: entry for entry in proc_table}

    def _default_writer(run_id: str, payload: dict[str, Any]) -> None:
        _write_json(_snapshot_path(run_id), payload)

    persist = writer if writer is not None else _default_writer

    for run in run_list:
        try:
            run_id = str(run.get("run_id") or "").strip()
            if not run_id:
                result.parse_errors.append("missing_run_id")
                continue
            payload = dict(run)

            if not _run_is_terminal(payload):
                # Live run: never legacy. Best-effort pgid recovery with env proof only.
                if recorded_worker_pgid(payload) is not None:
                    result.skipped_live.append(run_id)
                    continue
                recovered: int | None = None
                run_session_id = str(
                    payload.get("runtime_session_id")
                    or payload.get("session_id")
                    or ""
                ).strip()
                for pid, raw_identity in index.items():
                    identity = _coerce_env_identity(raw_identity)
                    if (
                        identity.run_id != run_id
                        or not run_session_id
                        or identity.session_id != run_session_id
                    ):
                        continue
                    entry = by_pid.get(pid)
                    if entry is None:
                        continue
                    if entry.pgid > 1:
                        recovered = entry.pgid
                        break
                if recovered is None:
                    result.skipped_live.append(run_id)
                    continue
                payload["worker_pgid"] = recovered
                if not dry_run:
                    persist(run_id, payload)
                result.recovered_pgid.append(
                    {"run_id": run_id, "worker_pgid": recovered}
                )
                result.changed += 1
                continue

            # Terminal path.
            if str(payload.get(REAPER_OWNERSHIP_KEY) or "").strip() == OWNERSHIP_LEGACY:
                result.already_legacy.append(run_id)
                continue
            if recorded_run_identity(payload) is not None:
                result.skipped_has_pgid.append(run_id)
                continue

            payload[REAPER_OWNERSHIP_KEY] = OWNERSHIP_LEGACY
            if not dry_run:
                persist(run_id, payload)
            result.marked_legacy.append(run_id)
            result.changed += 1
        except Exception as exc:  # noqa: BLE001
            # Quarantine variants, never crash the doctor path.
            rid = str(run.get("run_id") or "?")
            result.parse_errors.append(f"{rid}:{type(exc).__name__}:{exc}")

    return result


def reap_terminal_runs(
    dry_run: bool = False,
    env: Mapping[str, str] | None = None,
    runs: Iterable[Mapping[str, Any]] | None = None,
    table: Sequence[ProcessEntry] | None = None,
    env_index: Mapping[int, Any] | None = None,
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
    except Exception:  # noqa: BLE001
        # A garbage collector may never take down the thing it is cleaning up after.
        return ReapPlan(should_run=False, skip_reason="error")


def sweep_quietly(env: Mapping[str, str] | None = None) -> None:
    """Audit opportunistically at pre-flight; never signal from an implicit seam."""
    reap_terminal_runs(dry_run=True, env=env)


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
                plan_json_payload(plan, dry_run=args.dry_run),
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
