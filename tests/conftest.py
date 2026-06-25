import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
repo_root_str = str(REPO_ROOT)

if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

os.environ.setdefault("VIBECRAFTED_MARBLES_PROBE_NOTIFY", "0")
os.environ.setdefault("VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME", "1")


@pytest.fixture(autouse=True)
def _isolate_vibecrafted_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep root tests independent from the live Vibecrafted runtime."""
    for key in [name for name in os.environ if name.startswith("VIBECRAFTED_")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("VIBECRAFTED_MARBLES_PROBE_NOTIFY", "0")
    monkeypatch.setenv("VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME", "1")
