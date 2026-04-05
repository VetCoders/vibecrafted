from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ZELLIJ_CONFIG = REPO_ROOT / "config" / "zellij" / "config.kdl"


def test_zellij_config_moves_secondary_shortcuts_off_alt() -> None:
    payload = ZELLIJ_CONFIG.read_text(encoding="utf-8")

    assert 'unbind "Alt f" "Alt n" "Alt i" "Alt o"' in payload
    assert 'bind "Ctrl Shift f" { ToggleFloatingPanes; }' in payload
    assert 'bind "Ctrl Shift n" { NewPane; }' in payload
    assert 'bind "Ctrl Shift h" "Ctrl Shift Left" { MoveFocusOrTab "Left"; }' in payload
    assert 'bind "Ctrl Shift p" { TogglePaneInGroup; }' in payload


def test_zellij_config_replaces_immediate_quit_with_confirm_flow() -> None:
    payload = ZELLIJ_CONFIG.read_text(encoding="utf-8")

    assert 'bind "Ctrl Shift q" { SwitchToMode "Session"; }' in payload
    assert 'bind "Ctrl q" { CloseFocus; SwitchToMode "Normal"; }' in payload
    assert 'bind "Ctrl q" { CloseTab; SwitchToMode "Normal"; }' in payload
    assert 'bind "y" { Quit; }' in payload
    assert (
        'bind "n" "Esc" "Ctrl q" "Ctrl Shift q" { SwitchToMode "Normal"; }' in payload
    )
