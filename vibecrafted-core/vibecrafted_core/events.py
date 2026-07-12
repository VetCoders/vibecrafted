from __future__ import annotations

from typing import Any


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
