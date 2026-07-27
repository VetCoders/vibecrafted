from __future__ import annotations

import pytest

# Frame/session targeting env leaks from a live operator shell (vc-frame is a
# zellij fork, so both spellings appear). With any of these set, launcher paths
# see "inside a live frame" and switch sessions instead of launching layouts —
# tests then fail only on operator machines while CI stays green. Tests that
# simulate an in-frame caller still work: they set their own values after
# copying os.environ.
_AMBIENT_FRAME_ENV = (
    "ZELLIJ",
    "ZELLIJ_PANE_ID",
    "ZELLIJ_SESSION_NAME",
    "VC_FRAME",
    "VC_FRAME_PANE_ID",
    "VC_FRAME_SESSION_NAME",
    "VC_FRAME_CONFIG_DIR",
    "VIBECRAFTED_PREPARED_VC_FRAME_SESSION",
    "VIBECRAFTED_OPERATOR_SESSION",
    "VIBECRAFTED_WORKER_SESSION",
)


@pytest.fixture(autouse=True)
def _disable_live_perception_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """TUI/launcher tests must not reach live operator runtime surfaces."""

    monkeypatch.setenv("VIBECRAFTED_PERCEPTION_WATCH", "0")
    monkeypatch.setenv("VIBECRAFTED_TEST_MODE", "1")
    for name in _AMBIENT_FRAME_ENV:
        monkeypatch.delenv(name, raising=False)
