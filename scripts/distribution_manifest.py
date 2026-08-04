#!/usr/bin/env python3
"""Build and verify the complete Vibecrafted runtime payload.

The repository is a development surface. A distribution is an allowlisted
projection of it: required runtime paths must exist, development artifacts are
never copied, and symlinks must stay inside the payload.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path

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
    "vibecrafted-core/pyproject.toml",
    "vibecrafted-core/vibecrafted_core/VERSION",
    "vibecrafted-core/vibecrafted_core/deck/vibecrafted",
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
        "pyproject.toml",
        "plugin.json",
        "vibecrafted-framework.plugin",
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


def _relative_path(value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManifestError(f"unsafe relative path: {value}")
    return relative


def _component_is_secret_env(name: str) -> bool:
    # `.env` and every `.env.*` variant carry live credentials; only the
    # committed `*.example` templates are distributable.
    if name == ".env":
        return True
    return name.startswith(".env.") and not name.endswith(".example")


def path_is_forbidden(relative: str | Path) -> bool:
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
    relative_path = _relative_path(relative)
    return bool(
        relative_path.parts
        and relative_path.parts[0] in ALLOWED_TOP_LEVEL
        and not path_is_forbidden(relative_path)
    )


def _symlink_error(root: Path, path: Path) -> str | None:
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


def validate_payload(root: str | Path) -> None:
    payload_root = Path(root)
    if not payload_root.is_dir():
        raise ManifestError(f"payload root is not a directory: {payload_root}")

    errors = _required_errors(payload_root)
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
    errors = _required_errors(root, allow_runtime_projection=True)
    for path in _walk_entries(root):
        relative = path.relative_to(root)
        if not path_is_included(relative):
            continue
        if error := _symlink_error(root, path):
            errors.append(error)
    if errors:
        raise ManifestError("\n".join(sorted(set(errors))))


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_included(source_root: Path, source: Path, destination: Path) -> None:
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
        return
    if source.is_file():
        if destination.exists() and destination.is_dir():
            _remove_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def stage_payload(
    source: str | Path, destination: str | Path, *, mirror: bool = False
) -> None:
    source_root = Path(source).resolve()
    destination_root = Path(destination)
    if not source_root.is_dir():
        raise ManifestError(f"source root is not a directory: {source_root}")
    _validate_source(source_root)

    if mirror and (destination_root.exists() or destination_root.is_symlink()):
        _remove_path(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)
    for item in sorted(source_root.iterdir(), key=lambda entry: entry.name):
        _copy_included(source_root, item, destination_root / item.name)
    for alias, canonical in CANONICAL_PROJECTIONS.items():
        projection = destination_root / alias
        canonical_dir = destination_root / canonical
        if not projection.is_dir() and canonical_dir.is_dir():
            if projection.exists() or projection.is_symlink():
                _remove_path(projection)
            projection.symlink_to(canonical, target_is_directory=True)
    validate_payload(destination_root)


def _normalized_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    info.pax_headers = {}
    return info


def _write_archive(payload_root: Path, output: Path, root_name: str) -> None:
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


def create_archive(source: str | Path, output: str | Path, *, root_name: str) -> Path:
    if not root_name or root_name in {".", ".."} or "/" in root_name:
        raise ManifestError(f"unsafe archive root name: {root_name!r}")
    output_path = Path(output)
    with tempfile.TemporaryDirectory(prefix="vibecrafted-payload-") as temporary:
        payload_root = Path(temporary) / root_name
        stage_payload(source, payload_root, mirror=True)
        _write_archive(payload_root, output_path, root_name)
    return output_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Validate a staged payload")
    check.add_argument("--root", required=True, type=Path)

    stage = subparsers.add_parser("stage", help="Create an allowlisted payload")
    stage.add_argument("--source", required=True, type=Path)
    stage.add_argument("--destination", required=True, type=Path)
    stage.add_argument("--mirror", action="store_true")

    archive = subparsers.add_parser("archive", help="Create a validated tarball")
    archive.add_argument("--source", required=True, type=Path)
    archive.add_argument("--output", required=True, type=Path)
    archive.add_argument("--root-name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "check":
            validate_payload(args.root)
            print(f"Payload valid: {args.root}")
        elif args.command == "stage":
            stage_payload(args.source, args.destination, mirror=args.mirror)
            print(f"Payload staged: {args.destination}")
        elif args.command == "archive":
            archive = create_archive(
                args.source,
                args.output,
                root_name=args.root_name,
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
