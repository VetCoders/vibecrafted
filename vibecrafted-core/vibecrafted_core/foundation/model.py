from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


SCHEMA_ID = "vibecrafted.foundation.v1"


class FoundationStatus(StrEnum):
    SEALED = "SEALED"
    BLOCKED = "BLOCKED"
    OPERATOR_WAIVER_REQUIRED = "OPERATOR_WAIVER_REQUIRED"


class EvidenceState(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    ERROR = "error"


class RepoRelation(StrEnum):
    EXACT = "exact"
    DESCENDANT = "descendant"
    BEHIND = "behind"
    DIVERGED = "diverged"
    UNRELATED = "unrelated"
    UNKNOWN = "unknown"


class PremiseStatus(StrEnum):
    VERIFIED = "verified"
    REFUTED = "refuted"
    UNKNOWN = "unknown"
    WAIVED = "waived"


class SourceStatus(StrEnum):
    BOUND = "bound"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    UNBOUND = "unbound"
    UNKNOWN = "unknown"


class CapabilityClassification(StrEnum):
    INTENDED_DELETION = "intended_deletion"
    MIGRATED = "migrated"
    SUPERSEDED = "superseded"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvidenceValue:
    state: EvidenceState
    value: Any = None
    error_kind: str = ""
    error: str = ""
    evidence: str = ""
    observed_at: str = ""

    @classmethod
    def known(
        cls, value: Any, *, evidence: str = "", observed_at: str = ""
    ) -> EvidenceValue:
        return cls(
            EvidenceState.KNOWN, value, evidence=evidence, observed_at=observed_at
        )

    @classmethod
    def unknown(
        cls, *, error_kind: str, error: str = "", evidence: str = ""
    ) -> EvidenceValue:
        return cls(
            EvidenceState.UNKNOWN, error_kind=error_kind, error=error, evidence=evidence
        )

    @classmethod
    def failed(
        cls, *, error_kind: str, error: str, evidence: str = ""
    ) -> EvidenceValue:
        return cls(
            EvidenceState.ERROR, error_kind=error_kind, error=error, evidence=evidence
        )


@dataclass(frozen=True)
class RepoAuthority:
    root: str
    authority_source: str
    authority_remote_raw: str
    authority_remote_normalized: str
    authority_ref: str
    authority_sha: EvidenceValue
    fetch: dict[str, Any]
    branch: EvidenceValue
    head: EvidenceValue
    upstream: EvidenceValue
    merge_base: EvidenceValue
    dirty: EvidenceValue
    detached: EvidenceValue
    shallow: EvidenceValue
    submodules: EvidenceValue
    worktrees: EvidenceValue
    ahead: EvidenceValue
    behind: EvidenceValue
    relation: RepoRelation
    live_only_commits: tuple[str, ...] = ()
    authority_only_commits: tuple[str, ...] = ()
    patch_equivalents: tuple[str, ...] = ()
    snapshot_ref: str = ""


@dataclass(frozen=True)
class NormativeSource:
    identity: str
    path: str
    digest: EvidenceValue
    schema_version: str = ""
    oracle_identity: str = ""
    oracle_version: str = ""
    provenance: str = "unknown"
    required_provenance: str = ""
    coverage: tuple[str, ...] = ()
    status: SourceStatus = SourceStatus.UNKNOWN
    error: str = ""


@dataclass(frozen=True)
class CriticalPremise:
    id: str
    critical: bool
    probe: dict[str, Any]
    expected: Any
    actual: EvidenceValue
    evidence_ref: str
    status: PremiseStatus
    drift_policy: str = "per_launch"
    expires_at: str = ""
    waiver: dict[str, Any] | None = None


@dataclass(frozen=True)
class CapabilityDelta:
    kind: str
    identity: str
    authority_evidence: str
    live_evidence: str = ""
    classification: CapabilityClassification = CapabilityClassification.UNKNOWN
    classification_evidence: str = ""


@dataclass(frozen=True)
class DestructiveChangeLease:
    allowed_paths: tuple[str, ...]
    max_deleted_files: int
    max_deleted_loc: int
    expected_deleted_symbols: tuple[str, ...]
    risk_class: str
    approved_budget_hash: str
    approved_by: str
    recovery_checkpoint_ref: str
    dirty_snapshot_hash: str


@dataclass(frozen=True)
class FoundationReceipt:
    receipt_id: str
    repo_id: str
    run_id: str
    created_at: str
    created_by: str
    status: FoundationStatus
    repository: RepoAuthority
    normative_sources: tuple[NormativeSource, ...] = ()
    premises: tuple[CriticalPremise, ...] = ()
    capability_delta: tuple[CapabilityDelta, ...] = ()
    lease: DestructiveChangeLease | None = None
    bindings: dict[str, Any] = field(default_factory=dict)
    supervisor_decision: dict[str, Any] = field(default_factory=dict)
    decision_reasons: tuple[str, ...] = ()
    bootstrap: dict[str, Any] = field(default_factory=dict)
    issuer: dict[str, Any] = field(default_factory=dict)
    receipt_hash: str = ""
    schema_id: str = SCHEMA_ID
