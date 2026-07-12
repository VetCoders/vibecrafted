from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_SYNC = REPO_ROOT / "runtime" / "scripts" / "skills_sync.sh"
INSTALL_SHELL = REPO_ROOT / "runtime" / "scripts" / "install-shell.sh"


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

    assert "Syncing optional shell helper layer to fakehost" in stdout
    assert "$HOME/.local/share/vibecrafted/tools/vibecrafted-current/skills" in stdout
    assert "$HOME/.vibecrafted/skills" not in stdout
    assert "_template" not in stdout
    assert "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh" in stdout
    assert "ssh fakehost ln -sfn" in stdout
    assert "Skipping remote $HOME/.bashrc update" not in stdout
    assert "Skipping remote $HOME/.zshrc update" not in stdout
    assert "$HOME/.local/share/vibecrafted/tools/vibecrafted-local/skills" in stdout
    assert "rsync" in stdout
    assert ".bashrc" in stdout
    assert ".zshrc" in stdout
    assert not log_file.exists(), "dry-run must not execute ssh or rsync"


def test_skills_sync_with_shell_real_run_targets_canonical_helper_and_both_shells(
    tmp_path: Path,
) -> None:
    # Real run (no --dry-run) actually invokes the ssh/rsync shims; the shim log
    # captures the exact commands, proving canonical targeting and that both
    # shells are hit. Complements the dry-run test above, which only inspects
    # the printed plan and asserts zero execution.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_file = tmp_path / "sync.log"

    _write_stub_command(fake_bin, "ssh", f'printf "ssh:%s\\n" "$*" >> "{log_file}"')
    _write_stub_command(fake_bin, "rsync", f'printf "rsync:%s\\n" "$*" >> "{log_file}"')

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    subprocess.run(
        [
            "bash",
            str(SKILLS_SYNC),
            "fakehost",
            "--source",
            str(REPO_ROOT),
            "--with-shell",
            "--no-verify",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    log = log_file.read_text(encoding="utf-8")

    assert "$HOME/.local/share/vibecrafted/tools/vibecrafted-local/skills" in log
    assert "$HOME/.vibecrafted/skills" not in log
    assert "_template" not in log
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
    tools_path = '"$crafted_tools_home/vibecrafted-current/runtime/shell/vetcoders.sh"'
    home_path = '"$crafted_home/runtime/shell/vetcoders.sh"'

    assert shim.index(tools_path) < shim.index(home_path)
    assert str(REPO_ROOT) not in shim
    assert "DEV MODE OPT-IN: live repo override via VIBECRAFTED_ROOT" in shim


def test_install_shell_does_not_write_rc_files_without_consent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config = tmp_path / "config"
    home.mkdir()
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    zshrc.write_text("# zsh user config\n", encoding="utf-8")
    bashrc.write_text("# bash user config\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(config)

    result = subprocess.run(
        ["bash", str(INSTALL_SHELL), "--source", str(REPO_ROOT)],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert (config / "vetcoders" / "vc-skills.sh").exists()
    assert zshrc.read_text(encoding="utf-8") == "# zsh user config\n"
    assert bashrc.read_text(encoding="utf-8") == "# bash user config\n"
    assert "Shell rc files were not changed automatically." in result.stdout


def test_install_shell_writes_rc_files_with_consent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config = tmp_path / "config"
    home.mkdir()
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    zshrc.write_text("# zsh user config\n", encoding="utf-8")
    bashrc.write_text("# bash user config\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(config)

    subprocess.run(
        ["bash", str(INSTALL_SHELL), "--source", str(REPO_ROOT), "--write-rc"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "vetcoders/vc-skills.sh" in zshrc.read_text(encoding="utf-8")
    assert "vetcoders/vc-skills.sh" in bashrc.read_text(encoding="utf-8")
