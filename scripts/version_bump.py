#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)
PROJECT_VERSION_RE = re.compile(
    r'^(?P<prefix>\s*version\s*=\s*")(?P<version>[^"]+)(?P<suffix>".*)$'
)
PYPROJECT_RELATIVE = Path("vibecrafted-core/pyproject.toml")
PACKAGED_VERSION_RELATIVE = Path("vibecrafted-core/vibecrafted_core/VERSION")


def _parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"VERSION must be plain semver X.Y.Z, got {value!r}")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def resolve_next_version(current: str, requested: str) -> str:
    major, minor, patch = _parse_version(current)
    if requested == "patch":
        patch += 1
    elif requested == "minor":
        minor += 1
        patch = 0
    elif requested == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        _parse_version(requested)
        return requested
    return f"{major}.{minor}.{patch}"


def _project_version(text: str) -> str:
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project and (match := PROJECT_VERSION_RE.match(line)):
            return match.group("version")
    raise ValueError("pyproject.toml has no [project] version declaration")


def _replace_project_version(text: str, version: str) -> str:
    in_project = False
    output: list[str] = []
    replaced = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
        if in_project and not replaced:
            body = line.rstrip("\r\n")
            newline = line[len(body) :]
            if match := PROJECT_VERSION_RE.match(body):
                line = (
                    f"{match.group('prefix')}{version}{match.group('suffix')}{newline}"
                )
                replaced = True
        output.append(line)
    if not replaced:
        raise ValueError("pyproject.toml has no [project] version declaration")
    return "".join(output)


def _version_projections(version_file: Path) -> tuple[Path, Path] | None:
    project_root = version_file.parent
    pyproject = project_root / PYPROJECT_RELATIVE
    packaged = project_root / PACKAGED_VERSION_RELATIVE
    existing = (pyproject.exists(), packaged.exists())
    if not any(existing):
        return None
    if not all(existing):
        missing = pyproject if not existing[0] else packaged
        raise ValueError(f"version declaration missing: {missing}")
    return pyproject, packaged


def update_version_declarations(version_file: Path, requested: str) -> tuple[str, str]:
    current = version_file.read_text(encoding="utf-8").strip()
    next_version = resolve_next_version(current, requested)
    projections = _version_projections(version_file)

    updates = {version_file: next_version + "\n"}
    if projections is not None:
        pyproject, packaged = projections
        pyproject_text = pyproject.read_text(encoding="utf-8")
        declared = {
            version_file: current,
            pyproject: _project_version(pyproject_text),
            packaged: packaged.read_text(encoding="utf-8").strip(),
        }
        drift = {path: value for path, value in declared.items() if value != current}
        if drift:
            details = ", ".join(f"{path}={value}" for path, value in drift.items())
            raise ValueError(
                f"Version drift detected; expected {current} in every declaration: {details}"
            )
        updates[pyproject] = _replace_project_version(pyproject_text, next_version)
        updates[packaged] = next_version + "\n"

    for path, content in updates.items():
        path.write_text(content, encoding="utf-8")
    return current, next_version


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bump VERSION and every packaged version declaration.",
    )
    parser.add_argument("version", help="{patch|minor|major|x.y.z}")
    parser.add_argument("--file", default="VERSION", help="VERSION file path")
    args = parser.parse_args()

    version_file = Path(args.file)
    try:
        current, next_version = update_version_declarations(version_file, args.version)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Bumped: v{current} -> v{next_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
