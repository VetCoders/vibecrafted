#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHELLCHECK_EXCLUDES = ("SC1090", "SC1091", "SC2155", "SC2034", "SC2154", "SC2015")
SHELL_SUFFIXES = {".sh", ".bash", ".zsh"}
SHELL_NAMES = ("zsh", "bash", "sh")


def read_shebang(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            first_line = handle.readline().decode("utf-8", errors="ignore").strip()
    except OSError:
        return ""
    return first_line if first_line.startswith("#!") else ""


def shell_for_path(path: Path) -> str | None:
    shebang = read_shebang(path)
    if shebang:
        shebang_parts = shebang[2:].strip().split()
        if shebang_parts:
            interpreter = Path(shebang_parts[0]).name
            if interpreter == "env" and len(shebang_parts) > 1:
                interpreter = Path(shebang_parts[1]).name
            for shell_name in SHELL_NAMES:
                if interpreter == shell_name:
                    return shell_name

    suffix = path.suffix.lower()
    if suffix == ".zsh":
        return "zsh"
    if suffix in {".sh", ".bash"}:
        return "bash"
    return None


def is_shell_path(path: Path) -> bool:
    return path.suffix.lower() in SHELL_SUFFIXES or shell_for_path(path) is not None


def tracked_shell_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[Path] = []
    for raw_path in result.stdout.splitlines():
        if not raw_path:
            continue
        candidate = repo_root / raw_path
        if candidate.is_file() and is_shell_path(candidate):
            files.append(candidate.resolve())
    return sorted(files)


def resolve_shell_files(
    raw_paths: list[str], repo_root: Path = REPO_ROOT
) -> list[Path]:
    if not raw_paths:
        return tracked_shell_files(repo_root)

    files: list[Path] = []
    seen: set[Path] = set()
    for raw_path in raw_paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if not candidate.is_file() or not is_shell_path(candidate) or candidate in seen:
            continue

        files.append(candidate)
        seen.add(candidate)
    return files


def build_shellcheck_command(files: list[Path]) -> list[str]:
    return [
        "shellcheck",
        "-e",
        ",".join(SHELLCHECK_EXCLUDES),
        *(str(path) for path in files),
    ]


def syntax_check_command(path: Path) -> list[str]:
    shell_name = shell_for_path(path)
    if shell_name == "zsh":
        shell_binary = shutil.which("zsh") or "zsh"
    elif shell_name == "sh":
        shell_binary = shutil.which("sh") or "sh"
    else:
        shell_binary = shutil.which("bash") or "bash"
    return [shell_binary, "-n", str(path)]


def run_shellcheck(files: list[Path]) -> int:
    print(f"Running shellcheck on {len(files)} shell files...")
    return subprocess.run(build_shellcheck_command(files), check=False).returncode


def run_syntax_fallback(files: list[Path]) -> int:
    print("shellcheck not found; running syntax-only shell checks with local shells.")
    failed = False

    for path in files:
        command = syntax_check_command(path)
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            continue
        failed = True
        print(f"[fail] {path.relative_to(REPO_ROOT)}")
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)

    if failed:
        return 1

    print(f"Syntax-only shell checks passed for {len(files)} shell files.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell quality gate across tracked files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional shell files to lint. Defaults to tracked repo shell files.",
    )
    parser.add_argument(
        "--require-shellcheck",
        action="store_true",
        help="Fail instead of falling back when shellcheck is unavailable.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    files = resolve_shell_files(args.paths)
    if not files:
        print("No shell files to check.")
        return 0

    if shutil.which("shellcheck"):
        return run_shellcheck(files)

    if args.require_shellcheck or os.environ.get("CI"):
        print(
            "shellcheck is required for this quality gate but is not installed.",
            file=sys.stderr,
        )
        return 127

    return run_syntax_fallback(files)


if __name__ == "__main__":
    raise SystemExit(main())
