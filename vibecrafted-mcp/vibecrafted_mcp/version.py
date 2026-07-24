"""Package version without importing the server surface.

Kept separate so ``server.py`` can read ``__version__`` without forming a
breaking import cycle with ``__init__.py`` (which re-exports ``build_server`` /
``main`` from the server module).
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path


def resolve_installed_version() -> str:
    packaged = Path(__file__).with_name("VERSION")
    try:
        version = packaged.read_text(encoding="utf-8").strip()
    except OSError:
        version = ""
    if version:
        return version
    try:
        return importlib.metadata.version("vibecrafted-mcp")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


__version__ = resolve_installed_version()

__all__ = ["__version__", "resolve_installed_version"]
