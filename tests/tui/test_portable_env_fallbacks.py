from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FOUNDATIONS_SCRIPT = REPO_ROOT / "scripts" / "install-foundations.sh"
MIGRATE_SCRIPT = REPO_ROOT / "scripts" / "migrate_agents_workspace.sh"
BASE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"


def _write_fake_command(bin_dir: Path, name: str, body: str | None = None) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / name
    script.write_text(
        body
        or "#!/usr/bin/env bash\n"
        'case "${1:-}" in --version|--help) exit 0 ;; *) exit 0 ;; esac\n',
        encoding="utf-8",
    )
    script.chmod(0o755)


def test_install_foundations_check_falls_back_to_home_without_vibecrafted_root(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = BASE_PATH
    env.pop("VIBECRAFTED_ROOT", None)
    env.pop("VIBECRAFTED_HOME", None)
    env.pop("VIBECRAFTED_BIN", None)

    result = subprocess.run(
        ["bash", str(FOUNDATIONS_SCRIPT), "--check"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert str(home / ".vibecrafted" / "bin") in result.stdout
    assert "Would download loctree" in result.stdout


def test_install_foundations_default_treats_agent_cli_bootstrap_as_best_effort(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "fake-bin"
    prefix = tmp_path / "prefix"
    home.mkdir()

    for command in ("loctree", "loctree-mcp", "aicx-mcp", "zellij", "node"):
        _write_fake_command(fake_bin, command)
    _write_fake_command(
        fake_bin,
        "npm",
        "#!/usr/bin/env bash\n"
        'if [[ "${1:-}" == "install" ]]; then exit 1; fi\n'
        "exit 0\n",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}{os.pathsep}{BASE_PATH}"
    env.pop("VIBECRAFTED_ROOT", None)
    env.pop("VIBECRAFTED_HOME", None)

    result = subprocess.run(
        ["bash", str(FOUNDATIONS_SCRIPT), "--prefix", str(prefix)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Agent CLI bootstrap incomplete; continuing" in result.stdout


def test_install_foundations_explicit_agents_target_fails_when_bootstrap_fails(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "fake-bin"
    prefix = tmp_path / "prefix"
    home.mkdir()

    _write_fake_command(fake_bin, "node")
    _write_fake_command(
        fake_bin,
        "npm",
        "#!/usr/bin/env bash\n"
        'if [[ "${1:-}" == "install" ]]; then exit 1; fi\n'
        "exit 0\n",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}{os.pathsep}{BASE_PATH}"
    env.pop("VIBECRAFTED_ROOT", None)
    env.pop("VIBECRAFTED_HOME", None)

    result = subprocess.run(
        ["bash", str(FOUNDATIONS_SCRIPT), "--prefix", str(prefix), "agents"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Agent CLIs:" in result.stdout


def test_migrate_dry_run_falls_back_to_home_and_current_directory(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    repo = workspace / "demo-repo"
    agents_plans = repo / ".ai-agents" / "plans"

    home.mkdir()
    agents_plans.mkdir(parents=True)
    (agents_plans / "20260405_backlog.md").write_text("# backlog\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = BASE_PATH
    env.pop("VIBECRAFTED_ROOT", None)
    env.pop("VIBECRAFTED_HOME", None)

    result = subprocess.run(
        ["bash", str(MIGRATE_SCRIPT), "--dry-run"],
        cwd=workspace,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    expected_target = (
        home
        / ".vibecrafted"
        / "artifacts"
        / "local"
        / repo.name
        / "2026_0405"
        / "plans"
        / "20260405_backlog.md"
    )
    assert str(home / ".vibecrafted" / "artifacts") in result.stdout
    assert str(expected_target) in result.stdout
