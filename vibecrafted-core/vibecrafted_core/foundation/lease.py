from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .model import DestructiveChangeLease


@dataclass(frozen=True)
class LeaseValidation:
    allowed: bool
    deleted_files: int
    deleted_loc: int
    paths: tuple[str, ...]
    violations: tuple[str, ...]


def lease_budget_hash(
    *,
    allowed_paths: Iterable[str],
    max_deleted_files: int,
    max_deleted_loc: int,
    expected_deleted_symbols: Iterable[str],
    risk_class: str,
    approved_by: str,
) -> str:
    payload = {
        "allowed_paths": sorted(allowed_paths),
        "max_deleted_files": max_deleted_files,
        "max_deleted_loc": max_deleted_loc,
        "expected_deleted_symbols": sorted(expected_deleted_symbols),
        "risk_class": risk_class,
        "approved_by": approved_by,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dirty_snapshot_hash(root: str | Path) -> str:
    repo = Path(root).resolve()
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    digest = hashlib.sha256(result.stdout.encode("utf-8", errors="surrogateescape"))
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if diff.returncode != 0:
        raise RuntimeError((diff.stderr or b"git diff failed").decode(errors="replace"))
    digest.update(diff.stdout)
    for record in result.stdout.split("\0"):
        if not record.startswith("?? "):
            continue
        target = repo / record[3:]
        if target.is_file():
            digest.update(record[3:].encode("utf-8", errors="surrogateescape"))
            digest.update(target.read_bytes())
    return digest.hexdigest()


def create_recovery_checkpoint(root: str | Path, *, run_id: str, cut_id: str) -> str:
    repo = Path(root).resolve()
    ref = f"refs/vibecrafted/checkpoints/{run_id}/{cut_id}"
    result = subprocess.run(
        ["git", "update-ref", ref, "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return ref


def _allowed(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def validate_diff_text(
    lease: DestructiveChangeLease,
    *,
    name_status: str,
    numstat: str,
    deleted_symbols: Iterable[str] = (),
) -> LeaseValidation:
    paths: list[str] = []
    deleted_files = 0
    for line in name_status.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        changed = parts[-1]
        paths.append(changed)
        if status.startswith("D"):
            deleted_files += 1
    deleted_loc = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1].isdigit():
            deleted_loc += int(parts[1])
    violations: list[str] = []
    outside = sorted(path for path in paths if not _allowed(path, lease.allowed_paths))
    if outside:
        violations.append("paths outside lease: " + ", ".join(outside))
    if deleted_files > lease.max_deleted_files:
        violations.append(
            f"deleted files {deleted_files} exceeds {lease.max_deleted_files}"
        )
    if deleted_loc > lease.max_deleted_loc:
        violations.append(f"deleted LOC {deleted_loc} exceeds {lease.max_deleted_loc}")
    unexpected_symbols = sorted(
        set(deleted_symbols) - set(lease.expected_deleted_symbols)
    )
    if unexpected_symbols:
        violations.append(
            "unexpected deleted symbols: " + ", ".join(unexpected_symbols)
        )
    return LeaseValidation(
        allowed=not violations,
        deleted_files=deleted_files,
        deleted_loc=deleted_loc,
        paths=tuple(paths),
        violations=tuple(violations),
    )


def validate_delivery_commit(
    root: str | Path, lease: DestructiveChangeLease, commit: str
) -> LeaseValidation:
    repo = Path(root).resolve()
    parent = subprocess.run(
        ["git", "rev-parse", f"{commit}^"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if parent.returncode == 0:
        base = parent.stdout.strip()
    else:
        empty = subprocess.run(
            ["git", "hash-object", "-t", "tree", "--stdin"],
            cwd=repo,
            input="",
            capture_output=True,
            text=True,
            check=False,
        )
        if empty.returncode != 0:
            raise RuntimeError((empty.stderr or "cannot derive empty tree").strip())
        base = empty.stdout.strip()
    name = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", base, commit],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    num = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--numstat", "-r", base, commit],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if name.returncode != 0 or num.returncode != 0:
        raise RuntimeError((name.stderr or num.stderr or "diff-tree failed").strip())
    return validate_diff_text(
        lease,
        name_status=name.stdout,
        numstat=num.stdout,
        deleted_symbols=_deleted_python_symbols(repo, base, commit, name.stdout),
    )


def validate_staged_diff(
    root: str | Path, lease: DestructiveChangeLease
) -> LeaseValidation:
    repo = Path(root).resolve()
    name = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    num = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if name.returncode != 0 or num.returncode != 0:
        raise RuntimeError((name.stderr or num.stderr or "staged diff failed").strip())
    return validate_diff_text(lease, name_status=name.stdout, numstat=num.stdout)


def _deleted_python_symbols(
    repo: Path, base: str, commit: str, name_status: str
) -> tuple[str, ...]:
    import ast

    deleted: set[str] = set()
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        path = parts[-1]
        if not path.endswith(".py"):
            continue

        def symbols(ref: str) -> set[str]:
            result = subprocess.run(
                ["git", "show", f"{ref}:{path}"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return set()
            try:
                tree = ast.parse(result.stdout)
            except SyntaxError:
                return set()
            return {
                node.name
                for node in tree.body
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
                and not node.name.startswith("_")
            }

        deleted.update(symbols(base) - symbols(commit))
    return tuple(sorted(deleted))
