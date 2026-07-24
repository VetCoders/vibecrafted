"""Canonical delivery-proof contracts and orthogonal state axes.

This module is the ONE declarative authority for delivery-proof semantics.
Execution, proof, and delivery are deliberately separate facts: a successful
process exit cannot silently become proof, and proof cannot silently become a
delivery seal.

All cross-surface records are frozen, versioned, canonically serializable, and
fail closed when a reader encounters an unknown schema. Wall-clock observation
fields remain available in payloads but are excluded from content identity so
replaying the same immutable evidence produces the same digest.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, ClassVar, Self, cast


class ContractError(ValueError):
    """Base error for invalid delivery kernel contracts."""


class UnsupportedSchemaError(ContractError):
    """Raised when a payload uses a schema this reader cannot interpret."""


class ContractValidationError(ContractError):
    """Raised when a known-schema payload violates its proof contract."""


class ExecutionState(str, Enum):
    CREATED = "created"
    LAUNCHED = "launched"
    RUNNING = "running"
    EXITED = "exited"
    INTERRUPTED = "interrupted"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class ProofState(str, Enum):
    UNDECLARED = "undeclared"
    DECLARED = "declared"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    INVALID = "invalid"
    STALE = "stale"


class DeliveryState(str, Enum):
    UNVERIFIED = "unverified"
    DELIVERED = "delivered"
    SEALED = "sealed"
    INVALIDATED = "invalidated"


EXECUTION_TRANSITIONS: Mapping[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.CREATED: frozenset({ExecutionState.LAUNCHED, ExecutionState.FAILED}),
    ExecutionState.LAUNCHED: frozenset(
        {
            ExecutionState.RUNNING,
            ExecutionState.INTERRUPTED,
            ExecutionState.TIMED_OUT,
            ExecutionState.FAILED,
        }
    ),
    ExecutionState.RUNNING: frozenset(
        {
            ExecutionState.EXITED,
            ExecutionState.INTERRUPTED,
            ExecutionState.TIMED_OUT,
            ExecutionState.FAILED,
        }
    ),
    ExecutionState.EXITED: frozenset(),
    ExecutionState.INTERRUPTED: frozenset(),
    ExecutionState.TIMED_OUT: frozenset(),
    ExecutionState.FAILED: frozenset(),
}

PROOF_TRANSITIONS: Mapping[ProofState, frozenset[ProofState]] = {
    ProofState.UNDECLARED: frozenset({ProofState.DECLARED}),
    ProofState.DECLARED: frozenset(
        {ProofState.RUNNING, ProofState.INVALID, ProofState.STALE}
    ),
    ProofState.RUNNING: frozenset(
        {
            ProofState.PASSED,
            ProofState.FAILED,
            ProofState.INVALID,
            ProofState.STALE,
        }
    ),
    ProofState.PASSED: frozenset({ProofState.STALE}),
    ProofState.FAILED: frozenset(),
    ProofState.INVALID: frozenset(),
    ProofState.STALE: frozenset(),
}

DELIVERY_TRANSITIONS: Mapping[DeliveryState, frozenset[DeliveryState]] = {
    DeliveryState.UNVERIFIED: frozenset({DeliveryState.DELIVERED}),
    DeliveryState.DELIVERED: frozenset(
        {DeliveryState.SEALED, DeliveryState.INVALIDATED}
    ),
    DeliveryState.SEALED: frozenset({DeliveryState.INVALIDATED}),
    DeliveryState.INVALIDATED: frozenset(),
}

ALLOWED_TRANSITIONS: Mapping[str, Mapping[Any, frozenset[Any]]] = {
    "execution": EXECUTION_TRANSITIONS,
    "proof": PROOF_TRANSITIONS,
    "delivery": DELIVERY_TRANSITIONS,
}


def delivery_transition_allowed(
    *,
    current: DeliveryState,
    target: DeliveryState,
    execution_state: ExecutionState,
    execution_exit_code: int | None,
    proof_state: ProofState,
) -> bool:
    """Return whether a delivery transition is legal with cross-axis evidence.

    Advancing to ``delivered`` or ``sealed`` requires a clean process exit and
    a separately passed proof. Failure terminals can never advance delivery.
    Invalidation remains available as a fail-closed downgrade.
    """

    if target not in DELIVERY_TRANSITIONS[current]:
        return False
    if target is DeliveryState.INVALIDATED:
        return True
    return (
        execution_state is ExecutionState.EXITED
        and execution_exit_code == 0
        and proof_state is ProofState.PASSED
    )


def _payload_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _payload_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _payload_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_payload_value(item) for item in value]
    return value


class _ContractModel:
    SCHEMA: ClassVar[str]
    IDENTITY_EXCLUDED_FIELDS: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def _normalize_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        return dict(payload)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Self:
        if not isinstance(payload, Mapping):
            raise ContractValidationError(f"{cls.__name__} payload must be a mapping")
        schema = payload.get("schema")
        if schema != cls.SCHEMA:
            raise UnsupportedSchemaError(
                f"unsupported {cls.__name__} schema {schema!r}; expected {cls.SCHEMA!r}"
            )
        allowed = {item.name for item in fields(cast(Any, cls))}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ContractValidationError(
                f"unknown {cls.__name__} fields: {', '.join(unknown)}"
            )
        try:
            return cls(**cls._normalize_payload(payload))
        except ContractError:
            raise
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                f"invalid {cls.__name__} payload: {exc}"
            ) from exc

    def to_payload(self) -> dict[str, Any]:
        return {
            item.name: _payload_value(getattr(self, item.name))
            for item in fields(cast(Any, self))
        }

    def identity_payload(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.to_payload().items()
            if key not in self.IDENTITY_EXCLUDED_FIELDS
        }

    def canonical_json(self) -> str:
        """Return compact canonical JSON for this record's immutable identity."""
        return json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def content_digest(self) -> str:
        canonical_bytes = self.canonical_json().encode("utf-8")
        return f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"


@dataclass(frozen=True)
class ExecutionEnvelope(_ContractModel):
    SCHEMA: ClassVar[str] = "vibecrafted.execution-envelope.v1"

    schema: str
    agent: str
    repo: str
    root: str
    branch: str
    expected_head: str
    upstream_ref: str
    upstream_relation: Mapping[str, int]
    dirty_policy: str
    baseline_status_digest: str
    protected_paths: tuple[str, ...]
    owned_paths: tuple[str, ...]
    brief_path: str
    brief_sha256: str

    @classmethod
    def _normalize_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["protected_paths"] = tuple(normalized["protected_paths"])
        normalized["owned_paths"] = tuple(normalized["owned_paths"])
        return normalized


@dataclass(frozen=True)
class DeliveryProofContract(_ContractModel):
    SCHEMA: ClassVar[str] = "vibecrafted.delivery-proof.v1"

    schema: str
    id: str
    execution_envelope_sha256: str
    subject: Mapping[str, Any]
    witness: Mapping[str, Any]
    oracle: Mapping[str, Any] | None
    assertion: Mapping[str, Any]
    negative_controls: tuple[Mapping[str, Any], ...]
    delivery_scope: str
    integration_target: str | None
    runtime_probes: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        subject_id = self.subject.get("producer_id")
        if not isinstance(subject_id, str) or not subject_id:
            raise ContractValidationError("subject requires a non-empty producer_id")
        if self.oracle is not None:
            oracle_id = self.oracle.get("producer_id")
            if not isinstance(oracle_id, str) or not oracle_id:
                raise ContractValidationError("oracle requires a non-empty producer_id")
            if oracle_id == subject_id:
                raise ContractValidationError(
                    "subject and oracle require a distinct producer_id"
                )
        elif (
            not self.witness
            or not self.witness.get("expected_outcome")
            or not self.assertion
            or not self.negative_controls
        ):
            raise ContractValidationError(
                "oracle-free proof requires witness expected_outcome, assertion, "
                "and at least one negative control"
            )

    @classmethod
    def _normalize_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["negative_controls"] = tuple(normalized["negative_controls"])
        normalized["runtime_probes"] = tuple(normalized["runtime_probes"])
        return normalized


@dataclass(frozen=True)
class ExecutionEvidence(_ContractModel):
    SCHEMA: ClassVar[str] = "vibecrafted.execution-evidence.v1"
    IDENTITY_EXCLUDED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"started_at", "ended_at"}
    )

    schema: str
    evidence_id: str
    parent_contract_id: str
    run_id: str
    role: str
    argv: tuple[str, ...]
    cwd: str
    environment: Mapping[str, str]
    resolved_executable: str
    executable_version: str | None
    executable_sha256: str | None
    started_at: str
    ended_at: str
    elapsed_ms: int
    timeout_seconds: float
    exit_code: int | None
    stdout_sha256: str
    stderr_sha256: str
    stdout_excerpt: str
    stderr_excerpt: str
    input_digests: Mapping[str, str]
    output_digests: Mapping[str, str]
    repo_before: Mapping[str, Any]
    repo_after: Mapping[str, Any]
    run_identity_sha256: str | None
    liveness_evidence_sha256: tuple[str, ...]

    @classmethod
    def _normalize_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["argv"] = tuple(normalized["argv"])
        normalized["liveness_evidence_sha256"] = tuple(
            normalized["liveness_evidence_sha256"]
        )
        return normalized


@dataclass(frozen=True)
class ProofResult(_ContractModel):
    SCHEMA: ClassVar[str] = "vibecrafted.proof-result.v1"
    IDENTITY_EXCLUDED_FIELDS: ClassVar[frozenset[str]] = frozenset({"evaluated_at"})

    schema: str
    proof_id: str
    state: ProofState
    evidence: tuple[Mapping[str, Any], ...]
    assertion_results: tuple[Mapping[str, Any], ...]
    negative_control_results: tuple[Mapping[str, Any], ...]
    subject_executed: bool
    assertion_consumed_subject_output: bool
    refusal_reasons: tuple[str, ...]
    contract_sha256: str
    executor_sha256: str
    evaluated_at: str

    def __post_init__(self) -> None:
        if self.state not in {
            ProofState.PASSED,
            ProofState.FAILED,
            ProofState.INVALID,
            ProofState.STALE,
        }:
            raise ContractValidationError(
                f"ProofResult cannot use in-progress state {self.state.value!r}"
            )

    @classmethod
    def _normalize_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["state"] = ProofState(normalized["state"])
        for name in (
            "evidence",
            "assertion_results",
            "negative_control_results",
            "refusal_reasons",
        ):
            normalized[name] = tuple(normalized[name])
        return normalized


@dataclass(frozen=True)
class DeliveryRecord(_ContractModel):
    SCHEMA: ClassVar[str] = "vibecrafted.delivery-record.v1"
    IDENTITY_EXCLUDED_FIELDS: ClassVar[frozenset[str]] = frozenset({"recorded_at"})

    schema: str
    record_id: str
    proof_result_sha256: str
    declared_scope: str
    checked_scope: str
    target_identity: Mapping[str, Any]
    commit_provenance: Mapping[str, Any]
    runtime_probe_results: tuple[Mapping[str, Any], ...]
    state: DeliveryState
    refusal_reasons: tuple[str, ...]
    recorded_at: str

    def __post_init__(self) -> None:
        if self.state not in {DeliveryState.UNVERIFIED, DeliveryState.DELIVERED}:
            raise ContractValidationError(
                f"DeliveryRecord cannot use state {self.state.value!r}"
            )

    @classmethod
    def _normalize_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["runtime_probe_results"] = tuple(normalized["runtime_probe_results"])
        normalized["state"] = DeliveryState(normalized["state"])
        normalized["refusal_reasons"] = tuple(normalized["refusal_reasons"])
        return normalized


@dataclass(frozen=True)
class DeliverySeal(_ContractModel):
    SCHEMA: ClassVar[str] = "vibecrafted.delivery-seal.v1"
    IDENTITY_EXCLUDED_FIELDS: ClassVar[frozenset[str]] = frozenset({"issued_at"})

    schema: str
    seal_id: str
    issued_at: str
    issuer: str
    run_id: str
    lifecycle_id: str
    cut_id: str
    proof_id: str
    run_identity_sha256: str
    liveness_evidence_sha256: tuple[str, ...]
    execution_envelope_sha256: str
    delivery_proof_contract_sha256: str
    proof_result_sha256: str
    executor_source_sha256: str
    executor_version: str
    subject_evidence_sha256: str
    witness_sha256: str
    oracle_evidence_sha256: str | None
    assertion_evidence_sha256: str
    negative_control_evidence_sha256: tuple[str, ...]
    repo: str
    branch: str
    baseline_head: str
    final_head: str
    scoped_dirty_status_sha256: str
    commit_range: str
    declared_scope: str
    checked_scope: str
    runtime_probe_sha256: tuple[str, ...]
    report_sha256: str
    transcript_sha256: str
    control_plane_snapshot_sha256: str
    unverified_surfaces: tuple[str, ...]

    @classmethod
    def _normalize_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        for name in (
            "liveness_evidence_sha256",
            "negative_control_evidence_sha256",
            "runtime_probe_sha256",
            "unverified_surfaces",
        ):
            normalized[name] = tuple(normalized[name])
        return normalized
