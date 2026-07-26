from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_CORE_SRC = Path(__file__).resolve().parents[1] / "vibecrafted-core"
_CORE_MODULE = _CORE_SRC / "vibecrafted_core" / "runtime_paths.py"
_SPEC = importlib.util.spec_from_file_location(
    "_vibecrafted_canonical_runtime_paths",
    _CORE_MODULE,
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load canonical runtime paths from {_CORE_MODULE}")
_runtime_paths = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _runtime_paths
_SPEC.loader.exec_module(_runtime_paths)


def __getattr__(name: str) -> Any:
    """Forward every public name to the canonical module (PEP 562 shim)."""
    return getattr(_runtime_paths, name)


def __dir__() -> list[str]:
    return sorted(set(dir(_runtime_paths)))
