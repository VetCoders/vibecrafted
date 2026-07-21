"""Settlement layer — typed terminal for every finished run.

Contract (canonical draft v1, 2026-07-21):

**Artifact without settlement = automatically ``needs_attention`` (TUI ``n``),
never silence.**

The delivery-proof kernel (``DeliveryState`` / ``ProofState``) answers "was
the claim sealed?" Settlement answers a different question: "where does this
run sit on the operator board (f/x/n)?" Those axes are deliberately separate.
``exit_code == 0`` alone can never produce ``FINALIZED``.

Terminals (1:1 to TUI f/x/n; INVALID folds into ``x`` with reason):

- ``finalized`` (f) — claim evidence + report path + proof/seal, or explicit waive
- ``failed`` (x) — proof failed, death without delivery, or INVALID folded
- ``needs_attention`` (n) — default for unsealed reports, stalls, contradictions,
  orphans, and every unreadable signal
- ``invalid`` (x) — schema/contract invalidation, folded into the failed TUI cell

Settlement is written into the board projection (and, when a meta path is known,
into the run meta) so the supervisor's knowledge survives the supervisor.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .run_triage import (
    VERDICT_FAILED,
    VERDICT_FINALIZED,
    VERDICT_NEEDS_ATTENTION,
    read_run_signals,
)

__all__ = [
    "SettlementVerdict",
    "Settlement",
    "TUI_FAILED",
    "TUI_FINALIZED",
    "TUI_NEEDS_ATTENTION",
    "SETTLED_TERMINALS",
    "board_fxn_counts",
    "can_archive",
    "claim_digest_from_payload",
    "orphan_markdown_paths",
    "persist_await_verdict",
    "persist_settlement_to_meta",
    "settle_payload",
    "settlement_from_payload",
    "tui_key_for",
]

TUI_FINALIZED = "f"
TUI_FAILED = "x"
TUI_NEEDS_ATTENTION = "n"

# Operator waive must be explicit and traced — never inferred from exit 0.
_WAIVE_KEYS = ("settlement_waive", "operator_waive", "waive_settlement")


class SettlementVerdict(str, Enum):
    FINALIZED = "finalized"
    FAILED = "failed"
    NEEDS_ATTENTION = "needs_attention"
    INVALID = "invalid"


SETTLED_TERMINALS = frozenset(v.value for v in SettlementVerdict)


def tui_key_for(verdict: SettlementVerdict | str) -> str:
    """Map a settlement terminal onto the TUI f/x/n cell."""
    value = (
        (
            verdict.value
            if isinstance(verdict, SettlementVerdict)
            else str(verdict or "")
        )
        .strip()
        .lower()
    )
    if value == SettlementVerdict.FINALIZED.value:
        return TUI_FINALIZED
    if value in {
        SettlementVerdict.FAILED.value,
        SettlementVerdict.INVALID.value,
    }:
        return TUI_FAILED
    return TUI_NEEDS_ATTENTION


@dataclass(frozen=True)
class Settlement:
    """One settled terminal for a finished run."""

    verdict: SettlementVerdict
    reason: str
    settled_at: str
    source: str = "auto"
    claim_digest: str = ""
    waived: bool = False
    await_rc: int | None = None
    await_outcome: str = ""

    @property
    def tui_key(self) -> str:
        return tui_key_for(self.verdict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "settlement_verdict": self.verdict.value,
            "settlement_reason": self.reason,
            "settlement_at": self.settled_at,
            "settlement_source": self.source,
            "settlement_tui": self.tui_key,
            "settlement_waived": self.waived,
            "settlement_claim_digest": self.claim_digest,
        }
        if self.await_rc is not None:
            payload["await_rc"] = self.await_rc
        if self.await_outcome:
            payload["await_outcome"] = self.await_outcome
            payload["await_settled_at"] = self.settled_at
        return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "waived"}


def claim_digest_from_payload(payload: Mapping[str, Any]) -> str:
    """Stable digest of the run's claim surface (brief / mission / prompt).

    Empty when no claim text is present — FINALIZED then requires an explicit
    waive, never a silent promotion.
    """
    for key in (
        "claim_digest",
        "settlement_claim_digest",
        "mission_digest",
        "brief_digest",
    ):
        raw = str(payload.get(key) or "").strip()
        if raw:
            return raw

    chunks: list[str] = []
    for key in ("claim", "mission", "brief", "prompt", "file", "skill", "agent"):
        value = payload.get(key)
        if value not in (None, ""):
            chunks.append(f"{key}={value}")
    if not chunks:
        return ""
    material = "\n".join(chunks).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def _has_operator_waive(payload: Mapping[str, Any]) -> bool:
    for key in _WAIVE_KEYS:
        if _as_bool(payload.get(key)):
            return True
    settlement = payload.get("settlement")
    if isinstance(settlement, Mapping) and _as_bool(settlement.get("waived")):
        return True
    return False


def _proof_passed(payload: Mapping[str, Any]) -> bool:
    proof = str(payload.get("proof_state") or "").strip().lower()
    if proof == "passed":
        return True
    delivery = str(payload.get("delivery_state") or "").strip().lower()
    return delivery == "sealed"


def _proof_failed(payload: Mapping[str, Any]) -> bool:
    proof = str(payload.get("proof_state") or "").strip().lower()
    if proof in {"failed", "invalid"}:
        return True
    delivery = str(payload.get("delivery_state") or "").strip().lower()
    return delivery == "invalidated"


def _is_terminal(payload: Mapping[str, Any]) -> bool:
    state = str(payload.get("state") or payload.get("status") or "").strip().lower()
    if state in {
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
        "stalled",
        "killed_by_operator",
        "process_dead",
    }:
        return True
    if str(payload.get("liveness") or "") == "terminal":
        return True
    exit_code = payload.get("exit_code")
    if exit_code is None or exit_code == "":
        return False
    try:
        int(exit_code)
    except (TypeError, ValueError):
        return False
    return True


def settlement_from_payload(payload: Mapping[str, Any]) -> Settlement | None:
    """Read a previously written settlement, or None if absent/unreadable."""
    raw = str(payload.get("settlement_verdict") or "").strip().lower()
    if not raw:
        nested = payload.get("settlement")
        if isinstance(nested, Mapping):
            raw = str(nested.get("verdict") or "").strip().lower()
            if raw:
                try:
                    verdict = SettlementVerdict(raw)
                except ValueError:
                    return None
                return Settlement(
                    verdict=verdict,
                    reason=str(nested.get("reason") or ""),
                    settled_at=str(nested.get("settled_at") or ""),
                    source=str(nested.get("source") or "persisted"),
                    claim_digest=str(nested.get("claim_digest") or ""),
                    waived=_as_bool(nested.get("waived")),
                    await_rc=_coerce_int(nested.get("await_rc")),
                    await_outcome=str(nested.get("await_outcome") or ""),
                )
        return None
    try:
        verdict = SettlementVerdict(raw)
    except ValueError:
        return None
    return Settlement(
        verdict=verdict,
        reason=str(payload.get("settlement_reason") or ""),
        settled_at=str(payload.get("settlement_at") or ""),
        source=str(payload.get("settlement_source") or "persisted"),
        claim_digest=str(payload.get("settlement_claim_digest") or ""),
        waived=_as_bool(payload.get("settlement_waived")),
        await_rc=_coerce_int(payload.get("await_rc")),
        await_outcome=str(payload.get("await_outcome") or ""),
    )


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def settle_payload(
    payload: Mapping[str, Any],
    *,
    now: str | None = None,
    force: bool = False,
    source: str = "auto",
) -> Settlement | None:
    """Derive the settlement terminal for a run projection.

    Returns ``None`` for still-live runs (no terminal yet). Every finished run
    returns exactly one of the four terminals — never silence.
    """
    existing = settlement_from_payload(payload)
    if existing is not None and not force:
        # Operator waive and await-persisted settlements are sticky.
        if (
            existing.source in {"operator_waive", "await", "orphan_scan"}
            or existing.waived
        ):
            return existing
        # Auto settlements may be recomputed as more evidence lands (seal late).
        if existing.source not in {"auto", "persisted", ""}:
            return existing

    if not _is_terminal(payload):
        return None

    settled_at = now or _now_iso()
    claim_digest = claim_digest_from_payload(payload)
    waived = _has_operator_waive(payload)

    # Hard invalidation from the delivery kernel — folds into x.
    if _proof_failed(payload):
        return Settlement(
            verdict=SettlementVerdict.INVALID
            if str(payload.get("proof_state") or "").lower() == "invalid"
            or str(payload.get("delivery_state") or "").lower() == "invalidated"
            else SettlementVerdict.FAILED,
            reason="proof_or_delivery_failed",
            settled_at=settled_at,
            source=source,
            claim_digest=claim_digest,
            waived=False,
        )

    # Board projections use `latest_report` / `latest_transcript`; launcher
    # meta uses `report` / `transcript`. Normalize before classifying.
    signal_payload = dict(payload)
    if not str(signal_payload.get("report") or "").strip():
        alt = str(signal_payload.get("latest_report") or "").strip()
        if alt:
            signal_payload["report"] = alt
    if not str(signal_payload.get("transcript") or "").strip():
        alt = str(signal_payload.get("latest_transcript") or "").strip()
        if alt:
            signal_payload["transcript"] = alt
    signals = read_run_signals(signal_payload)
    classification = signals.classify()

    if waived:
        return Settlement(
            verdict=SettlementVerdict.FINALIZED,
            reason="operator_waive",
            settled_at=settled_at,
            source="operator_waive",
            claim_digest=claim_digest,
            waived=True,
        )

    if classification.verdict == VERDICT_FAILED:
        return Settlement(
            verdict=SettlementVerdict.FAILED,
            reason=classification.reason,
            settled_at=settled_at,
            source=source,
            claim_digest=claim_digest,
        )

    if classification.verdict == VERDICT_NEEDS_ATTENTION:
        return Settlement(
            verdict=SettlementVerdict.NEEDS_ATTENTION,
            reason=classification.reason,
            settled_at=settled_at,
            source=source,
            claim_digest=claim_digest,
        )

    # classify_run says finalized (exit 0 + delivered state + report). Contract
    # still requires claim + proof/seal — otherwise park as n.
    if classification.verdict == VERDICT_FINALIZED:
        if not claim_digest:
            return Settlement(
                verdict=SettlementVerdict.NEEDS_ATTENTION,
                reason="finalized_candidate_without_claim",
                settled_at=settled_at,
                source=source,
                claim_digest="",
            )
        if not _proof_passed(payload):
            return Settlement(
                verdict=SettlementVerdict.NEEDS_ATTENTION,
                reason="report_without_seal",
                settled_at=settled_at,
                source=source,
                claim_digest=claim_digest,
            )
        return Settlement(
            verdict=SettlementVerdict.FINALIZED,
            reason="claim_report_and_seal",
            settled_at=settled_at,
            source=source,
            claim_digest=claim_digest,
        )

    # Unreachable under current classify_run, but fail closed.
    return Settlement(
        verdict=SettlementVerdict.NEEDS_ATTENTION,
        reason=f"unmapped_classification:{classification.verdict}",
        settled_at=settled_at,
        source=source,
        claim_digest=claim_digest,
    )


def can_archive(payload: Mapping[str, Any]) -> bool:
    """Settlement precedes gc: refuse to archive unsettled runs.

    A run with no settlement_verdict is never collectable — it must be parked
    as needs_attention first. Any of the four terminals unlocks archive.
    """
    settlement = settlement_from_payload(payload)
    if settlement is None:
        return False
    return settlement.verdict.value in SETTLED_TERMINALS


def board_fxn_counts(runs: list[Mapping[str, Any]]) -> dict[str, int]:
    """Count TUI f/x/n cells from the settlement axis only.

    Never recomputed from exit codes or raw lifecycle states. Unsettled
    terminal runs count as ``n`` (never silence). Live runs are ignored.
    """
    counts = {TUI_FINALIZED: 0, TUI_FAILED: 0, TUI_NEEDS_ATTENTION: 0}
    for run in runs:
        settlement = settlement_from_payload(run)
        if settlement is None:
            if _is_terminal(run):
                counts[TUI_NEEDS_ATTENTION] += 1
            continue
        counts[settlement.tui_key] += 1
    return counts


_UNTITLED_RE = re.compile(r"(?i)^untitled.*\.md$")


def orphan_markdown_paths(artifacts_root: Path) -> list[Path]:
    """List bare ``Untitled*.md`` artifacts (no run_id binding).

    Contract rule 6: bare markdown is either uncreatable or lands directly
    in ``n``. Legacy orphans are listed here for settlement as ``n``.
    """
    if not artifacts_root.is_dir():
        return []
    found: list[Path] = []
    for path in artifacts_root.rglob("*.md"):
        if _UNTITLED_RE.match(path.name):
            found.append(path)
    return sorted(found)


def persist_settlement_to_meta(meta_path: Path, settlement: Settlement) -> bool:
    """Merge settlement fields into a run meta.json. Best-effort, never raises."""
    try:
        raw = meta_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return False
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False
    payload.update(settlement.to_payload())
    payload["settlement"] = {
        "verdict": settlement.verdict.value,
        "reason": settlement.reason,
        "settled_at": settlement.settled_at,
        "source": settlement.source,
        "claim_digest": settlement.claim_digest,
        "waived": settlement.waived,
        "tui": settlement.tui_key,
        "await_rc": settlement.await_rc,
        "await_outcome": settlement.await_outcome,
    }
    try:
        meta_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def persist_await_verdict(
    meta_path: Path | None,
    *,
    rc: int | None,
    outcome: str,
    worker_alive: bool,
    reason: str,
    settled_at: str | None = None,
) -> dict[str, Any]:
    """Persist the supervisor await verdict so it survives the supervisor.

    Returns the fields to merge into a board projection even when meta is
    missing (projection-only write).
    """
    stamp = settled_at or _now_iso()
    fields: dict[str, Any] = {
        "await_rc": rc,
        "await_outcome": outcome,
        "await_reason": reason,
        "await_worker_alive": bool(worker_alive),
        "await_settled_at": stamp,
    }
    if meta_path is not None and meta_path.is_file():
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.update(fields)
                meta_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return fields
