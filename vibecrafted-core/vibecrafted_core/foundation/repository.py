from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from .model import EvidenceState, EvidenceValue, RepoAuthority, RepoRelation

GitRunner = Callable[[Path, tuple[str, ...]], subprocess.CompletedProcess[str]]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _run(root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def _probe(root: Path, args: tuple[str, ...], runner: GitRunner) -> EvidenceValue:
    try:
        result = runner(root, args)
    except FileNotFoundError as exc:
        return EvidenceValue.failed(error_kind="git_missing", error=str(exc))
    except OSError as exc:
        return EvidenceValue.failed(error_kind="git_error", error=str(exc))
    command = "git " + " ".join(args)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return EvidenceValue.failed(
            error_kind="git_exit",
            error=detail or f"exit {result.returncode}",
            evidence=command,
        )
    return EvidenceValue.known(
        result.stdout.strip(), evidence=command, observed_at=_now()
    )


def normalize_remote_identity(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if re.match(r"^[^/@:]+@[^/:]+:.+", value):
        host_path = value.split("@", 1)[1]
        host, path = host_path.split(":", 1)
        return f"ssh://{host.lower()}/{path.removesuffix('.git')}"
    parsed = urlsplit(value)
    if parsed.scheme:
        host = (parsed.hostname or "").lower()
        port = f":{parsed.port}" if parsed.port else ""
        path = parsed.path.removesuffix(".git")
        return urlunsplit((parsed.scheme.lower(), host + port, path, "", ""))
    return str(Path(value).expanduser().resolve())


def _count_probe(
    root: Path, left: str, right: str, runner: GitRunner
) -> tuple[EvidenceValue, EvidenceValue]:
    raw = _probe(
        root, ("rev-list", "--left-right", "--count", f"{left}...{right}"), runner
    )
    if raw.state is not EvidenceState.KNOWN:
        unknown = EvidenceValue.failed(
            error_kind="ahead_behind_error", error=raw.error, evidence=raw.evidence
        )
        return unknown, unknown
    parts = str(raw.value).split()
    if len(parts) != 2:
        unknown = EvidenceValue.failed(
            error_kind="malformed_ahead_behind",
            error=f"expected two counts, got {raw.value!r}",
            evidence=raw.evidence,
        )
        return unknown, unknown
    try:
        return EvidenceValue.known(
            int(parts[0]), evidence=raw.evidence
        ), EvidenceValue.known(int(parts[1]), evidence=raw.evidence)
    except ValueError:
        unknown = EvidenceValue.failed(
            error_kind="malformed_ahead_behind",
            error=str(raw.value),
            evidence=raw.evidence,
        )
        return unknown, unknown


def _lines(probe: EvidenceValue) -> tuple[str, ...]:
    if probe.state is not EvidenceState.KNOWN:
        return ()
    return tuple(line for line in str(probe.value).splitlines() if line)


def collect_repository_authority(
    root: str | Path,
    *,
    authority_ref: str,
    authority_source: str,
    receipt_id: str,
    fetch: bool = True,
    runner: GitRunner = _run,
) -> RepoAuthority:
    requested = Path(root).expanduser().resolve()
    top = _probe(requested, ("rev-parse", "--show-toplevel"), runner)
    if top.state is not EvidenceState.KNOWN or not top.value:
        raise RuntimeError(
            f"foundation requires a Git repository: {top.error or requested}"
        )
    repo = Path(str(top.value)).resolve()
    if "/" not in authority_ref:
        raise ValueError(
            "authority_ref must name an explicit remote ref, for example origin/main"
        )
    remote, branch_name = authority_ref.split("/", 1)
    remote_url = _probe(repo, ("remote", "get-url", remote), runner)
    raw_url = (
        str(remote_url.value or "") if remote_url.state is EvidenceState.KNOWN else ""
    )

    started = _now()
    fetch_result: dict[str, str] = {"started_at": started, "status": "not_requested"}
    if fetch:
        try:
            result = runner(
                repo,
                (
                    "fetch",
                    "--no-tags",
                    remote,
                    f"+refs/heads/{branch_name}:refs/remotes/{remote}/{branch_name}",
                ),
            )
            fetch_result = {
                "started_at": started,
                "ended_at": _now(),
                "status": "ok" if result.returncode == 0 else "error",
                "error": ""
                if result.returncode == 0
                else (result.stderr or result.stdout).strip(),
            }
        except OSError as exc:
            fetch_result = {
                "started_at": started,
                "ended_at": _now(),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    authority_sha = _probe(repo, ("rev-parse", "--verify", authority_ref), runner)
    head = _probe(repo, ("rev-parse", "HEAD"), runner)
    branch = _probe(repo, ("branch", "--show-current"), runner)
    if branch.state is EvidenceState.KNOWN and not branch.value:
        branch = EvidenceValue.unknown(
            error_kind="detached_head", error="HEAD is detached"
        )
    upstream = _probe(
        repo, ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"), runner
    )
    if upstream.state is not EvidenceState.KNOWN:
        upstream = EvidenceValue.unknown(
            error_kind="missing_upstream",
            error=upstream.error,
            evidence=upstream.evidence,
        )

    merge_base = EvidenceValue.unknown(error_kind="unresolved_authority")
    relation = RepoRelation.UNKNOWN
    live_only: tuple[str, ...] = ()
    authority_only: tuple[str, ...] = ()
    patch_equivalents: tuple[str, ...] = ()
    ahead = EvidenceValue.unknown(error_kind="unresolved_authority")
    behind = EvidenceValue.unknown(error_kind="unresolved_authority")
    if head.state is EvidenceState.KNOWN and authority_sha.state is EvidenceState.KNOWN:
        merge_base = _probe(
            repo, ("merge-base", str(head.value), str(authority_sha.value)), runner
        )
        ahead, behind = _count_probe(
            repo, str(head.value), str(authority_sha.value), runner
        )
        live_only = _lines(
            _probe(
                repo,
                ("rev-list", "--no-merges", f"{authority_sha.value}..{head.value}"),
                runner,
            )
        )
        authority_only = _lines(
            _probe(
                repo,
                ("rev-list", "--no-merges", f"{head.value}..{authority_sha.value}"),
                runner,
            )
        )
        cherry = _lines(
            _probe(
                repo,
                (
                    "rev-list",
                    "--left-right",
                    "--cherry-mark",
                    f"{head.value}...{authority_sha.value}",
                ),
                runner,
            )
        )
        patch_equivalents = tuple(item[1:] for item in cherry if item.startswith("="))
        if merge_base.state is not EvidenceState.KNOWN:
            merge_error = merge_base.error.lower()
            relation = (
                RepoRelation.UNRELATED
                if "no merge base" in merge_error or merge_error == "exit 1"
                else RepoRelation.UNKNOWN
            )
        elif head.value == authority_sha.value:
            relation = RepoRelation.EXACT
        elif merge_base.value == authority_sha.value:
            relation = RepoRelation.DESCENDANT
        elif merge_base.value == head.value:
            relation = RepoRelation.BEHIND
        else:
            relation = RepoRelation.DIVERGED

    status = _probe(repo, ("status", "--porcelain=v1", "--untracked-files=all"), runner)
    dirty = (
        EvidenceValue.known(bool(status.value), evidence=status.evidence)
        if status.state is EvidenceState.KNOWN
        else status
    )
    detached_probe = _probe(repo, ("symbolic-ref", "-q", "HEAD"), runner)
    detached = EvidenceValue.known(detached_probe.state is not EvidenceState.KNOWN)
    shallow_raw = _probe(repo, ("rev-parse", "--is-shallow-repository"), runner)
    shallow = (
        EvidenceValue.known(
            str(shallow_raw.value).lower() == "true", evidence=shallow_raw.evidence
        )
        if shallow_raw.state is EvidenceState.KNOWN
        else shallow_raw
    )
    submodules = _probe(repo, ("submodule", "status", "--recursive"), runner)
    worktrees = _probe(repo, ("worktree", "list", "--porcelain"), runner)

    snapshot_ref = ""
    if authority_sha.state is EvidenceState.KNOWN:
        snapshot_ref = f"refs/vibecrafted/foundation/{receipt_id}/authority"
        updated = _probe(
            repo, ("update-ref", snapshot_ref, str(authority_sha.value)), runner
        )
        if updated.state is not EvidenceState.KNOWN:
            snapshot_ref = ""

    if fetch_result.get("status") == "error":
        relation = RepoRelation.UNKNOWN
        authority_sha = EvidenceValue.failed(
            error_kind="fetch_error",
            error=fetch_result.get("error", "authority fetch failed"),
            evidence=authority_ref,
        )
    elif shallow.state is EvidenceState.KNOWN and shallow.value:
        relation = RepoRelation.UNKNOWN

    return RepoAuthority(
        root=str(repo),
        authority_source=authority_source,
        authority_remote_raw=raw_url,
        authority_remote_normalized=normalize_remote_identity(raw_url),
        authority_ref=authority_ref,
        authority_sha=authority_sha,
        fetch=fetch_result,
        branch=branch,
        head=head,
        upstream=upstream,
        merge_base=merge_base,
        dirty=dirty,
        detached=detached,
        shallow=shallow,
        submodules=submodules,
        worktrees=worktrees,
        ahead=ahead,
        behind=behind,
        relation=relation,
        live_only_commits=live_only,
        authority_only_commits=authority_only,
        patch_equivalents=patch_equivalents,
        snapshot_ref=snapshot_ref,
    )
