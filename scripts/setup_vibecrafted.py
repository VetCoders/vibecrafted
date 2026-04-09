#!/usr/bin/env python3
import os
import subprocess
import sys

try:
    from runtime_paths import read_version_file
except (
    ModuleNotFoundError
):  # pragma: no cover - module import path depends on entrypoint
    from scripts.runtime_paths import read_version_file

_IS_TTY = sys.stdout.isatty() and sys.stdin.isatty()


class Colors:
    _on = sys.stdout.isatty()
    HEADER = "\033[95m" if _on else ""
    OKBLUE = "\033[94m" if _on else ""
    OKCYAN = "\033[96m" if _on else ""
    OKGREEN = "\033[92m" if _on else ""
    WARNING = "\033[93m" if _on else ""
    FAIL = "\033[91m" if _on else ""
    ENDC = "\033[0m" if _on else ""
    BOLD = "\033[1m" if _on else ""


def print_warning(msg):
    print(f"{Colors.WARNING}WARNING:{Colors.ENDC} {msg}")


def ask_yes_no(question, default=True):
    if not _IS_TTY:
        return default
    try:
        sys.stdout.write(
            f"\n  {Colors.OKCYAN}?{Colors.ENDC} {Colors.BOLD}{question}{Colors.ENDC} [Y/n]: "
        )
        choice = input().lower().strip()
        if not choice:
            return default
        return choice in ["y", "yes"]
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def run_underlying_installer(repo_dir):
    installer_path = os.path.join(repo_dir, "scripts", "vetcoders_install.py")
    if os.path.exists(installer_path):
        try:
            subprocess.run(
                [
                    sys.executable,
                    installer_path,
                    "install",
                    "--source",
                    repo_dir,
                    "--with-shell",
                    "--compact",
                    "--non-interactive",
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print_warning(f"Core installer exited with code {e.returncode}")
    else:
        print_warning(f"Underlying installer not found at {installer_path}")


def main():
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    fw_ver = read_version_file(repo_dir)

    # --- Compact header ---
    sep = "\u2500" * 37
    print()
    print(f"  {Colors.BOLD}\u2692  𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Installer v{fw_ver}{Colors.ENDC}")
    print(f"  {sep}")
    print()

    # --- Single Y/n prompt ---
    if not ask_yes_no("Start setup?"):
        print("\n  Setup cancelled. No changes were made.")
        sys.exit(0)

    print()

    # --- Run compact installer ---
    run_underlying_installer(repo_dir)


if __name__ == "__main__":
    main()
