"""Thin git CLI wrappers backing the `repo-full` compact repo-state summary."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git(
    path: Path, *args: str, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run one git subcommand in `path`, returning the raw completed process."""
    return subprocess.run(
        ["git", *args],
        cwd=path,
        capture_output=True,
        text=True,
        check=check,
    )


def _git_text(path: Path, *args: str, default: str = "") -> str:
    """Return trimmed stdout for one git command, or `default` on non-zero exit."""
    result = _git(path, *args)
    if result.returncode != 0:
        return default
    return result.stdout.strip()


def _git_lines(path: Path, *args: str) -> list[str]:
    """Return non-blank stdout lines for one git command."""
    text = _git_text(path, *args)
    return [line for line in text.splitlines() if line.strip()]


def _git_root(path: Path) -> Path:
    """Resolve the repo toplevel for `path`; falls back to `path` if not a repo."""
    root = _git_text(path, "rev-parse", "--show-toplevel")
    return Path(root).resolve() if root else path.resolve()


def _require_git_root(path: Path) -> Path:
    """Resolve the repo toplevel for `path`, raising RuntimeError if not a git repo."""
    try:
        result = _git(path, "rev-parse", "--show-toplevel")
    except FileNotFoundError as exc:
        raise RuntimeError("git executable is not available on PATH") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        message = f"not a git repository: {path}"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    return Path(result.stdout.strip()).resolve()


def _ahead_behind(path: Path, upstream: str) -> tuple[int, int]:
    """Return (ahead, behind) commit counts of HEAD vs `upstream`; (0, 0) if unset."""
    if not upstream:
        return (0, 0)
    raw = _git_text(path, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    parts = raw.split()
    if len(parts) != 2:
        return (0, 0)
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return (0, 0)


def _status_counts(path: Path) -> dict[str, int]:
    """Tally staged/unstaged/untracked files from `git status --porcelain`."""
    staged = unstaged = untracked = 0
    for line in _git_lines(path, "status", "--porcelain"):
        if line.startswith("??"):
            untracked += 1
            continue
        if line[:1].strip():
            staged += 1
        if line[1:2].strip():
            unstaged += 1
    return {"staged": staged, "unstaged": unstaged, "untracked": untracked}


def _remotes(path: Path) -> dict[str, dict[str, str]]:
    """Map remote name -> {fetch/push: url} from `git remote -v`."""
    remotes: dict[str, dict[str, str]] = {}
    for line in _git_lines(path, "remote", "-v"):
        parts = line.split()
        if len(parts) < 3:
            continue
        name, url, kind = parts[:3]
        remotes.setdefault(name, {})[kind.strip("()")] = url
    return remotes


def _recent_commits(path: Path, limit: int = 10) -> list[dict[str, str]]:
    """Return up to `limit` recent commits as short/full/date/author/title dicts."""
    commits: list[dict[str, str]] = []
    for line in _git_lines(
        path,
        "log",
        f"-n{limit}",
        "--date=short",
        "--pretty=format:%h%x00%H%x00%ad%x00%an%x00%s",
    ):
        parts = line.split("\x00")
        if len(parts) != 5:
            continue
        short, full, date, author, title = parts
        commits.append(
            {
                "short": short,
                "full": full,
                "date": date,
                "author": author,
                "title": title,
            }
        )
    return commits


def _worktrees(path: Path) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain` into one dict per worktree entry."""
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in _git_lines(path, "worktree", "list", "--porcelain"):
        if not line:
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                worktrees.append(current)
            current = {"path": value}
        elif current:
            current[key] = value
    if current:
        worktrees.append(current)
    return worktrees


def repo_full(path: str | Path = ".") -> dict[str, Any]:
    """Return compact repo state similar to the operator `repo-full` helper."""
    requested_path = Path(path).expanduser().resolve()
    root = _require_git_root(requested_path)
    branch = _git_text(root, "branch", "--show-current", default="HEAD")
    upstream = _git_text(
        root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
    )
    ahead, behind = _ahead_behind(root, upstream)
    status_counts = _status_counts(root)
    default_remote = (
        _git_text(root, "remote").splitlines()[0] if _git_text(root, "remote") else ""
    )
    default_branch = ""
    if default_remote:
        default_ref = _git_text(
            root, "symbolic-ref", f"refs/remotes/{default_remote}/HEAD"
        )
        if default_ref:
            default_branch = default_ref.rsplit("/", 1)[-1]

    return {
        "repo": root.name,
        "requested_path": str(requested_path),
        "root": str(root),
        "git_available": True,
        "branch": branch,
        "head_short": _git_text(root, "rev-parse", "--short", "HEAD"),
        "head_full": _git_text(root, "rev-parse", "HEAD"),
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "default_remote": default_remote,
        "default_branch": default_branch,
        "remotes": _remotes(root),
        "status": status_counts,
        "stashes": len(_git_lines(root, "stash", "list")),
        "worktrees": _worktrees(root),
        "recent_commits": _recent_commits(root),
    }


def repo_full_summary(path: str | Path = ".") -> str:
    """Render `repo_full` state as a short Markdown summary (branch/dirt/commits)."""
    state = repo_full(path)
    status = state["status"]
    lines = [
        f"# {state['repo']}",
        "",
        f"- Root: {state['root']}",
        f"- Branch: {state['branch']}",
        f"- Upstream: {state['upstream'] or 'none'}",
        f"- Ahead / behind: {state['ahead']} / {state['behind']}",
        f"- HEAD: {state['head_short']}",
        f"- Dirt: staged {status['staged']}, unstaged {status['unstaged']}, untracked {status['untracked']}",
        f"- Stashes: {state['stashes']}",
        f"- Worktrees: {len(state['worktrees'])}",
        "",
        "## Recent commits",
    ]
    for commit in state["recent_commits"][:5]:
        lines.append(f"- {commit['short']} {commit['date']} {commit['title']}")
    return "\n".join(lines)
