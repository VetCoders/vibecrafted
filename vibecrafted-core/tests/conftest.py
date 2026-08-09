from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


@pytest.fixture(autouse=True)
def _isolate_vibecrafted_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip ambient ``VIBECRAFTED_*`` vars leaked by a live dispatched runtime.

    The suite must behave identically whether it is launched from a bare shell
    or from inside a Vibecrafted-supervised run. A live runtime exports run and
    identity context (``VIBECRAFTED_AGENT``, ``VIBECRAFTED_REPORT_PATH``,
    session/run ids, ...). Those leak into the test process and override
    in-process inference — turning green tests red only when an agent runs the
    suite from within the product's own runtime (the failure that hid two
    supervisor tests). Clearing them here makes the local environment match a
    clean CI checkout, so a test green in CI cannot be reddened by ambient
    state. Tests that need a specific value set it explicitly via monkeypatch
    after this fixture runs.
    """
    for key in [
        name
        for name in os.environ
        if name.startswith(("VIBECRAFTED_", "VC_FRAME", "ZELLIJ"))
    ]:
        monkeypatch.delenv(key, raising=False)
    # The LIVE bucket viewer is on by default in the product, which means a
    # launch test run on a developer machine with vc-frame on PATH would open
    # real tabs in the operator's terminal. Hermetic by default; the tests that
    # exercise the viewer switch it back on explicitly.
    monkeypatch.setenv("VIBECRAFTED_LIVE_VIEWER", "0")
