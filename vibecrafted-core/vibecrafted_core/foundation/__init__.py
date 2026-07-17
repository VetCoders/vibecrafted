"""Foundation Seal: fail-closed authority and mutation preflight."""

from .model import (
    CapabilityDelta,
    CriticalPremise,
    DestructiveChangeLease,
    EvidenceState,
    EvidenceValue,
    FoundationReceipt,
    FoundationStatus,
    NormativeSource,
    RepoAuthority,
    RepoRelation,
)
from .service import (
    FoundationError,
    preflight_launch,
    receipt_hash,
    seal_repository,
    verify_receipt,
)

__all__ = [
    "CapabilityDelta",
    "CriticalPremise",
    "DestructiveChangeLease",
    "EvidenceState",
    "EvidenceValue",
    "FoundationError",
    "FoundationReceipt",
    "FoundationStatus",
    "NormativeSource",
    "RepoAuthority",
    "RepoRelation",
    "preflight_launch",
    "receipt_hash",
    "seal_repository",
    "verify_receipt",
]
