#!/usr/bin/env python3
"""Build and verify the complete Vibecrafted runtime payload.

The repository is a development surface. A distribution is an allowlisted
projection of it: required runtime paths must exist, development artifacts are
never copied, and symlinks must stay inside the payload.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path

SOURCE_PROVENANCE_FILE = "source-provenance.json"
SOURCE_PROVENANCE_SCHEMA = "vibecrafted.source-provenance.v1"
_OWNER_REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")

REQUIRED_FILES = (
    "VERSION",
    "LICENSE",
    "README.md",
    "Makefile",
    "install.sh",
    "install.ps1",
    "install.toml",
    "scripts/distribution_manifest.py",
    "scripts/vetcoders_install.py",
    "scripts/runtime_paths.py",
    "scripts/vibecrafted",
    "scripts/verify-vibecrafted-product.sh",
    "vibecrafted-core/pyproject.toml",
    "vibecrafted-core/vibecrafted_core/VERSION",
    "vibecrafted-core/vibecrafted_core/deck/vibecrafted",
    "vibecrafted-core/vibecrafted_core/product_contract.py",
    "vibecrafted-core/vibecrafted_core/walkaround_runner.py",
    "vibecrafted-core/vibecrafted_core/schemas/unified_product.schema.v1.json",
    "vibecrafted-core/vibecrafted_core/trust/release-policy.v1.json",
    "vibecrafted-core/vibecrafted_core/trust/vibecrafted-signing-v1.pub",
    "vibecrafted-mcp/pyproject.toml",
    "plugins/iterm2/pyproject.toml",
    "vibecrafted-app/Cargo.toml",
    "vibecrafted-app/Cargo.lock",
    "vibecrafted-server/Cargo.toml",
    "vibecrafted-server/Cargo.lock",
)

REQUIRED_DIRECTORIES = (
    "bin",
    "config",
    "docs",
    "plugins",
    "runtime/scripts",
    "runtime/shell/lib",
    "scripts/installer",
    "skills",
    "templates",
    "tools",
    "vibecrafted-app",
    "vibecrafted-core/vibecrafted_core/runtime",
    "vibecrafted-core/vibecrafted_core/skills",
    "vibecrafted-mcp",
    "vibecrafted-server",
    "vibecrafted-vm",
    "workflows",
)

# A directory name alone does not prove that its runtime survived packaging.
# Keep one stable, executable-or-documenting sentinel for every required
# surface so an empty subtree can never pass the complete-runtime gate.
REQUIRED_SURFACE_FILES = {
    "bin": "bin/vc-workflow",
    "config": "config/README.md",
    "docs": "docs/INSTALL.md",
    "plugins": "plugins/iterm2/README.md",
    "runtime/scripts": "runtime/scripts/README.md",
    "runtime/shell/lib": "runtime/shell/lib/core.sh",
    "scripts/installer": "scripts/installer/pyproject.toml",
    "skills": "skills/vc-init/SKILL.md",
    "templates": "templates/hooks/install.sh",
    "tools": "tools/README.md",
    "vibecrafted-app": "vibecrafted-app/Cargo.toml",
    "vibecrafted-core/vibecrafted_core/runtime": (
        "vibecrafted-core/vibecrafted_core/runtime/README.md"
    ),
    "vibecrafted-core/vibecrafted_core/skills": (
        "vibecrafted-core/vibecrafted_core/skills/LIVING_TREE_RULE.md"
    ),
    "vibecrafted-mcp": "vibecrafted-mcp/pyproject.toml",
    "vibecrafted-server": "vibecrafted-server/Cargo.toml",
    "vibecrafted-vm": "vibecrafted-vm/Containerfile",
    "workflows": "workflows/MARBLES.md",
}

ALLOWED_TOP_LEVEL = frozenset(
    {
        "VERSION",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "Makefile",
        "install.sh",
        "install.ps1",
        "install.toml",
        "runtime-manifest.json",
        SOURCE_PROVENANCE_FILE,
        "pyproject.toml",
        "plugin.json",
        "bin",
        "config",
        "docs",
        "plugins",
        "runtime",
        "scripts",
        "skills",
        "templates",
        "tools",
        "vibecrafted-app",
        "vibecrafted-core",
        "vibecrafted-mcp",
        "vibecrafted-server",
        "vibecrafted-vm",
        "workflows",
    }
)

FORBIDDEN_COMPONENTS = frozenset(
    {
        ".DS_Store",
        ".backup",
        ".build",
        ".circleci",
        ".coverage",
        ".devcontainer",
        ".dockerignore",
        ".env",
        ".git",
        ".github",
        ".gitignore",
        ".gitlab",
        ".junie",
        ".legacy-state-agency",
        ".loctignore",
        ".loctree",
        ".mypy_cache",
        ".next",
        ".prettierignore",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "AGENTS.md",
        "Cargo.lock",
        "CONTRIBUTING.md",
        "DerivedData",
        "Pipfile.lock",
        "__pycache__",
        "__tests__",
        "build",
        "coverage.xml",
        "dist",
        "node_modules",
        "package-lock.json",
        "pnpm-lock.yaml",
        "poetry.lock",
        "target",
        "test",
        "tests",
        "uv.lock",
        "yarn.lock",
    }
)

FORBIDDEN_SUFFIXES = (".pyc", ".pyo", ".swp", "~")
REQUIRED_LOCKFILES = frozenset(
    {
        "vibecrafted-app/Cargo.lock",
        "vibecrafted-server/Cargo.lock",
    }
)
CANONICAL_RUNTIME = Path("vibecrafted-core/vibecrafted_core/runtime")
CANONICAL_SKILLS = Path("vibecrafted-core/vibecrafted_core/skills")
# Repo-root aliases that are symlinks into the canonical package tree. Some
# mounts (colima's sshfs view of a macOS checkout) drop symlinks entirely, so
# source validation and staging must be able to project these from the
# canonical paths instead of requiring the symlink itself.
CANONICAL_PROJECTIONS = {
    "runtime": CANONICAL_RUNTIME,
    "skills": CANONICAL_SKILLS,
}


class ManifestError(ValueError):
    """The requested payload cannot satisfy the distribution contract."""


def _parse_owner_repo_url(url: str) -> str | None:
    normalized = url.strip().rstrip("/").removesuffix(".git")
    if not normalized:
        return None
    path = (
        normalized.split(":", 1)[-1]
        if ":" in normalized and not normalized.startswith("http")
        else normalized
    )
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if len(parts) < 2:
        return None
    owner_repo = f"{parts[-2]}/{parts[-1]}"
    return owner_repo if _OWNER_REPO_RE.fullmatch(owner_repo) else None


def load_source_provenance(root: str | Path) -> dict[str, str] | None:
    """Load a closed provenance record when ``root`` is an extracted release archive."""
    source_root = Path(root)
    path = source_root / SOURCE_PROVENANCE_FILE
    if not path.exists() and not path.is_symlink():
        return None
    if not path.is_file() or path.is_symlink():
        raise ManifestError(f"{SOURCE_PROVENANCE_FILE} must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"invalid {SOURCE_PROVENANCE_FILE}: {exc}") from exc
    required = {"schema", "owner_repo", "source_revision"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ManifestError(
            f"{SOURCE_PROVENANCE_FILE} does not satisfy the closed provenance schema"
        )
    owner_repo = payload.get("owner_repo")
    revision = payload.get("source_revision")
    if (
        payload.get("schema") != SOURCE_PROVENANCE_SCHEMA
        or not isinstance(owner_repo, str)
        or _OWNER_REPO_RE.fullmatch(owner_repo) is None
        or not isinstance(revision, str)
        or _GIT_SHA_RE.fullmatch(revision) is None
    ):
        raise ManifestError(
            f"{SOURCE_PROVENANCE_FILE} does not satisfy the closed provenance schema"
        )
    return {
        "schema": SOURCE_PROVENANCE_SCHEMA,
        "owner_repo": owner_repo,
        "source_revision": revision,
    }


def _git_output(root: Path, *arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *arguments],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _git_paths(root: Path, *arguments: str) -> set[Path]:
    """Return NUL-delimited Git paths, failing closed when Git cannot prove them."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = (
            exc.stderr.decode("utf-8", "replace").strip()
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr
            else str(exc)
        )
        raise ManifestError(
            f"cannot verify archive source against Git: {detail}"
        ) from exc
    return {
        Path(os.fsdecode(raw_path))
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    }


def _git_bytes(root: Path, *arguments: str) -> bytes:
    """Return raw Git output or fail closed with bounded diagnostic detail."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = (
            exc.stderr.decode("utf-8", "replace").strip()
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr
            else str(exc)
        )
        raise ManifestError(
            f"cannot verify source provenance against Git: {detail}"
        ) from exc
    return result.stdout


def _git_tree_entries(root: Path, revision: str) -> dict[Path, tuple[str, str, str]]:
    """Return included ``path -> (mode, type, object id)`` entries at revision."""
    entries: dict[Path, tuple[str, str, str]] = {}
    for raw_entry in _git_bytes(
        root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        revision,
        "--",
    ).split(b"\0"):
        if not raw_entry:
            continue
        try:
            raw_header, raw_path = raw_entry.split(b"\t", 1)
            raw_mode, raw_type, raw_oid = raw_header.split(b" ", 2)
        except ValueError as exc:
            raise ManifestError("Git returned a malformed source tree entry") from exc
        relative = Path(os.fsdecode(raw_path))
        if relative == Path(SOURCE_PROVENANCE_FILE) or not path_is_included(relative):
            continue
        entries[relative] = (
            raw_mode.decode("ascii"),
            raw_type.decode("ascii"),
            raw_oid.decode("ascii"),
        )
    return entries


def _git_object_format(root: Path) -> str:
    algorithm = _git_output(root, "rev-parse", "--show-object-format")
    if algorithm not in {"sha1", "sha256"}:
        raise ManifestError(f"unsupported Git object format: {algorithm or 'unknown'}")
    return algorithm


def _git_blob_hasher(algorithm: str, size: int):
    digest = hashlib.new(algorithm)
    digest.update(f"blob {size}\0".encode("ascii"))
    return digest


def _git_blob_oid_from_bytes(raw: bytes, algorithm: str) -> str:
    digest = _git_blob_hasher(algorithm, len(raw))
    digest.update(raw)
    return digest.hexdigest()


def _git_blob_oid_from_symlink(path: Path, algorithm: str) -> str:
    """Hash one stable symlink target as a Git blob."""
    before = path.lstat()
    if not stat.S_ISLNK(before.st_mode):
        raise ManifestError(f"staged payload path is not a symlink: {path}")
    raw = os.fsencode(os.readlink(path))
    after = path.lstat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_mode,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_mode,
    ):
        raise ManifestError(f"staged payload symlink changed during capture: {path}")
    return _git_blob_oid_from_bytes(raw, algorithm)


def _git_blob_oid_from_file(path: Path, algorithm: str) -> tuple[str, os.stat_result]:
    """Hash one no-follow, stable regular-file snapshot as a Git blob."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ManifestError(
            f"cannot capture staged payload file {path}: {exc}"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ManifestError(f"staged payload path is not a regular file: {path}")
        digest = _git_blob_hasher(algorithm, before.st_size)
        consumed = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            consumed += len(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
        if consumed != before.st_size or (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_mode,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_mode,
        ):
            raise ManifestError(f"staged payload file changed during capture: {path}")
        return digest.hexdigest(), after
    finally:
        os.close(descriptor)


def _expected_git_payload(
    root: Path, revision: str
) -> tuple[dict[Path, tuple[str, str, str]], set[Path]]:
    entries = _git_tree_entries(root, revision)
    directories: set[Path] = set()
    for relative in entries:
        directories.update(parent for parent in relative.parents if parent != Path("."))
    return entries, directories


def _assert_staged_payload_matches_git_revision(
    git_root: Path,
    payload_root: Path,
    revision: str,
) -> None:
    """Prove the copied allowlisted payload has HEAD-exact bytes, types, and modes."""
    entries, directories = _expected_git_payload(git_root, revision)
    expected_paths = set(entries) | directories
    actual_paths = {
        path.relative_to(payload_root)
        for path in _walk_entries(payload_root)
        if path.relative_to(payload_root) != Path(SOURCE_PROVENANCE_FILE)
        and path_is_included(path.relative_to(payload_root))
    }
    errors = [
        *(
            f"missing:{path.as_posix()}"
            for path in sorted(expected_paths - actual_paths)
        ),
        *(f"extra:{path.as_posix()}" for path in sorted(actual_paths - expected_paths)),
    ]
    algorithm = _git_object_format(git_root)
    for relative in sorted(expected_paths & actual_paths):
        path = payload_root / relative
        if relative in directories:
            if path.is_symlink() or not path.is_dir():
                errors.append(f"type:{relative.as_posix()}")
            continue
        mode, object_type, expected_oid = entries[relative]
        if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
            errors.append(
                f"unsupported-git-entry:{relative.as_posix()}:{mode}:{object_type}"
            )
            continue
        if mode == "120000":
            if not path.is_symlink():
                errors.append(f"type:{relative.as_posix()}")
                continue
            actual_oid = _git_blob_oid_from_symlink(path, algorithm)
        else:
            if path.is_symlink() or not path.is_file():
                errors.append(f"type:{relative.as_posix()}")
                continue
            actual_oid, metadata = _git_blob_oid_from_file(path, algorithm)
            if bool(metadata.st_mode & 0o111) != (mode == "100755"):
                errors.append(f"mode:{relative.as_posix()}")
        if actual_oid != expected_oid:
            errors.append(f"bytes:{relative.as_posix()}")
    if errors:
        raise ManifestError(
            "staged payload differs from claimed Git revision "
            f"{revision}: " + ", ".join(sorted(set(errors)))
        )


def _assert_git_payload_matches_revision(root: Path, revision: str) -> None:
    """Reject included source paths whose Git/index/worktree state is not ``revision``.

    Extracted release sources have no exact Git root and intentionally bypass this
    check: their closed provenance carrier remains the authority. For a checkout,
    however, an archive may claim its HEAD only when every path the distribution
    allowlist would copy is unchanged at HEAD. Development-only excluded paths do
    not participate in the archive and therefore do not block it.
    """
    git_root = _git_output(root, "rev-parse", "--show-toplevel")
    if not git_root or Path(git_root).resolve(strict=False) != root.resolve(
        strict=False
    ):
        return

    head_revision = _git_output(root, "rev-parse", "HEAD").lower()
    if head_revision != revision:
        raise ManifestError(
            "archive source revision does not match the exact Git root HEAD"
        )

    changed_paths: set[Path] = set()
    for arguments in (
        (
            "diff",
            "--cached",
            "--no-ext-diff",
            "--no-renames",
            "--name-only",
            "-z",
            revision,
            "--",
        ),
        (
            "diff",
            "--no-ext-diff",
            "--no-renames",
            "--name-only",
            "-z",
            "--",
        ),
        ("ls-files", "--others", "--exclude-standard", "-z"),
        ("ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
    ):
        changed_paths.update(_git_paths(root, *arguments))

    included_drift = sorted(
        {
            path.as_posix()
            for path in changed_paths
            if path.parts and path_is_included(path)
        }
    )
    if included_drift:
        raise ManifestError(
            "archive source differs from claimed Git revision "
            f"{revision}; included path(s): " + ", ".join(included_drift)
        )


def _is_exact_git_root(root: Path) -> bool:
    git_root = _git_output(root, "rev-parse", "--show-toplevel")
    return bool(
        git_root and Path(git_root).resolve(strict=False) == root.resolve(strict=False)
    )


def resolve_source_provenance(
    root: Path,
    *,
    owner_repo: str | None,
    source_revision: str | None,
) -> dict[str, str]:
    """Resolve one attributable archive identity from explicit input, env, Git, or an archive."""
    if (owner_repo is None) != (source_revision is None):
        raise ManifestError("explicit source provenance must provide an atomic pair")
    if owner_repo is not None and (not owner_repo or not source_revision):
        raise ManifestError("explicit source provenance is not canonical")
    explicit = (
        (owner_repo, source_revision)
        if owner_repo is not None and source_revision is not None
        else ("", "")
    )
    environment = (
        os.environ.get("VIBECRAFTED_SOURCE_OWNER_REPO", ""),
        os.environ.get("VIBECRAFTED_SOURCE_REVISION", ""),
    )
    git_root = _git_output(root, "rev-parse", "--show-toplevel")
    if git_root:
        resolved_git_root = Path(git_root).resolve(strict=False)
        if resolved_git_root != root.resolve(strict=False):
            raise ManifestError(
                "source root is nested inside an enclosing Git worktree; "
                f"expected the exact Git root {resolved_git_root}"
            )
        git = (
            _parse_owner_repo_url(_git_output(root, "remote", "get-url", "origin"))
            or "",
            _git_output(root, "rev-parse", "HEAD").lower(),
        )
    else:
        git = ("", "")
    inherited = load_source_provenance(root)
    carrier = (
        (inherited["owner_repo"], inherited["source_revision"])
        if inherited is not None
        else ("", "")
    )
    candidates = []
    for label, pair in (
        ("explicit", explicit),
        ("environment", environment),
        ("git", git),
        ("carrier", carrier),
    ):
        if bool(pair[0]) != bool(pair[1]):
            raise ManifestError(
                f"{label} source provenance must provide an atomic pair"
            )
        if pair[0]:
            candidates.append((label, pair))
    if not candidates:
        raise ManifestError("archive source provenance is unavailable")
    owner, revision = candidates[0][1]
    conflicts = [label for label, pair in candidates[1:] if pair != (owner, revision)]
    if conflicts:
        raise ManifestError(
            "source provenance providers disagree: "
            + ", ".join([candidates[0][0], *conflicts])
        )
    if _OWNER_REPO_RE.fullmatch(owner) is None:
        raise ManifestError("archive owner_repo must be an exact owner/repository slug")
    if _GIT_SHA_RE.fullmatch(revision) is None:
        raise ManifestError("archive source_revision must be a full lowercase Git SHA")
    return {
        "schema": SOURCE_PROVENANCE_SCHEMA,
        "owner_repo": owner,
        "source_revision": revision,
    }


def assert_source_payload_matches_provenance(
    root: Path,
    *,
    owner_repo: str | None,
    source_revision: str | None,
    payload_root: Path | None = None,
) -> dict[str, str]:
    """Resolve one provenance pair and prove an exact Git-root payload matches it.

    Git checkouts must be clean for every included distribution path at the
    claimed HEAD. When ``payload_root`` is provided, its already-copied inventory,
    types, executable bits, symlink targets, and raw blob bytes must also match
    that commit. Extracted sources intentionally retain the carrier-only path:
    provider agreement and the closed carrier schema remain their proof.
    """
    source_root = Path(root).resolve()
    provenance = resolve_source_provenance(
        source_root,
        owner_repo=owner_repo,
        source_revision=source_revision,
    )
    _assert_git_payload_matches_revision(
        source_root,
        provenance["source_revision"],
    )
    if payload_root is not None and _is_exact_git_root(source_root):
        _assert_staged_payload_matches_git_revision(
            source_root,
            Path(payload_root),
            provenance["source_revision"],
        )
    return provenance


def _relative_path(value: str | Path) -> Path:
    """Normalize ``value`` to a relative Path, rejecting absolute or ``..`` paths."""
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManifestError(f"unsafe relative path: {value}")
    return relative


def _component_is_secret_env(name: str) -> bool:
    """Return True when a path component is a live-credential env file.

    `.env` and every `.env.*` variant carry live credentials; only the
    committed `*.example` templates are distributable.
    """
    if name == ".env":
        return True
    return name.startswith(".env.") and not name.endswith(".example")


def path_is_forbidden(relative: str | Path) -> bool:
    """Return True when a relative path matches a forbidden component/suffix rule."""
    relative_path = _relative_path(relative)
    if not relative_path.parts:
        return True
    if relative_path.as_posix() in REQUIRED_LOCKFILES:
        return False
    return any(
        part in FORBIDDEN_COMPONENTS or _component_is_secret_env(part)
        for part in relative_path.parts
    ) or relative_path.name.endswith(FORBIDDEN_SUFFIXES)


def path_is_included(relative: str | Path) -> bool:
    """Return True when a relative path is under an allowed top-level and not forbidden."""
    relative_path = _relative_path(relative)
    return bool(
        relative_path.parts
        and relative_path.parts[0] in ALLOWED_TOP_LEVEL
        and not path_is_forbidden(relative_path)
    )


def _symlink_error(root: Path, path: Path) -> str | None:
    """Return a description of why a symlink is unsafe, or None if it is fine.

    Rejects absolute targets, targets resolving outside ``root``, and targets
    landing on an excluded path.
    """
    if not path.is_symlink():
        return None
    raw_target = os.readlink(path)
    target = Path(raw_target)
    relative = path.relative_to(root)
    if target.is_absolute():
        return f"symlink escapes payload: {relative} -> {raw_target}"
    resolved_root = root.resolve()
    resolved_target = (path.parent / target).resolve(strict=False)
    try:
        target_relative = resolved_target.relative_to(resolved_root)
    except ValueError:
        return f"symlink escapes payload: {relative} -> {raw_target}"
    if not path_is_included(target_relative):
        return f"symlink targets excluded path: {relative} -> {raw_target}"
    return None


def _required_candidate(
    root: Path, relative: str, *, allow_runtime_projection: bool
) -> Path:
    """Resolve a required-path candidate, projecting onto a canonical alias if needed.

    When ``allow_runtime_projection`` is set and the direct candidate is absent,
    falls back to the canonical `runtime`/`skills` package path (see
    ``CANONICAL_PROJECTIONS``) so source-tree validation survives mounts that
    drop symlinks (e.g. colima's sshfs view of a macOS checkout).
    """
    candidate = root / relative
    relative_path = Path(relative)
    if (
        allow_runtime_projection
        and relative_path.parts
        and relative_path.parts[0] in CANONICAL_PROJECTIONS
        and not candidate.exists()
    ):
        canonical = CANONICAL_PROJECTIONS[relative_path.parts[0]]
        return root / canonical.joinpath(*relative_path.parts[1:])
    return candidate


def _required_errors(
    root: Path, *, allow_runtime_projection: bool = False
) -> list[str]:
    """Collect human-readable errors for every missing required file/dir/surface."""
    errors = []
    for relative in REQUIRED_FILES:
        candidate = _required_candidate(
            root, relative, allow_runtime_projection=allow_runtime_projection
        )
        if not candidate.is_file():
            errors.append(f"missing required path: {relative}")
    for relative in REQUIRED_DIRECTORIES:
        candidate = _required_candidate(
            root, relative, allow_runtime_projection=allow_runtime_projection
        )
        if not candidate.is_dir():
            errors.append(f"missing required path: {relative}")
    for surface, relative in REQUIRED_SURFACE_FILES.items():
        candidate = _required_candidate(
            root, relative, allow_runtime_projection=allow_runtime_projection
        )
        if not candidate.is_file():
            errors.append(f"missing required runtime content: {surface} -> {relative}")
    return errors


def _walk_entries(root: Path) -> Iterable[Path]:
    """Yield every directory then file under root, sorted, pruning forbidden dirs in-place."""
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        directory_names.sort()
        file_names.sort()
        for name in directory_names:
            yield current_path / name
        for name in file_names:
            yield current_path / name
        directory_names[:] = [
            name
            for name in directory_names
            if not path_is_forbidden((current_path / name).relative_to(root))
        ]


def validate_payload(
    root: str | Path,
    *,
    require_source_provenance: bool = False,
    expected_owner_repo: str | None = None,
    expected_source_revision: str | None = None,
) -> None:
    """Raise ManifestError with every violation found in an already-staged payload."""
    payload_root = Path(root)
    if not payload_root.is_dir():
        raise ManifestError(f"payload root is not a directory: {payload_root}")

    errors = _required_errors(payload_root)
    if (expected_owner_repo is None) != (expected_source_revision is None):
        errors.append("expected source provenance must provide an atomic pair")
    elif expected_owner_repo is not None and (
        _OWNER_REPO_RE.fullmatch(expected_owner_repo) is None
        or _GIT_SHA_RE.fullmatch(expected_source_revision or "") is None
    ):
        errors.append("expected source provenance is not canonical")
    try:
        provenance = load_source_provenance(payload_root)
    except ManifestError as exc:
        errors.append(str(exc))
        provenance = None
    if require_source_provenance and provenance is None:
        errors.append(f"missing required path: {SOURCE_PROVENANCE_FILE}")
    if provenance is not None and expected_owner_repo is not None:
        expected = (expected_owner_repo, expected_source_revision or "")
        actual = (provenance["owner_repo"], provenance["source_revision"])
        if actual != expected:
            errors.append(
                "source provenance does not match the expected owner/revision"
            )
    for path in _walk_entries(payload_root):
        relative = path.relative_to(payload_root)
        if path_is_forbidden(relative):
            errors.append(f"forbidden path: {relative}")
            continue
        if relative.parts[0] not in ALLOWED_TOP_LEVEL:
            errors.append(f"unexpected top-level path: {relative}")
            continue
        if error := _symlink_error(payload_root, path):
            errors.append(error)

    if errors:
        raise ManifestError("\n".join(sorted(set(errors))))


def _validate_source(root: Path) -> None:
    """Raise ManifestError for missing required paths or unsafe symlinks in a source tree.

    Unlike ``validate_payload`` this only checks included paths and required
    surfaces (with runtime-projection fallback) — it does not flag paths as
    forbidden, since the source tree legitimately contains excluded content.
    """
    errors = _required_errors(root, allow_runtime_projection=True)
    try:
        load_source_provenance(root)
    except ManifestError as exc:
        errors.append(str(exc))
    for path in _walk_entries(root):
        relative = path.relative_to(root)
        if not path_is_included(relative):
            continue
        if error := _symlink_error(root, path):
            errors.append(error)
    if errors:
        raise ManifestError("\n".join(sorted(set(errors))))


def _remove_path(path: Path) -> None:
    """Delete a path regardless of whether it is a symlink, file, or directory tree."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_included(source_root: Path, source: Path, destination: Path) -> None:
    """Recursively copy source to destination, skipping anything path_is_included() excludes.

    Symlinks are re-created (after a safety check) rather than followed;
    directories are copied with their own recursive fan-out.
    """
    relative = source.relative_to(source_root)
    if not path_is_included(relative):
        return
    if source.is_symlink():
        if error := _symlink_error(source_root, source):
            raise ManifestError(error)
        if destination.exists() or destination.is_symlink():
            _remove_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(os.readlink(source))
        return
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            _copy_included(source_root, child, destination / child.name)
        try:
            destination.rmdir()
        except OSError:
            pass
        return
    if source.is_file():
        if destination.exists() and destination.is_dir():
            _remove_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def stage_payload(
    source: str | Path,
    destination: str | Path,
    *,
    mirror: bool = False,
    owner_repo: str | None = None,
    source_revision: str | None = None,
    require_source_provenance: bool = False,
) -> None:
    """Copy the allowlisted subset of source into destination and validate the result.

    When ``mirror`` is set the destination is wiped first. After copying, the
    `runtime`/`skills` alias symlinks are (re)created if only the canonical
    package paths were staged, then the whole payload is re-validated.
    """
    source_root = Path(source).resolve()
    destination_root = Path(destination)
    if not source_root.is_dir():
        raise ManifestError(f"source root is not a directory: {source_root}")
    _validate_source(source_root)
    if (owner_repo is None) != (source_revision is None):
        raise ManifestError("explicit source provenance must provide an atomic pair")
    provenance = (
        assert_source_payload_matches_provenance(
            source_root,
            owner_repo=owner_repo,
            source_revision=source_revision,
        )
        if owner_repo is not None or require_source_provenance
        else None
    )

    if mirror and (destination_root.exists() or destination_root.is_symlink()):
        _remove_path(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)
    for item in sorted(source_root.iterdir(), key=lambda entry: entry.name):
        if provenance is not None and item.name == SOURCE_PROVENANCE_FILE:
            continue
        _copy_included(source_root, item, destination_root / item.name)
    for alias, canonical in CANONICAL_PROJECTIONS.items():
        projection = destination_root / alias
        canonical_dir = destination_root / canonical
        if not projection.is_dir() and canonical_dir.is_dir():
            if projection.exists() or projection.is_symlink():
                _remove_path(projection)
            projection.symlink_to(canonical, target_is_directory=True)
    if provenance is not None:
        assert_source_payload_matches_provenance(
            source_root,
            owner_repo=provenance["owner_repo"],
            source_revision=provenance["source_revision"],
            payload_root=destination_root,
        )
        provenance_path = destination_root / SOURCE_PROVENANCE_FILE
        provenance_path.write_text(
            json.dumps(provenance, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        provenance_path.chmod(0o644)
    validate_payload(
        destination_root,
        require_source_provenance=require_source_provenance,
        expected_owner_repo=(
            provenance["owner_repo"] if provenance is not None else None
        ),
        expected_source_revision=(
            provenance["source_revision"] if provenance is not None else None
        ),
    )


def _normalized_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Zero out uid/gid/owner/mtime/pax-headers so archives build reproducibly."""
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    info.pax_headers = {}
    return info


def _git_blob_oid_from_stream(stream, size: int, algorithm: str) -> str:
    digest = _git_blob_hasher(algorithm, size)
    consumed = 0
    while consumed < size:
        chunk = stream.read(min(1024 * 1024, size - consumed))
        if not chunk:
            break
        consumed += len(chunk)
        digest.update(chunk)
    if consumed != size or stream.read(1):
        raise ManifestError("archive member size changed during verification")
    return digest.hexdigest()


def _assert_archive_matches_git_revision(
    git_root: Path,
    archive_path: Path,
    root_name: str,
    provenance: dict[str, str],
) -> None:
    """Verify the emitted tar, not merely its staging tree, against the claimed commit."""
    revision = provenance["source_revision"]
    entries, directories = _expected_git_payload(git_root, revision)
    expected_paths = set(entries) | directories
    members: dict[Path, tarfile.TarInfo] = {}
    carrier_member: tarfile.TarInfo | None = None
    errors: list[str] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.name == root_name:
                if not member.isdir():
                    errors.append("type:archive-root")
                continue
            prefix = f"{root_name}/"
            if not member.name.startswith(prefix):
                errors.append(f"outside-root:{member.name}")
                continue
            relative = Path(member.name.removeprefix(prefix))
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"unsafe:{relative.as_posix()}")
                continue
            if relative == Path(SOURCE_PROVENANCE_FILE):
                if carrier_member is not None:
                    errors.append(f"duplicate:{SOURCE_PROVENANCE_FILE}")
                carrier_member = member
                continue
            if relative in members:
                errors.append(f"duplicate:{relative.as_posix()}")
            members[relative] = member

        actual_paths = set(members)
        errors.extend(
            f"missing:{path.as_posix()}"
            for path in sorted(expected_paths - actual_paths)
        )
        errors.extend(
            f"extra:{path.as_posix()}" for path in sorted(actual_paths - expected_paths)
        )
        algorithm = _git_object_format(git_root)
        for relative in sorted(expected_paths & actual_paths):
            member = members[relative]
            if relative in directories:
                if not member.isdir():
                    errors.append(f"type:{relative.as_posix()}")
                continue
            mode, object_type, expected_oid = entries[relative]
            if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
                errors.append(
                    f"unsupported-git-entry:{relative.as_posix()}:{mode}:{object_type}"
                )
                continue
            if mode == "120000":
                if not member.issym():
                    errors.append(f"type:{relative.as_posix()}")
                    continue
                actual_oid = _git_blob_oid_from_bytes(
                    os.fsencode(member.linkname), algorithm
                )
            else:
                if not member.isreg():
                    errors.append(f"type:{relative.as_posix()}")
                    continue
                source = archive.extractfile(member)
                if source is None:
                    errors.append(f"unreadable:{relative.as_posix()}")
                    continue
                actual_oid = _git_blob_oid_from_stream(source, member.size, algorithm)
                if bool(member.mode & 0o111) != (mode == "100755"):
                    errors.append(f"mode:{relative.as_posix()}")
            if actual_oid != expected_oid:
                errors.append(f"bytes:{relative.as_posix()}")

        if carrier_member is None or not carrier_member.isreg():
            errors.append(f"missing-or-invalid:{SOURCE_PROVENANCE_FILE}")
        else:
            carrier_source = archive.extractfile(carrier_member)
            try:
                carrier = (
                    json.load(carrier_source) if carrier_source is not None else None
                )
            except (UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"invalid:{SOURCE_PROVENANCE_FILE}:{exc}")
            else:
                if carrier != provenance:
                    errors.append(f"mismatch:{SOURCE_PROVENANCE_FILE}")

    if errors:
        raise ManifestError(
            "archive differs from claimed Git revision "
            f"{revision}: " + ", ".join(sorted(set(errors)))
        )


def _write_archive(payload_root: Path, output: Path, root_name: str) -> None:
    """Write payload_root as a deterministic gzip+PAX tarball rooted at root_name."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        output.open("wb") as raw_output,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        root_info = tarfile.TarInfo(root_name)
        root_info.type = tarfile.DIRTYPE
        root_info.mode = 0o755
        tar.addfile(_normalized_tar_info(root_info))
        for path in _walk_entries(payload_root):
            relative = path.relative_to(payload_root)
            archive_name = f"{root_name}/{relative.as_posix()}"
            info = _normalized_tar_info(tar.gettarinfo(str(path), arcname=archive_name))
            if info.isreg():
                with path.open("rb") as source_file:
                    tar.addfile(info, source_file)
            else:
                tar.addfile(info)


def _assert_archive_matches_staged_payload(
    payload_root: Path,
    archive_path: Path,
    root_name: str,
) -> None:
    """Prove a candidate archive is a type/mode/byte-exact copy of its staging tree."""
    expected = {
        path.relative_to(payload_root): path for path in _walk_entries(payload_root)
    }
    actual: dict[Path, tarfile.TarInfo] = {}
    errors: list[str] = []
    root_count = 0
    prefix = f"{root_name}/"
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.name == root_name:
                    root_count += 1
                    if not member.isdir() or member.mode & 0o7777 != 0o755:
                        errors.append("invalid-root")
                    continue
                if not member.name.startswith(prefix):
                    errors.append(f"unexpected-root:{member.name}")
                    continue
                raw_relative = member.name.removeprefix(prefix)
                relative = Path(raw_relative)
                if (
                    not raw_relative
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or relative == Path(".")
                ):
                    errors.append(f"unsafe-path:{member.name}")
                    continue
                if relative in actual:
                    errors.append(f"duplicate:{relative.as_posix()}")
                    continue
                actual[relative] = member

            if root_count != 1:
                errors.append(f"root-count:{root_count}")
            errors.extend(
                f"missing:{path.as_posix()}"
                for path in sorted(set(expected) - set(actual))
            )
            errors.extend(
                f"extra:{path.as_posix()}"
                for path in sorted(set(actual) - set(expected))
            )
            for relative in sorted(set(expected) & set(actual)):
                path = expected[relative]
                member = actual[relative]
                metadata = path.lstat()
                if member.mode & 0o7777 != stat.S_IMODE(metadata.st_mode):
                    errors.append(f"mode:{relative.as_posix()}")
                if path.is_symlink():
                    if not member.issym() or member.linkname != os.readlink(path):
                        errors.append(f"symlink:{relative.as_posix()}")
                    continue
                if path.is_dir():
                    if not member.isdir():
                        errors.append(f"type:{relative.as_posix()}")
                    continue
                if not path.is_file() or not member.isreg():
                    errors.append(f"type:{relative.as_posix()}")
                    continue
                expected_oid, _ = _git_blob_oid_from_file(path, "sha256")
                source = archive.extractfile(member)
                if source is None:
                    errors.append(f"unreadable:{relative.as_posix()}")
                    continue
                actual_oid = _git_blob_oid_from_stream(source, member.size, "sha256")
                if actual_oid != expected_oid:
                    errors.append(f"bytes:{relative.as_posix()}")
    except (OSError, tarfile.TarError) as exc:
        raise ManifestError(f"cannot verify candidate archive: {exc}") from exc
    if errors:
        raise ManifestError(
            "candidate archive differs from staged payload: "
            + ", ".join(sorted(set(errors)))
        )


def create_archive(
    source: str | Path,
    output: str | Path,
    *,
    root_name: str,
    owner_repo: str | None = None,
    source_revision: str | None = None,
) -> Path:
    """Stage source into a temp dir under root_name and archive it to output.

    Returns the output path. Raises ManifestError if root_name is unsafe.
    """
    if not root_name or root_name in {".", ".."} or "/" in root_name:
        raise ManifestError(f"unsafe archive root name: {root_name!r}")
    output_path = Path(output)
    if output_path.is_symlink():
        raise ManifestError(f"archive output must not be a symlink: {output_path}")
    if output_path.exists() and output_path.is_dir():
        raise ManifestError(f"archive output must not be a directory: {output_path}")
    if output_path.exists() and not output_path.is_file():
        raise ManifestError(f"archive output must be a regular file: {output_path}")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ManifestError(
            f"cannot prepare archive output directory {output_path.parent}: {exc}"
        ) from exc
    source_root = Path(source).resolve()
    provenance = assert_source_payload_matches_provenance(
        source_root,
        owner_repo=owner_repo,
        source_revision=source_revision,
    )
    with tempfile.TemporaryDirectory(
        prefix=".vibecrafted-archive-",
        dir=output_path.parent,
    ) as temporary:
        temporary_root = Path(temporary)
        payload_root = temporary_root / root_name
        candidate_archive = temporary_root / "candidate.tar.gz"
        stage_payload(
            source_root,
            payload_root,
            mirror=True,
            owner_repo=provenance["owner_repo"],
            source_revision=provenance["source_revision"],
            require_source_provenance=True,
        )
        _write_archive(payload_root, candidate_archive, root_name)
        _assert_archive_matches_staged_payload(
            payload_root,
            candidate_archive,
            root_name,
        )
        if _is_exact_git_root(source_root):
            _assert_archive_matches_git_revision(
                source_root,
                candidate_archive,
                root_name,
                provenance,
            )
        os.replace(candidate_archive, output_path)
    return output_path


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser exposing the check/stage/archive subcommands."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Validate a staged payload")
    check.add_argument("--root", required=True, type=Path)
    check.add_argument("--require-source-provenance", action="store_true")
    check.add_argument("--expected-owner-repo")
    check.add_argument("--expected-source-revision")

    stage = subparsers.add_parser("stage", help="Create an allowlisted payload")
    stage.add_argument("--source", required=True, type=Path)
    stage.add_argument("--destination", required=True, type=Path)
    stage.add_argument("--mirror", action="store_true")
    stage.add_argument("--owner-repo")
    stage.add_argument("--source-revision")
    stage.add_argument("--require-source-provenance", action="store_true")

    archive = subparsers.add_parser("archive", help="Create a validated tarball")
    archive.add_argument("--source", required=True, type=Path)
    archive.add_argument("--output", required=True, type=Path)
    archive.add_argument("--root-name", required=True)
    archive.add_argument("--owner-repo")
    archive.add_argument("--source-revision")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: dispatch to check/stage/archive, printing errors to stderr."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "check":
            validate_payload(
                args.root,
                require_source_provenance=(
                    args.require_source_provenance
                    or args.expected_owner_repo is not None
                    or args.expected_source_revision is not None
                ),
                expected_owner_repo=args.expected_owner_repo,
                expected_source_revision=args.expected_source_revision,
            )
            print(f"Payload valid: {args.root}")
        elif args.command == "stage":
            stage_payload(
                args.source,
                args.destination,
                mirror=args.mirror,
                owner_repo=args.owner_repo,
                source_revision=args.source_revision,
                require_source_provenance=args.require_source_provenance,
            )
            print(f"Payload staged: {args.destination}")
        elif args.command == "archive":
            archive = create_archive(
                args.source,
                args.output,
                root_name=args.root_name,
                owner_repo=args.owner_repo,
                source_revision=args.source_revision,
            )
            print(f"Archive built: {archive}")
        else:  # pragma: no cover - argparse owns command validation.
            raise ManifestError(f"unknown command: {args.command}")
    except (ManifestError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
