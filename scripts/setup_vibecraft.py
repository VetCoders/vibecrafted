#!/usr/bin/env python3
import os
import shlex
import shutil
import subprocess
import sys

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

def run_underlying_installer(repo_dir):
    installer_path = os.path.join(repo_dir, "scripts", "vetcoders_install.py")
    if os.path.exists(installer_path):
        print_step("Running Core Installer...")
        try:
            subprocess.run(
                [sys.executable, installer_path, "install", "--source", repo_dir, "--with-shell"],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print_warning(f"Core installer exited with code {e.returncode}")
    else:
        print_warning(f"Underlying installer not found at {installer_path}")

def main():
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("VibeCraft Framework Setup")
    print("-------------------------")
    print(f"{Colors.ENDC}")

    print_info("This setup stays inside ~/.vibecrafted until you ask us to touch your shell.")
    print_info("Each step says what changes, why it matters, and how to undo it.")

    print_step("Plan")
    print_info("1. Keep the control plane in ~/.vibecrafted/tools.")
    print_info("2. Install the shared skill store in ~/.vibecrafted/skills.")
    print_info("3. Add one source line to your shell rc file.")
    print_info("4. Load frontier configs as sidecars only when VibeCraft runs.")
    
    if not ask_yes_no("Start setup?"):
        print("\nSetup cancelled. No changes were made.")
        sys.exit(0)

    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    vibecrafted_home = os.environ.get("VIBECRAFTED_HOME", os.path.join(os.path.expanduser("~"), ".vibecrafted"))
    control_plane = os.path.realpath(repo_dir)

    # Step 1: Run core installer — copies skills to ~/.vibecrafted/skills/,
    # creates symlinks, installs shell helpers to ~/.config/zsh/vc-skills.zsh
    skills_dir = os.path.join(repo_dir, "skills")
    skill_count = len([d for d in os.listdir(skills_dir)
                       if os.path.isdir(os.path.join(skills_dir, d))
                       and d.startswith("vc-")
                       and os.path.isfile(os.path.join(skills_dir, d, "SKILL.md"))
                       ]) if os.path.isdir(skills_dir) else 0
    print_step("Installing the shared skill store")
    print_info(f"What:   Copy {skill_count} VibeCraft skills to {vibecrafted_home}/skills/")
    print_info("Reason: Keep one canonical skill store for Claude, Codex, and Gemini")
    print_info(f"Safe: Everything reversible with 'make -C {shlex.quote(control_plane)} uninstall'")
    run_underlying_installer(repo_dir)

    print_success("VibeCraft is ready.")
    print_info(f"Control plane: {control_plane}")
    print_info(f"Shared skills: {vibecrafted_home}/skills/")
    print_info("Shell helper: ~/.config/vetcoders/vc-skills.sh")
    print_info("Agent views: ~/.claude/skills/, ~/.codex/skills/, ~/.agents/skills/")
    print()
    print(f"{Colors.BOLD}Reverse:{Colors.ENDC} make -C {control_plane} uninstall")
    print(f"{Colors.BOLD}Verify:{Colors.ENDC}  make -C {control_plane} doctor")
    print(f"{Colors.BOLD}Start:{Colors.ENDC}   source ~/.bashrc  (or source ~/.zshrc, or open a new terminal)")

if __name__ == "__main__":
    main()
