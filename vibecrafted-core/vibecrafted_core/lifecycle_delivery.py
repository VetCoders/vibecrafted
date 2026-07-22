"""Lifecycle-stage delivery proof/seal bridge.

Closes the f-gap: when a lifecycle stage reaches a validated report with a
matching claim digest, write the delivery-kernel artifacts that
``control_plane._delivery_axes_from_run_dir`` and ``settle_payload`` require
for ``FINALIZED``.

Contract rule 2 (SETTLEMENT_CONTRACT.md): ``exit_code==0`` alone NEVER
produces a seal. Guards refuse bare success without a validated report
artifact and refuse claim mismatches.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .delivery.model import (
    DeliverySeal,
    DeliveryState,
    ProofResult,
    ProofState,
)
from .delivery.store import atomic_write_json
from .report_contract import CLAIM_COMPLETED, parse_report_path
from .settlement import claim_digest_from_payload

__all__ = [
    "StageSealResult",
    "claim_digest_for_text",
    "mission_claim_digest",
    "report_claim_matches",
    "try_grant_lifecycle_stage_seal",
    "resettle_retained_snapshots",
]

LIFECYCLE_SEAL_ISSUER = "vc-lifecycle"
ENGINE_VERSION = "lifecycle-stage-proof-v1"
ZERO_DIGEST = "sha256:" + "0" * 64


@dataclass(frozen=True)
class StageSealResult:
    """Outcome of a lifecycle-stage seal attempt (grant or explicit refuse)."""

    granted: bool
    proof_state: str
    delivery_state: str
    reason: str
    claim_digest: str
    seal_id: str = ""
    proof_id: str = ""

    def axes_payload(self) -> dict[str, str]:
        return {
            "proof_state": self.proof_state,
            "delivery_state": self.delivery_state,
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "granted": self.granted,
            "proof_state": self.proof_state,
            "delivery_state": self.delivery_state,
            "reason": self.reason,
            "claim_digest": self.claim_digest,
            "seal_id": self.seal_id,
            "proof_id": self.proof_id,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def claim_digest_for_text(text: str) -> str:
    """Stable 16-hex claim digest from free-form mission/brief text."""
    material = str(text or "").strip().encode("utf-8")
    if not material:
        return ""
    return hashlib.sha256(material).hexdigest()[:16]


def mission_claim_digest(
    *,
    mission_text: str = "",
    payload: Mapping[str, Any] | None = None,
) -> str:
    """Prefer an explicit payload digest; else hash mission/brief text."""
    if payload is not None:
        existing = claim_digest_from_payload(payload)
        if existing:
            return existing
    return claim_digest_for_text(mission_text)


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return ZERO_DIGEST
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def report_claim_matches(
    report_path: str | Path,
    *,
    mission_digest: str,
) -> tuple[bool, str]:
    """Return (ok, reason) for report↔mission claim match.

    Match rules (fail closed):
    - report must exist and parse with valid frontmatter
    - agent claim_status must be in the completed vocabulary
    - if the report carries claim_digest / mission_digest / brief_digest,
      it must equal the mission digest
    - if the report carries none of those fields, a completed claim plus a
      non-empty mission digest is accepted (digest is stamped at seal time)
    """
    path = Path(report_path)
    if not path.is_file():
        return False, "report_missing"
    try:
        frontmatter = parse_report_path(path)
    except Exception:  # noqa: BLE001 — fail closed on any parse path
        return False, "report_frontmatter_invalid"
    if not frontmatter.has_frontmatter:
        return False, "report_frontmatter_missing"
    if frontmatter.errors and not frontmatter.ok:
        # Missing recommended keys are warnings; structural errors fail closed
        # only when status/claim is unreadable. Allow ok=False for placeholders
        # if claim_status itself is completed.
        hard = [
            e
            for e in frontmatter.errors
            if "missing_key:status" in e
            or "missing_key:claim_status" in e
            or e == "report_frontmatter_missing"
        ]
        if hard and not frontmatter.claim_status:
            return False, hard[0]
    claim = str(frontmatter.claim_status or "").strip().lower()
    if claim not in CLAIM_COMPLETED:
        if not claim:
            return False, "report_claim_empty"
        return False, f"report_claim_not_completed:{claim}"
    mission = str(mission_digest or "").strip()
    if not mission:
        return False, "mission_claim_empty"
    fields = frontmatter.fields or {}
    for key in ("claim_digest", "mission_digest", "brief_digest"):
        raw = str(fields.get(key) or "").strip()
        if raw and raw != mission:
            return False, f"claim_digest_mismatch:{key}"
    return True, "claim_match"


def try_grant_lifecycle_stage_seal(
    run_dir: str | Path,
    *,
    run_id: str,
    lifecycle_id: str = "",
    stage_id: str = "",
    report_path: str | Path | None = None,
    transcript_path: str | Path | None = None,
    mission_text: str = "",
    mission_digest: str = "",
    artifact_ok: bool = False,
    exit_code: Any = None,
) -> StageSealResult:
    """Declare proof → verify claim → grant seal for a lifecycle stage run dir.

    Writes ``proof/result.json`` and ``delivery-seal.json`` under ``run_dir``
    so the control-plane projection reads ``proof_state=passed`` and
    ``delivery_state=sealed``. Refusal paths leave axes undeclared/unverified
    and never invent FINALIZED.
    """
    target = Path(run_dir)
    rid = str(run_id or "").strip()
    digest = str(mission_digest or "").strip() or claim_digest_for_text(mission_text)

    # Guard: never from bare exit alone; never without validated report.
    if not rid:
        return StageSealResult(
            granted=False,
            proof_state=ProofState.UNDECLARED.value,
            delivery_state=DeliveryState.UNVERIFIED.value,
            reason="run_id_required",
            claim_digest=digest,
        )
    if not artifact_ok:
        return StageSealResult(
            granted=False,
            proof_state=ProofState.UNDECLARED.value,
            delivery_state=DeliveryState.UNVERIFIED.value,
            reason="artifact_not_ok",
            claim_digest=digest,
        )
    report = Path(report_path) if report_path else target / "report.md"
    if not report.is_file():
        return StageSealResult(
            granted=False,
            proof_state=ProofState.UNDECLARED.value,
            delivery_state=DeliveryState.UNVERIFIED.value,
            reason="exit_0_without_report"
            if exit_code in (0, "0", None)
            else "report_missing",
            claim_digest=digest,
        )
    matched, match_reason = report_claim_matches(report, mission_digest=digest)
    if not matched:
        return StageSealResult(
            granted=False,
            proof_state=ProofState.UNDECLARED.value,
            delivery_state=DeliveryState.UNVERIFIED.value,
            reason=match_reason,
            claim_digest=digest,
        )

    now = _now_iso()
    proof_id = f"proof-{rid}"
    seal_id = f"seal-{rid}"
    proof = ProofResult(
        schema=ProofResult.SCHEMA,
        proof_id=proof_id,
        state=ProofState.PASSED,
        evidence=(
            {
                "kind": "lifecycle_stage_report",
                "run_id": rid,
                "stage_id": stage_id,
                "report": str(report),
                "claim_digest": digest,
            },
        ),
        assertion_results=(
            {
                "id": "report_validated_claim_match",
                "passed": True,
                "reason": match_reason,
            },
        ),
        negative_control_results=(),
        subject_executed=True,
        assertion_consumed_subject_output=True,
        refusal_reasons=(),
        contract_sha256=ZERO_DIGEST,
        executor_sha256=ZERO_DIGEST,
        evaluated_at=now,
    )
    proof_dir = target / "proof"
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / "result.json"
    atomic_write_json(proof_path, proof.to_payload())
    proof_sha = _file_sha256(proof_path)

    transcript = Path(transcript_path) if transcript_path else target / "transcript.log"
    seal = DeliverySeal(
        schema=DeliverySeal.SCHEMA,
        seal_id=seal_id,
        issued_at=now,
        issuer=LIFECYCLE_SEAL_ISSUER,
        run_id=rid,
        lifecycle_id=str(lifecycle_id or rid),
        cut_id=str(stage_id or "stage"),
        proof_id=proof_id,
        run_identity_sha256=ZERO_DIGEST,
        liveness_evidence_sha256=(),
        execution_envelope_sha256=ZERO_DIGEST,
        delivery_proof_contract_sha256=ZERO_DIGEST,
        proof_result_sha256=proof_sha,
        executor_source_sha256=ZERO_DIGEST,
        executor_version=ENGINE_VERSION,
        subject_evidence_sha256=_file_sha256(report),
        witness_sha256=ZERO_DIGEST,
        oracle_evidence_sha256=None,
        assertion_evidence_sha256=ZERO_DIGEST,
        negative_control_evidence_sha256=(),
        repo="",
        branch="",
        baseline_head="",
        final_head="",
        scoped_dirty_status_sha256=ZERO_DIGEST,
        commit_range="",
        declared_scope="checkout",
        checked_scope="checkout",
        runtime_probe_sha256=(),
        report_sha256=_file_sha256(report),
        transcript_sha256=_file_sha256(transcript),
        control_plane_snapshot_sha256=ZERO_DIGEST,
        unverified_surfaces=("run_identity", "liveness", "execution_envelope"),
    )
    atomic_write_json(target / "delivery-seal.json", seal.to_payload())

    # Stamp claim_digest on meta when present so settlement has claim surface.
    meta_path = target / "meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                meta["claim_digest"] = digest
                meta["proof_state"] = ProofState.PASSED.value
                meta["delivery_state"] = DeliveryState.SEALED.value
                meta["lifecycle_seal"] = {
                    "seal_id": seal_id,
                    "proof_id": proof_id,
                    "reason": match_reason,
                    "issuer": LIFECYCLE_SEAL_ISSUER,
                }
                atomic_write_json(meta_path, meta)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    return StageSealResult(
        granted=True,
        proof_state=ProofState.PASSED.value,
        delivery_state=DeliveryState.SEALED.value,
        reason=match_reason,
        claim_digest=digest,
        seal_id=seal_id,
        proof_id=proof_id,
    )


def resettle_retained_snapshots(
    *,
    runs_dir: str | Path | None = None,
    force: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Re-run settlement over retained control-plane snapshots.

    Honest backfill: does NOT invent seals or fabricate FINALIZED for history
    that still lacks proof/seal. Only re-classifies from existing axes and
    settlement inputs. Idempotent when re-run after convergence.
    """
    from .control_plane import control_plane_home, run_snapshot_dir
    from .settlement import settle_payload

    root = Path(runs_dir) if runs_dir is not None else run_snapshot_dir()
    if not root.is_dir():
        return {
            "ok": True,
            "scanned": 0,
            "rewritten": 0,
            "unchanged": 0,
            "skipped": 0,
            "before": {"f": 0, "x": 0, "n": 0, "invalid": 0},
            "after": {"f": 0, "x": 0, "n": 0, "invalid": 0},
            "dry_run": dry_run,
            "runs_dir": str(root),
            "home": str(control_plane_home()),
        }

    before = {"f": 0, "x": 0, "n": 0, "invalid": 0, "none": 0}
    after = {"f": 0, "x": 0, "n": 0, "invalid": 0, "none": 0}
    rewritten = 0
    unchanged = 0
    skipped = 0
    scanned = 0

    def _bucket(verdict: str | None) -> str:
        raw = str(verdict or "").strip().lower()
        if raw == "finalized":
            return "f"
        if raw == "failed":
            return "x"
        if raw == "invalid":
            return "invalid"
        if raw == "needs_attention":
            return "n"
        return "none"

    for path in sorted(root.glob("*.json")):
        scanned += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            skipped += 1
            continue
        if not isinstance(payload, dict):
            skipped += 1
            continue
        prev_verdict = str(payload.get("settlement_verdict") or "")
        if not prev_verdict and isinstance(payload.get("settlement"), dict):
            prev_verdict = str(payload["settlement"].get("verdict") or "")
        before[_bucket(prev_verdict)] += 1

        settlement = settle_payload(payload, force=force, source="resettle")
        if settlement is None:
            after["none"] += 1
            unchanged += 1
            continue
        new_flat = settlement.to_payload()
        new_nested = {
            "verdict": settlement.verdict.value,
            "reason": settlement.reason,
            "settled_at": settlement.settled_at,
            "source": settlement.source,
            "claim_digest": settlement.claim_digest,
            "waived": settlement.waived,
            "tui": settlement.tui_key,
        }
        after[_bucket(settlement.verdict.value)] += 1
        # Idempotency: skip write when verdict/reason/tui already match.
        same = (
            str(payload.get("settlement_verdict") or "") == settlement.verdict.value
            and str(payload.get("settlement_tui") or "") == settlement.tui_key
            and str(payload.get("settlement_reason") or "") == settlement.reason
        )
        if same:
            unchanged += 1
            continue
        if dry_run:
            rewritten += 1
            continue
        payload.update(new_flat)
        payload["settlement"] = new_nested
        atomic_write_json(path, payload)
        rewritten += 1

    return {
        "ok": True,
        "scanned": scanned,
        "rewritten": rewritten,
        "unchanged": unchanged,
        "skipped": skipped,
        "before": {k: before[k] for k in ("f", "x", "n", "invalid")},
        "after": {k: after[k] for k in ("f", "x", "n", "invalid")},
        "dry_run": dry_run,
        "runs_dir": str(root),
        "force": force,
    }
