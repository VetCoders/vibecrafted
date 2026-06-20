"""Snapshot garbage collection — reclaim disk from orphaned install snapshots.

Thin package API over the installer's filesystem logic, mirroring ``doctor.py``:
all detection/move/remove lives in ``scripts/vetcoders_install.py`` (single source
of truth, shared with the doctor ``snapshot-orphan`` check); this module only loads
the installer and shapes results for the CLI.

Two-stage, trash-like safety model:
  * ``gc_collect`` — read-only: list de-pointed ``vibecrafted-<ref>`` snapshots.
  * ``gc_prune``   — MOVE orphans into a recoverable quarantine (no disk freed yet).
  * ``gc_purge``   — hard-remove the quarantine (the only irreversible step).
"""

from __future__ import annotations

from typing import Any

from .doctor import _installer_module


def _roots(installer: Any) -> tuple[Any, Any]:
    """Active tools dir + the legacy ``~/.vibecrafted/tools`` base."""
    return (
        installer.vibecrafted_tools_home(),
        installer.vibecrafted_home() / "tools",
    )


def _summary(
    mode: str, dry_run: bool, items: list[dict[str, Any]], installer: Any
) -> dict[str, Any]:
    total = sum(int(item["size_bytes"]) for item in items)
    return {
        "mode": mode,
        "dry_run": dry_run,
        "count": len(items),
        "total_bytes": total,
        "total_human": installer._human_size(total),
        "items": items,
    }


def gc_collect() -> dict[str, Any]:
    """List orphaned snapshots without touching anything."""
    installer = _installer_module()
    tools_home, legacy = _roots(installer)
    items = [
        {
            "path": str(path),
            "size_bytes": size,
            "size_human": installer._human_size(size),
        }
        for path, size in installer.collect_orphaned_snapshots(tools_home, legacy)
    ]
    return _summary("collect", False, items, installer)


def gc_prune(dry_run: bool = False) -> dict[str, Any]:
    """Move orphaned snapshots into the recoverable quarantine."""
    installer = _installer_module()
    tools_home, legacy = _roots(installer)
    items = [
        {
            "path": str(src),
            "quarantine": str(dst),
            "size_bytes": size,
            "size_human": installer._human_size(size),
        }
        for src, dst, size in installer.quarantine_orphaned_snapshots(
            tools_home, legacy, dry_run=dry_run
        )
    ]
    return _summary("prune", dry_run, items, installer)


def gc_purge(dry_run: bool = False) -> dict[str, Any]:
    """Hard-remove the quarantine to reclaim disk (irreversible)."""
    installer = _installer_module()
    tools_home, legacy = _roots(installer)
    items = [
        {
            "path": str(path),
            "size_bytes": size,
            "size_human": installer._human_size(size),
        }
        for path, size in installer.purge_orphan_quarantine(
            tools_home, legacy, dry_run=dry_run
        )
    ]
    return _summary("purge", dry_run, items, installer)
