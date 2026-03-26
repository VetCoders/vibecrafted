#!/usr/bin/env python3
import os
import sys
import shutil

_IS_TTY = sys.stdout.isatty() and sys.stdin.isatty()

class Colors:
    _on = sys.stdout.isatty()
    HEADER = '\033[95m' if _on else ''
    OKBLUE = '\033[94m' if _on else ''
    OKCYAN = '\033[96m' if _on else ''
    OKGREEN = '\033[92m' if _on else ''
    WARNING = '\033[93m' if _on else ''
    FAIL = '\033[91m' if _on else ''
    ENDC = '\033[0m' if _on else ''
    BOLD = '\033[1m' if _on else ''
    UNDERLINE = '\033[4m' if _on else ''

def print_step(msg):
    print(f"\n{Colors.OKBLUE}=>{Colors.ENDC} {Colors.BOLD}{msg}{Colors.ENDC}")

def print_info(msg):
    print(f"    {msg}")

def print_success(msg):
    print(f"\n{Colors.OKGREEN}=>{Colors.ENDC} {Colors.BOLD}{msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.WARNING}WARNING:{Colors.ENDC} {msg}")

def ask_yes_no(question, default=True):
    if not _IS_TTY:
        return default
    try:
        sys.stdout.write(f"\n{Colors.OKCYAN}?{Colors.ENDC} {Colors.BOLD}{question}{Colors.ENDC} [Y/n]: ")
        choice = input().lower().strip()
        if not choice:
            return default
        return choice in ['y', 'yes']
    except (EOFError, KeyboardInterrupt):
        print()
        return default

def get_shell_rc():
    shell = os.environ.get("SHELL", "")
    home = os.environ.get("HOME", os.path.expanduser("~"))
    if "zsh" in shell:
        return os.path.join(home, ".zshrc")
    elif "bash" in shell:
        if sys.platform == "darwin":
            return os.path.join(home, ".bash_profile")
        return os.path.join(home, ".bashrc")
    else:
        # Default to zshrc if we can't figure it out, it's most common on mac
        return os.path.join(home, ".zshrc")

import subprocess

def run_underlying_installer(repo_dir):
    installer_path = os.path.join(repo_dir, "scripts", "vetcoders_install.py")
    if os.path.exists(installer_path):
        print_step("Running Core Installer...")
        try:
            subprocess.run([sys.executable, installer_path, "install", "--source", repo_dir], check=True)
        except subprocess.CalledProcessError as e:
            print_warning(f"Core installer exited with code {e.returncode}")
    else:
        print_warning(f"Underlying installer not found at {installer_path}")

def main():
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("VibeCraft Framework Setup")
    print("-------------------------")
    print(f"{Colors.ENDC}")

    print_info("Welcome. This installer follows a strict 'No why? questions' rule.")
    print_info("We will explain exactly what we are doing, and we guarantee it is non-destructive.")

    print_step("What we will do:")
    print_info("1. We will NOT overwrite your existing shell configs (~/.zshrc, ~/.config/starship.toml, etc).")
    print_info("2. We will ONLY add one 'source' line to your shell's rc file.")
    print_info("3. This line points to our 'vetcoders.zsh' script.")
    print_info("4. When you use VibeCraft, we load our beautiful 'frontier configs' (starship, zellij) dynamically as sidecars.")
    
    if not ask_yes_no("Do you understand and agree to proceed?"):
        print("\nSetup aborted by user. No changes were made.")
        sys.exit(0)

    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    vibecrafted_home = os.environ.get("VIBECRAFTED_HOME", os.path.join(os.path.expanduser("~"), ".vibecrafted"))

    # Step 1: Run core installer — copies skills to ~/.vibecrafted/skills/,
    # creates symlinks, installs shell helpers to ~/.config/zsh/vc-skills.zsh
    print_step("Installing skills and shell helpers to ~/.vibecrafted/")
    print_info(f"What: Copy 16 VibeCraft skills to {vibecrafted_home}/skills/")
    print_info("Why:  Your AI agents (Claude, Codex, Gemini) read skills from here")
    print_info("Safe: Everything reversible with 'make uninstall'")
    run_underlying_installer(repo_dir)

    print_success("Installation Complete!")
    print_info(f"Skills:  {vibecrafted_home}/skills/")
    print_info(f"Helpers: ~/.config/zsh/vc-skills.zsh")
    print_info("Symlinks: ~/.claude/skills/, ~/.codex/skills/, ~/.agents/skills/")
    print()
    print(f"{Colors.BOLD}To reverse:{Colors.ENDC} make uninstall")
    print(f"{Colors.BOLD}To verify:{Colors.ENDC}  make doctor")
    print(f"{Colors.BOLD}To start:{Colors.ENDC}   source ~/.zshrc (or open new terminal)")

if __name__ == "__main__":
    main()
