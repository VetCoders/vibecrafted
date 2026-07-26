"""Ordered, cross-process locks for mutations of one run lineage.

The control-plane projection is intentionally cheap to read, but mutations that
change settlement or dispatch recovery work must agree on one ordering:

    parent run -> resume lineage -> idempotency key

Keeping this helper below ``workflow`` and ``trust`` avoids an import cycle
while giving both surfaces the same filesystem-backed exclusion boundary.
"""

from __future__ import annotations

import fcntl
import hashlib
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCAL_LOCKS_GUARD = threading.Lock()
_LOCAL_LOCKS: dict[str, threading.RLock] = {}


def _lock_path(root: Path, kind: str, value: str) -> Path:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return root / "run_mutation_locks" / kind / f"{digest}.lock"


def _local_lock(path: Path) -> threading.RLock:
    key = str(path)
    with _LOCAL_LOCKS_GUARD:
        return _LOCAL_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def run_mutation_locks(
    control_plane_root: Path,
    *,
    run_id: str,
    resume_root: str = "",
    idempotency_key: str = "",
) -> Iterator[None]:
    """Acquire the shared mutation locks in the only supported order."""

    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required for a mutation lock")
    ordered = [("run", target)]
    lineage = str(resume_root or "").strip()
    if lineage:
        ordered.append(("lineage", lineage))
    key = str(idempotency_key or "").strip()
    if key:
        ordered.append(("idempotency", key))

    paths = [
        _lock_path(Path(control_plane_root), kind, value) for kind, value in ordered
    ]
    local_locks = [_local_lock(path) for path in paths]
    handles = []
    try:
        for local, path in zip(local_locks, paths, strict=True):
            local.acquire()
            handle = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                handle = path.open("a+b")
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except BaseException:
                if handle is not None:
                    handle.close()
                local.release()
                raise
            handles.append((handle, local))
        yield
    finally:
        for handle, local in reversed(handles):
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
                local.release()
