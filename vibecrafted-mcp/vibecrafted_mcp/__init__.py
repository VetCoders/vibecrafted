"""Public package surface for vibecrafted-mcp.

``build_server`` / ``main`` are lazy-loaded so ``server.py`` can import sibling
modules (``version``, ``synthesis``) without a breaking import cycle through
this package root.
"""

from __future__ import annotations

from typing import Any

from .version import __version__

__all__ = ["__version__", "build_server", "main"]


def __getattr__(name: str) -> Any:
    """Lazily resolve ``build_server``/``main`` from ``server`` on first access.

    Deferring the ``server`` import here (instead of at module load) is what
    avoids the import cycle described in the module docstring.
    """
    if name in {"build_server", "main"}:
        from . import server as _server

        return getattr(_server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Report both eagerly-bound globals and the lazily-resolved ``__all__`` names."""
    return sorted({*globals(), *__all__})
