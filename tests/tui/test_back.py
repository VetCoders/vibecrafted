#!/usr/bin/env python3
"""VetCoders Smart Installer v2 — manifest-driven, multi-channel, interactive.

Subcommands:
    install         Install the VetCoders skill bundle
    doctor          Verify installation health
    list            Show available VetCoders skills and the runtime substrate beneath them
    uninstall       Remove VetCoders skills, symlinks, and helpers
    restore         Restore pre-install state from backup

Usage:
    python3 scripts/vetcoders_install.py install [--non-interactive] [--dry-run] [--advanced]
    python3 scripts/vetcoders_install.py doctor
    python3 scripts/vetcoders_install.py list
    python3 scripts/vetcoders_install.py uninstall [--dry-run]
    python3 scripts/vetcoders_install.py restore [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _IS_TTY else text


def bold(t: str) -> str:
    return _c("1", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def dim(t: str) -> str:
    return _c("2", t)


def cyan(t: str) -> str:
    return _c("36", t)


OK = green("[ok]")
MISS = red("[missing]")
WARN = yellow("[warn]")
OPT = dim("[optional]")
SKIP = dim("[skip]")

# ---------------------------------------------------------------------------
# Component manifest
# ---------------------------------------------------------------------------

SKILL_CATEGORIES = {
    "pipeline": {
        "label": "VetCoders Pipeline",
        "description": "Core workflow skills: init, workflow, followup, marbles, dou, hydrate, ship",
        "prefix": "vc-",
    },
    "foundations": {
        "label": "Runtime Foundations",
        "description": "Shared runtime substrate: memory, structure, and review artifacts",
        "names": [],
    },
    "specialist": {
        "label": "Specialist / Optional",
        "description": "Skills for specific workflows: decorate, screenscribe, prview, prune",
        "names": [],  # auto-detected: anything not in pipeline or foundations
    },
}


@dataclass
class Foundation:
    """A binary tool that skills depend on."""

    name: str
    description: str
    channels: List[str]
    packages: Dict[str, str]
    verify_cmd: str
    required: bool = True  # False = optional

    def is_installed(self) -> Optional[str]:
        """Return path if installed, None otherwise."""
        return shutil.which(self.name)

    def install_hint(self) -> str:
        hints = []
        for ch in self.channels:
            pkg = self.packages.get(ch, self.name)
            if ch == "crates":
                hints.append(f"cargo install {pkg}")
            elif ch == "npm":
                hints.append(f"npm i -g {pkg}")
            elif ch == "github":
                hints.append(f"Download from {pkg}")
        return " | ".join(hints)


FOUNDATIONS: List[Foundation] = [
    Foundation(
        name="aicx-mcp",
        description="AICX MCP server for session history and memory recovery",
        channels=["github", "crates"],
        packages={
            "crates": "ai-contexters",
            "github": "https://github.com/VetCoders/ai-contexters/releases",
        },
        verify_cmd="aicx-mcp --version",
    ),
    Foundation(
        name="loctree-mcp",
        description="Structural code mapping MCP server",
        channels=["github", "crates"],
        packages={
            "crates": "loctree-mcp",
            "github": "https://github.com/Loctree/loctree-mcp/releases",
        },
        verify_cmd="loctree-mcp --version",
    ),
    Foundation(
        name="prview",
        description="PR review artifact generator",
        channels=["github", "crates"],
        packages={
            "crates": "prview",
            "github": "https://github.com/VetCoders/prview-rs/releases",
        },
        verify_cmd="prview --version",
        required=False,
    ),
]

RUNTIME_DEPS = ["zsh", "python3", "git", "rsync"]

AGENT_RUNTIMES = ["codex", "claude", "gemini"]

# ---------------------------------------------------------------------------
# Install state
# ---------------------------------------------------------------------------

STATE_FILE = ".vc-install.json"


@dataclass
class GoBack(Exception):
    pass

@dataclass
class InstallState:
    """Persisted installation state."""

    version: str = "2.0"
    installed_at: str = ""
    updated_at: str = ""
    repo_commit: str = ""
    repo_url: str = ""
    skills: List[str] = field(default_factory=list)
    runtimes: List[str] = field(default_factory=list)
    foundations: Dict[str, Dict] = field(default_factory=dict)
    shell_helpers: bool = False
    install_path: str = ""

    @classmethod
    def load(cls, store_path: Path) -> InstallState:
        state_file = store_path / STATE_FILE
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                s = cls()
                for k, v in data.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
                return s
            except (json.JSONDecodeError, KeyError):
                pass
        return cls()

    def save(self, store_path: Path) -> None:
        state_file = store_path / STATE_FILE
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(asdict(self), indent=2) + "\n")


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def detect_system_deps() -> Dict[str, Optional[str]]:
    """Check which system dependencies are available."""
    result = {}
    for cmd in RUNTIME_DEPS:
        result[cmd] = shutil.which(cmd)
    return result


def detect_agent_runtimes() -> Dict[str, Optional[str]]:
    """Check which agent CLIs are available."""
    result = {}
    for rt in AGENT_RUNTIMES:
        result[rt] = shutil.which(rt)
    return result


def detect_osascript() -> Optional[str]:
    return shutil.which("osascript")


def detect_cargo() -> Optional[str]:
    return shutil.which("cargo")


def get_repo_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def get_repo_url(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------


def discover_skills(repo_root: Path) -> List[Path]:
    """Find all canonical VetCoders skill directories."""
    skills = []
    for entry in sorted(repo_root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name in ("docs", "scripts", "tests", ".github"):
            continue
        if not entry.name.startswith("vc-"):
            continue
        if (entry / "SKILL.md").exists():
            skills.append(entry)
    return skills


def categorize_skill(name: str) -> str:
    """Return category key for a skill name."""
    if name.startswith("vc-"):
        return "pipeline"
    return "specialist"


def categorize_all(skills: List[Path]) -> Dict[str, List[str]]:
    cats: Dict[str, List[str]] = {"pipeline": [], "foundations": [], "specialist": []}
    for s in skills:
        cat = categorize_skill(s.name)
        cats[cat].append(s.name)
    return cats


# ---------------------------------------------------------------------------
# Interactive UI
# ---------------------------------------------------------------------------


def ask_yn(prompt: str, default: bool = True) -> bool:
    """Ask yes/no question. Returns default in non-interactive mode."""
    if not _IS_TTY:
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(bold(prompt) + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer.startswith("y")


def _read_key() -> str:
    """Reads a single keypress or escape sequence from stdin."""
    import select
    char = sys.stdin.read(1)
    if char == '\x1b':
        r, _, _ = select.select([sys.stdin], [], [], 0.05)
        if r:
            char += sys.stdin.read(2)
    return char


def ask_choice(prompt: str, options: List[str], default: int = 0) -> int:
    """Ask user to pick from a list interactively."""
    if not _IS_TTY:
        return default

    try:
        import termios
        import tty
    except ImportError:
        print(bold(prompt))
        for i, opt in enumerate(options):
            marker = cyan(">") if i == default else " "
            print(f"  {marker} {i + 1}. {opt}")
        try:
            answer = input(dim(f"  Choice [1-{len(options)}, default {default + 1}]: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if not answer:
            return default
        try:
            idx = int(answer) - 1
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        return default

    # Interactive mode
    import termios
    import tty
    
    current_idx = default
    print(bold(prompt))
    print(dim("  (Use UP/DOWN to navigate, ENTER to confirm, or type number)"))
    
    for _ in options:
        print()
        
    def render():
        sys.stdout.write(f"\033[{len(options)}A")
        for i, opt in enumerate(options):
            marker = cyan(">") if i == current_idx else " "
            sys.stdout.write(f"\033[2K\r  {marker} {i + 1}. {opt}\n")
        sys.stdout.flush()
        
    render()
    
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            char = _read_key()
            if char in ('\n', '\r'):
                break
            elif char in '123456789':
                idx = int(char) - 1
                if 0 <= idx < len(options):
                    current_idx = idx
                    break
            elif char == '\x1b[A': # Up
                current_idx = max(0, current_idx - 1)
                render()
            elif char == '\x1b[B': # Down
                current_idx = min(len(options) - 1, current_idx + 1)
                render()
            elif char == '\x03': # Ctrl+C
                raise KeyboardInterrupt
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return default
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
    return current_idx


def ask_multi(prompt: str, options: List[str], defaults: List[bool]) -> List[bool]:
    """Ask user to toggle or select multiple options interactively."""
    if not _IS_TTY:
        return defaults

    try:
        import termios
        import tty
    except ImportError:
        print(bold(prompt))
        selected = list(defaults)
        for i, opt in enumerate(options):
            marker = green("[x]") if selected[i] else dim("[ ]")
            print(f"  {marker} {i + 1}. {opt}")
        try:
            print(dim("  (Type numbers space-separated. E.g. '1 2' to select exactly those, or '+3' / '-1' to toggle)"))
            answer = input(dim("  Selection: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return defaults

        if answer:
            tokens = answer.split()
            if all(tok.isdigit() for tok in tokens):
                selected = [False] * len(options)
                for tok in tokens:
                    idx = int(tok) - 1
                    if 0 <= idx < len(options):
                        selected[idx] = True
            else:
                for tok in tokens:
                    is_add = tok.startswith('+')
                    is_sub = tok.startswith('-')
                    clean_tok = tok.lstrip('+-')
                    try:
                        idx = int(clean_tok) - 1
                        if 0 <= idx < len(options):
                            if is_add:
                                selected[idx] = True
                            elif is_sub:
                                selected[idx] = False
                            else:
                                selected[idx] = not selected[idx]
                    except ValueError:
                        pass
        return selected

    # Interactive mode
    import termios
    import tty
    
    selected = list(defaults)
    current_idx = 0
    
    print(bold(prompt))
    print(dim("  (Use UP/DOWN to navigate, SPACE or number to toggle, ENTER to confirm)"))
    
    for _ in options:
        print()
        
    def render():
        sys.stdout.write(f"\033[{len(options)}A")
        for i, opt in enumerate(options):
            marker = green("[x]") if selected[i] else dim("[ ]")
            cursor = cyan(">") if i == current_idx else " "
            sys.stdout.write(f"\033[2K\r  {cursor} {marker} {i + 1}. {opt}\n")
        sys.stdout.flush()
        
    render()
    
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            char = _read_key()
            if char in ('\n', '\r'):
                break
            elif char == ' ':
                selected[current_idx] = not selected[current_idx]
                render()
            elif char in '123456789':
                idx = int(char) - 1
                if 0 <= idx < len(options):
                    selected[idx] = not selected[idx]
                    current_idx = idx
                    render()
            elif char == '\x1b[A': # Up
                current_idx = max(0, current_idx - 1)
                render()
            elif char == '\x1b[B': # Down
                current_idx = min(len(options) - 1, current_idx + 1)
                render()
            elif char == '\x03': # Ctrl+C
                raise KeyboardInterrupt
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return defaults
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
    return selected


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

BACKUP_DIR = ".backup"


def _backup_root(store_path: Path) -> Path:
    return store_path / BACKUP_DIR


def create_backup(store_path: Path, runtimes: List[str], bundle_names: List[str],
                  dry_run: bool = False) -> Optional[str]:
    """Snapshot existing state before install. Returns backup timestamp or None."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = _backup_root(store_path) / ts
    anything_backed = False

    # Back up skills in shared store (if they are copies, not fresh)
    for name in bundle_names:
        src = store_path / name
        if src.is_dir() and not src.is_symlink():
            dst = backup_dir / "store" / name
            if dry_run:
                print(f"  {dim('backup')} {src} -> {dst}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst, symlinks=True)
            anything_backed = True

    # Back up per-runtime entries that are copies (not symlinks)
    for rt in runtimes:
        rt_skills = Path.home() / f".{rt}" / "skills"
        if not rt_skills.exists():
            continue
        for name in bundle_names:
            entry = rt_skills / name
            if entry.exists() and not entry.is_symlink():
                dst = backup_dir / "runtimes" / rt / name
                if dry_run:
                    print(f"  {dim('backup')} {entry} -> {dst}")
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(entry, dst, symlinks=True)
                anything_backed = True

    # Back up helper file
    helper_file = _helper_target_path()
    if helper_file.exists():
        dst = backup_dir / "helpers" / helper_file.name
        if dry_run:
            print(f"  {dim('backup')} {helper_file} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(helper_file, dst)
        anything_backed = True

    # Back up .zshrc
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        dst = backup_dir / "helpers" / ".zshrc"
        if dry_run:
            print(f"  {dim('backup')} {zshrc} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(zshrc, dst)
        anything_backed = True

    if anything_backed and not dry_run:
        # Write a "latest" pointer
        latest = _backup_root(store_path) / "latest"
        latest.write_text(ts + "\n")
        return ts
    elif anything_backed:
        return ts
    return None


def _helper_target_path() -> Path:
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zsh"
    return config_dir / "vc-skills.zsh"


def _zshrc_source_line() -> str:
    return '[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh"'


# ---------------------------------------------------------------------------
# Helper conflict detection
# ---------------------------------------------------------------------------

KNOWN_HELPER_FUNCTIONS = [
    "codex-implement", "codex-plan", "codex-review", "codex-research",
    "codex-prompt", "codex-observe",
    "claude-implement", "claude-plan", "claude-review", "claude-research",
    "claude-prompt", "claude-observe",
    "gemini-implement", "gemini-plan", "gemini-review", "gemini-research",
    "gemini-prompt", "gemini-observe",
    "skills-sync",
    "gemini-keychain-set", "gemini-keychain-get", "gemini-keychain-clear",
]


@dataclass
class HelperConflict:
    file: Path
    function: str
    line_num: int


def scan_helper_conflicts() -> Dict[Path, List[HelperConflict]]:
    """Scan shell config files for existing helper function definitions."""
    canonical = _helper_target_path()
    conflicts: Dict[Path, List[HelperConflict]] = {}

    search_dirs = []
    config_zsh = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zsh"
    if config_zsh.is_dir():
        search_dirs.append(config_zsh)

    files_to_scan: List[Path] = []
    for d in search_dirs:
        files_to_scan.extend(d.glob("*.zsh"))
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        files_to_scan.append(zshrc)

    for fpath in files_to_scan:
        if fpath.resolve() == canonical.resolve():
            continue  # Skip our own file
        try:
            lines = fpath.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for fn in KNOWN_HELPER_FUNCTIONS:
                # Match function definitions: "func_name()" or "func_name ()"
                if stripped.startswith(f"{fn}()") or stripped.startswith(f"{fn} ()"):
                    if fpath not in conflicts:
                        conflicts[fpath] = []
                    conflicts[fpath].append(HelperConflict(file=fpath, function=fn, line_num=i))

    return conflicts


def report_helper_conflicts(conflicts: Dict[Path, List[HelperConflict]], interactive: bool) -> bool:
    """Report conflicts and ask user what to do. Returns True if should proceed with install."""
    if not conflicts:
        return True

    print(yellow(bold("\n  Helper conflicts detected:")))
    for fpath, items in conflicts.items():
        total_lines = 0
        try:
            total_lines = len(fpath.read_text().splitlines())
        except OSError:
            pass
        our_count = len(items)
        print(f"    {fpath} ({total_lines} lines, {our_count} ours)")
        for c in items:
            print(f"      {dim(f'line {c.line_num}:')} {c.function}()")

    print()
    print(yellow("  These files contain non-VetCoders content — installer will NOT edit them."))

    if not interactive:
        print(yellow("  Non-interactive mode: installing canonical helpers alongside."))
        print(yellow("  Remove duplicates from the files above manually."))
        return True

    choice = ask_choice(
        "  How to proceed?",
        [
            "Skip helper install (keep your current setup)",
            "Install canonical helpers alongside (you clean up duplicates later)",
        ],
        default=1,
    )

    if choice == 0:
        print(dim("  Skipping helper install."))
        return False

    print()
    print(yellow("  To clean up later, remove these functions from your files:"))
    for fpath, items in conflicts.items():
        for c in items:
            print(f"    {c.function} @ {fpath}:{c.line_num}")
    print()
    return True


# ---------------------------------------------------------------------------
# Install logic
# ---------------------------------------------------------------------------


def rsync_skill(src: Path, dst: Path, dry_run: bool = False, mirror: bool = False) -> None:
    """Rsync a single skill directory."""
    if not dry_run:
        dst.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-az", "--exclude", ".DS_Store", "--exclude", ".loctree"]
    if mirror:
        cmd.append("--delete")
    if dry_run:
        cmd += ["--dry-run"]
    cmd += [str(src) + "/", str(dst) + "/"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_symlink(target: Path, link: Path, dry_run: bool = False) -> None:
    """Create a symlink, removing any existing entry."""
    if dry_run:
        print(f"  {dim('ln -s')} {target} -> {link}")
        return
    if link.exists() or link.is_symlink():
        if link.is_symlink():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        else:
            link.unlink()
    link.symlink_to(target)


def install_foundation_cargo(foundation: Foundation, dry_run: bool = False) -> bool:
    """Install a foundation via cargo install. Returns True on success."""
    pkg = foundation.packages.get("crates", foundation.name)
    if dry_run:
        print(f"  {dim('cargo install')} {pkg}")
        return True
    print(f"  Installing {bold(pkg)} via cargo...")
    result = subprocess.run(
        ["cargo", "install", pkg],
        capture_output=False,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


@dataclass
class DoctorFinding:
    level: str  # ok, warn, fail
    component: str
    message: str


def run_doctor(store_path: Path, state: InstallState) -> List[DoctorFinding]:
    """Run full installation health check."""
    findings: List[DoctorFinding] = []

    # 1. Store exists
    if store_path.exists():
        findings.append(DoctorFinding("ok", "store", f"{store_path} exists"))
    else:
        findings.append(DoctorFinding("fail", "store", f"{store_path} does not exist"))
        return findings

    # 2. State file exists
    state_file = store_path / STATE_FILE
    if state_file.exists():
        findings.append(DoctorFinding("ok", "state", "Install manifest found"))
    else:
        findings.append(DoctorFinding("warn", "state", "No install manifest — was installer used?"))

    # 3. Expected skills present
    for skill_name in state.skills:
        skill_path = store_path / skill_name
        if skill_path.is_dir() and (skill_path / "SKILL.md").exists():
            findings.append(DoctorFinding("ok", f"skill:{skill_name}", "present"))
        elif skill_path.exists():
            findings.append(DoctorFinding("warn", f"skill:{skill_name}", "dir exists but no SKILL.md"))
        else:
            findings.append(DoctorFinding("fail", f"skill:{skill_name}", "missing from store"))

    # 4. Symlink views
    for runtime in state.runtimes:
        rt_skills = Path.home() / f".{runtime}" / "skills"
        if not rt_skills.exists():
            findings.append(DoctorFinding("fail", f"runtime:{runtime}", f"{rt_skills} does not exist"))
            continue
        for skill_name in state.skills:
            link = rt_skills / skill_name
            canonical = store_path / skill_name
            if link.is_symlink():
                target = link.resolve()
                if target == canonical.resolve():
                    findings.append(DoctorFinding("ok", f"symlink:{runtime}/{skill_name}", "correct"))
                else:
                    findings.append(
                        DoctorFinding(
                            "warn",
                            f"symlink:{runtime}/{skill_name}",
                            f"points to {target}, expected {canonical}",
                        )
                    )
            elif link.is_dir():
                findings.append(
                    DoctorFinding(
                        "fail",
                        f"symlink:{runtime}/{skill_name}",
                        "is a COPY, not a symlink — stale drift risk",
                    )
                )
            else:
                findings.append(DoctorFinding("fail", f"symlink:{runtime}/{skill_name}", "missing"))

    # 5. Foundations
    for f in FOUNDATIONS:
        path = f.is_installed()
        if path:
            findings.append(DoctorFinding("ok", f"foundation:{f.name}", f"-> {path}"))
        elif f.required:
            findings.append(
                DoctorFinding("fail", f"foundation:{f.name}", f"missing — {f.install_hint()}")
            )
        else:
            findings.append(
                DoctorFinding("warn", f"foundation:{f.name}", f"optional, not installed")
            )

    # 6. Shell helpers
    helper_file = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zsh" / "vc-skills.zsh"
    if helper_file.exists():
        findings.append(DoctorFinding("ok", "shell-helpers", str(helper_file)))
    elif state.shell_helpers:
        findings.append(DoctorFinding("warn", "shell-helpers", "marked as installed but file missing"))
    else:
        findings.append(DoctorFinding("ok", "shell-helpers", "not installed (optional)"))

    return findings


def print_doctor(findings: List[DoctorFinding]) -> int:
    """Print doctor findings. Returns exit code (0 if no failures)."""
    print(f"\n{bold('VetCoders Doctor')}\n")

    fails = 0
    warns = 0
    oks = 0

    for f in findings:
        if f.level == "ok":
            icon = OK
            oks += 1
        elif f.level == "warn":
            icon = WARN
            warns += 1
        else:
            icon = MISS
            fails += 1
        print(f"  {icon} {f.component}: {f.message}")

    print(f"\n  {green(str(oks))} ok  {yellow(str(warns))} warnings  {red(str(fails))} failures\n")

    if fails:
        print(f"  {red('Installation has issues.')} Run {bold('vetcoders install')} to fix.\n")
        return 1
    elif warns:
        print(f"  {yellow('Installation healthy with minor warnings.')}\n")
        return 0
    else:
        print(f"  {green('Installation healthy.')}\n")
        return 0


# ---------------------------------------------------------------------------
# Subcommand: install
# ---------------------------------------------------------------------------


def cmd_install(args: argparse.Namespace) -> int:
    repo_root = Path(args.source).resolve()
    if not repo_root.is_dir():
        print(red(f"Error: repo root not found: {repo_root}"))
        return 1

    interactive = _IS_TTY and not args.non_interactive
    dry_run = args.dry_run
    advanced = args.advanced
    mirror = args.mirror
    cli_with_shell = args.with_shell
    cli_tools = args.tools  # None = all, list = subset
    cli_skill_filter = args.skill_filter  # None = all, list = subset

    # --- Header ---
    print()
    print(bold("VetCoders Skills Installer v2"))
    print(dim(f"Source: {repo_root}"))
    print()

    # --- Discover skills ---
    skills = discover_skills(repo_root)
    if not skills:
        print(red("No skills found in repo."))
        return 1

    cats = categorize_all(skills)
    skill_names = [s.name for s in skills]

    # --- Show bundle ---
    print(bold("Bundle contents:"))
    for cat_key in ("pipeline", "specialist"):
        cat = SKILL_CATEGORIES[cat_key]
        names = cats[cat_key]
        if names:
            print(f"  {cyan(cat['label'])} ({len(names)})")
            for n in names:
                print(f"    - {n}")
    print()

    # --- Selective install ---
    selected_skills = list(skill_names)
    if cli_skill_filter:
        # CLI --skill flags take precedence
        unknown = [s for s in cli_skill_filter if s not in skill_names]
        if unknown:
            print(yellow(f"Unknown skills (skipped): {', '.join(unknown)}"))
        selected_skills = [s for s in cli_skill_filter if s in skill_names]
        if not selected_skills:
            print(red("No valid skills selected."))
            return 1
    elif advanced and interactive:
        defaults = [True] * len(skill_names)
        result = ask_multi("Select skills to install:", skill_names, defaults)
        selected_skills = [n for n, sel in zip(skill_names, result) if sel]
        if not selected_skills:
            print(red("No skills selected."))
            return 1
        print()

    # --- Detect system ---
    print(bold("System check:"))
    sys_deps = detect_system_deps()
    for cmd, path in sys_deps.items():
        if path:
            print(f"  {OK} {cmd} -> {dim(path)}")
        else:
            print(f"  {MISS} {cmd}")

    osascript = detect_osascript()
    if osascript:
        print(f"  {OK} osascript -> {dim(osascript)}")
    else:
        print(f"  {OPT} osascript {dim('(headless spawn still works)')}")
    print()

    # Missing critical deps
    missing_critical = [cmd for cmd in ("zsh", "python3", "git", "rsync") if not sys_deps.get(cmd)]
    if missing_critical:
        print(red(f"Missing critical dependencies: {', '.join(missing_critical)}"))
        print("Install them before continuing.")
        return 1

    # --- Agent runtimes ---
    print(bold("Agent runtimes:"))
    available_runtimes = detect_agent_runtimes()
    for rt, path in available_runtimes.items():
        if path:
            print(f"  {OK} {rt} -> {dim(path)}")
        else:
            print(f"  {OPT} {rt} {dim('(not installed)')}")
    print()

    # Choose runtimes for symlink views
    all_runtimes = [rt for rt in AGENT_RUNTIMES if rt != "gemini"]
    if cli_tools:
        # CLI --tool flags take precedence
        all_runtimes = [rt for rt in cli_tools if rt in AGENT_RUNTIMES]
    elif interactive and not advanced:
        print(dim("  Note: gemini-cli in some versions duplicates the workflows, inheriting"))
        print(dim("  skills from the other agents. Gemini symlinks skipped by default."))
        create_all = ask_yn("Create symlink views for default runtimes (codex, claude)?", default=True)
        if not create_all:
            defaults = [bool(available_runtimes.get(rt)) and rt != "gemini" for rt in AGENT_RUNTIMES]
            result = ask_multi("Select runtimes for symlink views:", AGENT_RUNTIMES, defaults)
            all_runtimes = [rt for rt, sel in zip(AGENT_RUNTIMES, result) if sel]
        print()
    elif advanced and interactive:
        print(dim("  Note: gemini-cli in some versions duplicates the workflows, inheriting"))
        print(dim("  skills from the other agents. Gemini symlinks skipped by default."))
        defaults = [rt != "gemini" for rt in AGENT_RUNTIMES]
        result = ask_multi("Select runtimes for symlink views:", AGENT_RUNTIMES, defaults)
        all_runtimes = [rt for rt, sel in zip(AGENT_RUNTIMES, result) if sel]
        print()

    # --- Runtime Foundations ---
    print(bold("Runtime Foundations:"))
    missing_foundations: List[Foundation] = []
    for f in FOUNDATIONS:
        path = f.is_installed()
        if path:
            print(f"  {OK} {f.name} -> {dim(path)}")
            print(f"       {dim(f.description)}")
        elif f.required:
            print(f"  {MISS} {f.name} — {f.description}")
            print(f"       {dim(f.install_hint())}")
            missing_foundations.append(f)
        else:
            print(f"  {OPT} {f.name} — {f.description}")
            print(f"       {dim(f.install_hint())}")
    print()

    # Offer to install missing foundations
    has_cargo = detect_cargo()
    installed_foundations: Dict[str, Dict] = {}
    if missing_foundations and has_cargo and interactive:
        for f in missing_foundations:
            if "crates" in f.channels:
                label = "required" if f.required else "optional"
                if ask_yn(f"Install {f.name} via cargo? ({label})", default=f.required):
                    success = install_foundation_cargo(f, dry_run=dry_run)
                    channel = "crates"
                    installed_foundations[f.name] = {
                        "channel": channel,
                        "success": success,
                    }
                    if success:
                        print(f"  {OK} {f.name} installed")
                    else:
                        print(f"  {MISS} {f.name} installation failed")
        print()
    elif missing_foundations and not has_cargo:
        print(yellow("cargo not found — cannot auto-install foundations."))
        print(dim("Install cargo (rustup) first, or install foundations manually:"))
        for f in missing_foundations:
            print(f"  {f.install_hint()}")
        print()

    # Record all foundations state
    for f in FOUNDATIONS:
        if f.name not in installed_foundations:
            path = f.is_installed()
            installed_foundations[f.name] = {
                "channel": "pre-existing" if path else "not-installed",
                "path": path or "",
            }

    # --- Shell helpers ---
    install_shell = cli_with_shell  # --with-shell flag
    if not install_shell and interactive:
        install_shell = ask_yn("Install zsh shell helpers (codex-implement, claude-plan, etc.)?", default=True)
        print()

    # --- Helper conflict check ---
    if install_shell:
        conflicts = scan_helper_conflicts()
        if conflicts:
            should_proceed = report_helper_conflicts(conflicts, interactive)
            if not should_proceed:
                install_shell = False

    # --- Confirm ---
    shared_home = Path(os.environ.get("VETCODERS_AGENTS_HOME", Path.home() / ".agents"))
    store_path = shared_home / "skills"

    print(bold("Install plan:"))
    print(f"  Skills:    {len(selected_skills)} -> {cyan(str(store_path))}")
    print(f"  Runtimes:  {', '.join(all_runtimes)} {dim('(symlink views)')}")
    print(f"  Shell:     {'yes' if install_shell else 'no'}")
    if dry_run:
        print(f"  Mode:      {yellow('DRY RUN')}")
    print()

    if interactive:
        if not ask_yn("Proceed with installation?", default=True):
            print("Aborted.")
            return 0
        print()

    # --- Backup existing state ---
    print(bold("Backing up existing state..."))
    backup_ts = create_backup(store_path, all_runtimes, selected_skills, dry_run=dry_run)
    if backup_ts:
        print(f"  {OK} Backup saved: {_backup_root(store_path) / backup_ts}")
    else:
        print(f"  {dim('nothing to back up (fresh install)')}")
    print()

    # --- Execute: rsync skills ---
    print(bold("Installing skills..."))
    if not dry_run:
        store_path.mkdir(parents=True, exist_ok=True)

    for name in selected_skills:
        src = repo_root / name
        dst = store_path / name
        print(f"  {dim('->')} {name}")
        rsync_skill(src, dst, dry_run=dry_run, mirror=mirror)
    print()

    # --- Execute: symlink views ---
    print(bold("Creating symlink views..."))
    for rt in all_runtimes:
        rt_skills = Path.home() / f".{rt}" / "skills"
        if not dry_run:
            rt_skills.mkdir(parents=True, exist_ok=True)
        print(f"  {cyan(rt)} -> {rt_skills}")
        for name in selected_skills:
            canonical = store_path / name
            link = rt_skills / name
            create_symlink(canonical, link, dry_run=dry_run)
    print()

    # --- Execute: shell helpers ---
    if install_shell:
        print(bold("Installing shell helpers..."))
        shell_script = repo_root / "vc-agents" / "scripts" / "install-shell.sh"
        if shell_script.exists():
            cmd = ["bash", str(shell_script), "--source", str(repo_root)]
            if dry_run:
                cmd.append("--dry-run")
            subprocess.run(cmd, check=False)
        else:
            print(f"  {WARN} Shell installer not found: {shell_script}")
        print()

    # --- Save state ---
    now = datetime.now(timezone.utc).isoformat()
    state = InstallState(
        installed_at=now,
        updated_at=now,
        repo_commit=get_repo_commit(repo_root),
        repo_url=get_repo_url(repo_root),
        skills=selected_skills,
        runtimes=all_runtimes,
        foundations=installed_foundations,
        shell_helpers=install_shell,
        install_path=str(store_path),
    )
    if not dry_run:
        state.save(store_path)
        print(f"  {OK} Install manifest saved to {store_path / STATE_FILE}")
    else:
        print(f"  {SKIP} Dry run — manifest not saved")
    print()

    # --- Doctor ---
    print(bold("Post-install verification:"))
    if dry_run:
        print(f"  {SKIP} Skipped in dry-run mode")
    else:
        findings = run_doctor(store_path, state)
        # Print only failures and warnings
        issues = [f for f in findings if f.level != "ok"]
        if issues:
            for f in issues:
                icon = WARN if f.level == "warn" else MISS
                print(f"  {icon} {f.component}: {f.message}")
        else:
            print(f"  {OK} All checks passed")
    print()

    # --- Done ---
    print(green(bold("Install complete.")))
    print()
    print(dim("Next steps:"))
    print(dim("  - Run 'python3 scripts/vetcoders_install.py doctor' anytime to re-verify"))
    print(dim("  - Start a new shell session to pick up helpers"))

    missing_fnd = [f for f in FOUNDATIONS if f.required and not f.is_installed()]
    if missing_fnd:
        print()
        print(yellow("Foundations still missing:"))
        for f in missing_fnd:
            print(f"  {f.name}: {f.install_hint()}")
    print()

    return 0


# ---------------------------------------------------------------------------
# Subcommand: doctor
# ---------------------------------------------------------------------------


def _known_bundle_names() -> List[str]:
    """Skill names this installer manages. Used to scope doctor checks."""
    # Try to discover from repo checkout next to this script
    script_dir = Path(__file__).resolve().parent
    repo_candidate = script_dir.parent
    if (repo_candidate / ".git").is_dir():
        return [s.name for s in discover_skills(repo_candidate)]
    return []


def cmd_doctor(args: argparse.Namespace) -> int:
    shared_home = Path(os.environ.get("VETCODERS_AGENTS_HOME", Path.home() / ".agents"))
    store_path = shared_home / "skills"
    state = InstallState.load(store_path)
    has_manifest = bool(state.skills)

    if not state.skills:
        # No manifest — discover from disk, but only OUR skills
        bundle = set(_known_bundle_names())
        if store_path.exists():
            state.skills = [
                d.name for d in sorted(store_path.iterdir())
                if d.is_dir() and (d / "SKILL.md").exists() and d.name in bundle
            ]
        # Only check runtimes that actually have a skills dir
        state.runtimes = [
            rt for rt in AGENT_RUNTIMES
            if (Path.home() / f".{rt}" / "skills").exists()
        ]

    findings = run_doctor(store_path, state)

    # Extra checks when no manifest: scan per-agent dirs for stale copies
    # but ONLY for skills in our bundle — don't claim ownership of other tools
    if not has_manifest:
        bundle = set(_known_bundle_names())
        findings.insert(0, DoctorFinding(
            "warn", "manifest",
            "No install manifest found — running in discovery mode. "
            "Install with the Smart Installer to get full tracking.",
        ))
        for rt in state.runtimes:
            rt_skills = Path.home() / f".{rt}" / "skills"
            if not rt_skills.exists():
                continue
            for entry in sorted(rt_skills.iterdir()):
                if not entry.is_dir() or entry.name.startswith("."):
                    continue
                if entry.name not in bundle:
                    continue  # Not our skill — skip
                if not (entry / "SKILL.md").exists():
                    continue
                if not entry.is_symlink():
                    findings.append(DoctorFinding(
                        "fail",
                        f"stale-copy:{rt}/{entry.name}",
                        f"is a local COPY, not a symlink to shared store — drift risk",
                    ))
                elif store_path.exists():
                    target = entry.resolve()
                    expected = (store_path / entry.name).resolve()
                    if target != expected and (store_path / entry.name).exists():
                        findings.append(DoctorFinding(
                            "warn",
                            f"symlink:{rt}/{entry.name}",
                            f"points to {target}, expected {expected}",
                        ))

    return print_doctor(findings)


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    repo_root = Path(args.source).resolve()
    if not repo_root.is_dir():
        print(red(f"Error: repo root not found: {repo_root}"))
        return 1

    skills = discover_skills(repo_root)
    cats = categorize_all(skills)

    print(f"\n{bold('VetCoders Skills Bundle')}")
    print(dim(f"Source: {repo_root}\n"))

    for cat_key in ("pipeline", "specialist"):
        cat = SKILL_CATEGORIES[cat_key]
        names = cats[cat_key]
        if names:
            print(f"  {bold(cat['label'])} — {dim(cat['description'])}")
            for n in names:
                print(f"    - {n}")
            print()

    print(f"{bold('Runtime Foundations')} {dim('(substrate beneath the suite)')}")
    for f in FOUNDATIONS:
        path = f.is_installed()
        status = green("installed") if path else (red("missing") if f.required else dim("optional"))
        print(f"  {f.name}: {status} — {f.description}")
        print(f"    Channels: {', '.join(f.channels)}")
    print()

    return 0


# ---------------------------------------------------------------------------
# Subcommand: uninstall
# ---------------------------------------------------------------------------


def cmd_uninstall(args: argparse.Namespace) -> int:
    shared_home = Path(os.environ.get("VETCODERS_AGENTS_HOME", Path.home() / ".agents"))
    store_path = shared_home / "skills"
    state = InstallState.load(store_path)
    dry_run = args.dry_run
    bundle = set(_known_bundle_names())

    # Use manifest if available, otherwise use bundle names
    skill_names = state.skills if state.skills else [n for n in bundle]
    runtimes = state.runtimes if state.runtimes else [
        rt for rt in AGENT_RUNTIMES if (Path.home() / f".{rt}" / "skills").exists()
    ]

    print(f"\n{bold('VetCoders Uninstall')}\n")

    if not skill_names:
        print(dim("Nothing to uninstall — no manifest and no known skills found."))
        return 0

    print(f"  Will remove {len(skill_names)} skills from:")
    print(f"    Store: {store_path}")
    for rt in runtimes:
        print(f"    Symlinks: ~/.{rt}/skills/")
    print()

    if _IS_TTY and not dry_run:
        if not ask_yn("Proceed with uninstall?", default=False):
            print("Aborted.")
            return 0
        print()

    # Backup before removing
    print(bold("Backing up before uninstall..."))
    backup_ts = create_backup(store_path, runtimes, skill_names, dry_run=dry_run)
    if backup_ts:
        print(f"  {OK} Backup saved: {_backup_root(store_path) / backup_ts}")
        print(f"  {dim('Use `make restore` to undo this uninstall.')}")
    print()

    # Remove symlinks from per-runtime dirs
    print(bold("Removing symlink views..."))
    for rt in runtimes:
        rt_skills = Path.home() / f".{rt}" / "skills"
        if not rt_skills.exists():
            continue
        for name in skill_names:
            link = rt_skills / name
            if link.exists() or link.is_symlink():
                if dry_run:
                    print(f"  {dim('rm')} {link}")
                else:
                    if link.is_symlink():
                        link.unlink()
                    elif link.is_dir():
                        shutil.rmtree(link)
                    print(f"  {dim('-')} {rt}/{name}")
    print()

    # Remove skills from shared store
    print(bold("Removing skills from store..."))
    for name in skill_names:
        skill_path = store_path / name
        if skill_path.exists():
            if dry_run:
                print(f"  {dim('rm -rf')} {skill_path}")
            else:
                shutil.rmtree(skill_path)
                print(f"  {dim('-')} {name}")
    print()

    # Remove shell helpers
    helper_file = _helper_target_path()
    if helper_file.exists():
        print(bold("Removing shell helpers..."))
        if dry_run:
            print(f"  {dim('rm')} {helper_file}")
        else:
            helper_file.unlink()
            print(f"  {dim('-')} {helper_file}")

        # Remove source line from .zshrc
        zshrc = Path.home() / ".zshrc"
        source_line = _zshrc_source_line()
        if zshrc.exists():
            content = zshrc.read_text()
            if source_line in content:
                if dry_run:
                    print(f"  {dim('remove source line from')} {zshrc}")
                else:
                    new_content = content.replace(f"\n# VetCoders shell helpers\n{source_line}\n", "\n")
                    new_content = new_content.replace(source_line, "")
                    zshrc.write_text(new_content)
                    print(f"  {dim('-')} source line from {zshrc}")
        print()

    # Remove manifest
    state_file = store_path / STATE_FILE
    if state_file.exists():
        if dry_run:
            print(f"  {dim('rm')} {state_file}")
        else:
            state_file.unlink()

    print(green(bold("Uninstall complete.")))
    if backup_ts:
        print(dim(f"  Backup at: {_backup_root(store_path) / backup_ts}"))
        print(dim("  Run 'make restore' to undo."))
    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: restore
# ---------------------------------------------------------------------------


def cmd_restore(args: argparse.Namespace) -> int:
    shared_home = Path(os.environ.get("VETCODERS_AGENTS_HOME", Path.home() / ".agents"))
    store_path = shared_home / "skills"
    dry_run = args.dry_run
    backup_root = _backup_root(store_path)

    print(f"\n{bold('VetCoders Restore')}\n")

    # Find latest backup
    latest_file = backup_root / "latest"
    if not latest_file.exists():
        print(red("No backup found. Nothing to restore."))
        return 1

    ts = latest_file.read_text().strip()
    backup_dir = backup_root / ts
    if not backup_dir.is_dir():
        print(red(f"Backup directory not found: {backup_dir}"))
        return 1

    print(f"  Restoring from backup: {bold(ts)}")
    print()

    restored = 0

    # Restore skills in store
    store_backup = backup_dir / "store"
    if store_backup.is_dir():
        print(bold("Restoring skills to store..."))
        for entry in sorted(store_backup.iterdir()):
            if not entry.is_dir():
                continue
            dst = store_path / entry.name
            if dry_run:
                print(f"  {dim('restore')} {entry.name}")
            else:
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(entry, dst, symlinks=True)
                print(f"  {OK} {entry.name}")
            restored += 1
        print()

    # Restore per-runtime entries
    rt_backup = backup_dir / "runtimes"
    if rt_backup.is_dir():
        print(bold("Restoring runtime entries..."))
        for rt_dir in sorted(rt_backup.iterdir()):
            if not rt_dir.is_dir():
                continue
            rt = rt_dir.name
            rt_skills = Path.home() / f".{rt}" / "skills"
            for entry in sorted(rt_dir.iterdir()):
                if not entry.is_dir():
                    continue
                dst = rt_skills / entry.name
                if dry_run:
                    print(f"  {dim('restore')} {rt}/{entry.name}")
                else:
                    if dst.exists() or dst.is_symlink():
                        if dst.is_symlink():
                            dst.unlink()
                        else:
                            shutil.rmtree(dst)
                    shutil.copytree(entry, dst, symlinks=True)
                    print(f"  {OK} {rt}/{entry.name}")
                restored += 1
        print()

    # Restore helpers
    helper_backup = backup_dir / "helpers"
    if helper_backup.is_dir():
        print(bold("Restoring helpers..."))
        # Helper file
        backed_helper = helper_backup / "vc-skills.zsh"
        if backed_helper.exists():
            dst = _helper_target_path()
            if dry_run:
                print(f"  {dim('restore')} {dst.name}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backed_helper, dst)
                print(f"  {OK} {dst}")
            restored += 1

        # .zshrc
        backed_zshrc = helper_backup / ".zshrc"
        if backed_zshrc.exists():
            dst = Path.home() / ".zshrc"
            if dry_run:
                print(f"  {dim('restore')} .zshrc")
            else:
                shutil.copy2(backed_zshrc, dst)
                print(f"  {OK} .zshrc")
            restored += 1
        print()

    # Remove manifest (since we're reverting to pre-install state)
    state_file = store_path / STATE_FILE
    if state_file.exists() and not dry_run:
        state_file.unlink()

    if restored:
        print(green(bold(f"Restored {restored} items from backup {ts}.")))
    else:
        print(yellow("Backup existed but contained no items to restore."))
    print()
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def detect_repo_root() -> str:
    """Try to find the repo root from script location."""
    script_dir = Path(__file__).resolve().parent
    # scripts/vetcoders_install.py -> repo root is parent
    candidate = script_dir.parent
    if (candidate / ".git").is_dir():
        return str(candidate)
    return str(Path.cwd())


def main(argv: Optional[Sequence[str]] = None) -> int:
    default_source = detect_repo_root()

    parser = argparse.ArgumentParser(
        prog="vc-install",
        description="VetCoders Skills Installer v2 — manifest-driven, multi-channel, interactive.",
    )
    sub = parser.add_subparsers(dest="command")

    # install
    p_install = sub.add_parser("install", help="Install the VetCoders skill bundle")
    p_install.add_argument("--source", default=default_source, help="Repo root (default: auto-detect)")
    p_install.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")
    p_install.add_argument("--non-interactive", action="store_true", help="Skip all prompts, use defaults")
    p_install.add_argument("--advanced", action="store_true", help="Enable selective skill/runtime install")
    p_install.add_argument("--with-shell", action="store_true", help="Install zsh shell helpers")
    p_install.add_argument(
        "--tool", dest="tools", action="append", choices=["codex", "claude", "gemini"],
        help="Limit symlink views to these runtimes (repeatable, default: all)",
    )
    p_install.add_argument(
        "--skill", dest="skill_filter", action="append",
        help="Install only these skills (repeatable, default: full bundle)",
    )
    p_install.add_argument("--mirror", action="store_true", help="Delete extra files in installed skill dirs (rsync --delete)")

    # doctor
    sub.add_parser("doctor", help="Verify installation health")

    # list
    p_list = sub.add_parser("list", help="Show available VetCoders skills and the runtime substrate beneath them")
    p_list.add_argument("--source", default=default_source, help="Repo root (default: auto-detect)")

    # uninstall
    p_uninstall = sub.add_parser("uninstall", help="Remove VetCoders skills, symlinks, and helpers")
    p_uninstall.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")

    # restore
    p_restore = sub.add_parser("restore", help="Restore pre-install state from backup")
    p_restore.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "install":
        return cmd_install(args)
    elif args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "uninstall":
        return cmd_uninstall(args)
    elif args.command == "restore":
        return cmd_restore(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
