from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .model import CriticalPremise, EvidenceState, EvidenceValue, PremiseStatus


def evaluate_premises(
    root: str | Path, declarations: Iterable[dict[str, Any]]
) -> tuple[CriticalPremise, ...]:
    repo = Path(root).resolve()
    results: list[CriticalPremise] = []
    now = datetime.now(UTC)
    for item in declarations:
        probe = dict(item.get("probe") or {})
        kind = str(probe.get("kind") or "")
        expected = item.get("expected")
        actual = EvidenceValue.unknown(error_kind="unsupported_probe", error=kind)
        if kind == "path_exists":
            target = (repo / str(probe.get("path") or "")).resolve()
            actual = EvidenceValue.known(target.exists(), evidence=str(target))
        elif kind == "literal_file_value":
            target = (repo / str(probe.get("path") or "")).resolve()
            try:
                actual = EvidenceValue.known(
                    target.read_text(encoding="utf-8").strip(), evidence=str(target)
                )
            except OSError as exc:
                actual = EvidenceValue.failed(
                    error_kind="probe_read_error", error=str(exc), evidence=str(target)
                )
        expires_at = str(item.get("expires_at") or "")
        expired = False
        if expires_at:
            try:
                expired = (
                    datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= now
                )
            except ValueError:
                actual = EvidenceValue.failed(
                    error_kind="invalid_expiration", error=expires_at
                )
        status = PremiseStatus.UNKNOWN
        if expired:
            status = PremiseStatus.UNKNOWN
        elif actual.state is EvidenceState.KNOWN:
            status = (
                PremiseStatus.VERIFIED
                if actual.value == expected
                else PremiseStatus.REFUTED
            )
        results.append(
            CriticalPremise(
                id=str(item.get("id") or "unnamed"),
                critical=bool(item.get("critical", True)),
                probe=probe,
                expected=expected,
                actual=actual,
                evidence_ref=str(item.get("evidence_ref") or actual.evidence),
                status=status,
                drift_policy=str(item.get("drift_policy") or "per_launch"),
                expires_at=expires_at,
            )
        )
    return tuple(results)


def premise_set_hash(premises: Iterable[CriticalPremise]) -> str:
    payload = [
        {
            "id": premise.id,
            "critical": premise.critical,
            "probe": premise.probe,
            "expected": premise.expected,
            "actual": premise.actual.value,
            "actual_state": premise.actual.state,
            "status": premise.status,
            "drift_policy": premise.drift_policy,
            "expires_at": premise.expires_at,
        }
        for premise in premises
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
