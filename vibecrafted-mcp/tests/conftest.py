from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
CORE_ROOT = PACKAGE_ROOT.parent / "vibecrafted-core"

for candidate in (PACKAGE_ROOT, CORE_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)
