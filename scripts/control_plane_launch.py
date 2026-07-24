from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_CORE_SRC = Path(__file__).resolve().parents[1] / "vibecrafted-core"
if _CORE_SRC.is_dir() and str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

from vibecrafted_core import workflow as _workflow


def __getattr__(name: str) -> Any:
    """Forward every public name to the canonical module (PEP 562 shim)."""
    return getattr(_workflow, name)


def __dir__() -> list[str]:
    return sorted(set(dir(_workflow)))
