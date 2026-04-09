from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"


def _write_fake_binary(bin_dir: Path, name: str) -> None:
    script = bin_dir / name
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)


def test_sourcing_helper_respects_existing_user_config(
    tmp_path: Path,
) -> None:
    """When the user already has config env vars set, vetcoders.sh must NOT
    override them. Frontier configs are suggestions, not mandates."""
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

    user_starship = str(tmp_path / "user-starship.toml")
    user_atuin = str(tmp_path / "user-atuin.toml")
    user_zellij = str(tmp_path / "user-zellij")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["STARSHIP_CONFIG"] = user_starship
    env["ATUIN_CONFIG"] = user_atuin
    env["ZELLIJ_CONFIG_DIR"] = user_zellij

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

    # User's configs must be preserved — not overwritten by frontier
    assert f"STARSHIP_CONFIG={user_starship}" in result.stdout
    assert f"ATUIN_CONFIG={user_atuin}" in result.stdout
    assert f"ZELLIJ_CONFIG_DIR={user_zellij}" in result.stdout


def test_sourcing_helper_sets_frontier_when_no_user_config(
    tmp_path: Path,
) -> None:
    """When user has no config env vars, vetcoders.sh provides frontier defaults."""
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
    # No STARSHIP_CONFIG, ATUIN_CONFIG, ZELLIJ_CONFIG_DIR set
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

    # Frontier defaults should be set
    assert "STARSHIP_CONFIG=" in result.stdout
    assert f"ZELLIJ_CONFIG_DIR={zellij_config.parent}" in result.stdout
