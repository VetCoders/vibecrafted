from __future__ import annotations

from enum import Enum
from typing import Any


class DeliveryEventKind(str, Enum):
    """Delivery-kernel events carried by the existing append-only stream."""

    EXECUTION_EXITED = "execution.exited"
    PROOF_STARTED = "proof.started"
    PROOF_FAILED = "proof.failed"
    PROOF_INVALID = "proof.invalid"
    PROOF_PASSED = "proof.passed"
    DELIVERY_DELIVERED = "delivery.delivered"
    DELIVERY_SEALED = "delivery.sealed"
    DELIVERY_INVALIDATED = "delivery.invalidated"


DELIVERY_EVENT_KINDS = frozenset(kind.value for kind in DeliveryEventKind)


def append_event(
    kind: str,
    run_id: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one control-plane event via an atomic, lockless O_APPEND write."""
    from . import control_plane

    event = {
        "ts": control_plane._now().isoformat(),
        "run_id": str(run_id or ""),
        "kind": str(kind or "event"),
        "message": str(message or ""),
        "payload": payload or {},
    }
    # No global lock: _append_event is a single atomic O_APPEND write, so the
    # hot emit path never serializes on the shared control-plane mutex.
    control_plane._append_event(event)
    return event


def append_delivery_event(
    kind: DeliveryEventKind | str,
    run_id: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish one typed delivery event through the lockless event path."""

    value = kind.value if isinstance(kind, DeliveryEventKind) else str(kind)
    if value not in DELIVERY_EVENT_KINDS:
        raise ValueError(f"unsupported delivery event kind {value!r}")
    return append_event(value, run_id, message, payload)


__all__ = [
    "DELIVERY_EVENT_KINDS",
    "DeliveryEventKind",
    "append_delivery_event",
    "append_event",
]
