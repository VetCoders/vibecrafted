"""Durable settlement history and best-effort vc-frame publication.

The per-run snapshot is the authority.  Every accepted settlement revision
advances an append-only ledger embedded in that snapshot before the snapshot is
published.  The global document is a deterministic projection across active and
archived snapshots; Guardian only republishes that projection.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import json
import logging
import os
import shutil
import stat
import subprocess
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime_paths import vibecrafted_home

RUN_HISTORY_SCHEMA = "vibecrafted.settlement-run-history.v1"
SETTLEMENT_HISTORY_SCHEMA = "vibecrafted.settlement-history.v1"
SETTLEMENT_HISTORY_GENERATION_SCHEMA = "vibecrafted.settlement-history-generation.v1"
DELIVERY_OUTBOX_SCHEMA = "vibecrafted.settlement-history-delivery.v1"
SETTLEMENT_COUNTS_PIPE = "vc_settlement_counts"
SETTLEMENT_REPLAY_INTERVAL_SECONDS = 5.0
MAX_U64 = (1 << 64) - 1
_TUI_KEYS = ("f", "x", "n")
LOGGER = logging.getLogger(__name__)


class SettlementHistoryError(RuntimeError):
    """A persisted settlement-history invariant was violated."""


@dataclass(frozen=True)
class SettlementCounts:
    f: int = 0
    x: int = 0
    n: int = 0

    def __post_init__(self) -> None:
        values = (self.f, self.x, self.n)
        if any(type(value) is not int or not 0 <= value <= MAX_U64 for value in values):
            raise SettlementHistoryError("settlement counts exceed the u64 contract")
        if sum(values) > MAX_U64:
            raise SettlementHistoryError("settlement counts total exceeds u64")

    @property
    def total(self) -> int:
        return self.f + self.x + self.n

    def increment(self, tui: str) -> SettlementCounts:
        if tui not in _TUI_KEYS:
            raise SettlementHistoryError(f"invalid settlement tui {tui!r}")
        return SettlementCounts(
            f=self.f + (tui == "f"),
            x=self.x + (tui == "x"),
            n=self.n + (tui == "n"),
        )

    def to_payload(self) -> dict[str, int]:
        return {"f": self.f, "x": self.x, "n": self.n, "total": self.total}

    @classmethod
    def from_payload(cls, payload: object) -> SettlementCounts:
        if not isinstance(payload, Mapping) or set(payload) != {
            "f",
            "x",
            "n",
            "total",
        }:
            raise SettlementHistoryError("settlement counts shape is invalid")
        values = {key: payload.get(key) for key in ("f", "x", "n", "total")}
        if any(
            type(value) is not int or not 0 <= value <= MAX_U64
            for value in values.values()
        ):
            raise SettlementHistoryError("settlement counts must be u64 integers")
        counts = cls(f=values["f"], x=values["x"], n=values["n"])
        if values["total"] != counts.total:
            raise SettlementHistoryError("settlement counts total is invalid")
        return counts


@dataclass(frozen=True)
class RunSettlementHistory:
    historical_transitions: SettlementCounts
    latest_revision: int
    latest_tui: str
    latest_digest: str
    gaps: int
    complete_from: int | None

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": RUN_HISTORY_SCHEMA,
            "historical_transitions": self.historical_transitions.to_payload(),
            "latest": {
                "revision": self.latest_revision,
                "tui": self.latest_tui,
                "digest": self.latest_digest,
            },
            "gaps": self.gaps,
            "complete_from": self.complete_from,
        }

    @classmethod
    def from_payload(cls, payload: object) -> RunSettlementHistory:
        if not isinstance(payload, Mapping) or set(payload) != {
            "schema",
            "historical_transitions",
            "latest",
            "gaps",
            "complete_from",
        }:
            raise SettlementHistoryError("run settlement history shape is invalid")
        if payload.get("schema") != RUN_HISTORY_SCHEMA:
            raise SettlementHistoryError("run settlement history schema is invalid")
        latest = payload.get("latest")
        if not isinstance(latest, Mapping) or set(latest) != {
            "revision",
            "tui",
            "digest",
        }:
            raise SettlementHistoryError("run settlement history latest is invalid")
        revision = latest.get("revision")
        tui = latest.get("tui")
        digest = latest.get("digest")
        gaps = payload.get("gaps")
        complete_from = payload.get("complete_from")
        if type(revision) is not int or not 0 < revision <= MAX_U64:
            raise SettlementHistoryError(
                "latest settlement revision must be a positive u64"
            )
        if tui not in _TUI_KEYS:
            raise SettlementHistoryError("latest settlement tui is invalid")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise SettlementHistoryError("latest settlement digest is invalid")
        if type(gaps) is not int or not 0 <= gaps <= MAX_U64:
            raise SettlementHistoryError("run settlement gaps must be a u64")
        if complete_from is not None and (
            type(complete_from) is not int or not 0 < complete_from <= MAX_U64
        ):
            raise SettlementHistoryError("run settlement complete_from is invalid")
        counts = SettlementCounts.from_payload(payload.get("historical_transitions"))
        if counts.total <= 0:
            raise SettlementHistoryError("run settlement history cannot be empty")
        if gaps and complete_from is not None:
            raise SettlementHistoryError(
                "incomplete run history cannot claim completeness"
            )
        if not gaps and complete_from != 1:
            raise SettlementHistoryError(
                "complete run history must start at transition 1"
            )
        return cls(
            historical_transitions=counts,
            latest_revision=revision,
            latest_tui=tui,
            latest_digest=digest,
            gaps=gaps,
            complete_from=complete_from,
        )


@dataclass(frozen=True)
class SettlementHistorySnapshot:
    generation: str
    sequence: int
    historical_transitions: SettlementCounts
    latest_by_run: SettlementCounts
    gaps: int
    complete_from: int | None

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": SETTLEMENT_HISTORY_SCHEMA,
            "generation": self.generation,
            "sequence": self.sequence,
            "historical_transitions": self.historical_transitions.to_payload(),
            "latest_by_run": self.latest_by_run.to_payload(),
            "gaps": self.gaps,
            "complete_from": self.complete_from,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_payload(cls, payload: object) -> SettlementHistorySnapshot:
        if not isinstance(payload, Mapping) or set(payload) != {
            "schema",
            "generation",
            "sequence",
            "historical_transitions",
            "latest_by_run",
            "gaps",
            "complete_from",
        }:
            raise SettlementHistoryError("settlement history document shape is invalid")
        if payload.get("schema") != SETTLEMENT_HISTORY_SCHEMA:
            raise SettlementHistoryError(
                "settlement history document schema is invalid"
            )
        generation = payload.get("generation")
        if not isinstance(generation, str):
            raise SettlementHistoryError("settlement history generation is invalid")
        try:
            canonical_generation = str(uuid.UUID(generation))
        except ValueError as exc:
            raise SettlementHistoryError(
                "settlement history generation is invalid"
            ) from exc
        if canonical_generation != generation:
            raise SettlementHistoryError(
                "settlement history generation is not canonical"
            )
        sequence = payload.get("sequence")
        gaps = payload.get("gaps")
        complete_from = payload.get("complete_from")
        if type(sequence) is not int or not 0 <= sequence <= MAX_U64:
            raise SettlementHistoryError("settlement history sequence is invalid")
        if type(gaps) is not int or not 0 <= gaps <= MAX_U64:
            raise SettlementHistoryError("settlement history gaps are invalid")
        if complete_from is not None and (
            type(complete_from) is not int or not 0 < complete_from <= MAX_U64
        ):
            raise SettlementHistoryError("settlement history complete_from is invalid")
        historical = SettlementCounts.from_payload(
            payload.get("historical_transitions")
        )
        latest = SettlementCounts.from_payload(payload.get("latest_by_run"))
        if historical.total != sequence:
            raise SettlementHistoryError("sequence must equal known transition count")
        if any(
            getattr(latest, bucket) > getattr(historical, bucket)
            for bucket in _TUI_KEYS
        ):
            raise SettlementHistoryError(
                "latest run bucket exceeds its known transitions"
            )
        if gaps and complete_from is not None:
            raise SettlementHistoryError("incomplete history cannot claim completeness")
        if sequence == 0 and complete_from is not None:
            raise SettlementHistoryError("empty history cannot claim completeness")
        if sequence > 0 and not gaps and complete_from != 1:
            raise SettlementHistoryError("complete history must start at transition 1")
        return cls(
            generation=generation,
            sequence=sequence,
            historical_transitions=historical,
            latest_by_run=latest,
            gaps=gaps,
            complete_from=complete_from,
        )


@dataclass(frozen=True)
class DeliveryReport:
    attempted_sessions: tuple[str, ...] = ()
    delivered_sessions: tuple[str, ...] = ()
    failed_sessions: tuple[str, ...] = ()
    pending: bool = False
    reason: str = ""


@dataclass(frozen=True)
class _GenerationState:
    generation: str
    continuity_gaps: int

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": SETTLEMENT_HISTORY_GENERATION_SCHEMA,
            "generation": self.generation,
            "continuity_gaps": self.continuity_gaps,
        }


def _settlement_tui(payload: Mapping[str, Any]) -> str:
    nested = payload.get("settlement")
    if isinstance(nested, Mapping):
        tui = str(nested.get("tui") or "").strip()
        if tui in _TUI_KEYS:
            return tui
    tui = str(payload.get("settlement_tui") or "").strip()
    if tui in _TUI_KEYS:
        return tui
    verdict = str(payload.get("settlement_verdict") or "").strip()
    if verdict == "finalized":
        return "f"
    if verdict in {"failed", "invalid"}:
        return "x"
    if verdict == "needs_attention":
        return "n"
    return ""


def _settlement_revision(payload: Mapping[str, Any]) -> int:
    revision = payload.get("settlement_revision")
    if type(revision) is int and revision > MAX_U64:
        raise SettlementHistoryError("settlement revision exceeds u64")
    return revision if type(revision) is int and revision > 0 else 1


def _transition_digest(
    *,
    run_id: str,
    revision: int,
    tui: str,
    event: Mapping[str, Any] | None,
) -> str:
    authority: object = (
        event
        if event is not None
        else {
            "run_id": run_id,
            "revision": revision,
            "tui": tui,
            "source": "snapshot_adoption",
        }
    )
    encoded = json.dumps(
        authority,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _adopt_payload(
    payload: Mapping[str, Any],
    event: Mapping[str, Any] | None = None,
) -> RunSettlementHistory | None:
    tui = _settlement_tui(payload)
    if not tui:
        return None
    revision = _settlement_revision(payload)
    # A persisted settlement without its ledger predates this authority and is
    # only a lower bound, even when legacy data omitted a revision and therefore
    # looks like r1. A freshly prepared event proves the current transition.
    gaps = max(revision - 1, 0)
    if event is None:
        gaps = max(gaps, 1)
    run_id = str(payload.get("run_id") or "").strip()
    return RunSettlementHistory(
        historical_transitions=SettlementCounts().increment(tui),
        latest_revision=revision,
        latest_tui=tui,
        latest_digest=_transition_digest(
            run_id=run_id,
            revision=revision,
            tui=tui,
            event=event,
        ),
        gaps=gaps,
        complete_from=None if gaps else 1,
    )


def run_history_from_payload(
    payload: Mapping[str, Any],
) -> RunSettlementHistory | None:
    tui = _settlement_tui(payload)
    if not tui:
        return None
    raw = payload.get("settlement_history")
    if raw is None:
        return _adopt_payload(payload)
    history = RunSettlementHistory.from_payload(raw)
    revision = _settlement_revision(payload)
    if history.latest_revision != revision or history.latest_tui != tui:
        raise SettlementHistoryError(
            f"run history does not match settlement r{revision}/{tui}"
        )
    return history


def advance_run_settlement_history(
    previous_payload: Mapping[str, Any] | None,
    current_payload: Mapping[str, Any],
    event: Mapping[str, Any] | None = None,
) -> dict[str, object] | None:
    """Return the canonical per-run ledger for ``current_payload``.

    Existing legacy settlement state is adopted once as a lower bound.  A
    revision jump records the known current transition and exposes every
    unobserved intermediate revision through ``gaps``.
    """

    current_tui = _settlement_tui(current_payload)
    if not current_tui:
        previous_history = (
            run_history_from_payload(previous_payload)
            if previous_payload is not None
            else None
        )
        return previous_history.to_payload() if previous_history else None

    run_id = str(current_payload.get("run_id") or "").strip()
    current_revision = _settlement_revision(current_payload)
    history = (
        run_history_from_payload(previous_payload)
        if previous_payload is not None and _settlement_tui(previous_payload)
        else None
    )
    if history is None:
        adopted = _adopt_payload(current_payload, event)
        if adopted is None:
            return None
        return adopted.to_payload()
    if current_revision < history.latest_revision:
        raise SettlementHistoryError("settlement history revision moved backwards")
    if current_revision == history.latest_revision:
        if current_tui != history.latest_tui:
            raise SettlementHistoryError(
                "same settlement revision changed its terminal bucket"
            )
        return history.to_payload()

    missing = max(current_revision - history.latest_revision - 1, 0)
    gaps = history.gaps + missing
    if gaps > MAX_U64:
        raise SettlementHistoryError("run settlement gaps exceed u64")
    advanced = RunSettlementHistory(
        historical_transitions=history.historical_transitions.increment(current_tui),
        latest_revision=current_revision,
        latest_tui=current_tui,
        latest_digest=_transition_digest(
            run_id=run_id,
            revision=current_revision,
            tui=current_tui,
            event=event,
        ),
        gaps=gaps,
        complete_from=None if gaps else history.complete_from,
    )
    return advanced.to_payload()


def default_settlement_history_path() -> Path:
    return vibecrafted_home() / "control_plane" / "settlement_history.json"


def default_delivery_outbox_path() -> Path:
    return vibecrafted_home() / "control_plane" / "settlement_history_delivery.json"


def default_generation_path() -> Path:
    return vibecrafted_home() / "control_plane" / "settlement_history_generation.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise SettlementHistoryError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SettlementHistoryError(f"JSON document is not an object: {path}")
    return payload


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_durable(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = -1
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(temporary, flags, 0o600)
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError(errno.EIO, f"short write to {temporary}")
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        with contextlib.suppress(OSError):
            temporary.unlink()


@contextlib.contextmanager
def _history_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".settlement-history.lock"
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SettlementHistoryError("settlement history lock is not regular")
        if metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
            raise SettlementHistoryError("settlement history lock ownership is unsafe")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _snapshot_candidates(root: Path) -> Sequence[Path]:
    runs = root / "runs"
    return tuple(sorted(runs.glob("*.json"))) + tuple(
        sorted((runs / "archive").glob("*.json"))
    )


def _load_generation_locked(root: Path) -> _GenerationState | None:
    path = root / "settlement_history_generation.json"
    payload = _read_json(path)
    if not payload:
        return None
    if (
        set(payload) != {"schema", "generation", "continuity_gaps"}
        or payload.get("schema") != SETTLEMENT_HISTORY_GENERATION_SCHEMA
    ):
        raise SettlementHistoryError("settlement history generation file is invalid")
    generation = payload.get("generation")
    continuity_gaps = payload.get("continuity_gaps")
    if not isinstance(generation, str):
        raise SettlementHistoryError("settlement history generation is invalid")
    try:
        canonical = str(uuid.UUID(generation))
    except ValueError as exc:
        raise SettlementHistoryError(
            "settlement history generation is invalid"
        ) from exc
    if canonical != generation:
        raise SettlementHistoryError("settlement history generation is not canonical")
    if type(continuity_gaps) is not int or not 0 <= continuity_gaps <= MAX_U64:
        raise SettlementHistoryError(
            "settlement history generation continuity is invalid"
        )
    return _GenerationState(
        generation=generation,
        continuity_gaps=continuity_gaps,
    )


def _write_generation_locked(root: Path, state: _GenerationState) -> None:
    _write_json_durable(
        root / "settlement_history_generation.json",
        state.to_payload(),
    )


def _load_or_create_generation_locked(
    root: Path,
    *,
    prior: SettlementHistorySnapshot | None,
) -> _GenerationState:
    state = _load_generation_locked(root)
    if state is None:
        state = _GenerationState(
            generation=str(uuid.uuid4()),
            continuity_gaps=1 if prior is not None else 0,
        )
        _write_generation_locked(root, state)
        return state
    if (
        prior is not None
        and state.generation != prior.generation
        and state.continuity_gaps == 0
    ):
        state = _GenerationState(
            generation=state.generation,
            continuity_gaps=1,
        )
        _write_generation_locked(root, state)
    return state


def reconcile_settlement_history(
    *,
    control_plane_root: Path | None = None,
    output_path: Path | None = None,
) -> SettlementHistorySnapshot:
    """Project all active + archived per-run ledgers into the public v1 schema."""

    root = (
        control_plane_root
        if control_plane_root is not None
        else vibecrafted_home() / "control_plane"
    )
    target = (
        output_path if output_path is not None else root / "settlement_history.json"
    )
    by_run: dict[str, RunSettlementHistory] = {}
    for path in _snapshot_candidates(root):
        payload = _read_json(path)
        run_id = str(payload.get("run_id") or path.stem).strip()
        if not run_id:
            continue
        history = run_history_from_payload(payload)
        if history is None:
            continue
        existing = by_run.get(run_id)
        if existing is None or history.latest_revision > existing.latest_revision:
            by_run[run_id] = history
        elif (
            history.latest_revision == existing.latest_revision and history != existing
        ):
            raise SettlementHistoryError(
                f"divergent active/archive history for {run_id} r{history.latest_revision}"
            )

    historical = SettlementCounts()
    latest = SettlementCounts()
    gaps = 0
    for history in by_run.values():
        historical = SettlementCounts(
            f=historical.f + history.historical_transitions.f,
            x=historical.x + history.historical_transitions.x,
            n=historical.n + history.historical_transitions.n,
        )
        latest = latest.increment(history.latest_tui)
        gaps += history.gaps
    with _history_lock(root):
        prior_payload = _read_json(target)
        prior = (
            SettlementHistorySnapshot.from_payload(prior_payload)
            if prior_payload
            else None
        )
        generation = _load_or_create_generation_locked(root, prior=prior)
        total_gaps = gaps + generation.continuity_gaps
        if total_gaps > MAX_U64:
            raise SettlementHistoryError("settlement history gaps exceed u64")
        snapshot = SettlementHistorySnapshot(
            generation=generation.generation,
            sequence=historical.total,
            historical_transitions=historical,
            latest_by_run=latest,
            gaps=total_gaps,
            complete_from=1 if historical.total and not total_gaps else None,
        )
        if prior is not None and snapshot.generation == prior.generation:
            if snapshot.sequence < prior.sequence:
                raise SettlementHistoryError(
                    "settlement history projection would move sequence backwards"
                )
            if snapshot.sequence == prior.sequence and snapshot != prior:
                raise SettlementHistoryError(
                    "settlement history projection diverged at the same sequence"
                )
        if prior is None or snapshot != prior:
            _write_json_durable(target, snapshot.to_payload())
    return snapshot


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _default_runner(
    argv: Sequence[str], *, timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _resolve_vc_frame_binary(env: Mapping[str, str]) -> str:
    explicit = str(env.get("VIBECRAFTED_VC_FRAME_BIN") or "").strip()
    if explicit:
        return explicit if Path(explicit).is_file() else ""
    return shutil.which("vc-frame", path=env.get("PATH")) or ""


def _running_session_names(output: str) -> tuple[str, ...]:
    sessions: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "(EXITED - attach to resurrect)" in line:
            continue
        name, separator, _rest = line.partition(" [Created ")
        if separator and name and name not in sessions:
            sessions.append(name)
    return tuple(sessions)


class SettlementHistoryPublisher:
    """Coalesced latest-only delivery to already-running vc-frame plugins."""

    def __init__(
        self,
        *,
        control_plane_root: Path | None = None,
        history_path: Path | None = None,
        outbox_path: Path | None = None,
        runner: Runner = _default_runner,
        env: Mapping[str, str] | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.root = (
            control_plane_root
            if control_plane_root is not None
            else vibecrafted_home() / "control_plane"
        )
        self.history_path = (
            history_path
            if history_path is not None
            else self.root / "settlement_history.json"
        )
        self.outbox_path = (
            outbox_path
            if outbox_path is not None
            else self.root / "settlement_history_delivery.json"
        )
        self.runner = runner
        self.env = dict(os.environ if env is None else env)
        self.timeout = timeout
        self._refresh_lock = threading.Lock()
        self._refresh_requested = False
        self._refresh_thread: threading.Thread | None = None
        self._periodic_lock = threading.Lock()
        self._periodic_stop = threading.Event()
        self._periodic_thread: threading.Thread | None = None

    def stage(self, snapshot: SettlementHistorySnapshot) -> None:
        snapshot = SettlementHistorySnapshot.from_payload(snapshot.to_payload())
        document = {
            "schema": DELIVERY_OUTBOX_SCHEMA,
            "sequence": snapshot.sequence,
            "payload": snapshot.to_payload(),
        }
        with _history_lock(self.root):
            generation = _load_generation_locked(self.root)
            if generation is None or snapshot.generation != generation.generation:
                raise SettlementHistoryError(
                    "cannot stage a stale settlement history generation"
                )
            current = _read_json(self.outbox_path)
            if current:
                sequence = current.get("sequence")
                current_snapshot = SettlementHistorySnapshot.from_payload(
                    current.get("payload")
                )
                if (
                    current.get("schema") != DELIVERY_OUTBOX_SCHEMA
                    or type(sequence) is not int
                    or sequence != current_snapshot.sequence
                ):
                    raise SettlementHistoryError("delivery outbox sequence is invalid")
                if current_snapshot.generation == snapshot.generation:
                    if sequence > snapshot.sequence:
                        return
                    if sequence == snapshot.sequence and current != document:
                        raise SettlementHistoryError(
                            "delivery outbox diverged at the same sequence"
                        )
            if current != document:
                _write_json_durable(self.outbox_path, document)

    def flush(self) -> DeliveryReport:
        with _history_lock(self.root):
            document = _read_json(self.outbox_path)
            if not document:
                return DeliveryReport(reason="idle")
            if (
                document.get("schema") != DELIVERY_OUTBOX_SCHEMA
                or type(document.get("sequence")) is not int
            ):
                raise SettlementHistoryError("delivery outbox is invalid")
            snapshot = SettlementHistorySnapshot.from_payload(document.get("payload"))
            generation = _load_generation_locked(self.root)
            if generation is None or snapshot.generation != generation.generation:
                return DeliveryReport(
                    pending=True,
                    reason="stale settlement history generation",
                )
        binary = _resolve_vc_frame_binary(self.env)
        if not binary:
            return DeliveryReport(pending=True, reason="vc-frame unavailable")
        try:
            listed = self.runner(
                [binary, "list-sessions", "--no-formatting"],
                timeout=self.timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return DeliveryReport(
                pending=True,
                reason=f"session discovery failed: {type(exc).__name__}",
            )
        if listed.returncode != 0:
            return DeliveryReport(pending=True, reason="no running vc-frame sessions")
        sessions = _running_session_names(listed.stdout)
        if not sessions:
            return DeliveryReport(pending=True, reason="no running vc-frame sessions")

        delivered: list[str] = []
        failed: list[str] = []
        payload = snapshot.to_json()
        for session in sessions:
            try:
                result = self.runner(
                    [
                        binary,
                        "--session",
                        session,
                        "pipe",
                        "--name",
                        SETTLEMENT_COUNTS_PIPE,
                        "--",
                        payload,
                    ],
                    timeout=self.timeout,
                )
            except (OSError, subprocess.SubprocessError):
                failed.append(session)
                continue
            if result.returncode == 0:
                delivered.append(session)
            else:
                failed.append(session)

        if not failed:
            with _history_lock(self.root):
                current = _read_json(self.outbox_path)
                if (
                    current.get("schema") == DELIVERY_OUTBOX_SCHEMA
                    and current.get("sequence") == snapshot.sequence
                    and current.get("payload") == snapshot.to_payload()
                ):
                    self.outbox_path.unlink(missing_ok=True)
                    _fsync_directory(self.outbox_path.parent)
        return DeliveryReport(
            attempted_sessions=sessions,
            delivered_sessions=tuple(delivered),
            failed_sessions=tuple(failed),
            pending=bool(failed),
            reason="" if not failed else "one or more vc-frame deliveries failed",
        )

    def refresh_and_flush(self) -> DeliveryReport:
        snapshot = reconcile_settlement_history(
            control_plane_root=self.root,
            output_path=self.history_path,
        )
        self.stage(snapshot)
        return self.flush()

    def request_refresh(self) -> bool:
        """Schedule one coalesced refresh without blocking Guardian's SSE loop."""

        with self._refresh_lock:
            self._refresh_requested = True
            if self._refresh_thread is not None and self._refresh_thread.is_alive():
                return False
            thread = threading.Thread(
                target=self._drain_refresh_requests,
                name="vibecrafted-settlement-history",
                daemon=True,
            )
            self._refresh_thread = thread
            thread.start()
            return True

    def start_periodic_refresh(
        self,
        interval: float = SETTLEMENT_REPLAY_INTERVAL_SECONDS,
    ) -> bool:
        """Replay latest truth often enough for newly loaded session managers."""

        if not 0 < interval <= SETTLEMENT_REPLAY_INTERVAL_SECONDS:
            raise ValueError(
                "settlement history replay interval must be within five seconds"
            )
        with self._periodic_lock:
            if self._periodic_thread is not None and self._periodic_thread.is_alive():
                return False
            stop = threading.Event()
            thread = threading.Thread(
                target=self._periodic_refresh_loop,
                args=(stop, interval),
                name="vibecrafted-settlement-history-replay",
                daemon=True,
            )
            self._periodic_stop = stop
            self._periodic_thread = thread
            thread.start()
        self.request_refresh()
        return True

    def _periodic_refresh_loop(
        self,
        stop: threading.Event,
        interval: float,
    ) -> None:
        try:
            while not stop.wait(interval):
                self.request_refresh()
        finally:
            with self._periodic_lock:
                if self._periodic_stop is stop:
                    self._periodic_thread = None

    def stop_periodic_refresh(self, timeout: float = 5.0) -> bool:
        """Stop the replay timer; any in-flight publication stays non-blocking."""

        with self._periodic_lock:
            thread = self._periodic_thread
            self._periodic_stop.set()
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _drain_refresh_requests(self) -> None:
        while True:
            with self._refresh_lock:
                if not self._refresh_requested:
                    self._refresh_thread = None
                    return
                self._refresh_requested = False
            try:
                self.refresh_and_flush()
            except Exception:
                LOGGER.exception("settlement-history background refresh failed")

    def wait_for_idle(self, timeout: float = 5.0) -> bool:
        """Test/doctor seam: wait for the current coalesced worker."""

        with self._refresh_lock:
            thread = self._refresh_thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()


__all__ = [
    "DELIVERY_OUTBOX_SCHEMA",
    "MAX_U64",
    "RUN_HISTORY_SCHEMA",
    "SETTLEMENT_COUNTS_PIPE",
    "SETTLEMENT_HISTORY_GENERATION_SCHEMA",
    "SETTLEMENT_HISTORY_SCHEMA",
    "SETTLEMENT_REPLAY_INTERVAL_SECONDS",
    "DeliveryReport",
    "RunSettlementHistory",
    "SettlementCounts",
    "SettlementHistoryError",
    "SettlementHistoryPublisher",
    "SettlementHistorySnapshot",
    "advance_run_settlement_history",
    "default_delivery_outbox_path",
    "default_generation_path",
    "default_settlement_history_path",
    "reconcile_settlement_history",
    "run_history_from_payload",
]
