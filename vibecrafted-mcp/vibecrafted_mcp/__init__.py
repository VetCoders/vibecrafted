from __future__ import annotations

import importlib.metadata
from pathlib import Path

from .server import build_server, main


def _resolve_installed_version() -> str:
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


__version__ = _resolve_installed_version()

__all__ = ["__version__", "build_server", "main"]
