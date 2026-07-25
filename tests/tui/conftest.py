from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_live_perception_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """TUI/launcher tests must not reach live operator runtime surfaces."""

    monkeypatch.setenv("VIBECRAFTED_PERCEPTION_WATCH", "0")
    monkeypatch.setenv("VIBECRAFTED_TEST_MODE", "1")
