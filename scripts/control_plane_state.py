"""Legacy scripts/ shim re-exporting vibecrafted_core.control_plane (PEP 562).

Kept so old ``scripts/control_plane_state.py`` import/CLI paths keep
working; the canonical implementation lives in vibecrafted-core.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_CORE_SRC = Path(__file__).resolve().parents[1] / "vibecrafted-core"
if _CORE_SRC.is_dir() and str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

from vibecrafted_core import control_plane as _control_plane
from vibecrafted_core.control_plane import vibecrafted_home


def _sync_overrides() -> None:
    """Rebind the canonical module's `vibecrafted_home` to this shim's resolved copy.

    Guards against the two modules' `vibecrafted_home` diverging if the
    canonical module is reloaded independently of this shim.
    """
    _control_plane.vibecrafted_home = vibecrafted_home


def sync_state() -> dict[str, object]:
    """Sync overrides then delegate to the canonical module's `sync_state`."""
    _sync_overrides()
    return _control_plane.sync_state()


def cli(argv: list[str] | None = None) -> int:
    """Sync overrides then delegate to the canonical module's `cli` entry point."""
    _sync_overrides()
    return _control_plane.cli(argv)


def __getattr__(name: str) -> Any:
    """Forward every other public name to the canonical module (PEP 562 shim)."""
    return getattr(_control_plane, name)


def __dir__() -> list[str]:
    """Report the canonical module's public names plus this shim's own wrappers."""
    return sorted(set(dir(_control_plane)) | {"sync_state", "cli"})


if __name__ == "__main__":  # pragma: no cover - shim CLI entrypoint
    raise SystemExit(cli())
