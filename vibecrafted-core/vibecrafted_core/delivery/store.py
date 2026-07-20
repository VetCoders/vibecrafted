"""Atomic run-directory persistence for the delivery-proof kernel.

This module owns the physical names from spec section 12.  It deliberately does
not decide whether proof passed or whether a delivery may be sealed; the typed
contracts remain the semantic owners and this store only persists them without
exposing readers to half-written JSON.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar

from .model import (
    DeliveryProofContract,
    DeliveryRecord,
    DeliverySeal,
    ExecutionEnvelope,
    ExecutionEvidence,
    ProofResult,
)

EXECUTION_ENVELOPE_PATH = Path("execution-envelope.json")
PROOF_CONTRACT_PATH = Path("delivery-proof-contract.json")
ASSERTIONS_PATH = Path("proof/assertions.json")
NEGATIVE_CONTROLS_PATH = Path("proof/negative-controls.json")
PROOF_RESULT_PATH = Path("proof/result.json")
DELIVERY_RECORD_PATH = Path("delivery-record.json")
DELIVERY_SEAL_PATH = Path("delivery-seal.json")

ASSERTIONS_SCHEMA = "vibecrafted.proof-assertions.v1"
NEGATIVE_CONTROLS_SCHEMA = "vibecrafted.proof-negative-controls.v1"

_ROLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ModelT = TypeVar(
    "_ModelT",
    ExecutionEnvelope,
    DeliveryProofContract,
    ExecutionEvidence,
    ProofResult,
    DeliveryRecord,
    DeliverySeal,
)


class DeliveryStoreError(ValueError):
    """Raised when an artifact cannot be safely persisted or loaded."""


def atomic_write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Atomically replace ``path`` with one canonical JSON mapping.

    The temporary file lives beside the target so ``os.replace`` stays on one
    filesystem.  A process killed before replace can leave only an unreferenced
    ``.tmp`` file; it can never truncate the canonical artifact.
    """

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = (
            json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DeliveryStoreError(f"artifact is not canonical JSON: {exc}") from exc

    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        with contextlib.suppress(OSError):
            temporary.unlink()
    return target


def read_json(path: str | Path) -> dict[str, Any]:
    """Load one JSON mapping, failing closed on missing or malformed data."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeliveryStoreError(
            f"cannot read delivery artifact {source}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise DeliveryStoreError(f"delivery artifact {source} must contain a mapping")
    return payload


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(directory, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Some filesystems do not support directory fsync.  The file itself was
        # still flushed before replace, which preserves reader atomicity.
        pass
    finally:
        os.close(descriptor)


def _source_digests(values: Mapping[str, str]) -> dict[str, str]:
    normalized = {str(key): str(value) for key, value in values.items()}
    if not normalized:
        raise DeliveryStoreError("derived artifact requires source_digests")
    invalid = sorted(
        key for key, value in normalized.items() if not value.startswith("sha256:")
    )
    if invalid:
        raise DeliveryStoreError(
            "source digests must use sha256: values: " + ", ".join(invalid)
        )
    return normalized


class DeliveryStore:
    """Typed, atomic access to the canonical artifacts for one run directory."""

    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)

    def path(self, relative: str | Path) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise DeliveryStoreError("delivery artifact path must stay inside run_dir")
        return self.run_dir / candidate

    def write_execution_envelope(self, value: ExecutionEnvelope) -> Path:
        return self._write_model(EXECUTION_ENVELOPE_PATH, value)

    def read_execution_envelope(self) -> ExecutionEnvelope:
        return self._read_model(EXECUTION_ENVELOPE_PATH, ExecutionEnvelope)

    def write_proof_contract(self, value: DeliveryProofContract) -> Path:
        return self._write_model(PROOF_CONTRACT_PATH, value)

    def read_proof_contract(self) -> DeliveryProofContract:
        return self._read_model(PROOF_CONTRACT_PATH, DeliveryProofContract)

    def write_execution(
        self,
        value: ExecutionEvidence,
        *,
        role: str | None = None,
        sequence: int = 1,
    ) -> Path:
        resolved_role = str(role or value.role)
        if not _ROLE_RE.fullmatch(resolved_role):
            raise DeliveryStoreError(f"unsafe execution role {resolved_role!r}")
        if resolved_role != value.role:
            raise DeliveryStoreError(
                f"execution role {resolved_role!r} does not match evidence role "
                f"{value.role!r}"
            )
        if sequence < 1:
            raise DeliveryStoreError("execution sequence must be >= 1")
        return self._write_model(
            Path("proof/executions") / f"{resolved_role}-{sequence}.json", value
        )

    def read_execution(self, role: str, *, sequence: int = 1) -> ExecutionEvidence:
        if not _ROLE_RE.fullmatch(role) or sequence < 1:
            raise DeliveryStoreError("invalid execution role or sequence")
        return self._read_model(
            Path("proof/executions") / f"{role}-{sequence}.json", ExecutionEvidence
        )

    def write_assertions(
        self,
        assertions: Sequence[Mapping[str, Any]],
        *,
        source_digests: Mapping[str, str],
    ) -> Path:
        return atomic_write_json(
            self.path(ASSERTIONS_PATH),
            {
                "schema": ASSERTIONS_SCHEMA,
                "source_digests": _source_digests(source_digests),
                "assertions": [dict(assertion) for assertion in assertions],
            },
        )

    def read_assertions(self) -> dict[str, Any]:
        return self._read_derived(ASSERTIONS_PATH, ASSERTIONS_SCHEMA)

    def write_negative_controls(
        self,
        controls: Sequence[Mapping[str, Any]],
        *,
        source_digests: Mapping[str, str],
    ) -> Path:
        return atomic_write_json(
            self.path(NEGATIVE_CONTROLS_PATH),
            {
                "schema": NEGATIVE_CONTROLS_SCHEMA,
                "source_digests": _source_digests(source_digests),
                "negative_controls": [dict(control) for control in controls],
            },
        )

    def read_negative_controls(self) -> dict[str, Any]:
        return self._read_derived(NEGATIVE_CONTROLS_PATH, NEGATIVE_CONTROLS_SCHEMA)

    def write_proof_result(self, value: ProofResult) -> Path:
        return self._write_model(PROOF_RESULT_PATH, value)

    def read_proof_result(self) -> ProofResult:
        return self._read_model(PROOF_RESULT_PATH, ProofResult)

    def write_delivery_record(self, value: DeliveryRecord) -> Path:
        return self._write_model(DELIVERY_RECORD_PATH, value)

    def read_delivery_record(self) -> DeliveryRecord:
        return self._read_model(DELIVERY_RECORD_PATH, DeliveryRecord)

    def write_delivery_seal(self, value: DeliverySeal) -> Path:
        return self._write_model(DELIVERY_SEAL_PATH, value)

    def read_delivery_seal(self) -> DeliverySeal:
        return self._read_model(DELIVERY_SEAL_PATH, DeliverySeal)

    def _write_model(self, relative: Path, value: _ModelT) -> Path:
        payload = value.to_payload()
        # Dataclass construction is intentionally lightweight; round-trip the
        # payload through its fail-closed reader before making it canonical.
        type(value).from_payload(payload)
        return atomic_write_json(self.path(relative), payload)

    def _read_model(self, relative: Path, model: type[_ModelT]) -> _ModelT:
        return model.from_payload(read_json(self.path(relative)))

    def _read_derived(self, relative: Path, schema: str) -> dict[str, Any]:
        payload = read_json(self.path(relative))
        if payload.get("schema") != schema:
            raise DeliveryStoreError(
                f"unsupported schema {payload.get('schema')!r}; expected {schema!r}"
            )
        _source_digests(dict(payload.get("source_digests") or {}))
        return payload


__all__ = [
    "ASSERTIONS_PATH",
    "ASSERTIONS_SCHEMA",
    "DELIVERY_RECORD_PATH",
    "DELIVERY_SEAL_PATH",
    "EXECUTION_ENVELOPE_PATH",
    "NEGATIVE_CONTROLS_PATH",
    "NEGATIVE_CONTROLS_SCHEMA",
    "PROOF_CONTRACT_PATH",
    "PROOF_RESULT_PATH",
    "DeliveryStore",
    "DeliveryStoreError",
    "atomic_write_json",
    "read_json",
]
