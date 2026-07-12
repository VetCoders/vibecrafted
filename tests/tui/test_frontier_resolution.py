from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"
COMMON_SCRIPT = REPO_ROOT / "runtime" / "scripts" / "common.sh"
INSTALL_FRONTIER_SCRIPT = (
    REPO_ROOT / "runtime" / "scripts" / "install-frontier-config.sh"
)


def _write_fake_binary(bin_dir: Path, name: str) -> None:
    script_names = [name]
    if name == "vc-frame":
        script_names.insert(0, "vc-frame")
    for script_name in script_names:
        script = bin_dir / script_name
        script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        script.chmod(0o755)


def _write_capture_binary(bin_dir: Path, name: str, capture_file: Path) -> None:
    script_names = [name]
    if name == "vc-frame":
        script_names.insert(0, "vc-frame")
    for script_name in script_names:
        script = bin_dir / script_name
        script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "{",
                    '  printf "%s\\n" "$@"',
                    '  printf "VC_FRAME_CONFIG_DIR=%s\\n" "${VC_FRAME_CONFIG_DIR:-}"',
                    '} > "$CAPTURE_FILE"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        script.chmod(0o755)


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def test_dashboard_layouts_resolve_helpers_from_home_store_first() -> None:
    expected_home_root = "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/runtime"
    expected_repo_store_root = (
        "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/.vibecrafted/runtime}"
    )
    expected_repo_root = "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/runtime}"

    # operator.kdl is the stock strider layout (file browser + shell); it carries
    # no mission-control helper panes, so it has no home-store resolution payload.
    for layout_name in ("dashboard.kdl", "marbles.kdl"):
        payload = (
            REPO_ROOT / "config" / "vc-frame" / "layouts" / layout_name
        ).read_text(encoding="utf-8")
        assert expected_home_root in payload
        assert expected_repo_store_root in payload
        assert expected_repo_root in payload


def test_operator_layout_does_not_append_nested_vibecrafted_store() -> None:
    payload = (
        REPO_ROOT / "config" / "vc-frame" / "layouts" / "operator.kdl"
    ).read_text(encoding="utf-8")
    assert (
        "${VIBECRAFTED_HOME:-$VIBECRAFTED_ROOT}/.vibecrafted/skills/vc-agents"
        not in payload
    )


def test_shell_helper_prefers_current_control_plane_over_home_store(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    current_store = (
        home
        / ".local"
        / "share"
        / "vibecrafted"
        / "tools"
        / "vibecrafted-current"
        / "skills"
        / "vc-agents"
    )
    stale_store = home / ".vibecrafted" / "skills" / "vc-agents"

    # A real runtime store carries a scripts/ dir; the resolver only selects
    # candidates that look like real stores. Both are realistic so the test
    # exercises the installed>home preference, not the real-store filter.
    (current_store / "scripts").mkdir(parents=True)
    (stale_store / "scripts").mkdir(parents=True)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("VIBECRAFTED_ROOT", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'cd "{tmp_path}" && source "{HELPER_SCRIPT}"; _vetcoders_spawn_home codex',
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == str(current_store)


def test_vc_frontier_paths_mix_repo_prompt_with_companion_vc_frame(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )
    vc_frame_config.parent.mkdir(parents=True)
    vc_frame_config.write_text("layout {}\n", encoding="utf-8")
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env.pop("STARSHIP_CONFIG", None)
    env.pop("VC_FRAME_CONFIG_DIR", None)

    result = subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-frontier-paths'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert f"STARSHIP_CONFIG={REPO_ROOT / 'config' / 'starship.toml'}" in result.stdout
    assert (
        f"ATUIN_CONFIG={REPO_ROOT / 'config' / 'atuin' / 'config.toml'}"
        in result.stdout
    )
    assert f"VC_FRAME_CONFIG_DIR={vc_frame_config.parent}" in result.stdout


def test_vc_dashboard_mixes_companion_vc_frame_config_with_repo_layout(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "vc_frame-args.txt"
    vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )

    home.mkdir()
    fake_bin.mkdir()
    vc_frame_config.parent.mkdir(parents=True)
    vc_frame_config.write_text('default_layout "compact"\n', encoding="utf-8")
    _write_capture_binary(fake_bin, "vc-frame", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env.pop("VC_FRAME_CONFIG_DIR", None)
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-dashboard vc-marbles'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert _expected_operator_session() in payload
    assert f"{_expected_operator_session()}-marbles" not in payload
    assert "--new-session-with-layout" in payload
    assert str(REPO_ROOT / "config" / "vc-frame" / "layouts" / "marbles.kdl") in payload
    assert f"VC_FRAME_CONFIG_DIR={vc_frame_config.parent}" in payload


def test_vc_dashboard_uses_base_run_id_session_without_layout_suffix(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "vc_frame-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_capture_binary(fake_bin, "vc-frame", capture_file)

    vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )
    vc_frame_config.parent.mkdir(parents=True)
    vc_frame_config.write_text("layout {}\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    env.pop("VC_FRAME_CONFIG_DIR", None)
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    # Scrub any operator-session context leaked from a running operator shell so
    # the dashboard resolves the run-id session rather than the ambient one.
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)
    env.pop("VIBECRAFTED_OPERATOR_MODE", None)

    subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-dashboard vc-marbles'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert _expected_operator_session(env["VIBECRAFTED_RUN_ID"]) in payload
    assert (
        f"{_expected_operator_session(env['VIBECRAFTED_RUN_ID'])}-marbles"
        not in payload
    )


def test_zsh_skill_wrappers_do_not_depend_on_external_has_agent(
    tmp_path: Path,
) -> None:
    if shutil.which("zsh") is None:
        pytest.skip("zsh required")

    home = tmp_path / "home"
    capture_file = tmp_path / "wrapper-args.txt"
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        [
            "zsh",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "unfunction _has_agent >/dev/null 2>&1 || true; "
                '_vetcoders_skill_entry() { printf "%s\\n" "$@" > "$CAPTURE_FILE"; }; '
                # vc-intents is now a command-backed skill (command vibecrafted
                # intents); use vc-review, which still routes through the shell
                # skill-wrapper, to exercise the wrapper machinery under zsh.
                'vc-review codex --prompt "hello"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    assert capture_file.read_text(encoding="utf-8").splitlines() == [
        "codex",
        "review",
        "--prompt",
        "hello",
    ]


def test_operator_session_name_compacts_long_repo_scope_for_vc_frame_limit(
    tmp_path: Path,
) -> None:
    long_repo = tmp_path / "mcp-server-semgrep"
    long_repo.mkdir()

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'cd "{long_repo}" && '
                f'source "{HELPER_SCRIPT}"; '
                'export VIBECRAFTED_RUN_ID="inte-091338"; '
                "_vetcoders_operator_session_name"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    session_name = result.stdout.strip()
    assert len(session_name) <= 24
    assert session_name.endswith("-inte-091338")


def test_operator_session_name_supports_folder_scope(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "mcp-server-semgrep"
    folder = repo_root / "feature-lab"
    folder.mkdir(parents=True)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'cd "{folder}" && '
                f'source "{HELPER_SCRIPT}"; '
                'export VIBECRAFTED_VC_FRAME_SESSION_SCOPE="folder"; '
                "_vetcoders_operator_session_name"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "feature-lab"


def test_zsh_skill_wrapper_accepts_runtime_without_bad_substitution(
    tmp_path: Path,
) -> None:
    if shutil.which("zsh") is None:
        pytest.skip("zsh required")

    home = tmp_path / "home"
    capture_file = tmp_path / "spawn-plan.txt"
    fake_spawn = tmp_path / "fake_spawn.sh"
    home.mkdir()
    fake_spawn.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_spawn.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["FAKE_SPAWN"] = str(fake_spawn)

    subprocess.run(
        [
            "zsh",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "_vetcoders_ensure_run_context() { :; }; "
                '_vetcoders_prepare_operator_runtime() { printf "%s\\n" "$1" > "$CAPTURE_FILE"; }; '
                '_vetcoders_spawn_script() { printf "%s" "$FAKE_SPAWN"; }; '
                # vc-intents is command-backed now; vc-review still routes through
                # the shell skill-wrapper that parses --runtime under zsh.
                'vc-review codex --runtime visible --prompt "hello"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    assert capture_file.read_text(encoding="utf-8").splitlines() == ["visible"]


def test_sourcing_helper_exports_frontier_sidecars_per_asset(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )

    home.mkdir()
    fake_bin.mkdir()
    vc_frame_config.parent.mkdir(parents=True)
    vc_frame_config.write_text("layout {}\n", encoding="utf-8")
    _write_fake_binary(fake_bin, "starship")
    _write_fake_binary(fake_bin, "atuin")
    _write_fake_binary(fake_bin, "vc-frame")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env.pop("STARSHIP_CONFIG", None)
    env.pop("ATUIN_CONFIG", None)
    env.pop("VC_FRAME_CONFIG_DIR", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'printf "STARSHIP_CONFIG=%s\\n" "$STARSHIP_CONFIG"; '
                'printf "ATUIN_CONFIG=%s\\n" "$ATUIN_CONFIG"; '
                'printf "VC_FRAME_CONFIG_DIR=%s\\n" "$VC_FRAME_CONFIG_DIR"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert f"STARSHIP_CONFIG={REPO_ROOT / 'config' / 'starship.toml'}" in result.stdout
    assert (
        f"ATUIN_CONFIG={REPO_ROOT / 'config' / 'atuin' / 'config.toml'}"
        in result.stdout
    )
    assert f"VC_FRAME_CONFIG_DIR={vc_frame_config.parent}" in result.stdout


def test_frontier_install_dry_run_succeeds_without_repo_alacritty_preset(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    home.mkdir()
    xdg_config_home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)

    result = subprocess.run(
        ["bash", str(INSTALL_FRONTIER_SCRIPT), "--source", str(REPO_ROOT), "--dry-run"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    sidecar_root = xdg_config_home / "vetcoders" / "frontier"
    assert "config/vc-frame/config.kdl" in result.stdout
    assert str(sidecar_root / "vc-frame" / "config.kdl") in result.stdout
    assert str(sidecar_root / "starship.toml") in result.stdout
    assert "config/alacritty" not in result.stdout
    assert str(xdg_config_home / "vc-frame" / "config.kdl") not in result.stdout
    assert "Done." in result.stdout


def test_frontier_install_uses_sidecar_root_without_touching_global_layout(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    home.mkdir()
    xdg_config_home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)

    subprocess.run(
        ["bash", str(INSTALL_FRONTIER_SCRIPT), "--source", str(REPO_ROOT)],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    sidecar_root = xdg_config_home / "vetcoders" / "frontier"
    installed_layout = sidecar_root / "vc-frame" / "layouts" / "dashboard.kdl"
    assert installed_layout.is_symlink()
    assert (
        installed_layout.resolve()
        == REPO_ROOT / "config" / "vc-frame" / "layouts" / "dashboard.kdl"
    )
    assert (sidecar_root / "starship.toml").is_symlink()
    assert not (xdg_config_home / "vc-frame" / "config.kdl").exists()
    assert not (xdg_config_home / "starship.toml").exists()


def test_spawn_export_frontier_sidecars_mix_repo_prompt_with_companion_vc_frame(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )

    home.mkdir()
    fake_bin.mkdir()
    vc_frame_config.parent.mkdir(parents=True)
    vc_frame_config.write_text("layout {}\n", encoding="utf-8")
    _write_fake_binary(fake_bin, "starship")
    _write_fake_binary(fake_bin, "atuin")
    _write_fake_binary(fake_bin, "vc-frame")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["SPAWN_ROOT"] = str(REPO_ROOT)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env.pop("STARSHIP_CONFIG", None)
    env.pop("ATUIN_CONFIG", None)
    env.pop("VC_FRAME_CONFIG_DIR", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{COMMON_SCRIPT}"; '
                "spawn_export_frontier_sidecars; "
                'printf "STARSHIP_CONFIG=%s\\n" "$STARSHIP_CONFIG"; '
                'printf "ATUIN_CONFIG=%s\\n" "$ATUIN_CONFIG"; '
                'printf "VC_FRAME_CONFIG_DIR=%s\\n" "$VC_FRAME_CONFIG_DIR"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert f"STARSHIP_CONFIG={REPO_ROOT / 'config' / 'starship.toml'}" in result.stdout
    assert (
        f"ATUIN_CONFIG={REPO_ROOT / 'config' / 'atuin' / 'config.toml'}"
        in result.stdout
    )
    assert f"VC_FRAME_CONFIG_DIR={vc_frame_config.parent}" in result.stdout
