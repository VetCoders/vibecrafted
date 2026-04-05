from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"
COMMON_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "common.sh"
INSTALL_FRONTIER_SCRIPT = (
    REPO_ROOT / "skills" / "vc-agents" / "scripts" / "install-frontier-config.sh"
)


def _write_fake_binary(bin_dir: Path, name: str) -> None:
    script = bin_dir / name
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)


def _write_capture_binary(bin_dir: Path, name: str, capture_file: Path) -> None:
    script = bin_dir / name
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf "%s\\n" "$@"',
                '  printf "ZELLIJ_CONFIG_DIR=%s\\n" "${ZELLIJ_CONFIG_DIR:-}"',
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


def test_vc_frontier_paths_mix_repo_prompt_with_companion_zellij(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    zellij_config = xdg_config_home / "vetcoders" / "frontier" / "zellij" / "config.kdl"
    zellij_config.parent.mkdir(parents=True)
    zellij_config.write_text("layout {}\n", encoding="utf-8")
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env.pop("STARSHIP_CONFIG", None)
    env.pop("ZELLIJ_CONFIG_DIR", None)

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
    assert f"ZELLIJ_CONFIG_DIR={zellij_config.parent}" in result.stdout


def test_vc_dashboard_mixes_companion_zellij_config_with_repo_layout(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"
    zellij_config = xdg_config_home / "vetcoders" / "frontier" / "zellij" / "config.kdl"

    home.mkdir()
    fake_bin.mkdir()
    zellij_config.parent.mkdir(parents=True)
    zellij_config.write_text('default_layout "compact"\n', encoding="utf-8")
    _write_capture_binary(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env.pop("ZELLIJ_CONFIG_DIR", None)
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
    assert f"{_expected_operator_session()}-marbles" in payload
    assert "--new-session-with-layout" in payload
    assert (
        str(REPO_ROOT / "config" / "zellij" / "layouts" / "vc-marbles.kdl") in payload
    )
    assert f"ZELLIJ_CONFIG_DIR={zellij_config.parent}" in payload


def test_vc_dashboard_uses_base_run_id_session_without_layout_suffix(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_capture_binary(fake_bin, "zellij", capture_file)

    zellij_config = xdg_config_home / "vetcoders" / "frontier" / "zellij" / "config.kdl"
    zellij_config.parent.mkdir(parents=True)
    zellij_config.write_text("layout {}\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    env.pop("ZELLIJ_CONFIG_DIR", None)
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
    assert _expected_operator_session(env["VIBECRAFTED_RUN_ID"]) in payload
    assert (
        f"{_expected_operator_session(env['VIBECRAFTED_RUN_ID'])}-marbles"
        not in payload
    )


def test_sourcing_helper_exports_frontier_sidecars_per_asset(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    zellij_config = xdg_config_home / "vetcoders" / "frontier" / "zellij" / "config.kdl"

    home.mkdir()
    fake_bin.mkdir()
    zellij_config.parent.mkdir(parents=True)
    zellij_config.write_text("layout {}\n", encoding="utf-8")
    _write_fake_binary(fake_bin, "starship")
    _write_fake_binary(fake_bin, "atuin")
    _write_fake_binary(fake_bin, "zellij")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env.pop("STARSHIP_CONFIG", None)
    env.pop("ATUIN_CONFIG", None)
    env.pop("ZELLIJ_CONFIG_DIR", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'printf "STARSHIP_CONFIG=%s\\n" "$STARSHIP_CONFIG"; '
                'printf "ATUIN_CONFIG=%s\\n" "$ATUIN_CONFIG"; '
                'printf "ZELLIJ_CONFIG_DIR=%s\\n" "$ZELLIJ_CONFIG_DIR"'
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
    assert f"ZELLIJ_CONFIG_DIR={zellij_config.parent}" in result.stdout


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
    assert "config/zellij/config.kdl" in result.stdout
    assert str(sidecar_root / "zellij" / "config.kdl") in result.stdout
    assert str(sidecar_root / "starship.toml") in result.stdout
    assert "config/alacritty" not in result.stdout
    assert str(xdg_config_home / "zellij" / "config.kdl") not in result.stdout
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
    installed_layout = sidecar_root / "zellij" / "layouts" / "vc-dashboard.kdl"
    assert installed_layout.is_symlink()
    assert (
        installed_layout.resolve()
        == REPO_ROOT / "config" / "zellij" / "layouts" / "vc-dashboard.kdl"
    )
    assert (sidecar_root / "starship.toml").is_symlink()
    assert not (xdg_config_home / "zellij" / "config.kdl").exists()
    assert not (xdg_config_home / "starship.toml").exists()


def test_spawn_export_frontier_sidecars_mix_repo_prompt_with_companion_zellij(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    zellij_config = xdg_config_home / "vetcoders" / "frontier" / "zellij" / "config.kdl"

    home.mkdir()
    fake_bin.mkdir()
    zellij_config.parent.mkdir(parents=True)
    zellij_config.write_text("layout {}\n", encoding="utf-8")
    _write_fake_binary(fake_bin, "starship")
    _write_fake_binary(fake_bin, "atuin")
    _write_fake_binary(fake_bin, "zellij")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["SPAWN_ROOT"] = str(REPO_ROOT)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env.pop("STARSHIP_CONFIG", None)
    env.pop("ZELLIJ_CONFIG_DIR", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{COMMON_SCRIPT}"; '
                "spawn_export_frontier_sidecars; "
                'printf "STARSHIP_CONFIG=%s\\n" "$STARSHIP_CONFIG"; '
                'printf "ATUIN_CONFIG=%s\\n" "$ATUIN_CONFIG"; '
                'printf "ZELLIJ_CONFIG_DIR=%s\\n" "$ZELLIJ_CONFIG_DIR"'
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
    assert f"ZELLIJ_CONFIG_DIR={zellij_config.parent}" in result.stdout
