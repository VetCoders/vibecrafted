from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_SYNC = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "skills_sync.sh"
INSTALL_SHELL = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "install-shell.sh"


def _write_stub_command(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(
        "\n".join(["#!/usr/bin/env bash", "set -euo pipefail", body]) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_skills_sync_with_shell_targets_canonical_helper_and_both_shells(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_file = tmp_path / "sync.log"

    _write_stub_command(fake_bin, "ssh", f'printf "ssh:%s\\n" "$*" >> "{log_file}"')
    _write_stub_command(fake_bin, "rsync", f'printf "rsync:%s\\n" "$*" >> "{log_file}"')

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        [
            "bash",
            str(SKILLS_SYNC),
            "fakehost",
            "--source",
            str(REPO_ROOT),
            "--with-shell",
            "--dry-run",
            "--no-verify",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    stdout = result.stdout
    log = log_file.read_text(encoding="utf-8")

    assert "Syncing optional shell helper layer to fakehost" in stdout
    assert "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh" in stdout
    assert "ssh fakehost ln -sfn" in stdout
    assert "Skipping remote $HOME/.bashrc update" not in stdout
    assert "Skipping remote $HOME/.zshrc update" not in stdout
    assert "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh" in log
    assert ".bashrc" in log
    assert ".zshrc" in log


def test_install_shell_shim_prefers_current_control_plane_before_home_store(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    config = tmp_path / "config"
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(config)

    subprocess.run(
        [
            "bash",
            str(INSTALL_SHELL),
            "--source",
            str(REPO_ROOT),
            "--no-zshrc",
            "--no-bashrc",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    shim = (config / "vetcoders" / "vc-skills.sh").read_text(encoding="utf-8")
    tools_path = (
        '"$crafted_home/tools/vibecrafted-current/skills/vc-agents/shell/vetcoders.sh"'
    )
    home_path = '"$crafted_home/skills/vc-agents/shell/vetcoders.sh"'

    assert shim.index(tools_path) < shim.index(home_path)
