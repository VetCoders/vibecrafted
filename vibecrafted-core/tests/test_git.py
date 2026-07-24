from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from vibecrafted_core import git


def _init_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "tester"], check=True
    )
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)


def test_repo_full_reports_git_availability_and_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    payload = git.repo_full(repo)

    assert payload["git_available"] is True
    assert payload["repo"] == "repo"
    assert payload["branch"] == "main"
    assert payload["recent_commits"][0]["title"] == "init"


def test_repo_full_rejects_non_repo_path(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a git repository"):
        git.repo_full(tmp_path)
