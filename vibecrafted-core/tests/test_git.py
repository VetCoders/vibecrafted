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


def test_repo_full_preserves_porcelain_index_columns(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("unstaged\n", encoding="utf-8")

    payload = git.repo_full(repo)

    assert payload["status"] == {"staged": 0, "unstaged": 1, "untracked": 0}


def test_repo_full_rejects_non_repo_path(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a git repository"):
        git.repo_full(tmp_path)


def test_vc_git_preserves_rich_repo_full_and_prints_every_worktree(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    sibling = tmp_path / "visible-worktree"
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "worktree",
            "add",
            "-q",
            "-b",
            "visible",
            str(sibling),
        ],
        check=True,
    )

    assert git.main([str(repo)]) == 0

    output = capfd.readouterr().out
    assert "==================== REPO FULL ====================" in output
    assert "==================== WORKTREES ====================" in output
    assert str(repo) in output
    assert str(sibling) in output
    assert "visible" in output
