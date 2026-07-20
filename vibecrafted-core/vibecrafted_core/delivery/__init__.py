"""Typed delivery-proof kernel contracts.

The package owns data shape and state legality only. Execution, persistence,
shipping authority, and public package-root re-exports land in later waves.
"""

from .model import (
    ALLOWED_TRANSITIONS,
    DELIVERY_TRANSITIONS,
    EXECUTION_TRANSITIONS,
    PROOF_TRANSITIONS,
    ContractError,
    ContractValidationError,
    DeliveryProofContract,
    DeliveryRecord,
    DeliverySeal,
    DeliveryState,
    ExecutionEnvelope,
    ExecutionEvidence,
    ExecutionState,
    ProofResult,
    ProofState,
    UnsupportedSchemaError,
    delivery_transition_allowed,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "DELIVERY_TRANSITIONS",
    "EXECUTION_TRANSITIONS",
    "PROOF_TRANSITIONS",
    "ContractError",
    "ContractValidationError",
    "DeliveryProofContract",
    "DeliveryRecord",
    "DeliverySeal",
    "DeliveryState",
    "ExecutionEnvelope",
    "ExecutionEvidence",
    "ExecutionState",
    "ProofResult",
    "ProofState",
    "UnsupportedSchemaError",
    "delivery_transition_allowed",
]
