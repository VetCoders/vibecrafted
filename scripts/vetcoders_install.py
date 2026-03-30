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
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

try:
    from installer_brand import (
        FOOTER_BRANDING,
        FRAMEWORK_STAMP,
        PRODUCT_LINE,
        TAGLINE,
        VAPOR_HEADER,
        separator as brand_separator,
        version_line as brand_version_line,
    )
except (
    ModuleNotFoundError
):  # pragma: no cover - module import path depends on entrypoint
    from scripts.installer_brand import (
        FOOTER_BRANDING,
        FRAMEWORK_STAMP,
        PRODUCT_LINE,
        TAGLINE,
        VAPOR_HEADER,
        separator as brand_separator,
        version_line as brand_version_line,
    )

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
# Compact-mode output: TeeLogger + helpers
# ---------------------------------------------------------------------------


class TeeLogger:
    """Captures print output to a log file while optionally suppressing stdout."""

    def __init__(self, log_path: Path, quiet: bool = False):
        self.log = open(log_path, "w")
        self.quiet = quiet
        self._real_stdout = sys.__stdout__

    def write(self, text: str) -> int:
        self.log.write(text)
        if not self.quiet:
            self._real_stdout.write(text)
        return len(text)

    def flush(self) -> None:
        self.log.flush()
        if not self.quiet:
            self._real_stdout.flush()

    def close(self) -> None:
        self.log.close()


@contextmanager
def compact_logging(log_path: Path, quiet: bool = True):
    """Context manager: redirects stdout to log, keeps real stdout for compact lines."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tee = TeeLogger(log_path, quiet=quiet)
    real_stdout = sys.stdout
    sys.stdout = tee  # type: ignore[assignment]
    try:
        yield real_stdout  # caller prints compact lines to this
    finally:
        sys.stdout = real_stdout
        tee.close()


def _compact_line(out, icon: str, label: str, value: str) -> None:
    """Print one compact status line to the real stdout."""
    out.write(f"  {icon} {label:13s} {value}\n")


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
            elif ch == "brew":
                hints.append(f"brew install {pkg}")
            elif ch == "npm":
                hints.append(f"npm i -g {pkg}")
            elif ch == "github":
                hints.append(f"Download from {pkg}")
            elif ch == "pip":
                hints.append(f"pipx install {pkg}")
            elif ch == "source":
                hints.append(f"Download from {pkg}")
        return " | ".join(hints)


FOUNDATIONS: List[Foundation] = [
    Foundation(
        name="aicx-mcp",
        description="AICX MCP server for session history and memory recovery",
        channels=["crates", "github"],
        packages={
            "crates": "ai-contexters",
            "github": "https://github.com/VetCoders/ai-contexters/releases",
        },
        verify_cmd="aicx-mcp --version",
    ),
    Foundation(
        name="loctree-mcp",
        description="Structural code mapping MCP server",
        channels=["crates", "npm", "github"],
        packages={
            "crates": "loctree-mcp",
            "npm": "loctree-mcp",
            "github": "https://github.com/Loctree/Loctree/releases",
        },
        verify_cmd="loctree-mcp --version",
    ),
    Foundation(
        name="prview",
        description="PR review artifact generator",
        channels=["crates", "github"],
        packages={
            "crates": "prview",
            "github": "https://github.com/VetCoders/prview/releases",
        },
        verify_cmd="prview --version",
        required=False,
    ),
    Foundation(
        name="screenscribe",
        description="Screencast analysis — turns narrated recordings into structured engineering findings",
        channels=["pip", "source"],
        packages={
            "pip": "screenscribe",
            "source": "https://github.com/VetCoders/Screenscribe/releases",
        },
        verify_cmd="screenscribe --version",
        required=False,
    ),
    Foundation(
        name="mise",
        description="Repo-owned toolchain, environment, and task substrate",
        channels=["brew", "github"],
        packages={
            "brew": "mise",
            "github": "https://github.com/jdx/mise/releases",
        },
        verify_cmd="mise --version",
        required=False,
    ),
    Foundation(
        name="starship",
        description="Cross-shell prompt/status line for operator UX",
        channels=["brew", "github"],
        packages={
            "brew": "starship",
            "github": "https://github.com/starship/starship/releases",
        },
        verify_cmd="starship --version",
        required=False,
    ),
    Foundation(
        name="atuin",
        description="Shell history recall with optional encrypted sync",
        channels=["brew", "github"],
        packages={
            "brew": "atuin",
            "github": "https://github.com/atuinsh/atuin/releases",
        },
        verify_cmd="atuin --version",
        required=False,
    ),
    Foundation(
        name="zoxide",
        description="Fast directory jumping for agent-heavy shell workflows",
        channels=["brew", "github"],
        packages={
            "brew": "zoxide",
            "github": "https://github.com/ajeetdsouza/zoxide/releases",
        },
        verify_cmd="zoxide --version",
        required=False,
    ),
    Foundation(
        name="zellij",
        description="Visible multi-agent terminal workspace surface",
        channels=["brew", "github"],
        packages={
            "brew": "zellij",
            "github": "https://github.com/zellij-org/zellij/releases",
        },
        verify_cmd="zellij --version",
        required=False,
    ),
]

RUNTIME_DEPS = ["python3", "git", "rsync"]
OPTIONAL_DEPS = [
    "zsh"
]  # helpers work in bash and zsh; core install works without either

OLD_SKILL_PREFIX = "vetcoders-"
OLD_HELPER_NAME = "vetcoders-skills.zsh"


def _is_writable(path: Path) -> bool:
    """Check if a file is actually writable (respects uchg/immutable flags)."""
    if not path.exists():
        return True
    try:
        with open(path, "a"):
            pass
        return True
    except OSError:
        return False


AGENT_RUNTIMES = ["codex", "claude", "gemini"]
SYMLINK_TARGETS = ["agents", "claude", "codex"]
SYMLINK_TARGET_CHOICES = [*SYMLINK_TARGETS, "gemini"]

# ---------------------------------------------------------------------------
# Install state
# ---------------------------------------------------------------------------

STATE_FILE = ".vc-install.json"


@dataclass
class InstallState:
    """Persisted installation state."""

    version: str = "2.0"
    framework_version: str = ""
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


def runtime_skills_dir(runtime: str) -> Path:
    return Path.home() / f".{runtime}" / "skills"


def detect_osascript() -> Optional[str]:
    return shutil.which("osascript")


def detect_cargo() -> Optional[str]:
    return shutil.which("cargo")


def get_framework_version(repo_root: Path) -> str:
    version_file = repo_root / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"


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
    skills_dir = repo_root / "skills"
    if not skills_dir.exists() or not skills_dir.is_dir():
        return skills

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name in ("docs", "scripts", "tests", ".github"):
            continue
        if not entry.name.startswith("vc-") and not entry.name.startswith("vetcoders-"):
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
    """Reads a single keypress or escape sequence from stdin (unbuffered)."""
    import select

    fd = sys.stdin.fileno()
    ch = os.read(fd, 1)
    if ch == b"\x1b":
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            ch += os.read(fd, 2)
    return ch.decode("utf-8", errors="ignore")


def _accumulate_digits(first: str) -> str:
    """Collect multi-digit number input with a short timeout between digits."""
    import select

    fd = sys.stdin.fileno()
    buf = first
    while True:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            nxt = os.read(fd, 1).decode("utf-8", errors="ignore")
            if nxt.isdigit():
                buf += nxt
            else:
                break
        else:
            break
    return buf


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
            answer = input(
                dim(f"  Choice [1-{len(options)}, default {default + 1}]: ")
            ).strip()
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
            if char in ("\n", "\r"):
                break
            elif char.isdigit() and char != "0":
                num_str = _accumulate_digits(char) if len(options) >= 10 else char
                idx = int(num_str) - 1
                if 0 <= idx < len(options):
                    current_idx = idx
                    break
            elif char == "\x1b[A":  # Up
                current_idx = max(0, current_idx - 1)
                render()
            elif char == "\x1b[B":  # Down
                current_idx = min(len(options) - 1, current_idx + 1)
                render()
            elif char == "\x03":  # Ctrl+C
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
            print(
                dim(
                    "  (Type numbers space-separated. E.g. '1 2' to select exactly those, or '+3' / '-1' to toggle)"
                )
            )
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
                    is_add = tok.startswith("+")
                    is_sub = tok.startswith("-")
                    clean_tok = tok.lstrip("+-")
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
    print(
        dim("  (Use UP/DOWN to navigate, SPACE or number to toggle, ENTER to confirm)")
    )

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
            if char in ("\n", "\r"):
                break
            elif char == " ":
                selected[current_idx] = not selected[current_idx]
                render()
            elif char.isdigit() and char != "0":
                num_str = _accumulate_digits(char) if len(options) >= 10 else char
                idx = int(num_str) - 1
                if 0 <= idx < len(options):
                    selected[idx] = not selected[idx]
                    current_idx = idx
                    render()
            elif char == "\x1b[A":  # Up
                current_idx = max(0, current_idx - 1)
                render()
            elif char == "\x1b[B":  # Down
                current_idx = min(len(options) - 1, current_idx + 1)
                render()
            elif char == "\x03":  # Ctrl+C
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


def _copy_path_to_backup(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():
        dst.symlink_to(os.readlink(src))
    elif src.is_dir():
        shutil.copytree(src, dst, symlinks=True)
    elif src.is_file():
        shutil.copy2(src, dst)


def _restore_path_from_backup(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)

    if src.is_symlink():
        dst.symlink_to(os.readlink(src))
    elif src.is_dir():
        shutil.copytree(src, dst, symlinks=True)
    elif src.is_file():
        shutil.copy2(src, dst)


def collect_orphaned_skills(
    store_path: Path, runtimes: List[str], current_bundle: Set[str]
) -> List[Tuple[str, Path]]:
    """Return vc-* entries that no longer exist in the current bundle."""
    orphans: List[Tuple[str, Path]] = []

    if store_path.exists():
        for entry in sorted(store_path.iterdir()):
            if entry.name.startswith(".") or entry.name in current_bundle:
                continue
            if not entry.name.startswith("vc-"):
                continue
            if entry.is_symlink():
                orphans.append(("store", entry))
            elif entry.is_dir() and (entry / "SKILL.md").exists():
                orphans.append(("store", entry))

    for rt in runtimes:
        rt_skills = runtime_skills_dir(rt)
        if not rt_skills.exists():
            continue
        for entry in sorted(rt_skills.iterdir()):
            if not entry.name.startswith("vc-") or entry.name in current_bundle:
                continue
            if entry.is_symlink():
                orphans.append((rt, entry))
            elif entry.is_dir() and (entry / "SKILL.md").exists():
                orphans.append((rt, entry))

    return orphans


def create_backup(
    store_path: Path,
    runtimes: List[str],
    bundle_names: List[str],
    orphaned_entries: Optional[List[Tuple[str, Path]]] = None,
    dry_run: bool = False,
) -> Optional[str]:
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
        rt_skills = runtime_skills_dir(rt)
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

    # Back up orphaned vc-* entries before pruning so restore can bring them back.
    for location, entry in orphaned_entries or []:
        dst = (
            backup_dir
            / ("store" if location == "store" else f"runtimes/{location}")
            / entry.name
        )
        if dry_run:
            print(f"  {dim('backup')} {entry} -> {dst}")
        else:
            _copy_path_to_backup(entry, dst)
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

    # Back up RC files
    for rcname in (".zshrc", ".bashrc"):
        rcfile = Path.home() / rcname
        if rcfile.exists():
            dst = backup_dir / "helpers" / rcname
            if dry_run:
                print(f"  {dim('backup')} {rcfile} -> {dst}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rcfile, dst)
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
    config_dir = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vetcoders"
    )
    return config_dir / "vc-skills.sh"


def _helper_legacy_path() -> Path:
    config_dir = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zsh"
    )
    return config_dir / "vc-skills.zsh"


def _shell_source_line() -> str:
    """Source line works in both bash and zsh."""
    return '[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"'


def _old_zshrc_source_line() -> str:
    return '[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh"'


# ---------------------------------------------------------------------------
# Helper conflict detection
# ---------------------------------------------------------------------------

KNOWN_HELPER_FUNCTIONS = [
    "codex-implement",
    "codex-plan",
    "codex-review",
    "codex-research",
    "codex-prompt",
    "codex-observe",
    "claude-implement",
    "claude-plan",
    "claude-review",
    "claude-research",
    "claude-prompt",
    "claude-observe",
    "gemini-implement",
    "gemini-plan",
    "gemini-review",
    "gemini-research",
    "gemini-prompt",
    "gemini-observe",
    "skills-sync",
    "gemini-keychain-set",
    "gemini-keychain-get",
    "gemini-keychain-clear",
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
    config_base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    for subdir in ("vetcoders", "zsh"):
        candidate = config_base / subdir
        if candidate.is_dir():
            search_dirs.append(candidate)

    files_to_scan: List[Path] = []
    for d in search_dirs:
        files_to_scan.extend(d.glob("*.sh"))
        files_to_scan.extend(d.glob("*.zsh"))
    for rcfile in (".zshrc", ".bashrc"):
        rc = Path.home() / rcfile
        if rc.exists():
            files_to_scan.append(rc)

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
                    conflicts[fpath].append(
                        HelperConflict(file=fpath, function=fn, line_num=i)
                    )

    return conflicts


def report_helper_conflicts(
    conflicts: Dict[Path, List[HelperConflict]], interactive: bool
) -> bool:
    """Report conflicts and ask user what to do. Returns True if should proceed with install."""
    if not conflicts:
        return True

    print(yellow(bold("\n  Helper overlap detected:")))
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
    print(
        yellow(
            "  These files already contain non-VetCoders content — installer will NOT edit them."
        )
    )

    if not interactive:
        print(
            yellow(
                "  Non-interactive mode: installing the canonical helper file alongside."
            )
        )
        print(yellow("  Clean up duplicates in the files above manually."))
        return True

    choice = ask_choice(
        "  How should we handle it?",
        [
            "Skip helper install and keep the current setup",
            "Install the canonical helper file alongside and clean up duplicates later",
        ],
        default=1,
    )

    if choice == 0:
        print(dim("  Skipping helper install."))
        return False

    print()
    print(yellow("  To clean this up later, remove these functions from your files:"))
    for fpath, items in conflicts.items():
        for c in items:
            print(f"    {c.function} @ {fpath}:{c.line_num}")
    print()
    return True


# ---------------------------------------------------------------------------
# Install logic
# ---------------------------------------------------------------------------


def rsync_skill(
    src: Path, dst: Path, dry_run: bool = False, mirror: bool = False
) -> None:
    """Rsync a single skill directory."""
    if not dry_run:
        dst.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-az", "--exclude", ".DS_Store", "--exclude", ".loctree"]
    if mirror:
        cmd.append("--delete")
    if dry_run:
        cmd += ["--dry-run"]
    cmd += [str(src) + "/", str(dst) + "/"]
    subprocess.run(
        cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def prune_orphaned_skills(
    store_path: Path,
    runtimes: List[str],
    current_bundle: Set[str],
    dry_run: bool = False,
    orphaned_entries: Optional[List[Tuple[str, Path]]] = None,
    interactive: bool = True,
) -> int:
    """Remove vc-* skills from store and runtime dirs that are no longer in the bundle."""
    orphans = orphaned_entries or collect_orphaned_skills(
        store_path, runtimes, current_bundle
    )

    if not orphans:
        return 0

    print(bold("Orphaned skills detected (no longer in bundle):"))
    for location, entry in orphans:
        kind = "symlink" if entry.is_symlink() else "dir"
        print(f"  {yellow(f'[{kind}]')} {location}/{entry.name}")
    print()

    if interactive:
        if not ask_yn("Remove orphaned skills?", default=True):
            print(dim("  Keeping orphaned skills."))
            print()
            return 0

    removed = 0
    for location, entry in orphans:
        if dry_run:
            print(f"  {dim('rm')} {entry}")
            removed += 1
        else:
            if entry.is_symlink() or entry.is_file():
                entry.unlink(missing_ok=True)
            elif entry.is_dir():
                shutil.rmtree(entry)
            removed += 1

    if removed:
        print(f"  {OK} Removed {removed} orphaned entries")
    print()
    return removed


def prune_legacy_skills(
    store_path: Path,
    runtimes: List[str],
    dry_run: bool = False,
    interactive: bool = True,
) -> int:
    """Remove old vetcoders-* skills replaced by vc-* equivalents."""
    legacy: List[tuple] = []

    if store_path.exists():
        for entry in sorted(store_path.iterdir()):
            if entry.is_dir() and entry.name.startswith(OLD_SKILL_PREFIX):
                legacy.append(("store", entry))

    for rt in runtimes:
        rt_skills = Path.home() / f".{rt}" / "skills"
        if not rt_skills.exists():
            continue
        for entry in sorted(rt_skills.iterdir()):
            if (entry.is_dir() or entry.is_symlink()) and entry.name.startswith(
                OLD_SKILL_PREFIX
            ):
                legacy.append((rt, entry))

    old_helper = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "zsh"
        / OLD_HELPER_NAME
    )
    if old_helper.exists():
        legacy.append(("helper", old_helper))

    if not legacy:
        return 0

    print(bold("Old vetcoders-* entries detected:"))
    for location, entry in legacy:
        kind = (
            "symlink" if entry.is_symlink() else ("file" if entry.is_file() else "dir")
        )
        print(f"  {yellow(f'[{kind}]')} {location}/{entry.name}")
    print()

    if interactive:
        if not ask_yn("Remove the old vetcoders-* entries now?", default=True):
            print(dim("  Keeping the old entries."))
            print()
            return 0

    removed = 0
    for location, entry in legacy:
        if dry_run:
            print(f"  {dim('rm')} {entry}")
            removed += 1
        else:
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
            removed += 1

    if removed:
        print(f"  {OK} Removed {removed} legacy entries")

    # Clean old source line from .zshrc
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        content = zshrc.read_text()
        if OLD_HELPER_NAME in content:
            if not _is_writable(zshrc):
                print(f"  {WARN} {zshrc} is locked — cannot remove old source line")
                print(
                    f"       {dim('Remove manually: line referencing ' + OLD_HELPER_NAME)}"
                )
            elif not dry_run:
                lines = content.splitlines(keepends=True)
                new_lines = [ln for ln in lines if OLD_HELPER_NAME not in ln]
                zshrc.write_text("".join(new_lines))
                print(f"  {OK} Cleaned old source line from .zshrc")
            else:
                print(f"  {dim('would clean old source line from .zshrc')}")

    print()
    return removed


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


def _configure_gemini_plans(dry_run: bool = False) -> None:
    """Fix Gemini CLI plan.directory if it points into .vibecrafted.

    Gemini resolves symlinks with realpath() and rejects plans directories
    that resolve outside the project root.  Our .vibecrafted/plans symlink
    points to ~/.vibecrafted/artifacts/…  which is always outside the repo.

    Fix: reset plan.directory to the Gemini-native default so Gemini writes
    plans into $PWD/.gemini/plans/ (its own space).  Our spawn system handles
    artifact centralisation separately via spawn_link_repo_artifacts().
    """
    gemini_settings = Path.home() / ".gemini" / "settings.json"
    if not gemini_settings.exists():
        return

    try:
        data = json.loads(gemini_settings.read_text())
    except (json.JSONDecodeError, OSError):
        return

    plan_dir = (data.get("general") or {}).get("plan", {}).get("directory", "")
    if ".vibecrafted" not in plan_dir:
        return

    # Remove the override — let Gemini use its default (.gemini/plans/)
    if dry_run:
        print(f"  {dim('would reset')} gemini plan.directory (was {plan_dir!r})")
        return

    data["general"]["plan"].pop("directory", None)
    # Clean up empty plan dict if only modelRouting or nothing left
    if not data["general"]["plan"] or data["general"]["plan"] == {}:
        data["general"].pop("plan", None)

    gemini_settings.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  {OK} Gemini plan.directory reset (was {plan_dir!r} -> default)")


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


KNOWN_ZSH_SESSION_NOISE = {
    "saving session",
    "copying shared history",
    "saving history",
    "truncating history files",
    "completed",
    "deleting expired sessions",
    "none found",
}


def is_benign_zsh_session_noise(stderr: str) -> bool:
    """Return True when stderr only contains macOS shell session housekeeping."""
    normalized = " ".join(
        line.strip().lower() for line in stderr.splitlines() if line.strip()
    )
    if not normalized:
        return False

    remainder = normalized
    for fragment in sorted(KNOWN_ZSH_SESSION_NOISE, key=len, reverse=True):
        remainder = remainder.replace(fragment, "")
    remainder = remainder.replace(".", "").replace(" ", "")
    return not remainder


def run_doctor(store_path: Path, state: InstallState) -> List[DoctorFinding]:
    """Run full installation health check."""
    findings: List[DoctorFinding] = []

    # 0. Framework version
    fw_ver = state.framework_version or "unknown"
    findings.append(DoctorFinding("ok", "version", fw_ver))

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
        findings.append(
            DoctorFinding("warn", "state", "No install manifest — was installer used?")
        )

    # 3. Expected skills present
    for skill_name in state.skills:
        skill_path = store_path / skill_name
        if skill_path.is_dir() and (skill_path / "SKILL.md").exists():
            findings.append(DoctorFinding("ok", f"skill:{skill_name}", "present"))
        elif skill_path.exists():
            findings.append(
                DoctorFinding(
                    "warn", f"skill:{skill_name}", "dir exists but no SKILL.md"
                )
            )
        else:
            findings.append(
                DoctorFinding("fail", f"skill:{skill_name}", "missing from store")
            )

    # 4. Symlink views
    for runtime in state.runtimes:
        rt_skills = Path.home() / f".{runtime}" / "skills"
        if not rt_skills.exists():
            findings.append(
                DoctorFinding(
                    "fail", f"runtime:{runtime}", f"{rt_skills} does not exist"
                )
            )
            continue
        for skill_name in state.skills:
            link = rt_skills / skill_name
            canonical = store_path / skill_name
            if link.is_symlink():
                target = link.resolve()
                if target == canonical.resolve():
                    findings.append(
                        DoctorFinding(
                            "ok", f"symlink:{runtime}/{skill_name}", "correct"
                        )
                    )
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
                findings.append(
                    DoctorFinding("fail", f"symlink:{runtime}/{skill_name}", "missing")
                )

    # 5. Foundations
    for f in FOUNDATIONS:
        path = f.is_installed()
        if path:
            findings.append(DoctorFinding("ok", f"foundation:{f.name}", f"-> {path}"))
        elif f.required:
            findings.append(
                DoctorFinding(
                    "fail", f"foundation:{f.name}", f"missing — {f.install_hint()}"
                )
            )
        else:
            findings.append(
                DoctorFinding("warn", f"foundation:{f.name}", "optional, not installed")
            )

    # 6. Shell helpers
    helper_file = _helper_target_path()
    legacy_file = _helper_legacy_path()
    if helper_file.exists():
        findings.append(DoctorFinding("ok", "shell-helpers", str(helper_file)))
    elif legacy_file.exists():
        findings.append(
            DoctorFinding(
                "warn",
                "shell-helpers",
                f"legacy location only: {legacy_file} — re-run install",
            )
        )
    elif state.shell_helpers:
        findings.append(
            DoctorFinding(
                "warn", "shell-helpers", "marked as installed but file missing"
            )
        )
    else:
        findings.append(
            DoctorFinding("ok", "shell-helpers", "not installed (optional)")
        )

    # 7. Shell smoke check: non-interactive zsh should stay quiet under TERM=dumb
    zsh_path = shutil.which("zsh")
    if zsh_path:
        env = os.environ.copy()
        env["TERM"] = "dumb"
        smoke = subprocess.run(
            [zsh_path, "-ic", "exit"],
            env=env,
            capture_output=True,
            text=True,
        )
        stderr = (smoke.stderr or "").strip()
        if smoke.returncode == 0 and (
            not stderr or is_benign_zsh_session_noise(stderr)
        ):
            findings.append(
                DoctorFinding("ok", "shell:dumb-terminal", "zsh -ic stays quiet")
            )
        elif smoke.returncode == 0:
            findings.append(
                DoctorFinding(
                    "warn",
                    "shell:dumb-terminal",
                    "zsh -ic emits stderr under TERM=dumb — guard prompt init for non-interactive shells",
                )
            )
        else:
            findings.append(
                DoctorFinding(
                    "warn",
                    "shell:dumb-terminal",
                    f"zsh -ic exit failed under TERM=dumb (exit {smoke.returncode})",
                )
            )

    return findings


def print_doctor(findings: List[DoctorFinding]) -> int:
    """Print doctor findings. Returns exit code (0 if no failures)."""
    if _IS_TTY:
        print(
            f"\n{bold('\U0001d54d\U0001d55a\U0001d553\U0001d556\U0001d554\U0001d563\U0001d552\U0001d557\U0001d565 Doctor')}\n"
        )
    else:
        print(f"\n{bold('VibeCrafted Doctor')}\n")

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

    print(
        f"\n  {green(str(oks))} ok  {yellow(str(warns))} warnings  {red(str(fails))} failures\n"
    )

    if fails:
        print(
            f"  {red('Installation has issues.')} Run {bold('vetcoders install')} to fix.\n"
        )
        return 1
    elif warns:
        print(f"  {yellow('Installation healthy with minor warnings.')}\n")
        return 0
    else:
        print(f"  {green('\u2713 Installation healthy.')}\n")
        return 0


# ---------------------------------------------------------------------------
# Subcommand: install
# ---------------------------------------------------------------------------


class GoBack(Exception):
    """Raised by the interactive wizard to re-visit a previous step."""

    pass


def _cmd_install_verbose(args: argparse.Namespace, repo_root: Path) -> int:
    """Original verbose install flow — used when --compact is NOT set."""
    interactive = _IS_TTY and not args.non_interactive
    dry_run = args.dry_run
    advanced = args.advanced
    mirror = args.mirror
    cli_with_shell = args.with_shell
    cli_tools = args.tools  # None = all, list = subset
    cli_skill_filter = args.skill_filter  # None = all, list = subset

    # --- Header ---
    sep = brand_separator(33)
    print()
    fw_ver = get_framework_version(repo_root)
    print(f"  \u2692 {VAPOR_HEADER} \u2692")
    print()
    print(f"  {brand_version_line(fw_ver)}")
    print(f"  {TAGLINE}")
    print(f"  {PRODUCT_LINE}")
    print(f"  {sep}")
    print(f"  Source: {repo_root}")
    print()

    # --- Discover skills ---
    skills = discover_skills(repo_root)
    if not skills:
        print(red("No skills found in repo."))
        return 1

    cats = categorize_all(skills)
    skill_names = [s.name for s in skills]

    # --- Show bundle ---
    print(bold("Framework bundle:"))
    print(f"  Pipeline skills   {len(cats['pipeline'])}")
    if cats["specialist"]:
        print(f"  Specialist skills {len(cats['specialist'])}")
    if advanced:
        print()
        for cat_key in ("pipeline", "specialist"):
            cat = SKILL_CATEGORIES[cat_key]
            names = cats[cat_key]
            if names:
                print(f"  {cyan(cat['label'])} ({len(names)})")
                for n in names:
                    print(f"    - {n}")
    else:
        print(
            f"  Use {cyan('--advanced')} to choose skills and runtimes interactively."
        )
    print()

    # --- Interactive Wizard ---
    step = 0
    selected_skills = list(skill_names)
    all_runtimes = list(SYMLINK_TARGETS)
    install_shell = cli_with_shell
    installed_foundations: Dict[str, Dict] = {}

    while True:
        try:
            if step == 0:
                # Skills selection
                if cli_skill_filter:
                    unknown = [s for s in cli_skill_filter if s not in skill_names]
                    if unknown:
                        print(yellow(f"Unknown skills (skipped): {', '.join(unknown)}"))
                    selected_skills = [s for s in cli_skill_filter if s in skill_names]
                    if not selected_skills:
                        print(red("No valid skills selected."))
                        return 1
                    step += 1
                elif advanced and interactive:
                    defaults = [s in selected_skills for s in skill_names]
                    result = ask_multi(
                        "Select skills to install:", skill_names, defaults
                    )
                    selected_skills = [n for n, sel in zip(skill_names, result) if sel]
                    if not selected_skills:
                        print(red("No skills selected."))
                        return 1
                    print()
                    step += 1
                else:
                    step += 1

            elif step == 1:
                # System check (static output, just flows through unless error)
                if not getattr(args, "_sys_checked", False):
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
                        print(
                            f"  {OPT} osascript {dim('(visible Terminal automation unavailable; non-visible fallback exists)')}"
                        )
                    print()

                    missing_critical = [
                        cmd
                        for cmd in ("python3", "git", "rsync")
                        if not sys_deps.get(cmd)
                    ]
                    if missing_critical:
                        print(
                            red(
                                f"Missing critical dependencies: {', '.join(missing_critical)}"
                            )
                        )
                        print("Install them before continuing.")
                        return 1
                    if not sys_deps.get("zsh"):
                        print(
                            f"  {OPT} zsh {dim('(not found — helpers will use bash only)')}"
                        )
                    args._sys_checked = True
                step += 1

            elif step == 2:
                # Runtimes
                if not getattr(args, "_rt_checked", False):
                    print(bold("Agent runtimes:"))
                    available_runtimes = detect_agent_runtimes()
                    for rt, path in available_runtimes.items():
                        if path:
                            print(f"  {OK} {rt} -> {dim(path)}")
                        else:
                            print(f"  {OPT} {rt} {dim('(not installed)')}")
                    print()
                    args._rt_checked = True

                if cli_tools:
                    all_runtimes = [
                        rt for rt in cli_tools if rt in SYMLINK_TARGET_CHOICES
                    ]
                    step += 1
                elif interactive and not advanced:
                    print(
                        dim(
                            "  Note: gemini-cli in some versions duplicates the workflows, inheriting"
                        )
                    )
                    print(
                        dim(
                            "  skills from the other agents. Gemini symlinks skipped by default."
                        )
                    )
                    create_all = ask_yn(
                        "Create the standard skill views for agents, claude, and codex?",
                        default=True,
                    )
                    if not create_all:
                        defaults = [rt in all_runtimes for rt in SYMLINK_TARGET_CHOICES]
                        result = ask_multi(
                            "Select runtimes for symlink views:",
                            SYMLINK_TARGET_CHOICES,
                            defaults,
                        )
                        all_runtimes = [
                            rt for rt, sel in zip(SYMLINK_TARGET_CHOICES, result) if sel
                        ]
                    print()
                    step += 1
                elif advanced and interactive:
                    print(
                        dim(
                            "  Note: gemini-cli in some versions duplicates the workflows, inheriting"
                        )
                    )
                    print(
                        dim(
                            "  skills from the other agents. Gemini symlinks skipped by default."
                        )
                    )
                    defaults = [rt in all_runtimes for rt in SYMLINK_TARGET_CHOICES]
                    result = ask_multi(
                        "Select runtimes for symlink views:",
                        SYMLINK_TARGET_CHOICES,
                        defaults,
                    )
                    all_runtimes = [
                        rt for rt, sel in zip(SYMLINK_TARGET_CHOICES, result) if sel
                    ]
                    print()
                    step += 1
                else:
                    step += 1

            elif step == 3:
                # Foundations
                if not getattr(args, "_fnd_checked", False):
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
                    args._missing_foundations = missing_foundations
                    args._fnd_checked = True

                missing_foundations = args._missing_foundations
                has_cargo = detect_cargo()

                if missing_foundations and has_cargo and interactive:
                    for f in missing_foundations:
                        if "crates" in f.channels:
                            label = "required" if f.required else "optional"
                            if ask_yn(
                                f"Install {f.name} with cargo? ({label})",
                                default=f.required,
                            ):
                                success = install_foundation_cargo(f, dry_run=dry_run)
                                installed_foundations[f.name] = {
                                    "channel": "crates",
                                    "success": success,
                                }
                                if success:
                                    print(f"  {OK} {f.name} installed")
                                else:
                                    print(f"  {MISS} {f.name} installation failed")
                    print()
                elif missing_foundations and not has_cargo and interactive:
                    if not getattr(args, "_fnd_warn_done", False):
                        print(
                            yellow("cargo not found — cannot auto-install foundations.")
                        )
                        print(
                            dim(
                                "Install cargo (rustup) first, or install foundations manually."
                            )
                        )
                        args._fnd_warn_done = True

                step += 1

            elif step == 4:
                # Shell helpers
                if not cli_with_shell and interactive:
                    install_shell = ask_yn(
                        "Install the shell helper layer?",
                        default=install_shell,
                    )
                    print()

                if install_shell:
                    conflicts = scan_helper_conflicts()
                    if conflicts:
                        should_proceed = report_helper_conflicts(conflicts, interactive)
                        if not should_proceed:
                            install_shell = False
                step += 1

            elif step == 5:
                # Post-wizard setup
                for f in FOUNDATIONS:
                    if f.name not in installed_foundations:
                        path = f.is_installed()
                        installed_foundations[f.name] = {
                            "channel": "pre-existing" if path else "not-installed",
                            "path": path or "",
                        }
                break

        except GoBack:
            # Re-evaluate previous interactive steps to find the closest one
            if step == 4:
                # Going back from shell helpers
                if missing_foundations and has_cargo and interactive:
                    step = 3
                else:
                    step = 2
            elif step == 3:
                # Going back from foundations
                if cli_tools:
                    step = 0 if (advanced and interactive) else 0  # actually 0
                else:
                    step = 2
            elif step == 2:
                # Going back from runtimes
                if advanced and interactive:
                    step = 0
                else:
                    print(dim("  (Cannot go back further)"))
            elif step == 0:
                print(dim("  (Cannot go back further)"))

    # --- Confirm ---
    shared_home = Path(os.environ.get("VIBECRAFTED_HOME", Path.home() / ".vibecrafted"))
    store_path = shared_home / "skills"

    print(bold("Plan:"))
    print(f"  Skills:    {len(selected_skills)} -> {cyan(str(store_path))}")
    print(f"  Runtimes:  {', '.join(all_runtimes)} {dim('(skill views)')}")
    print(f"  Shell:     {'enabled' if install_shell else 'skipped'}")
    if dry_run:
        print(f"  Mode:      {yellow('DRY RUN')}")
    print()

    if interactive:
        if not ask_yn("Start install?", default=True):
            print("Install stopped. No changes were made.")
            return 0
        print()

    # --- Backup existing state ---
    print(bold("Saving current state..."))
    orphaned_entries = collect_orphaned_skills(
        store_path, all_runtimes, set(selected_skills)
    )
    backup_ts = create_backup(
        store_path,
        all_runtimes,
        selected_skills,
        orphaned_entries=orphaned_entries,
        dry_run=dry_run,
    )
    if backup_ts:
        print(f"  {OK} Backup saved: {_backup_root(store_path) / backup_ts}")
    else:
        print(f"  {dim('nothing to back up (fresh install)')}")
    print()

    # --- Execute: rsync skills ---
    print(bold("Installing shared skills..."))
    if not dry_run:
        store_path.mkdir(parents=True, exist_ok=True)

    skills_dir = repo_root / "skills" if (repo_root / "skills").is_dir() else repo_root
    for name in selected_skills:
        src = skills_dir / name
        dst = store_path / name
        print(f"  {dim('->')} {name}")
        rsync_skill(src, dst, dry_run=dry_run, mirror=mirror)
    print()

    # --- Execute: symlink views ---
    print(bold("Linking agent views..."))
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

    # --- Prune orphaned vc-* skills no longer in bundle ---
    prune_orphaned_skills(
        store_path,
        all_runtimes,
        set(selected_skills),
        dry_run=dry_run,
        orphaned_entries=orphaned_entries,
        interactive=interactive,
    )

    # --- Prune legacy vetcoders-* skills ---
    prune_legacy_skills(
        store_path, all_runtimes, dry_run=dry_run, interactive=interactive
    )

    # --- Execute: shell helpers ---
    if install_shell:
        print(bold("Installing shell helper..."))
        shell_script = (
            repo_root / "skills" / "vc-agents" / "scripts" / "install-shell.sh"
        )
        if shell_script.exists():
            cmd = ["bash", str(shell_script), "--source", str(repo_root)]
            if dry_run:
                cmd.append("--dry-run")
            subprocess.run(cmd, check=False)
        else:
            print(f"  {WARN} Shell installer not found: {shell_script}")
        print()

    # --- Execute: vibecrafted launcher ---
    _install_launcher(repo_root, dry_run)

    # --- Fix Gemini plan.directory if it points into .vibecrafted ---
    _configure_gemini_plans(dry_run)

    # --- Save state ---
    now = datetime.now(timezone.utc).isoformat()
    state = InstallState(
        installed_at=now,
        updated_at=now,
        framework_version=get_framework_version(repo_root),
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
    print(bold("Verification:"))
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

    # --- Done: compact one-screen summary ---
    _print_unicode_summary(repo_root, store_path, skills)
    return 0


def _install_launcher(repo_root: Path, dry_run: bool) -> None:
    """Install vibecrafted launcher to ~/.vibecrafted/bin/."""
    launcher_src = repo_root / "scripts" / "vibecrafted"
    launcher_bin_dir = (
        Path(os.environ.get("VIBECRAFTED_HOME", Path.home() / ".vibecrafted")) / "bin"
    )
    launcher_dst = launcher_bin_dir / "vibecrafted"
    if launcher_src.exists():
        if not dry_run:
            launcher_bin_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(launcher_src, launcher_dst)
            launcher_dst.chmod(0o755)
        # Ensure ~/.vibecrafted/bin is in PATH via shell rc files
        path_line = 'export PATH="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/bin:$PATH"'
        for rcname in (".bashrc", ".zshrc"):
            rcfile = Path.home() / rcname
            if rcfile.exists():
                content = rcfile.read_text()
                if (
                    "vibecrafted/bin" not in content
                    and ".vibecrafted/bin" not in content
                ):
                    if not dry_run:
                        with rcfile.open("a") as f:
                            f.write(f"\n# VibeCrafted launcher\n{path_line}\n")
        print()


def _print_unicode_summary(
    repo_root: Path, store_path: Path, skills: List[Path], out=None
) -> None:
    """Print the unicode summary box. If out is given, write there instead of stdout."""
    _out = out or sys.stdout
    fw_ver_display = get_framework_version(repo_root)
    skill_count = len(skills)
    agent_list = " \u00b7 ".join(
        a
        for a in ("claude", "codex", "gemini")
        if (store_path / "vc-agents" / "scripts" / f"{a}_spawn.sh").exists()
    )
    shell_list = []
    if (Path.home() / ".bashrc").exists():
        shell_list.append("bash")
    if (Path.home() / ".zshrc").exists():
        shell_list.append("zsh")
    shell_str = " + ".join(shell_list) if shell_list else "manual"
    fnd_ok = [f.name for f in FOUNDATIONS if f.is_installed()]
    fnd_str = " \u00b7 ".join(fnd_ok[:3]) if fnd_ok else "none"
    if len(fnd_ok) > 3:
        fnd_str += f" +{len(fnd_ok) - 3}"
    store_display = str(store_path).replace(str(Path.home()), "~")

    sep = brand_separator(37)

    lines = [
        f"\u2692 {VAPOR_HEADER} \u2692",
        "",
        brand_version_line(fw_ver_display),
        TAGLINE,
        PRODUCT_LINE,
        sep,
        "",
        f"\u2713 Skills       {skill_count} installed",
        f"\u2713 Agents       {agent_list}",
        f"\u2713 Helpers      {shell_str}",
        f"\u2713 Foundations   {fnd_str}",
        f"\u2713 Store        {store_display}",
        "",
        sep,
        "  Start        vibecrafted help",
        "  Verify       vibecrafted doctor",
        "  Reverse      vibecrafted uninstall",
        "",
        f"  {FOOTER_BRANDING}",
        f"  {FRAMEWORK_STAMP}",
    ]

    _out.write("\n")
    for line in lines:
        _out.write(f"  {line}\n")
    _out.write("\n")

    missing_fnd = [f for f in FOUNDATIONS if f.required and not f.is_installed()]
    if missing_fnd:
        _out.write("\n")
        _out.write("  Foundations still missing:\n")
        for f in missing_fnd:
            _out.write(f"    - {f.name}: {f.install_hint()}\n")
    _out.write("\n")
    _out.flush()


def _cmd_install_compact(args: argparse.Namespace, repo_root: Path) -> int:
    """Compact install — one screen of output, details to log."""
    dry_run = args.dry_run
    mirror = args.mirror
    cli_with_shell = args.with_shell
    fw_ver = get_framework_version(repo_root)

    shared_home = Path(os.environ.get("VIBECRAFTED_HOME", Path.home() / ".vibecrafted"))
    store_path = shared_home / "skills"
    log_path = shared_home / "install.log"

    # --- Discover skills (before redirecting stdout) ---
    skills = discover_skills(repo_root)
    if not skills:
        print(red("No skills found in repo."))
        return 1

    skill_names = [s.name for s in skills]
    selected_skills = list(skill_names)
    all_runtimes = list(SYMLINK_TARGETS)
    install_shell = cli_with_shell
    installed_foundations: Dict[str, Dict] = {}

    # --- System check (critical deps — must fail visibly) ---
    sys_deps = detect_system_deps()
    missing_critical = [
        cmd for cmd in ("python3", "git", "rsync") if not sys_deps.get(cmd)
    ]
    if missing_critical:
        print(red(f"  Missing critical dependencies: {', '.join(missing_critical)}"))
        print("  Install them before continuing.")
        return 1

    # --- All verbose output goes to log; compact lines go to real stdout ---
    with compact_logging(log_path, quiet=True) as out:
        # Log header
        print(f"VibeCrafted Installer v{fw_ver} — compact mode")
        print(f"Source: {repo_root}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print()

        # Log system deps
        print("System check:")
        for cmd, path in sys_deps.items():
            print(f"  {cmd}: {path or 'MISSING'}")
        print()

        # Log agent runtimes
        available_runtimes = detect_agent_runtimes()
        print("Agent runtimes:")
        for rt, path in available_runtimes.items():
            print(f"  {rt}: {path or 'not installed'}")
        print()

        # Log foundations
        print("Runtime Foundations:")
        for f in FOUNDATIONS:
            path = f.is_installed()
            installed_foundations[f.name] = {
                "channel": "pre-existing" if path else "not-installed",
                "path": path or "",
            }
            print(
                f"  {f.name}: {path or 'not installed'} {'(required)' if f.required else '(optional)'}"
            )
        print()

        # Backup
        print("Backup:")
        orphaned_entries = collect_orphaned_skills(
            store_path, all_runtimes, set(selected_skills)
        )
        backup_ts = create_backup(
            store_path,
            all_runtimes,
            selected_skills,
            orphaned_entries=orphaned_entries,
            dry_run=dry_run,
        )
        if backup_ts:
            print(f"  Saved: {_backup_root(store_path) / backup_ts}")
        else:
            print("  Fresh install, nothing to back up")
        print()

        # Install skills
        print("Installing skills:")
        if not dry_run:
            store_path.mkdir(parents=True, exist_ok=True)
        skills_dir = (
            repo_root / "skills" if (repo_root / "skills").is_dir() else repo_root
        )
        for name in selected_skills:
            src = skills_dir / name
            dst = store_path / name
            print(f"  -> {name}")
            rsync_skill(src, dst, dry_run=dry_run, mirror=mirror)
        print()

        # Compact status lines on real stdout
        _compact_line(
            out, green("\u2713"), "Skills", f"{len(selected_skills)} installed"
        )

        # Symlink views
        print("Linking agent views:")
        for rt in all_runtimes:
            rt_skills = Path.home() / f".{rt}" / "skills"
            if not dry_run:
                rt_skills.mkdir(parents=True, exist_ok=True)
            print(f"  {rt} -> {rt_skills}")
            for name in selected_skills:
                canonical = store_path / name
                link = rt_skills / name
                create_symlink(canonical, link, dry_run=dry_run)
        print()

        # Compact line: agents
        agent_names = [
            rt for rt in ("claude", "codex", "gemini") if available_runtimes.get(rt)
        ]
        _compact_line(
            out,
            green("\u2713"),
            "Agents",
            " \u00b7 ".join(agent_names) if agent_names else "none detected",
        )

        # Prune (logged only)
        prune_orphaned_skills(
            store_path,
            all_runtimes,
            set(selected_skills),
            dry_run=dry_run,
            orphaned_entries=orphaned_entries,
            interactive=False,
        )
        prune_legacy_skills(
            store_path, all_runtimes, dry_run=dry_run, interactive=False
        )

        # Shell helpers
        if install_shell:
            print("Installing shell helper:")
            shell_script = (
                repo_root / "skills" / "vc-agents" / "scripts" / "install-shell.sh"
            )
            if shell_script.exists():
                cmd = ["bash", str(shell_script), "--source", str(repo_root)]
                if dry_run:
                    cmd.append("--dry-run")
                result = subprocess.run(cmd, capture_output=True, text=True)
                # Log the shell installer output
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            else:
                print(f"  Shell installer not found: {shell_script}")
            print()

        shell_list = []
        if (Path.home() / ".bashrc").exists():
            shell_list.append("bash")
        if (Path.home() / ".zshrc").exists():
            shell_list.append("zsh")
        _compact_line(
            out,
            green("\u2713"),
            "Helpers",
            " + ".join(shell_list) if shell_list else "manual",
        )

        # Foundations compact line
        fnd_ok = [f.name for f in FOUNDATIONS if f.is_installed()]
        fnd_str = " \u00b7 ".join(fnd_ok[:3]) if fnd_ok else "none"
        if len(fnd_ok) > 3:
            fnd_str += f" +{len(fnd_ok) - 3}"
        _compact_line(out, green("\u2713"), "Foundations", fnd_str)

        # Store path
        store_display = str(store_path).replace(str(Path.home()), "~")
        _compact_line(out, green("\u2713"), "Store", store_display)

        # Launcher
        _install_launcher(repo_root, dry_run)

        # Fix Gemini plan.directory if it points into .vibecrafted
        _configure_gemini_plans(dry_run)

        # Save state
        now = datetime.now(timezone.utc).isoformat()
        state = InstallState(
            installed_at=now,
            updated_at=now,
            framework_version=fw_ver,
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
            print(f"Manifest saved: {store_path / STATE_FILE}")
        print()

        # Doctor (logged)
        if not dry_run:
            print("Verification:")
            findings = run_doctor(store_path, state)
            issues = [f for f in findings if f.level != "ok"]
            if issues:
                for f in issues:
                    print(f"  [{f.level}] {f.component}: {f.message}")
                # Surface critical issues on compact output too
                critical = [f for f in issues if f.level == "fail"]
                if critical:
                    out.write(f"\n  {red('Issues found')} — check {log_path}\n")
            else:
                print("  All checks passed")
        print()

    # --- Compact footer: header + commands (no repeated status lines) ---
    fw_ver_display = get_framework_version(repo_root)
    sep = brand_separator(37)
    log_display = str(log_path).replace(str(Path.home()), "~")
    missing_fnd = [f for f in FOUNDATIONS if f.required and not f.is_installed()]

    print()
    print(f"  \u2692 {VAPOR_HEADER} \u2692")
    print()
    print(f"  {brand_version_line(fw_ver_display)}")
    print(f"  {TAGLINE}")
    print(f"  {PRODUCT_LINE}")
    print(f"  {sep}")
    print("    Start        vibecrafted help")
    print("    Verify       vibecrafted doctor")
    print("    Reverse      vibecrafted uninstall")
    print(f"    Log          {log_display}")
    if missing_fnd:
        print()
        print("    Foundations  still missing")
        for f in missing_fnd:
            print(f"      - {f.name}: {f.install_hint()}")
    print()
    print(f"    {FOOTER_BRANDING}")
    print(f"    {FRAMEWORK_STAMP}")
    print()

    return 0


def cmd_install(args: argparse.Namespace) -> int:
    repo_root = Path(args.source).resolve()
    if not repo_root.is_dir():
        print(red(f"Error: repo root not found: {repo_root}"))
        return 1

    compact = getattr(args, "compact", False)

    if compact:
        return _cmd_install_compact(args, repo_root)
    else:
        return _cmd_install_verbose(args, repo_root)


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
    shared_home = Path(os.environ.get("VIBECRAFTED_HOME", Path.home() / ".vibecrafted"))
    store_path = shared_home / "skills"
    state = InstallState.load(store_path)
    has_manifest = bool(state.skills)

    if not state.skills:
        # No manifest — discover from disk, but only OUR skills
        bundle = set(_known_bundle_names())
        if store_path.exists():
            state.skills = [
                d.name
                for d in sorted(store_path.iterdir())
                if d.is_dir() and (d / "SKILL.md").exists() and d.name in bundle
            ]
        # Only check runtimes that actually have a skills dir
        state.runtimes = [
            rt for rt in SYMLINK_TARGET_CHOICES if runtime_skills_dir(rt).exists()
        ]

    findings = run_doctor(store_path, state)

    # Extra checks when no manifest: scan per-agent dirs for stale copies
    # but ONLY for skills in our bundle — don't claim ownership of other tools
    if not has_manifest:
        bundle = set(_known_bundle_names())
        findings.insert(
            0,
            DoctorFinding(
                "warn",
                "manifest",
                "No install manifest found — running in discovery mode. "
                "Install with the Smart Installer to get full tracking.",
            ),
        )
        for rt in state.runtimes:
            rt_skills = runtime_skills_dir(rt)
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
                    findings.append(
                        DoctorFinding(
                            "fail",
                            f"stale-copy:{rt}/{entry.name}",
                            "is a local COPY, not a symlink to shared store — drift risk",
                        )
                    )
                elif store_path.exists():
                    target = entry.resolve()
                    expected = (store_path / entry.name).resolve()
                    if target != expected and (store_path / entry.name).exists():
                        findings.append(
                            DoctorFinding(
                                "warn",
                                f"symlink:{rt}/{entry.name}",
                                f"points to {target}, expected {expected}",
                            )
                        )

    # Orphan detection: vc-* entries in store/runtime dirs not in current bundle
    bundle = set(_known_bundle_names())
    if bundle and store_path.exists():
        for entry in sorted(store_path.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if entry.name.startswith("vc-") and entry.name not in bundle:
                if (entry / "SKILL.md").exists():
                    findings.append(
                        DoctorFinding(
                            "warn",
                            f"orphan:store/{entry.name}",
                            "in store but no longer in bundle — run installer to clean up",
                        )
                    )
    if bundle:
        for rt in state.runtimes:
            rt_skills = runtime_skills_dir(rt)
            if not rt_skills.exists():
                continue
            for entry in sorted(rt_skills.iterdir()):
                if not entry.name.startswith("vc-"):
                    continue
                if entry.name in bundle or entry.name in state.skills:
                    continue
                if entry.is_symlink() or (
                    entry.is_dir() and (entry / "SKILL.md").exists()
                ):
                    findings.append(
                        DoctorFinding(
                            "warn",
                            f"orphan:{rt}/{entry.name}",
                            "symlink/dir for skill no longer in bundle",
                        )
                    )

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
        status = (
            green("installed")
            if path
            else (red("missing") if f.required else dim("optional"))
        )
        print(f"  {f.name}: {status} — {f.description}")
        print(f"    Channels: {', '.join(f.channels)}")
    print()

    return 0


# ---------------------------------------------------------------------------
# Subcommand: uninstall
# ---------------------------------------------------------------------------


def cmd_uninstall(args: argparse.Namespace) -> int:
    shared_home = Path(os.environ.get("VIBECRAFTED_HOME", Path.home() / ".vibecrafted"))
    store_path = shared_home / "skills"
    state = InstallState.load(store_path)
    dry_run = args.dry_run
    bundle = set(_known_bundle_names())

    # Use manifest if available, otherwise use bundle names
    skill_names = state.skills if state.skills else [n for n in bundle]
    runtimes = (
        state.runtimes
        if state.runtimes
        else [rt for rt in SYMLINK_TARGET_CHOICES if runtime_skills_dir(rt).exists()]
    )

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
        if not ask_yn("Remove the installed VibeCrafted bundle?", default=False):
            print("Uninstall cancelled.")
            return 0
        print()

    # Backup before removing
    print(bold("Saving current state..."))
    backup_ts = create_backup(store_path, runtimes, skill_names, dry_run=dry_run)
    if backup_ts:
        print(f"  {OK} Backup saved: {_backup_root(store_path) / backup_ts}")
        print(f"  {dim('Use `make restore` to undo this uninstall.')}")
    print()

    # Remove symlinks from per-runtime dirs
    print(bold("Removing agent views..."))
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
    print(bold("Removing shared skills..."))
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
    legacy_file = _helper_legacy_path()
    any_helper = helper_file.exists() or legacy_file.exists()
    if any_helper:
        print(bold("Removing shell helpers..."))
        for hf in (helper_file, legacy_file):
            if hf.exists():
                if dry_run:
                    print(f"  {dim('rm')} {hf}")
                else:
                    hf.unlink()
                    print(f"  {dim('-')} {hf}")

        # Remove source lines from both .zshrc and .bashrc
        source_lines = [_shell_source_line(), _old_zshrc_source_line()]
        for rcname in (".zshrc", ".bashrc"):
            rcfile = Path.home() / rcname
            if not rcfile.exists():
                continue
            content = rcfile.read_text()
            changed = False
            for sl in source_lines:
                if sl in content:
                    if not _is_writable(rcfile):
                        print(
                            f"  {WARN} {rcfile} is locked — cannot remove source line"
                        )
                        break
                    elif dry_run:
                        print(f"  {dim('remove source line from')} {rcfile}")
                    else:
                        content = content.replace(
                            f"\n# VetCoders shell helpers\n{sl}\n", "\n"
                        )
                        content = content.replace(sl, "")
                        changed = True
            if changed and not dry_run:
                rcfile.write_text(content)
                print(f"  {dim('-')} source line from {rcfile}")
        print()

    # Remove manifest
    state_file = store_path / STATE_FILE
    if state_file.exists():
        if dry_run:
            print(f"  {dim('rm')} {state_file}")
        else:
            state_file.unlink()

    print(green(bold("Removed.")))
    if backup_ts:
        print(dim(f"  Backup at: {_backup_root(store_path) / backup_ts}"))
        print(dim("  Run 'make restore' to undo."))
    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: restore
# ---------------------------------------------------------------------------


def cmd_restore(args: argparse.Namespace) -> int:
    shared_home = Path(os.environ.get("VIBECRAFTED_HOME", Path.home() / ".vibecrafted"))
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
            if not (entry.is_dir() or entry.is_symlink() or entry.is_file()):
                continue
            dst = store_path / entry.name
            if dry_run:
                print(f"  {dim('restore')} {entry.name}")
            else:
                _restore_path_from_backup(entry, dst)
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
            rt_skills = runtime_skills_dir(rt)
            for entry in sorted(rt_dir.iterdir()):
                if not (entry.is_dir() or entry.is_symlink() or entry.is_file()):
                    continue
                dst = rt_skills / entry.name
                if dry_run:
                    print(f"  {dim('restore')} {rt}/{entry.name}")
                else:
                    _restore_path_from_backup(entry, dst)
                    print(f"  {OK} {rt}/{entry.name}")
                restored += 1
        print()

    # Restore helpers
    helper_backup = backup_dir / "helpers"
    if helper_backup.is_dir():
        print(bold("Restoring helpers..."))
        # Helper file
        # Try new name first, then legacy
        backed_helper = helper_backup / "vc-skills.sh"
        if not backed_helper.exists():
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

        # RC files
        for rcname in (".zshrc", ".bashrc"):
            backed_rc = helper_backup / rcname
            if backed_rc.exists():
                dst = Path.home() / rcname
                if dry_run:
                    print(f"  {dim('restore')} {rcname}")
                else:
                    shutil.copy2(backed_rc, dst)
                    print(f"  {OK} {rcname}")
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
        description="VibeCrafted installer — the founders' framework for shipping software with AI agents.",
    )
    sub = parser.add_subparsers(dest="command")

    # install
    p_install = sub.add_parser(
        "install", help="Install the VibeCrafted framework bundle"
    )
    p_install.add_argument(
        "--source", default=default_source, help="Repo root (default: auto-detect)"
    )
    p_install.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be done"
    )
    p_install.add_argument(
        "--non-interactive", action="store_true", help="Skip all prompts, use defaults"
    )
    p_install.add_argument(
        "--advanced", action="store_true", help="Open the selective install wizard"
    )
    p_install.add_argument(
        "--with-shell", action="store_true", help="Install the shell helper layer"
    )
    p_install.add_argument(
        "--tool",
        dest="tools",
        action="append",
        choices=SYMLINK_TARGET_CHOICES,
        help="Limit symlink views to these runtimes (repeatable, default: all)",
    )
    p_install.add_argument(
        "--skill",
        dest="skill_filter",
        action="append",
        help="Install only these skills (repeatable, default: full bundle)",
    )
    p_install.add_argument(
        "--mirror",
        action="store_true",
        help="Delete extra files in installed skill dirs (rsync --delete)",
    )
    p_install.add_argument(
        "--compact",
        action="store_true",
        help="Compact output — one screen, details to log",
    )

    # doctor
    sub.add_parser("doctor", help="Verify installation health")

    # list
    p_list = sub.add_parser(
        "list",
        help="Show available VibeCrafted skills and the runtime substrate beneath them",
    )
    p_list.add_argument(
        "--source", default=default_source, help="Repo root (default: auto-detect)"
    )

    # uninstall
    p_uninstall = sub.add_parser(
        "uninstall", help="Remove VibeCrafted skills, views, and helpers"
    )
    p_uninstall.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be done"
    )

    # restore
    p_restore = sub.add_parser("restore", help="Restore pre-install state from backup")
    p_restore.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be done"
    )

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
