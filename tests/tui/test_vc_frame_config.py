from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VC_FRAME_CONFIG = REPO_ROOT / "config" / "vc-frame" / "config.kdl"
LAYOUTS_DIR = REPO_ROOT / "config" / "vc-frame" / "layouts"
THEMES_DIR = REPO_ROOT / "config" / "vc-frame" / "themes"


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


def test_vc_frame_config_dual_theme_monochrome_dark_ivory_light() -> None:
    payload = VC_FRAME_CONFIG.read_text(encoding="utf-8")

    # Brand block stays defined (graphite + amber) for explicit / mesh use.
    assert "vibecrafted {" in payload
    assert "amber gold" in payload.lower() or "214 175 54" in payload
    # Fleet chrome: dark monochrome + light ivory; never default pastel green.
    assert 'theme "monochrome"' in payload
    assert 'theme_dark "monochrome"' in payload
    assert 'theme_light "vibecrafted-ivory"' in payload
    assert 'theme "pastel"' not in payload
    # Flat key tiles — no powerline  triangles on status-bar / tab-bar.
    assert "simplified_ui true" in payload


def test_vibecrafted_ivory_theme_file_exists_and_is_warm_paper() -> None:
    ivory = THEMES_DIR / "vibecrafted-ivory.kdl"
    assert ivory.is_file()
    payload = ivory.read_text(encoding="utf-8")
    assert "vibecrafted-ivory" in payload
    # Ivory paper background (not dark, not neon green ribbons).
    assert "250 246 238" in payload
    assert "166 227 161" not in payload  # catppuccin green ribbon from pastel


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


def test_all_layouts_keep_sessions_rail_always_visible() -> None:
    """Every layout tab template must pin session-manager rail ALWAYS."""
    for layout_file in sorted(LAYOUTS_DIR.glob("*.kdl")):
        payload = layout_file.read_text(encoding="utf-8")
        assert "session-manager" in payload, (
            f"{layout_file.name} missing session-manager"
        )
        assert "rail true" in payload or 'rail "true"' in payload, (
            f"{layout_file.name} missing rail true on session-manager"
        )
        assert "default_tab_template" in payload or "new_tab_template" in payload, (
            f"{layout_file.name} missing tab template"
        )


def test_all_layouts_have_status_chrome() -> None:
    for layout_file in sorted(LAYOUTS_DIR.glob("*.kdl")):
        payload = layout_file.read_text(encoding="utf-8")
        assert 'plugin location="status-bar"' in payload, (
            f"{layout_file.name} missing status-bar"
        )
        assert (
            'plugin location="compact-bar"' in payload
            or 'plugin location="tab-bar"' in payload
        ), f"{layout_file.name} missing top bar plugin"


def test_layout_tab_branding_matches_frame_contract() -> None:
    """Non-operator layouts use the brand prefix on primary tabs."""
    for layout_file in sorted(LAYOUTS_DIR.glob("*.kdl")):
        payload = layout_file.read_text(encoding="utf-8")
        if layout_file.name == "operator.kdl":
            # Operator uses Guide + vibecrafted names (synced to default_layout).
            assert 'tab name="Guide"' in payload
            assert 'tab name="vibecrafted"' in payload
            continue
        assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." in payload, f"{layout_file.name} missing branded tab name"


def test_marbles_layout_is_operator_centric() -> None:
    """Marbles layout must give operator the majority of screen space and
    keep monitoring in a compact section."""
    payload = (LAYOUTS_DIR / "marbles.kdl").read_text(encoding="utf-8")
    assert 'name="operator"' in payload
    assert 'size="75%"' in payload
    assert "focus=true" in payload


def test_operator_layout_matches_vibecrafted_standard() -> None:
    """vc-start operator layout is the same eye as default_layout vibecrafted:
    Guide + shell, SESSIONS rail on every tab, no strider split."""
    payload = (LAYOUTS_DIR / "operator.kdl").read_text(encoding="utf-8")
    assert 'tab name="Guide"' in payload
    assert 'tab name="vibecrafted"' in payload
    assert 'guide_mode "mission-control"' in payload
    assert "session-manager" in payload
    assert "rail true" in payload
    assert "default_tab_template" in payload
    assert "compact-bar" in payload
    assert "status-bar" in payload
    # Rejected parallel path (ignore comments).
    active = "\n".join(
        line
        for line in payload.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    )
    assert "strider" not in active
    assert 'tab name="Operator"' not in active


def test_operator_layout_guide_and_shell_tabs() -> None:
    payload = (LAYOUTS_DIR / "operator.kdl").read_text(encoding="utf-8")
    assert 'plugin location="about"' in payload
    assert 'command="/bin/zsh"' in payload
    assert 'name="operator"' in payload


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
