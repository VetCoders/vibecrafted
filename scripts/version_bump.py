#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bump the root VERSION file.",
    )
    parser.add_argument("version", help="{patch|minor|major|x.y.z}")
    parser.add_argument("--file", default="VERSION", help="VERSION file path")
    args = parser.parse_args()

    version_file = Path(args.file)
    current = version_file.read_text(encoding="utf-8").strip()
    try:
        next_version = resolve_next_version(current, args.version)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    version_file.write_text(next_version + "\n", encoding="utf-8")
    print(f"Bumped: v{current} -> v{next_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
