from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FOUNDATIONS_SCRIPT = REPO_ROOT / "scripts" / "install-foundations.sh"
MIGRATE_SCRIPT = REPO_ROOT / "scripts" / "migrate_agents_workspace.sh"
BASE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"


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
