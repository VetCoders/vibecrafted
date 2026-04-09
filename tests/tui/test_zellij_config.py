from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ZELLIJ_CONFIG = REPO_ROOT / "config" / "zellij" / "config.kdl"
LAYOUTS_DIR = REPO_ROOT / "config" / "zellij" / "layouts"


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


def test_zellij_config_has_vibecrafted_theme() -> None:
    payload = ZELLIJ_CONFIG.read_text(encoding="utf-8")

    assert "vibecrafted {" in payload
    assert 'theme "vibecrafted"' in payload
    # Brand accent colors present
    assert "amber gold" in payload.lower() or "214 175 54" in payload


def test_zellij_config_session_resilience() -> None:
    payload = ZELLIJ_CONFIG.read_text(encoding="utf-8")

    assert 'on_force_close "detach"' in payload
    assert "session_serialization true" in payload
    assert "serialize_pane_viewport true" in payload


def test_zellij_config_has_plugin_aliases() -> None:
    payload = ZELLIJ_CONFIG.read_text(encoding="utf-8")

    assert 'compact-bar location="zellij:compact-bar"' in payload
    assert 'session-manager location="zellij:session-manager"' in payload


def test_all_layouts_have_new_tab_template() -> None:
    """Every layout must define new_tab_template so dynamically spawned agent
    tabs get branded chrome (compact-bar + status-bar)."""
    for layout_file in sorted(LAYOUTS_DIR.glob("*.kdl")):
        payload = layout_file.read_text(encoding="utf-8")
        assert "new_tab_template" in payload, (
            f"{layout_file.name} missing new_tab_template"
        )
        assert 'plugin location="compact-bar"' in payload, (
            f"{layout_file.name} missing compact-bar in new_tab_template"
        )


def test_all_layouts_have_vibecrafted_branding() -> None:
    """Every layout tab name must use the branded unicode prefix."""
    for layout_file in sorted(LAYOUTS_DIR.glob("*.kdl")):
        payload = layout_file.read_text(encoding="utf-8")
        assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." in payload, f"{layout_file.name} missing branded tab name"


def test_marbles_layout_is_operator_centric() -> None:
    """Marbles layout must give operator the majority of screen space and
    keep monitoring in a compact section."""
    payload = (LAYOUTS_DIR / "vc-marbles.kdl").read_text(encoding="utf-8")
    assert 'name="operator"' in payload
    assert 'size="75%"' in payload
    assert "focus=true" in payload


def test_operator_layout_has_swap_layouts() -> None:
    """Operator layout should have swap layouts for toggling monitoring."""
    payload = (LAYOUTS_DIR / "vibecrafted.kdl").read_text(encoding="utf-8")
    assert "swap_tiled_layout" in payload


def test_workflow_layout_has_swap_layouts() -> None:
    """Workflow layout should support solo/dual swap modes."""
    payload = (LAYOUTS_DIR / "vc-workflow.kdl").read_text(encoding="utf-8")
    assert "swap_tiled_layout" in payload
    assert '"solo"' in payload
    assert '"dual"' in payload


def test_research_layout_synthesis_focused() -> None:
    """Research layout should give synthesis pane the focus and majority."""
    payload = (LAYOUTS_DIR / "vc-research.kdl").read_text(encoding="utf-8")
    assert 'name="synthesis"' in payload
    assert 'size="55%"' in payload
