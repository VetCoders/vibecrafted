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


def test_sourcing_helper_repins_frontier_sidecars_over_inherited_env(
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
    env["VIBECRAFT_ROOT"] = str(REPO_ROOT)
    env["STARSHIP_CONFIG"] = str(tmp_path / "stale-starship.toml")
    env["ATUIN_CONFIG"] = str(tmp_path / "stale-atuin.toml")
    env["ZELLIJ_CONFIG_DIR"] = str(tmp_path / "stale-zellij")

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
