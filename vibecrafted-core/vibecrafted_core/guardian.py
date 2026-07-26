"""Event-driven f/x/n guardian for terminal Vibecrafted runs.

The guardian has one trigger substrate: the vibecrafted-server
``GET /api/control/events`` SSE stream.  For each new typed settlement it
performs one exact run-projection read before deciding.  It never tails
``events.jsonl``, polls run lists, or starts a vc-frame loop.

On the first attachment, historical frames are checkpointed without side
effects until the server's ``: ping`` heartbeat proves that the initial drain
is complete.  Subsequent ``settlement.changed`` revisions move through a
durable ``pending -> completed`` outbox.  Adapters receive the stable
``(run_id, settlement_revision)`` key and must make their external effect
idempotent; after a crash, pending work is retried rather than silently lost.

After the baseline, every network reconnect replays SSE from byte zero.  That
is intentional: a bare byte offset cannot detect a rotated stream whose new
file has already grown beyond the old offset.  The durable key ledger makes
that correctness-first replay side-effect safe.

Resume is deliberately an injected boundary.  The CLI wires the guarded
server-projection -> ``vc-guard`` -> tracked ``native_resume_run`` adapter;
library callers without an adapter remain fail-closed.  Only ``n`` may request
resume, and only when both the event and fresh projection carry an explicit
``trust`` settlement source.  ``x`` and ``f`` are always notification-only and
can never reach the resume callback.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .delivery.store import atomic_write_json
from .runtime_paths import vibecrafted_home
from .settlement import (
    SETTLEMENT_EVENT_KIND,
    SETTLEMENT_EVENT_SCHEMA,
    TUI_FAILED,
    TUI_FINALIZED,
    TUI_NEEDS_ATTENTION,
)

LOGGER = logging.getLogger(__name__)

GUARDIAN_STATE_SCHEMA = "vibecrafted.guardian-state.v1"
GUARDIAN_DEAD_LETTER_SCHEMA = "vibecrafted.guardian-dead-letter.v1"
GUARDIAN_READY_SCHEMA = "vibecrafted.guardian-ready.v1"
DEFAULT_SERVER_URL = "http://127.0.0.1:3024"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 30.0
DEFAULT_RECOVERY_TIMEOUT_SECONDS = 5.0
DEFAULT_BACKOFF_INITIAL_SECONDS = 1.0
DEFAULT_BACKOFF_MAX_SECONDS = 30.0
DEFAULT_REPLAY_HEARTBEATS = 4

_TUI_SEVERITY = {
    TUI_FINALIZED: "info",
    TUI_NEEDS_ATTENTION: "warning",
    TUI_FAILED: "critical",
}
_TUI_LABEL = {
    TUI_FINALIZED: "finalized",
    TUI_NEEDS_ATTENTION: "needs attention",
    TUI_FAILED: "failed",
}
_VERDICT_TUI = {
    "finalized": TUI_FINALIZED,
    "needs_attention": TUI_NEEDS_ATTENTION,
    "failed": TUI_FAILED,
    "invalid": TUI_FAILED,
}

SettlementKey = tuple[str, int]


class GuardianAlreadyRunning(RuntimeError):
    """Another guardian process owns the single-instance lock."""


class GuardianProtocolError(RuntimeError):
    """The configured endpoint did not return the guardian's SSE contract."""


@dataclass(frozen=True)
class SettlementRevision:
    """Validated terminal settlement carried by one SSE frame."""

    run_id: str
    revision: int
    verdict: str
    tui: str
    reason: str
    source: str
    settled_at: str

    @property
    def key(self) -> SettlementKey:
        return (self.run_id, self.revision)

    @property
    def idempotency_key(self) -> str:
        return f"settlement:{self.run_id}:{self.revision}"

    def to_state_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "settlement_revision": self.revision,
            "verdict": self.verdict,
            "tui": self.tui,
            "reason": self.reason,
            "source": self.source,
            "settled_at": self.settled_at,
        }

    @classmethod
    def from_state_payload(
        cls, payload: Mapping[str, object]
    ) -> SettlementRevision | None:
        run_id = payload.get("run_id")
        revision = payload.get("settlement_revision")
        verdict = payload.get("verdict")
        tui = payload.get("tui")
        if (
            not isinstance(run_id, str)
            or not run_id
            or type(revision) is not int
            or revision <= 0
            or not isinstance(verdict, str)
            or not isinstance(tui, str)
            or _VERDICT_TUI.get(verdict) != tui
        ):
            return None
        return cls(
            run_id=run_id,
            revision=revision,
            verdict=verdict,
            tui=tui,
            reason=str(payload.get("reason") or ""),
            source=str(payload.get("source") or ""),
            settled_at=str(payload.get("settled_at") or ""),
        )


@dataclass(frozen=True)
class GuardianNotification:
    """One operator-facing f/x/n notification."""

    event: SettlementRevision
    severity: str
    title: str
    message: str


@dataclass(frozen=True)
class ReconcileDecision:
    """Result of one idempotently keyed reconcile operation."""

    request_resume: bool = False
    reason: str = "resume adapter unavailable"


Notifier = Callable[[GuardianNotification], None]
Reconciler = Callable[[SettlementRevision], ReconcileDecision]
ResumeCallback = Callable[[SettlementRevision, str], object]
UrlOpener = Callable[..., Any]
ReadyCallback = Callable[[], None]
GuardEnforcer = Callable[..., object]
NativeResumer = Callable[..., Mapping[str, object]]


@dataclass(frozen=True)
class SSEFrame:
    """One complete SSE data frame with its durable byte cursor."""

    cursor: int
    data: str


@dataclass(frozen=True)
class SSEHeartbeat:
    """The vibecrafted-server ``: ping`` keepalive."""


SSEItem = SSEFrame | SSEHeartbeat


@dataclass
class ConnectionStats:
    """Small observability receipt for one SSE connection."""

    frames: int = 0
    heartbeats: int = 0
    claimed: int = 0
    completed_actions: int = 0
    action_failures: int = 0
    completed_baseline: bool = False

    @property
    def proved_stable(self) -> bool:
        # One accept + one immediate ping + drop must not pin reconnect delay to
        # the minimum forever. Two quiet heartbeats prove a sustained stream;
        # a completed settlement action proves useful forward progress.
        return self.completed_actions > 0 or self.heartbeats >= 2


@dataclass
class GuardianState:
    """Durable cursor, baseline gate, and settlement action outbox."""

    path: Path
    cursor: int = 0
    baseline_complete: bool = False
    processed: list[SettlementKey] = field(default_factory=list)
    pending: dict[SettlementKey, SettlementRevision] = field(default_factory=dict)
    _processed_set: set[SettlementKey] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.cursor = max(int(self.cursor), 0)
        normalized: list[SettlementKey] = []
        seen: set[SettlementKey] = set()
        for run_id, revision in self.processed:
            key = (str(run_id), int(revision))
            if not key[0] or key[1] <= 0 or key in seen:
                continue
            normalized.append(key)
            seen.add(key)
        self.processed = normalized
        self._processed_set = set(self.processed)
        self.pending = {
            event.key: event
            for event in self.pending.values()
            if event.key not in self._processed_set
        }

    @classmethod
    def load(
        cls,
        path: Path,
    ) -> GuardianState:
        """Load state; malformed or foreign state starts a suppressed baseline."""

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls(path=path)
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("guardian state unreadable; starting suppressed: %s", exc)
            return cls(path=path)
        if not isinstance(raw, dict) or raw.get("schema") != GUARDIAN_STATE_SCHEMA:
            LOGGER.warning("guardian state schema invalid; starting suppressed")
            return cls(path=path)

        cursor_raw = raw.get("cursor")
        cursor = (
            cursor_raw
            if type(cursor_raw) is int and cursor_raw >= 0  # bool is not a cursor
            else 0
        )
        baseline_complete = raw.get("baseline_complete") is True
        processed: list[SettlementKey] = []
        entries = raw.get("processed")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                run_id = entry.get("run_id")
                revision = entry.get("settlement_revision")
                if (
                    isinstance(run_id, str)
                    and run_id
                    and type(revision) is int
                    and revision > 0
                ):
                    processed.append((run_id, revision))
        pending: dict[SettlementKey, SettlementRevision] = {}
        pending_entries = raw.get("pending")
        if isinstance(pending_entries, list):
            for entry in pending_entries:
                if not isinstance(entry, dict):
                    continue
                event = SettlementRevision.from_state_payload(entry)
                if event is not None:
                    pending[event.key] = event
        return cls(
            path=path,
            cursor=cursor,
            baseline_complete=baseline_complete,
            processed=processed,
            pending=pending,
        )

    @staticmethod
    def _payload(
        *,
        cursor: int,
        baseline_complete: bool,
        processed: Sequence[SettlementKey],
        pending: Mapping[SettlementKey, SettlementRevision],
    ) -> dict[str, object]:
        return {
            "schema": GUARDIAN_STATE_SCHEMA,
            "cursor": cursor,
            "baseline_complete": baseline_complete,
            "processed": [
                {"run_id": run_id, "settlement_revision": revision}
                for run_id, revision in processed
            ],
            "pending": [event.to_state_payload() for event in pending.values()],
        }

    def _persist_snapshot(
        self,
        *,
        cursor: int,
        baseline_complete: bool,
        processed: Sequence[SettlementKey],
        pending: Mapping[SettlementKey, SettlementRevision],
    ) -> None:
        atomic_write_json(
            self.path,
            self._payload(
                cursor=cursor,
                baseline_complete=baseline_complete,
                processed=processed,
                pending=pending,
            ),
        )

    def persist(self) -> None:
        """Atomically persist the current cursor and action ledger."""

        self._persist_snapshot(
            cursor=self.cursor,
            baseline_complete=self.baseline_complete,
            processed=self.processed,
            pending=self.pending,
        )

    def checkpoint(self, cursor: int) -> None:
        """Persist one frame cursor transactionally.

        A lower cursor is valid after ``events.jsonl`` rotation.  The settlement
        key ledger survives that reset and prevents replayed revisions from
        producing duplicate effects.
        """

        if cursor < 0:
            raise ValueError("SSE cursor must be non-negative")
        if cursor == self.cursor:
            return
        self._persist_snapshot(
            cursor=cursor,
            baseline_complete=self.baseline_complete,
            processed=self.processed,
            pending=self.pending,
        )
        self.cursor = cursor

    def suppress(self, cursor: int, key: SettlementKey) -> bool:
        """Checkpoint one baseline key directly as intentionally completed."""

        if key in self._processed_set or key in self.pending:
            self.checkpoint(cursor)
            return False
        processed = [*self.processed, key]
        self._persist_snapshot(
            cursor=cursor,
            baseline_complete=self.baseline_complete,
            processed=processed,
            pending=self.pending,
        )
        self.cursor = cursor
        self.processed = processed
        self._processed_set.add(key)
        return True

    def claim(self, cursor: int, event: SettlementRevision) -> bool:
        """Durably enqueue one action before invoking external adapters."""

        if event.key in self._processed_set or event.key in self.pending:
            return False
        pending = {**self.pending, event.key: event}
        self._persist_snapshot(
            cursor=cursor,
            baseline_complete=self.baseline_complete,
            processed=self.processed,
            pending=pending,
        )
        self.cursor = cursor
        self.pending = pending
        return True

    def complete(self, key: SettlementKey) -> bool:
        """Move one attempted action from pending to the durable dedupe ledger."""

        if key not in self.pending:
            return False
        pending = dict(self.pending)
        pending.pop(key)
        processed = [*self.processed, key]
        self._persist_snapshot(
            cursor=self.cursor,
            baseline_complete=self.baseline_complete,
            processed=processed,
            pending=pending,
        )
        self.pending = pending
        self.processed = processed
        self._processed_set.add(key)
        return True

    def pending_events(self) -> tuple[SettlementRevision, ...]:
        return tuple(self.pending.values())

    def quarantine(self, cursor: int, data: str) -> bool:
        """Persist one invalid settlement frame as an idempotent dead letter."""

        encoded = data.encode("utf-8", errors="replace")
        digest = hashlib.sha256(encoded).hexdigest()
        target = self.path.parent / "dead_letters" / f"{digest}.json"
        created = not target.is_file()
        if created:
            limit = 64 * 1024
            atomic_write_json(
                target,
                {
                    "schema": GUARDIAN_DEAD_LETTER_SCHEMA,
                    "sha256": digest,
                    "sse_cursor": cursor,
                    "reason": "invalid settlement.changed contract",
                    "data": encoded[:limit].decode("utf-8", errors="replace"),
                    "truncated": len(encoded) > limit,
                },
            )
        if not self.baseline_complete:
            self.checkpoint(cursor)
        return created

    def complete_baseline(self) -> bool:
        """Open the side-effect gate exactly once after the first heartbeat."""

        if self.baseline_complete:
            return False
        self._persist_snapshot(
            cursor=self.cursor,
            baseline_complete=True,
            processed=self.processed,
            pending=self.pending,
        )
        self.baseline_complete = True
        return True


@dataclass
class BoundedBackoff:
    """Exponential reconnect delay with an explicit upper bound."""

    initial: float = DEFAULT_BACKOFF_INITIAL_SECONDS
    maximum: float = DEFAULT_BACKOFF_MAX_SECONDS
    _next: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.initial <= 0:
            raise ValueError("initial backoff must be > 0")
        if self.maximum < self.initial:
            raise ValueError("maximum backoff must be >= initial backoff")
        self._next = self.initial

    def next_delay(self) -> float:
        delay = self._next
        self._next = min(self.maximum, self._next * 2)
        return delay

    def reset(self) -> None:
        self._next = self.initial


def iter_sse(lines: Iterable[bytes | str]) -> Iterator[SSEItem]:
    """Parse complete numeric-id data frames and ``: ping`` heartbeats."""

    cursor: int | None = None
    data: list[str] = []
    heartbeat = False

    for raw_line in lines:
        line = (
            raw_line.decode("utf-8", errors="replace")
            if isinstance(raw_line, bytes)
            else raw_line
        ).rstrip("\r\n")
        if line:
            if line == ": ping":
                heartbeat = True
            elif line.startswith("id:"):
                value = line[3:].strip()
                try:
                    parsed = int(value)
                except ValueError:
                    cursor = None
                else:
                    cursor = parsed if parsed >= 0 else None
            elif line.startswith("data:"):
                value = line[5:]
                data.append(value.removeprefix(" "))
            continue

        if data and cursor is not None:
            yield SSEFrame(cursor=cursor, data="\n".join(data))
        elif heartbeat:
            yield SSEHeartbeat()
        cursor = None
        data = []
        heartbeat = False


def _declares_settlement_event(data: str) -> bool:
    try:
        frame = json.loads(data)
    except json.JSONDecodeError:
        return False
    return isinstance(frame, dict) and frame.get("kind") == SETTLEMENT_EVENT_KIND


def parse_settlement_revision(data: str) -> SettlementRevision | None:
    """Validate the typed settlement event; reject contradictions fail-closed."""

    try:
        frame = json.loads(data)
    except json.JSONDecodeError:
        return None
    if not isinstance(frame, dict) or frame.get("kind") != SETTLEMENT_EVENT_KIND:
        return None
    payload = frame.get("payload")
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != SETTLEMENT_EVENT_SCHEMA
    ):
        return None
    current = payload.get("current")
    if not isinstance(current, dict):
        return None

    top_run_id = frame.get("run_id")
    run_id = payload.get("run_id")
    revision = payload.get("revision")
    verdict = current.get("verdict")
    tui = current.get("tui")
    if (
        not isinstance(top_run_id, str)
        or not isinstance(run_id, str)
        or not run_id
        or top_run_id != run_id
        or type(revision) is not int
        or revision <= 0
        or not isinstance(verdict, str)
        or not isinstance(tui, str)
        or _VERDICT_TUI.get(verdict) != tui
    ):
        return None
    return SettlementRevision(
        run_id=run_id,
        revision=revision,
        verdict=verdict,
        tui=tui,
        reason=str(payload.get("reason") or ""),
        source=str(payload.get("source") or ""),
        settled_at=str(payload.get("settled_at") or ""),
    )


def notification_for(event: SettlementRevision) -> GuardianNotification:
    """Map f/n/x onto the operator severity contract."""

    severity = _TUI_SEVERITY[event.tui]
    label = _TUI_LABEL[event.tui]
    reason = event.reason or "no settlement reason"
    return GuardianNotification(
        event=event,
        severity=severity,
        title=f"Vibecrafted {event.tui}: {label}",
        message=f"{event.run_id} · r{event.revision} · {reason}",
    )


def notify_operator(
    notification: GuardianNotification,
    *,
    desktop: bool = True,
    platform: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> None:
    """Log every notification and best-effort a native macOS notification."""

    level = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "critical": logging.CRITICAL,
    }[notification.severity]
    LOGGER.log(level, "%s — %s", notification.title, notification.message)

    if not desktop or (platform or sys.platform) != "darwin":
        return
    osascript = which("osascript")
    if not osascript:
        return
    script = (
        "on run argv\n"
        "display notification item 2 of argv with title item 1 of argv\n"
        "end run"
    )
    try:
        result = runner(
            [osascript, "-e", script, "--", notification.title, notification.message],
            check=False,
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.warning("macOS notification unavailable: %s", exc)
        return
    if result.returncode != 0:
        LOGGER.warning("macOS notification failed with exit %s", result.returncode)


def fail_closed_reconcile(_event: SettlementRevision) -> ReconcileDecision:
    """Default reconcile boundary: observe once, never infer resume authority."""

    return ReconcileDecision()


@dataclass(frozen=True)
class RecoveryContext:
    """Server-verified arguments for one guarded native resume."""

    root: Path
    agent: str
    skill: str
    sha: str


def _default_guard_enforcer(**kwargs: object) -> object:
    from .guard import enforce_continuation

    return enforce_continuation(**kwargs)


def _default_native_resumer(
    run_id: str,
    source_dir: str | Path,
    *,
    expected_agent: str,
    idempotency_key: str,
) -> Mapping[str, object]:
    from .workflow import native_resume_run

    return native_resume_run(
        run_id,
        source_dir=source_dir,
        expected_agent=expected_agent,
        idempotency_key=idempotency_key,
    )


def _explicit_identity(value: object) -> str:
    candidate = str(value or "").strip()
    if candidate.lower() in {"", "unknown", "pending", "none", "null"}:
        return ""
    return candidate


def _validate_server_url(value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("server URL must be an http(s) origin without a path")
    return normalized


def _server_run_is_terminal(run: Mapping[str, object]) -> bool:
    # Mirrors control_plane._run_is_terminal / control-core RunStatus::is_terminal.
    terminal_states = {
        "report_validated",
        "completed",
        "closed",
        "converged",
        "stopped",
        "blocked",
        "failed",
        "report_missing",
        "report_invalid",
        "contract_failed",
        "recovery_required",
        "timed_out",
        "gc",
        "ghost",
    }
    return (
        str(run.get("state") or "") in terminal_states
        or str(run.get("liveness") or "") == "terminal"
        or run.get("exit_code") is not None
    )


class GuardianRecoveryAdapter:
    """HTTP truth check -> vc-guard -> idempotent native-resume adapter."""

    def __init__(
        self,
        *,
        server_url: str,
        opener: UrlOpener = urllib.request.urlopen,
        timeout: float = 5.0,
        guard_enforcer: GuardEnforcer = _default_guard_enforcer,
        native_resumer: NativeResumer = _default_native_resumer,
    ) -> None:
        self.server_url = _validate_server_url(server_url)
        if timeout <= 0:
            raise ValueError("recovery HTTP timeout must be > 0")
        self.opener = opener
        self.timeout = timeout
        self.guard_enforcer = guard_enforcer
        self.native_resumer = native_resumer
        self._contexts: dict[SettlementKey, RecoveryContext] = {}

    def _fetch_run(self, run_id: str) -> dict[str, object]:
        encoded = urllib.parse.quote(run_id, safe="")
        request = urllib.request.Request(
            f"{self.server_url}/api/control/runs/{encoded}",
            headers={"Accept": "application/json", "Cache-Control": "no-cache"},
        )
        response = self.opener(request, timeout=self.timeout)
        with contextlib.closing(response):
            status = getattr(response, "status", 200)
            if status != 200:
                raise GuardianProtocolError(
                    f"run projection returned HTTP {status} for {run_id}"
                )
            headers = getattr(response, "headers", {})
            content_type = str(headers.get("Content-Type", "") or "").lower()
            if not content_type.startswith("application/json"):
                raise GuardianProtocolError(
                    f"run projection returned unexpected content type {content_type!r}"
                )
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise GuardianProtocolError("run projection exceeds 1 MiB")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GuardianProtocolError(
                f"run projection is not valid JSON for {run_id}"
            ) from exc
        if not isinstance(payload, dict):
            raise GuardianProtocolError("run projection must be a JSON object")
        return payload

    @staticmethod
    def _attempt(run: Mapping[str, object]) -> int | None:
        raw = run.get("attempt")
        if raw is None:
            return 0
        if type(raw) is not int or raw < 0:
            return None
        return raw

    def reconcile(self, event: SettlementRevision) -> ReconcileDecision:
        """Fetch the exact run projection and decide whether resume is safe."""

        self._contexts.pop(event.key, None)
        run = self._fetch_run(event.run_id)
        revision = run.get("settlement_revision")
        if (
            run.get("run_id") != event.run_id
            or run.get("settlement_tui") != event.tui
            or run.get("settlement_verdict") != event.verdict
            or type(revision) is not int
            or revision != event.revision
        ):
            return ReconcileDecision(reason="stale_or_mismatched_settlement")
        if event.tui != TUI_NEEDS_ATTENTION:
            return ReconcileDecision(reason=f"settlement_{event.tui}_not_resumable")
        if (
            event.verdict != "needs_attention"
            or event.source != "trust"
            or run.get("settlement_source") != "trust"
        ):
            return ReconcileDecision(reason="vc_trust_authority_missing")
        if run.get("worker_alive") is not False:
            return ReconcileDecision(reason="worker_not_confirmed_dead")
        if run.get("recovery_required") is not True:
            return ReconcileDecision(reason="recovery_not_required")
        stop_reason = str(run.get("stop_reason") or "").strip().lower()
        if any(token in stop_reason for token in ("manual", "stop", "cancel")):
            return ReconcileDecision(reason="manual_stop_or_cancel")
        if not _server_run_is_terminal(run):
            return ReconcileDecision(reason="run_not_terminal")
        attempt = self._attempt(run)
        if attempt is None or attempt >= 1:
            return ReconcileDecision(reason="automatic_attempt_budget_exhausted")

        controls = run.get("controls")
        if not isinstance(controls, Mapping):
            return ReconcileDecision(reason="native_resume_candidate_missing")
        candidate = controls.get("native_resume_candidate")
        if not isinstance(candidate, Mapping):
            return ReconcileDecision(reason="native_resume_candidate_missing")
        agent = _explicit_identity(candidate.get("agent"))
        agent_session_id = _explicit_identity(candidate.get("agent_session_id"))
        if not agent or not agent_session_id:
            return ReconcileDecision(reason="native_resume_identity_missing")
        projected_agent = _explicit_identity(run.get("agent"))
        if projected_agent and projected_agent != agent:
            return ReconcileDecision(reason="native_resume_agent_mismatch")

        root = _explicit_identity(run.get("root"))
        if not root:
            return ReconcileDecision(reason="run_root_missing")
        skill = str(run.get("skill") or "").strip()
        sha = ""
        for projection_field in ("commit_sha", "sha", "commit"):
            sha = _explicit_identity(run.get(projection_field))
            if sha:
                break
        decision = self.guard_enforcer(
            repo=Path(root),
            sha=sha,
            skill=skill,
        )
        allowed = (
            decision.get("allowed") is True
            if isinstance(decision, Mapping)
            else getattr(decision, "allowed", None) is True
        )
        if not allowed:
            return ReconcileDecision(reason="vc_guard_blocked")

        self._contexts[event.key] = RecoveryContext(
            root=Path(root),
            agent=agent,
            skill=skill,
            sha=sha,
        )
        return ReconcileDecision(
            request_resume=True,
            reason="server_truth_and_vc_guard_allow_resume",
        )

    def resume(
        self,
        event: SettlementRevision,
        idempotency_key: str,
    ) -> Mapping[str, object]:
        """Invoke the tracked native-resume boundary with the stable key."""

        context = self._contexts.get(event.key)
        if context is None:
            raise RuntimeError(f"resume context missing for {event.idempotency_key}")
        result = self.native_resumer(
            event.run_id,
            source_dir=context.root,
            expected_agent=context.agent,
            idempotency_key=idempotency_key,
        )
        if result.get("accepted") is True:
            self._contexts.pop(event.key, None)
        return result


class GuardianWorker:
    """Long-lived SSE consumer with durable dedupe and injected side effects."""

    def __init__(
        self,
        *,
        server_url: str,
        state: GuardianState,
        notifier: Notifier = notify_operator,
        reconciler: Reconciler = fail_closed_reconcile,
        resume: ResumeCallback | None = None,
        opener: UrlOpener = urllib.request.urlopen,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        replay_heartbeats: int = DEFAULT_REPLAY_HEARTBEATS,
        ready_callback: ReadyCallback | None = None,
    ) -> None:
        self.server_url = _validate_server_url(server_url)
        self.state = state
        self.notifier = notifier
        self.reconciler = reconciler
        self.resume = resume
        self.opener = opener
        if connect_timeout <= 0:
            raise ValueError("connect timeout must be > 0")
        if replay_heartbeats <= 0:
            raise ValueError("replay heartbeat count must be > 0")
        self.connect_timeout = connect_timeout
        self.replay_heartbeats = replay_heartbeats
        self.ready_callback = ready_callback
        self._ready_announced = False

    def _request(self) -> urllib.request.Request:
        # During the first suppressed drain, resuming the saved cursor avoids
        # repeatedly walking a large historical stream. Once armed, always
        # replay from zero: only a full replay is safe across file generations
        # because the server cursor is a generation-less byte offset.
        cursor = 0 if self.state.baseline_complete else self.state.cursor
        url = f"{self.server_url}/api/control/events?since={cursor}"
        return urllib.request.Request(
            url,
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "Last-Event-ID": str(cursor),
            },
        )

    @staticmethod
    def _validate_response(response: Any) -> None:
        status = getattr(response, "status", 200)
        if status != 200:
            raise GuardianProtocolError(f"SSE endpoint returned HTTP {status}")
        headers = getattr(response, "headers", {})
        content_type = str(headers.get("Content-Type", "") or "").lower()
        if not content_type.startswith("text/event-stream"):
            raise GuardianProtocolError(
                f"SSE endpoint returned unexpected content type {content_type!r}"
            )

    def consume_connection(self) -> ConnectionStats:
        """Consume one SSE connection until the server disconnects."""

        stats = ConnectionStats()
        for pending in self.state.pending_events():
            stats.claimed += 1
            if self._attempt_and_complete(pending):
                stats.completed_actions += 1
            else:
                stats.action_failures += 1
        if stats.action_failures:
            return stats

        latest_cursor: int | None = None
        try:
            response = self.opener(self._request(), timeout=self.connect_timeout)
            with contextlib.closing(response):
                self._validate_response(response)
                if not self._ready_announced and self.ready_callback is not None:
                    self.ready_callback()
                    self._ready_announced = True
                for item in iter_sse(response):
                    if isinstance(item, SSEHeartbeat):
                        stats.heartbeats += 1
                        if self.state.complete_baseline():
                            stats.completed_baseline = True
                            LOGGER.info(
                                "guardian baseline drained at cursor %s",
                                self.state.cursor,
                            )
                            # Close the first attachment deliberately. The next
                            # connection performs the first generation-safe replay
                            # from zero with the now-armed dedupe ledger.
                            return stats
                        if stats.heartbeats >= self.replay_heartbeats:
                            # A generation-less byte cursor cannot notice every
                            # rotation while a socket stays open. Periodic,
                            # heartbeat-paced SSE reattachment bounds that blind
                            # window without polling another API or vc-frame.
                            return stats
                        continue

                    stats.frames += 1
                    latest_cursor = item.cursor
                    event = parse_settlement_revision(item.data)
                    if event is None:
                        if _declares_settlement_event(item.data):
                            if self.state.quarantine(item.cursor, item.data):
                                LOGGER.critical(
                                    "guardian quarantined invalid settlement frame at "
                                    "SSE cursor %s",
                                    item.cursor,
                                )
                        elif not self.state.baseline_complete:
                            self.state.checkpoint(item.cursor)
                        continue

                    baseline_was_complete = self.state.baseline_complete
                    claimed = (
                        self.state.claim(item.cursor, event)
                        if baseline_was_complete
                        else self.state.suppress(item.cursor, event.key)
                    )
                    if not claimed:
                        continue
                    stats.claimed += 1
                    if not baseline_was_complete:
                        LOGGER.debug(
                            "guardian suppressed baseline settlement %s r%s",
                            event.run_id,
                            event.revision,
                        )
                        continue
                    if self._attempt_and_complete(event):
                        stats.completed_actions += 1
                    else:
                        stats.action_failures += 1
                        return stats
            return stats
        finally:
            # The armed stream always replays from zero, so per-frame cursor
            # fsync would turn a large replay into quadratic disk churn. One
            # transactional checkpoint per connection is enough for evidence.
            if self.state.baseline_complete and latest_cursor is not None:
                self.state.checkpoint(latest_cursor)

    def _attempt_and_complete(self, event: SettlementRevision) -> bool:
        """Attempt pending work, then complete it with a transactional receipt."""

        if not self._handle_claimed(event):
            return False
        self.state.complete(event.key)
        return True

    def _handle_claimed(self, event: SettlementRevision) -> bool:
        """Run one idempotent reconcile/resume attempt for a claimed key."""

        notification = notification_for(event)
        try:
            self.notifier(notification)
        except Exception:
            LOGGER.exception(
                "guardian notifier failed for %s r%s", event.run_id, event.revision
            )

        try:
            decision = self.reconciler(event)
        except Exception:
            LOGGER.exception(
                "guardian reconcile failed for %s r%s", event.run_id, event.revision
            )
            return False
        if not isinstance(decision, ReconcileDecision):
            LOGGER.error(
                "guardian reconcile returned invalid decision for %s r%s",
                event.run_id,
                event.revision,
            )
            return False
        if not decision.request_resume:
            return True

        # Hard policy boundary: failed/invalid runs never resume. Finalized runs
        # have nothing to resume. Only needs-attention may reach the adapter.
        if event.tui != TUI_NEEDS_ATTENTION:
            LOGGER.warning(
                "guardian denied resume for %s settlement %s",
                event.tui,
                event.run_id,
            )
            return True
        if self.resume is None:
            LOGGER.warning(
                "guardian resume requested for %s but adapter is unavailable",
                event.run_id,
            )
            return False
        try:
            result = self.resume(event, event.idempotency_key)
        except Exception:
            LOGGER.exception("guardian resume adapter failed for %s", event.run_id)
            return False
        if isinstance(result, bool):
            accepted = result
        elif isinstance(result, Mapping):
            accepted = result.get("accepted") is True
        else:
            accepted = False
        if not accepted:
            LOGGER.warning(
                "guardian resume adapter did not accept %s (%s)",
                event.run_id,
                event.idempotency_key,
            )
            return False
        return True

    def run_forever(
        self,
        *,
        backoff: BoundedBackoff | None = None,
        sleep: Callable[[float], None] = time.sleep,
        stop_requested: Callable[[], bool] = lambda: False,
        max_connections: int | None = None,
    ) -> None:
        """Reconnect with bounded backoff; never enter a zero-delay spin."""

        retry = backoff or BoundedBackoff()
        attempts = 0
        while not stop_requested():
            stats: ConnectionStats | None = None
            try:
                stats = self.consume_connection()
            except (
                GuardianProtocolError,
                OSError,
                TimeoutError,
                urllib.error.URLError,
            ) as exc:
                LOGGER.warning("guardian SSE disconnected: %s", exc)
            attempts += 1
            if stats is not None and stats.proved_stable:
                retry.reset()
            if stop_requested() or (
                max_connections is not None and attempts >= max_connections
            ):
                return
            sleep(retry.next_delay())


@contextlib.contextmanager
def single_instance_lock(path: Path) -> Iterator[None]:
    """Own one non-blocking process lock for the guardian lifetime."""

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                raise
            raise GuardianAlreadyRunning(
                f"guardian lock is already held: {path}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def default_state_path() -> Path:
    return vibecrafted_home() / "control_plane" / "guardian" / "state.json"


def default_lock_path() -> Path:
    return vibecrafted_home() / "control_plane" / "guardian" / "guardian.lock"


def write_ready_receipt(
    path: Path,
    *,
    nonce: str,
    server_url: str,
    pid: int | None = None,
) -> Path:
    """Atomically prove that this process owns the lock and accepted SSE."""

    if not nonce:
        raise ValueError("guardian readiness nonce must not be empty")
    return atomic_write_json(
        path,
        {
            "schema": GUARDIAN_READY_SCHEMA,
            "nonce": nonce,
            "pid": os.getpid() if pid is None else pid,
            "server_url": _validate_server_url(server_url),
        },
    )


def remove_ready_receipt_if_owned(
    path: Path,
    *,
    nonce: str,
    pid: int | None = None,
) -> bool:
    """Remove only the receipt written by this exact guardian invocation."""

    expected_pid = os.getpid() if pid is None else pid
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or (
        payload.get("schema") != GUARDIAN_READY_SCHEMA
        or payload.get("nonce") != nonce
        or payload.get("pid") != expected_pid
    ):
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-url",
        default=os.environ.get("VIBECRAFTED_SERVER_URL", DEFAULT_SERVER_URL),
        help="vibecrafted-server origin (default: %(default)s)",
    )
    parser.add_argument("--state", type=Path, default=default_state_path())
    parser.add_argument("--lock", type=Path, default=default_lock_path())
    parser.add_argument(
        "--ready-file",
        type=Path,
        help="atomic launcher readiness receipt (requires --ready-nonce)",
    )
    parser.add_argument(
        "--ready-nonce",
        help="launcher nonce copied into --ready-file after a valid SSE response",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=DEFAULT_CONNECT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--recovery-timeout",
        type=float,
        default=DEFAULT_RECOVERY_TIMEOUT_SECONDS,
        help="timeout for the exact run-projection truth check",
    )
    parser.add_argument(
        "--backoff-initial",
        type=float,
        default=DEFAULT_BACKOFF_INITIAL_SECONDS,
    )
    parser.add_argument(
        "--backoff-max",
        type=float,
        default=DEFAULT_BACKOFF_MAX_SECONDS,
    )
    parser.add_argument(
        "--replay-heartbeats",
        type=int,
        default=DEFAULT_REPLAY_HEARTBEATS,
        help="reattach from byte zero after this many SSE heartbeats",
    )
    parser.add_argument(
        "--no-desktop",
        action="store_true",
        help="log f/x/n notifications without macOS Notification Center",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    state = GuardianState.load(args.state)
    if (args.ready_file is None) != (args.ready_nonce is None):
        parser.error("--ready-file and --ready-nonce must be provided together")

    def notifier(notification: GuardianNotification) -> None:
        notify_operator(notification, desktop=not args.no_desktop)

    try:
        recovery = GuardianRecoveryAdapter(
            server_url=args.server_url,
            timeout=args.recovery_timeout,
        )
        worker = GuardianWorker(
            server_url=args.server_url,
            state=state,
            notifier=notifier,
            reconciler=recovery.reconcile,
            resume=recovery.resume,
            connect_timeout=args.connect_timeout,
            replay_heartbeats=args.replay_heartbeats,
            ready_callback=(
                (
                    lambda: write_ready_receipt(
                        args.ready_file,
                        nonce=args.ready_nonce,
                        server_url=args.server_url,
                    )
                )
                if args.ready_file is not None and args.ready_nonce is not None
                else None
            ),
        )
        backoff = BoundedBackoff(args.backoff_initial, args.backoff_max)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        with single_instance_lock(args.lock):
            try:
                LOGGER.info(
                    "guardian attaching to %s/api/control/events; "
                    "guarded native recovery adapter active",
                    worker.server_url,
                )
                worker.run_forever(backoff=backoff)
            finally:
                if args.ready_file is not None and args.ready_nonce is not None:
                    remove_ready_receipt_if_owned(
                        args.ready_file,
                        nonce=args.ready_nonce,
                    )
    except GuardianAlreadyRunning as exc:
        LOGGER.error("%s", exc)
        return 75
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
