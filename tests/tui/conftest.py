from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_live_perception_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """TUI/launcher tests must not leave repository watchers behind."""

    monkeypatch.setenv("VIBECRAFTED_PERCEPTION_WATCH", "0")
