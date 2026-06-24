from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VC_FRAME_CONFIG = REPO_ROOT / "config" / "vc-frame" / "config.kdl"
LAYOUTS_DIR = REPO_ROOT / "config" / "vc-frame" / "layouts"


def test_vc_frame_config_uses_plain_ctrl_without_option_layer() -> None:
    payload = VC_FRAME_CONFIG.read_text(encoding="utf-8")

    assert 'unbind "Alt f" "Alt n" "Alt i" "Alt o"' in payload
    assert "support_kitty_keyboard_protocol false" in payload
    assert 'bind "Ctrl n" { NewPane; }' in payload
    assert "Ctrl Shift" not in payload


def test_vc_frame_config_ctrl_q_closes_focus_not_session() -> None:
    payload = VC_FRAME_CONFIG.read_text(encoding="utf-8")
    active_lines = [
        line.strip()
        for line in payload.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]

    # Plain Ctrl+q must never map to Quit. Full quit stays inside session mode.
    assert 'unbind "Ctrl q"' in payload
    assert 'bind "Ctrl q" { CloseFocus; SwitchToMode "Normal"; }' in payload
    assert 'bind "q" { Quit; }' in payload
    assert 'bind "Ctrl q" { Quit; }' not in active_lines


def test_vc_frame_config_has_vibecrafted_theme() -> None:
    payload = VC_FRAME_CONFIG.read_text(encoding="utf-8")

    assert "vibecrafted {" in payload
    assert 'theme "pastel"' in payload
    assert '"vibecrafted" for the amber/gold brand palette' in payload
    # Brand accent colors present
    assert "amber gold" in payload.lower() or "214 175 54" in payload


def test_vc_frame_config_session_resilience() -> None:
    payload = VC_FRAME_CONFIG.read_text(encoding="utf-8")

    assert 'on_force_close "detach"' in payload
    assert "session_serialization true" in payload
    assert "serialize_pane_viewport true" in payload


def test_vc_frame_config_has_plugin_aliases() -> None:
    payload = VC_FRAME_CONFIG.read_text(encoding="utf-8")

    # vc-frame still accepts builtin plugin aliases through the upstream
    # zellij: URL scheme; vc-frame: is rejected by the 0.45.x parser.
    assert 'compact-bar location="zellij:compact-bar"' in payload
    assert 'session-manager location="zellij:session-manager"' in payload


def test_all_layouts_have_new_tab_template() -> None:
    """Every layout must define new_tab_template so dynamically spawned agent
    tabs get branded chrome (compact-bar + status-bar). Operator is the compact
    stock entrypoint and opens additional agents as separate tabs."""
    for layout_file in sorted(LAYOUTS_DIR.glob("*.kdl")):
        payload = layout_file.read_text(encoding="utf-8")
        if layout_file.name == "operator.kdl":
            assert 'plugin location="tab-bar"' in payload
            assert 'plugin location="status-bar"' in payload
            continue
        assert "new_tab_template" in payload, (
            f"{layout_file.name} missing new_tab_template"
        )
        assert 'plugin location="compact-bar"' in payload, (
            f"{layout_file.name} missing compact-bar in new_tab_template"
        )


def test_layout_tab_branding_matches_frame_contract() -> None:
    """Most layout tabs use the brand prefix; operator avoids duplication.

    vc-frame already brands the session title, so the operator tab should be
    plain and scan-friendly instead of repeating "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." twice.
    """
    for layout_file in sorted(LAYOUTS_DIR.glob("*.kdl")):
        payload = layout_file.read_text(encoding="utf-8")
        if layout_file.name == "operator.kdl":
            assert 'tab name="𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Operator"' not in payload
            continue
        assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." in payload, f"{layout_file.name} missing branded tab name"


def test_marbles_layout_is_operator_centric() -> None:
    """Marbles layout must give operator the majority of screen space and
    keep monitoring in a compact section."""
    payload = (LAYOUTS_DIR / "marbles.kdl").read_text(encoding="utf-8")
    assert 'name="operator"' in payload
    assert 'size="75%"' in payload
    assert "focus=true" in payload


def test_operator_layout_uses_stock_strider_shell_split() -> None:
    """Operator layout stays on the stock strider + shell split that parses and
    starts reliably under vc-frame."""
    payload = (LAYOUTS_DIR / "operator.kdl").read_text(encoding="utf-8")
    assert 'pane split_direction="Vertical"' in payload
    assert 'plugin location="strider"' in payload
    assert "swap_tiled_layout" not in payload


def test_operator_layout_keeps_usable_shell_beside_strider() -> None:
    """Operator first screen keeps a file browser beside an uncommanded shell."""
    payload = (LAYOUTS_DIR / "operator.kdl").read_text(encoding="utf-8")
    active_lines = [
        line.strip()
        for line in payload.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]

    assert 'plugin location="strider"' in payload
    assert "pane\n" in payload
    assert not any("${VIBECRAFTED_HOME" in line for line in active_lines)


def test_workflow_layout_has_swap_layouts() -> None:
    """Workflow layout should support solo/dual swap modes."""
    payload = (LAYOUTS_DIR / "workflow.kdl").read_text(encoding="utf-8")
    assert "swap_tiled_layout" in payload
    assert '"solo"' in payload
    assert '"dual"' in payload


def test_research_layout_synthesis_focused() -> None:
    """Research layout should give synthesis pane the focus and majority."""
    payload = (LAYOUTS_DIR / "research.kdl").read_text(encoding="utf-8")
    assert 'name="synthesis"' in payload
    assert 'size="55%"' in payload
