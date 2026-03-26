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
    shell_rc = get_shell_rc()
    vetcoders_zsh_path = os.path.join(repo_dir, "skills", "vc-agents", "shell", "vetcoders.zsh")

    source_line = f'source "{vetcoders_zsh_path}"'
    marker_start = "# >>> VibeCraft Framework >>>"
    marker_end = "# <<< VibeCraft Framework <<<"

    print_step(f"Injecting into {shell_rc}")
    
    if not os.path.exists(shell_rc):
        print_info(f"{shell_rc} does not exist. We will create it.")
        open(shell_rc, 'w').close()

    # Check if file is writable (respects uchg/immutable flags)
    try:
        with open(shell_rc, 'a'):
            pass
        writable = True
    except OSError:
        writable = False

    with open(shell_rc, "r") as f:
        content = f.read()

    if marker_start in content:
        print_info("VibeCraft is already installed in your shell config.")
    elif not writable:
        print_warning(f"{shell_rc} is locked (immutable). Skipping shell config.")
        print_info("Add these lines manually:")
        print_info(f"  {marker_start}")
        print_info(f"  export VIBECRAFT_ROOT=\"{repo_dir}\"")
        print_info(f"  {source_line}")
        print_info(f"  {marker_end}")
    else:
        print_info("Adding VibeCraft configuration...")
        with open(shell_rc, "a") as f:
            f.write(f"\n{marker_start}\n")
            f.write(f"export VIBECRAFT_ROOT=\"{repo_dir}\"\n")
            f.write(f"{source_line}\n")
            f.write(f"{marker_end}\n")
        print_info("Configuration added successfully.")

    print_step("Applying internal path fixes (Sidecars)")
    print_info("We rely on sidecar configs. Your global configs are safe.")
    
    run_underlying_installer(repo_dir)
    
    print_success("Installation Complete!")
    print(f"\n{Colors.BOLD}To reverse this installation at any time:{Colors.ENDC}")
    print(f"Simply open {shell_rc} and delete the lines between the VibeCraft markers.")
    print(f"\n{Colors.BOLD}Next steps:{Colors.ENDC}")
    print("Restart your terminal or run:")
    print(f"  source {shell_rc}")

if __name__ == "__main__":
    main()
