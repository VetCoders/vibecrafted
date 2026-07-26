#!/usr/bin/env python3
"""𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Smart Installer v2 — manifest-driven, multi-channel, interactive.

Subcommands:
    install         Install the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. skill bundle
    doctor          Verify installation health
    list            Show available 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. skills and the runtime substrate beneath them
    uninstall       Remove 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. skills, views, launchers, and helpers
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
import fcntl
import importlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    _distribution_manifest = importlib.import_module("distribution_manifest")
    _installer_brand = importlib.import_module("installer_brand")
    _runtime_paths = importlib.import_module("runtime_paths")
except ModuleNotFoundError:  # pragma: no cover - import path depends on entrypoint
    _distribution_manifest = importlib.import_module("scripts.distribution_manifest")
    _installer_brand = importlib.import_module("scripts.installer_brand")
    _runtime_paths = importlib.import_module("scripts.runtime_paths")

FOOTER_BRANDING = _installer_brand.FOOTER_BRANDING
FRAMEWORK_STAMP = _installer_brand.FRAMEWORK_STAMP
PRODUCT_LINE = _installer_brand.PRODUCT_LINE
TAGLINE = _installer_brand.TAGLINE
VAPOR_HEADER = _installer_brand.VAPOR_HEADER
brand_separator = _installer_brand.separator
brand_version_line = _installer_brand.version_line
read_version_file = _runtime_paths.read_version_file
vibecrafted_backups_home = _runtime_paths.vibecrafted_backups_home
vibecrafted_launcher_bin = _runtime_paths.vibecrafted_launcher_bin
vibecrafted_runtime_home = _runtime_paths.vibecrafted_runtime_home
vibecrafted_runtime_bin = _runtime_paths.vibecrafted_runtime_bin
vibecrafted_tools_home = _runtime_paths.vibecrafted_tools_home
vibecrafted_home = _runtime_paths.vibecrafted_home
xdg_data_home = _runtime_paths.xdg_data_home
xdg_config_home = _runtime_paths.xdg_config_home
stage_distribution_payload = _distribution_manifest.stage_payload
distribution_path_is_forbidden = _distribution_manifest.path_is_forbidden
DistributionManifestError = _distribution_manifest.ManifestError

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


# Glyph language (docs/CLI_PRODUCT_SPEC.md §3.1): the glyph is the prefix —
# bracket tags ([ok], [missing], …) are retired everywhere.
OK = green("✓")
MISS = red("✗")
WARN = yellow("!")
OPT = dim("·")
SKIP = dim("·")

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def err_line(what_failed: str, fix: str = "", log: str = "") -> None:
    """Error shape (CLI_PRODUCT_SPEC §3.4): what failed · one fix · log path.

    Always stderr — the compact installer redirects stdout into the log."""
    print(f"{red('✗')} {what_failed}", file=sys.stderr)
    if fix:
        print(f"  {dim('→ fix:')} {fix}", file=sys.stderr)
    if log:
        print(f"  {dim('log: ' + log)}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Compact-mode output: TeeLogger + helpers
# ---------------------------------------------------------------------------


class TeeLogger:
    """Captures print output to a log file while optionally suppressing stdout."""

    def __init__(self, log_path: Path, quiet: bool = False):
        # Long-lived tee: open for the logger lifetime; closed in close().
        self.log = log_path.open("w", encoding="utf-8")
        self.quiet = quiet
        self._real_stdout = sys.__stdout__ if sys.__stdout__ is not None else sys.stdout

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
    """Render one compact status update on stdout."""
    line = f"  {icon} {label:13s} {value}"
    if _compact_status_is_live(out):
        out.write(f"\r\033[K{line}")
        out.flush()
        return
    out.write(f"{line}\n")


def _compact_status_is_live(out) -> bool:
    isatty = getattr(out, "isatty", None)
    return bool(callable(isatty) and isatty())


def _clear_compact_status(out) -> None:
    """Erase the live compact status row before printing a stable block."""
    if _compact_status_is_live(out):
        out.write("\r\033[K")
        out.flush()


def _compact_checkpoint(
    out,
    step: int,
    title: str,
    details: Sequence[str] = (),
) -> None:
    """Print a stable compact checkpoint: step, title, bounded detail lines."""
    _clear_compact_status(out)
    out.write(f"\n  [{step}/4] {bold(title)}\n")
    for detail in details:
        out.write(f"      {detail}\n")
    out.flush()


# ---------------------------------------------------------------------------
# Component manifest
# ---------------------------------------------------------------------------

SKILL_CATEGORIES: dict[str, dict[str, Any]] = {
    "pipeline": {
        "label": "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Pipeline",
        "description": "Core workflow skills: init, workflow, followup, marbles, dou, hydrate, release",
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
    channels: list[str]
    packages: dict[str, str]
    verify_cmd: str
    required: bool = True  # False = optional

    def is_installed(self) -> str | None:
        """Return path if installed, None otherwise."""
        if self.name == "vc-frame":
            for candidate in ("vc-frame",):
                found = shutil.which(candidate)
                if found:
                    return found
        found = shutil.which(self.name)
        if found:
            return found
        local_bin = Path.home() / ".local" / "bin" / self.name
        if local_bin.is_file() and os.access(local_bin, os.X_OK):
            return str(local_bin)
        return None

    def install_hint(self) -> str:
        hints = []
        for ch in self.channels:
            pkg = self.packages.get(ch, self.name)
            if ch == "canonical":
                hints.append(f"Use canonical installer: {pkg}")
            elif ch == "crates":
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


VENDORED_FOUNDATION_BINARIES = {
    "aicx": "aicx",
    "aicx-mcp": "aicx-mcp",
    "loct": "loct",
    "loctree-mcp": "loctree-mcp",
    "vc-frame": "vc-frame",
}


def detect_vendor_platform() -> str | None:
    try:
        uname = os.uname()
    except AttributeError:
        return None

    os_name = {"Darwin": "darwin", "Linux": "linux"}.get(
        uname.sysname, uname.sysname.lower()
    )
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64"}.get(
        uname.machine, uname.machine
    )
    return f"{os_name}-{arch}"


def vendored_foundation_dir(repo_root: Path) -> Path | None:
    platform = detect_vendor_platform()
    if not platform:
        return None
    return repo_root / "bin" / "vendor" / platform


def install_foundation_from_bundle(
    foundation: Foundation,
    repo_root: Path,
    bin_dir: Path | None = None,
    dry_run: bool = False,
) -> Path | None:
    vendor_name = VENDORED_FOUNDATION_BINARIES.get(foundation.name)
    if not vendor_name:
        return None

    vendor_dir = vendored_foundation_dir(repo_root)
    if vendor_dir is None:
        return None

    src = vendor_dir / vendor_name
    if not src.is_file():
        return None

    target_dir = bin_dir or (Path.home() / ".local" / "bin")
    dst = target_dir / vendor_name
    if dry_run:
        return dst

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(0o755)

    result = subprocess.run(
        [str(dst), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        print(f"  {WARN} {vendor_name} copied but version check failed{suffix}")
    return dst


def install_or_find_foundation(
    foundation: Foundation, repo_root: Path, dry_run: bool = False
) -> tuple[str, str]:
    bundled = install_foundation_from_bundle(foundation, repo_root, dry_run=dry_run)
    if bundled:
        return str(bundled), "bundled"

    found = foundation.is_installed()
    if found:
        return found, "pre-existing"
    return "", "not-installed"


FOUNDATIONS: list[Foundation] = [
    Foundation(
        name="aicx",
        description="AICX CLI for session history and memory recovery",
        channels=["canonical"],
        packages={
            "canonical": "curl -fsSL https://loct.io/install.sh | sh",
        },
        verify_cmd="aicx --version",
    ),
    Foundation(
        name="aicx-mcp",
        description="AICX MCP server for session history and memory recovery",
        channels=["canonical"],
        packages={
            "canonical": "curl -fsSL https://loct.io/install.sh | sh",
        },
        verify_cmd="aicx-mcp --version",
    ),
    Foundation(
        name="loct",
        description="Loctree operator CLI short command",
        channels=["canonical"],
        packages={
            "canonical": "curl -fsSL https://loct.io/install.sh | sh",
        },
        verify_cmd="loct --version",
    ),
    Foundation(
        name="loctree",
        description="Loctree structural code mapping CLI",
        channels=["canonical"],
        packages={
            "canonical": "curl -fsSL https://loct.io/install.sh | sh",
        },
        verify_cmd="loctree --version",
    ),
    Foundation(
        name="loctree-mcp",
        description="Structural code mapping MCP server",
        channels=["canonical"],
        packages={
            "canonical": "curl -fsSL https://loct.io/install.sh | sh",
        },
        verify_cmd="loctree-mcp --version",
    ),
    Foundation(
        name="prview",
        description="PR review artifact generator",
        channels=["crates", "github"],
        packages={
            "crates": "prview",
            "github": "https://github.com/vetcoders/prview/releases",
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
            "source": "https://github.com/vetcoders/Screenscribe/releases",
        },
        verify_cmd="screenscribe --version",
        required=False,
    ),
    Foundation(
        name="semgrep",
        description="Static analysis and security scanning — quality gate in agent workflows",
        channels=["brew", "pip", "github"],
        packages={
            "brew": "semgrep",
            "pip": "semgrep",
            "github": "https://github.com/semgrep/semgrep/releases",
        },
        verify_cmd="semgrep --version",
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
        name="vc-frame",
        description="VC Frame multi-agent terminal workspace surface",
        channels=["canonical"],
        packages={
            "canonical": "curl -fsSL https://vibecrafted.io/install.sh | bash",
        },
        verify_cmd="vc-frame --version",
        required=True,
    ),
]

RUNTIME_COMMANDS = {
    "wezterm": "wezterm",
    "vc-apprt": "vc_",
    "locterm": None,
    "microsandbox": "msb",
}


def runtime_status_path() -> Path:
    return vibecrafted_home() / "runtime" / "runtime.json"


def read_runtime_status() -> dict:
    status_file = runtime_status_path()
    if not status_file.is_file():
        return {}
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "runtime": "unknown",
            "status": "failed",
            "message": f"cannot read runtime status: {status_file}",
        }
    return data if isinstance(data, dict) else {}


def doctor_runtime_finding() -> DoctorFinding:
    status = read_runtime_status()
    runtime = str(status.get("runtime") or "none")
    if runtime == "none":
        return DoctorFinding("ok", "runtime:none", "no runtime horse selected")

    component = f"runtime:{runtime}"
    state = str(status.get("status") or "unknown")
    message = str(status.get("message") or "")
    path_value = str(status.get("path") or "")

    if state != "ok":
        return DoctorFinding(
            "fail",
            component,
            message or f"runtime installer reported status={state}",
        )

    if path_value and Path(path_value).exists():
        return DoctorFinding("ok", component, f"-> {path_value}")

    command = RUNTIME_COMMANDS.get(runtime)
    if command:
        found = shutil.which(command)
        if found:
            return DoctorFinding("ok", component, f"-> {found}")

    if path_value:
        return DoctorFinding(
            "warn",
            component,
            f"recorded path is missing: {path_value}; {message}".strip(),
        )
    return DoctorFinding("warn", component, message or "runtime status lacks path")


RUNTIME_DEPS = ["python3", "git"]
RECOMMENDED_DEPS = ["rsync"]
OPTIONAL_DEPS = [
    "zsh"
]  # helpers work in bash and zsh; core install works without either

OLD_SKILL_PREFIX = "vetcoders-"
OLD_HELPER_NAME = "vetcoders-skills.zsh"
SKILL_ROOT_RULE_FILES = ("VERIFICATION_RULE.md", "LIVING_TREE_RULE.md")
LOCALIZED_SKILL_RULE_DIRS = ("pl",)


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


AGENT_RUNTIMES = ["codex", "claude", "agy", "junie", "grok"]
SYMLINK_TARGETS = ["agents"]
# gemini kept in CHOICES only for legacy .gemini data dir compat (no active runtime)
SYMLINK_TARGET_CHOICES = [
    *SYMLINK_TARGETS,
    "claude",
    "codex",
    "gemini",
    "agy",
    "junie",
    "grok",
]
SHADOWED_SKILL_VIEW_RUNTIMES = ("claude", "codex")
# Claude Code and Codex CLIs read only their own ~/.claude/skills and
# ~/.codex/skills — the canonical .agents view is invisible to them, so the
# standard install must keep their views or the /vc-* deck goes dark.
STANDARD_VIEW_RUNTIMES = [*SYMLINK_TARGETS, *SHADOWED_SKILL_VIEW_RUNTIMES]

# ---------------------------------------------------------------------------
# Install state
# ---------------------------------------------------------------------------

STATE_FILE = ".vc-install.json"
START_HERE_FILE = "START_HERE.md"


@dataclass
class InstallState:
    """Persisted installation state."""

    version: str = "2.0"
    framework_version: str = ""
    installed_at: str = ""
    updated_at: str = ""
    repo_commit: str = ""
    repo_url: str = ""
    skills: list[str] = field(default_factory=list)
    runtimes: list[str] = field(default_factory=list)
    launcher_entries: list[str] = field(default_factory=list)
    helper_files: list[str] = field(default_factory=list)
    foundations: dict[str, dict] = field(default_factory=dict)
    product_tools: dict[str, dict[str, str]] = field(default_factory=dict)
    layout_transfers: list[dict[str, str]] = field(default_factory=list)
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


def start_here_path() -> Path:
    return vibecrafted_home() / START_HERE_FILE


def _doctor_totals(findings: Sequence[DoctorFinding]) -> tuple[int, int, int]:
    oks = sum(1 for finding in findings if finding.level == "ok")
    warns = sum(1 for finding in findings if finding.level == "warn")
    fails = sum(1 for finding in findings if finding.level == "fail")
    return oks, warns, fails


def _doctor_action_items(findings: Sequence[DoctorFinding]) -> list[str]:
    """One bounded, copy-pasteable fix per issue class (CLI_PRODUCT_SPEC §3.4)."""
    issues = [finding for finding in findings if finding.level != "ok"]
    if not issues:
        return ["start here: `vibecrafted init claude`"]

    actions: list[str] = []
    if any(finding.component.startswith("foundation:") for finding in issues):
        # Foundation findings are now warn-level (externally managed), so key off
        # the component, not the level — the repair guidance must still surface.
        actions.append(
            "repair Loctree/AICX from their own release surface, then "
            "`bash scripts/install-foundations.sh --check`"
        )
    if any(
        finding.component.startswith(("runtime:", "symlink:", "stale-copy:"))
        for finding in issues
    ):
        actions.append("rebuild skill views: `vibecrafted update`")
    if any(
        finding.component in ("launcher-wrappers", "launcher-runtime")
        for finding in issues
    ):
        actions.append("repair launchers: `vibecrafted doctor --fix-launchers`")
    if any(finding.component.startswith("commands:") for finding in issues):
        actions.append("restore agent slash commands: `vibecrafted update`")
    if any(
        finding.component.startswith("shell-helper")
        or finding.component == "shell-helpers"
        for finding in issues
    ):
        actions.append("restore `vc-*` shortcuts: re-run `make install`")
    if any(finding.component == "manifest" for finding in issues):
        actions.append("enable tracking and restore: run the installer once")
    if any(finding.component.startswith("orphan:") for finding in issues):
        actions.append("clean bundle leftovers: re-run the installer")
    if not actions:
        actions.append("review the warnings above, then re-run `vibecrafted doctor`")
    return actions


def write_start_here_guide(
    store_path: Path, state: InstallState, findings: Sequence[DoctorFinding]
) -> Path:
    guide_path = start_here_path()
    guide_path.parent.mkdir(parents=True, exist_ok=True)

    ok_count, warn_count, fail_count = _doctor_totals(findings)
    if fail_count:
        health_line = f"Needs attention ({ok_count} ok, {warn_count} warnings, {fail_count} failures)"
    elif warn_count:
        health_line = f"Ready with warnings ({ok_count} ok, {warn_count} warnings, {fail_count} failures)"
    else:
        health_line = f"Ready to work ({ok_count} ok, {warn_count} warnings, {fail_count} failures)"

    runtime_views = ", ".join(state.runtimes) if state.runtimes else "none detected"
    helper_file = _helper_target_path()
    helper_line = (
        f"installed at {helper_file}"
        if helper_file.exists()
        else "not installed; `vibecrafted ...` still works, `vc-*` shortcuts stay optional"
    )
    present_foundations = [
        foundation.name for foundation in FOUNDATIONS if foundation.is_installed()
    ]
    missing_required = [
        foundation.name
        for foundation in FOUNDATIONS
        if foundation.required and not foundation.is_installed()
    ]
    action_items = _doctor_action_items(findings)
    framework_version = state.framework_version or "unknown"
    store_display = str(store_path)

    lines = [
        "# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Start Here",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Framework version: {framework_version}",
        f"Health: {health_line}",
        "",
        "## Current state",
        f"- Store: {store_display}",
        f"- Skills in shared store: {len(state.skills)}",
        f"- Runtime views: {runtime_views}",
        f"- Shell helpers: {helper_line}",
        "- Foundations present: "
        + (", ".join(present_foundations) if present_foundations else "none detected"),
        "- Foundations still missing: "
        + (", ".join(missing_required) if missing_required else "none required"),
        "",
        "## Simplest path",
        "1. `vibecrafted init claude`",
        '2. `vibecrafted workflow claude --prompt "Plan and implement <task>"`',
        '3. `vibecrafted implement codex --prompt "Ship <task>"`',
        "",
        "## Ship-ready path",
        '1. `vibecrafted dou claude --prompt "Audit launch readiness"`',
        '2. `vibecrafted decorate codex --prompt "Polish the release surface"`',
        '3. `vibecrafted hydrate codex --prompt "Package the product"`',
        '4. `vibecrafted release codex --prompt "Prepare release steps"`',
        "",
        "## Optional operator surface",
        "- `vibecrafted dashboard`",
        "- Dashboard is optional. You can ignore it and stay in plain terminal commands.",
        "",
        "## What to fix next",
    ]

    for action in action_items:
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "## Safety valves",
            "- `vibecrafted doctor`",
            "- `vibecrafted help`",
            "- `vibecrafted uninstall`",
            "",
        ]
    )

    guide_path.write_text("\n".join(lines), encoding="utf-8")
    return guide_path


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def detect_system_deps() -> dict[str, str | None]:
    """Check which system dependencies are available."""
    result = {}
    for cmd in RUNTIME_DEPS:
        result[cmd] = shutil.which(cmd)
    for cmd in RECOMMENDED_DEPS:
        result[cmd] = shutil.which(cmd)
    for cmd in OPTIONAL_DEPS:
        result[cmd] = shutil.which(cmd)
    return result


def detect_agent_runtimes() -> dict[str, str | None]:
    """Check which agent CLIs are available."""
    result = {}
    for rt in AGENT_RUNTIMES:
        result[rt] = shutil.which(rt)
    return result


def runtime_skills_dir(runtime: str) -> Path:
    return Path.home() / f".{runtime}" / "skills"


def runtime_commands_dir(runtime: str) -> Path:
    return Path.home() / f".{runtime}" / "commands"


def detect_osascript() -> str | None:
    return shutil.which("osascript")


def detect_cargo() -> str | None:
    return shutil.which("cargo")


def source_skills_root(repo_root: Path) -> Path:
    skills_dir = repo_root / "skills"
    if skills_dir.is_dir():
        return skills_dir

    packaged_skills_dir = repo_root / "vibecrafted-core" / "vibecrafted_core" / "skills"
    if packaged_skills_dir.is_dir():
        return packaged_skills_dir

    return repo_root


def get_framework_version(repo_root: Path) -> str:
    """Base semver from VERSION (no local git slug)."""
    return read_version_file(repo_root)


def get_repo_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def get_install_version(repo_root: Path) -> str:
    """Version shown and stamped by ``make install``: ``X.Y.Z+gSHORTSHA``.

    Source VERSION stays plain semver for version-bump; install always appends
    the commit slug so installed runtimes are attributable.
    """
    base = get_framework_version(repo_root).strip()
    if not base or base == "unknown":
        return base or "unknown"
    # Drop a prior local version segment if re-installing from a stamped tree.
    base = base.split("+", 1)[0].strip()
    sha = get_repo_commit(repo_root)
    if not sha or sha == "unknown":
        return base
    return f"{base}+g{sha}"


_INSTALL_VERSION_TARGETS = (
    Path("VERSION"),
    Path("vibecrafted-core/vibecrafted_core/VERSION"),
    Path("vibecrafted-mcp/vibecrafted_mcp/VERSION"),
    Path("vibecrafted-core/pyproject.toml"),
    Path("vibecrafted-mcp/pyproject.toml"),
)


def stamp_install_version(root: Path, version: str) -> list[Path]:
    """Write ``version`` (with +gSHA) into every VERSION / [project] version under root.

    Returns the list of files actually updated. Missing paths are skipped so a
    partial distribution payload still stamps what it has.
    """
    import re

    project_version_re = re.compile(
        r'^(?P<prefix>\s*version\s*=\s*")(?P<version>[^"]+)(?P<suffix>".*)$'
    )
    stamped: list[Path] = []
    for relative in _INSTALL_VERSION_TARGETS:
        path = root / relative
        if not path.is_file():
            continue
        if path.name == "VERSION":
            path.write_text(version + "\n", encoding="utf-8")
            stamped.append(path)
            continue
        if path.name == "pyproject.toml":
            text = path.read_text(encoding="utf-8")
            in_project = False
            lines: list[str] = []
            replaced = False
            for line in text.splitlines(keepends=True):
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_project = stripped == "[project]"
                if in_project and not replaced:
                    body = line.rstrip("\r\n")
                    newline = line[len(body) :]
                    match = project_version_re.match(body)
                    if match:
                        line = (
                            f"{match.group('prefix')}{version}"
                            f"{match.group('suffix')}{newline}"
                        )
                        replaced = True
                lines.append(line)
            if replaced:
                path.write_text("".join(lines), encoding="utf-8")
                stamped.append(path)
    return stamped


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


def discover_skills(repo_root: Path) -> list[Path]:
    """Find all default 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. skill directories."""
    skills: list[Path] = []
    skills_dir = source_skills_root(repo_root)
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


def iter_skill_root_rule_files(skills_root: Path) -> list[tuple[Path, Path]]:
    rule_files: list[tuple[Path, Path]] = []

    for filename in SKILL_ROOT_RULE_FILES:
        source = skills_root / filename
        if source.is_file():
            rule_files.append((source, Path(filename)))

    for localized_dir in LOCALIZED_SKILL_RULE_DIRS:
        localized_root = skills_root / localized_dir
        if not localized_root.is_dir():
            continue
        for filename in SKILL_ROOT_RULE_FILES:
            source = localized_root / filename
            if source.is_file():
                rule_files.append((source, Path(localized_dir) / filename))

    return rule_files


def sync_skill_root_rules(
    skills_root: Path, store_path: Path, dry_run: bool = False
) -> list[Path]:
    """Copy rule files that skill directories link to via ../RULE.md."""
    copied: list[Path] = []
    for source, relative_target in iter_skill_root_rule_files(skills_root):
        target = store_path / relative_target
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            # When the skill store is a symlink back to the source checkout
            # (portable CI wires vibecrafted-current -> vibecrafted-main),
            # source and target resolve to the same inode; copy2 would raise
            # shutil.SameFileError and the copy is a no-op, so skip it.
            if not (target.exists() and source.resolve() == target.resolve()):
                shutil.copy2(source, target)
        copied.append(relative_target)
    return copied


def categorize_skill(name: str) -> str:
    """Return category key for a skill name."""
    if name.startswith("vc-"):
        return "pipeline"
    return "specialist"


def categorize_all(skills: list[Path]) -> dict[str, list[str]]:
    cats: dict[str, list[str]] = {"pipeline": [], "foundations": [], "specialist": []}
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


def ask_choice(prompt: str, options: list[str], default: int = 0) -> int:
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


def ask_multi(prompt: str, options: list[str], defaults: list[bool]) -> list[bool]:
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

BACKUP_DIR = "backups/installer"


def _backup_root(store_path: Path) -> Path:
    _ = store_path
    return vibecrafted_backups_home()


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


@dataclass(frozen=True)
class ManagedPath:
    kind: str
    path: Path
    action: str = "remove"
    reason: str = ""


RESTORE_MANIFEST_FILE = "restore-manifest.json"
RESTORE_SCRIPT_FILE = "restore.py"

_SELF_CONTAINED_RESTORE_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def restore_path(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        remove_path(destination)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    elif source.is_file():
        shutil.copy2(source, destination)


backup_dir = Path(__file__).resolve().parent
manifest = json.loads((backup_dir / "restore-manifest.json").read_text(encoding="utf-8"))
restored = 0
for item in manifest["items"]:
    source = backup_dir / item["backup"]
    destination = Path(item["path"])
    if source.exists() or source.is_symlink():
        restore_path(source, destination)
        restored += 1
print(f"Restored {restored} managed paths from {backup_dir}")
"""


def _path_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _teardown_backup_records(inventory: Sequence[ManagedPath]) -> list[ManagedPath]:
    candidates = [
        record
        for record in inventory
        if record.action in {"remove", "edit"} and _path_present(record.path)
    ]
    selected: list[ManagedPath] = []
    selected_roots: list[Path] = []
    for record in sorted(candidates, key=lambda item: len(item.path.parts)):
        if record.path.is_symlink():
            selected.append(record)
            continue
        resolved = record.path.resolve(strict=False)
        if any(resolved == root or root in resolved.parents for root in selected_roots):
            continue
        selected.append(record)
        selected_roots.append(resolved)
    return selected


def create_teardown_backup(
    inventory: Sequence[ManagedPath], *, dry_run: bool = False
) -> str | None:
    records = _teardown_backup_records(inventory)
    if not records:
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    if dry_run:
        return timestamp

    backup_root = vibecrafted_backups_home()
    backup_dir = backup_root / timestamp
    items_dir = backup_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=False)
    manifest_items: list[dict[str, str]] = []
    for index, record in enumerate(records):
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", record.path.name) or "root"
        relative_backup = Path("items") / f"{index:04d}-{safe_name}"
        _copy_path_to_backup(record.path, backup_dir / relative_backup)
        manifest_items.append(
            {
                "kind": record.kind,
                "path": str(record.path),
                "backup": str(relative_backup),
            }
        )

    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": manifest_items,
    }
    (backup_dir / RESTORE_MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    restore_script = backup_dir / RESTORE_SCRIPT_FILE
    restore_script.write_text(_SELF_CONTAINED_RESTORE_SCRIPT, encoding="utf-8")
    restore_script.chmod(0o755)
    backup_root.mkdir(parents=True, exist_ok=True)
    (backup_root / "latest").write_text(timestamp + "\n", encoding="utf-8")
    return timestamp


def _restore_command(backup_timestamp: str) -> str:
    script = vibecrafted_backups_home() / backup_timestamp / RESTORE_SCRIPT_FILE
    return f"python3 {shlex_quote(str(script))}"


def shlex_quote(value: str) -> str:
    """Shell-quote one path without adding a runtime dependency."""
    if not value:
        return "''"
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def collect_orphaned_skills(
    store_path: Path, runtimes: list[str], current_bundle: set[str]
) -> list[tuple[str, Path]]:
    """Return vc-* entries that no longer exist in the current bundle."""
    orphans: list[tuple[str, Path]] = []

    if store_path.exists():
        for entry in sorted(store_path.iterdir()):
            if entry.name.startswith(".") or entry.name in current_bundle:
                continue
            if not entry.name.startswith("vc-"):
                continue
            if entry.is_symlink() or entry.is_dir() and (entry / "SKILL.md").exists():
                orphans.append(("store", entry))

    for rt in runtimes:
        rt_skills = runtime_skills_dir(rt)
        if not rt_skills.exists():
            continue
        for entry in sorted(rt_skills.iterdir()):
            if not entry.name.startswith("vc-") or entry.name in current_bundle:
                continue
            if entry.is_symlink() or entry.is_dir() and (entry / "SKILL.md").exists():
                orphans.append((rt, entry))

    return orphans


def create_backup(
    store_path: Path,
    runtimes: list[str],
    bundle_names: list[str],
    orphaned_entries: list[tuple[str, Path]] | None = None,
    launcher_entries: list[str] | None = None,
    helper_entries: list[str] | None = None,
    dry_run: bool = False,
) -> str | None:
    """Snapshot existing state before install. Returns backup timestamp or None."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
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

    # Back up per-runtime entries exactly as they exist (dirs or symlinks)
    for rt in runtimes:
        rt_skills = runtime_skills_dir(rt)
        if not rt_skills.exists():
            continue
        for name in bundle_names:
            entry = rt_skills / name
            if entry.exists() or entry.is_symlink():
                dst = backup_dir / "runtimes" / rt / name
                if dry_run:
                    print(f"  {dim('backup')} {entry} -> {dst}")
                else:
                    _copy_path_to_backup(entry, dst)
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

    # Back up helper files from either provided manifest or current helper files.
    if helper_entries is None:
        helper_paths = [
            p for p in (_helper_target_path(), _helper_legacy_path()) if p.exists()
        ]
    else:
        helper_paths = []
        for raw_helper in helper_entries:
            candidate = Path(raw_helper)
            if candidate.exists():
                helper_paths.append(candidate)

    for helper_file in helper_paths:
        dst = backup_dir / "helpers" / helper_file.name
        if dry_run:
            print(f"  {dim('backup')} {helper_file} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(helper_file, dst)
        anything_backed = True

    # Back up launchers/wrappers from either provided manifest or current surface.
    if launcher_entries is None:
        launcher_items = collect_installed_launchers()
    else:
        launcher_items = _parse_manifest_launchers(launcher_entries)

    for launcher_bin_dir, entry in launcher_items:
        dst = (
            backup_dir / "launchers" / _launcher_dir_key(launcher_bin_dir) / entry.name
        )
        if dry_run:
            print(f"  {dim('backup')} {entry} -> {dst}")
        else:
            _copy_path_to_backup(entry, dst)
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
    config_dir = xdg_config_home() / "vetcoders"
    return config_dir / "vc-skills.sh"


def _helper_legacy_path() -> Path:
    config_dir = xdg_config_home() / "zsh"
    return config_dir / "vc-skills.zsh"


def _shell_source_line() -> str:
    """Source line works in both bash and zsh."""
    return '[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"'


def _old_zshrc_source_line() -> str:
    return '[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh"'


def _helper_surface_label(*, zsh_available: bool | None = None) -> str:
    helper_file = _helper_target_path()
    legacy_file = _helper_legacy_path()
    if zsh_available is None:
        zsh_available = shutil.which("zsh") is not None

    if helper_file.exists():
        return "bash + zsh" if zsh_available else "bash only"
    if legacy_file.exists():
        return "compat zsh"
    return "not installed"


def _launcher_path_line() -> str:
    return 'case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac'


def _legacy_launcher_path_lines() -> list[str]:
    return ['export PATH="$HOME/.local/bin:$PATH"']


def _doctor_repair_rc_content(
    content: str, *, ensure_helper: bool, ensure_path: bool
) -> str:
    repaired, _removed = _clean_legacy_rc_entries(content)
    for line, comment in _uninstall_rc_entries():
        repaired, _ = _strip_rc_entry(repaired, line, comment)
    blocks: list[tuple[str, str]] = []
    if ensure_helper:
        blocks.append(("𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell helpers", _shell_source_line()))
    if ensure_path:
        blocks.append(("𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher", _launcher_path_line()))

    if not blocks:
        return repaired

    repaired = repaired.rstrip("\n")
    block_text = "\n\n".join(f"# {comment}\n{line}" for comment, line in blocks)
    if repaired:
        repaired = f"{repaired}\n\n{block_text}\n"
    else:
        repaired = f"{block_text}\n"
    return repaired


def _doctor_fix_rc_files() -> list[DoctorFinding]:
    findings: list[DoctorFinding] = []
    ensure_helper = _helper_target_path().exists() or _helper_legacy_path().exists()
    ensure_path = _find_launcher_wrapper("vibecrafted") is not None

    for rcname in (".zshrc", ".bashrc"):
        rcfile = Path.home() / rcname
        if not rcfile.exists():
            continue
        try:
            content = rcfile.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                DoctorFinding("warn", f"rc-fix:{rcname}", f"could not read: {exc}")
            )
            continue
        if not _is_writable(rcfile):
            findings.append(
                DoctorFinding(
                    "warn",
                    f"rc-fix:{rcname}",
                    f"{rcfile} is locked — cannot repair launcher/source hints",
                )
            )
            continue

        repaired = _doctor_repair_rc_content(
            content, ensure_helper=ensure_helper, ensure_path=ensure_path
        )
        if repaired == content:
            findings.append(DoctorFinding("ok", f"rc-fix:{rcname}", "already default"))
            continue

        rcfile.write_text(repaired, encoding="utf-8")
        findings.append(
            DoctorFinding(
                "ok",
                f"rc-fix:{rcname}",
                "repaired compat rc entries and restored default launcher/helper hints",
            )
        )

    if not findings:
        findings.append(
            DoctorFinding(
                "ok",
                "rc-fix",
                "no existing shell rc files found — nothing to repair",
            )
        )
    return findings


_LEGACY_BOOTSTRAP_ROOT = Path("/opt/vibecrafted")
_LEGACY_ROOT_EXPORT_MARK = (
    "# vibecrafted doctor --fix-legacy-bootstrap: retired legacy root"
)
_LEGACY_ROOT_UNSET_MARK = (
    "# vibecrafted doctor --fix-legacy-bootstrap: retire container-image legacy root"
)
_LEGACY_ROOT_UNSET_BLOCK = (
    f"\n{_LEGACY_ROOT_UNSET_MARK}\n"
    f'if [ "${{VIBECRAFTED_ROOT:-}}" = "{_LEGACY_BOOTSTRAP_ROOT}" ]; then\n'
    "  unset VIBECRAFTED_ROOT\n"
    "fi\n"
)


def _doctor_fix_legacy_bootstrap() -> list[DoctorFinding]:
    """Neutralize the retired /opt/vibecrafted bootstrap layout.

    Comments out ``export VIBECRAFTED_ROOT=...`` lines that pin the legacy
    bootstrap root in shell rc files (backing the file up first) and reports
    the leftover tree. When the environment itself carries the legacy root
    (container images bake it via ENV), appends an idempotent unset guard to
    ``.zshrc``/``.bashrc`` so fresh shells shed it. The tree itself is never
    deleted — removal stays an explicit operator action.
    """
    findings: list[DoctorFinding] = []
    legacy_token = str(_LEGACY_BOOTSTRAP_ROOT)

    for rcname in (".zshrc", ".zshenv", ".bashrc", ".profile"):
        rcfile = Path.home() / rcname
        if not rcfile.exists():
            continue
        try:
            content = rcfile.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                DoctorFinding(
                    "warn", f"legacy-bootstrap:{rcname}", f"could not read: {exc}"
                )
            )
            continue
        lines = content.splitlines(keepends=True)
        changed = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Only neutralize actual export statements. The unset guard this
            # same fix appends also mentions the legacy token — commenting its
            # `if` line would orphan the closing `fi` and break the rc file.
            if (
                "export" in stripped
                and "VIBECRAFTED_ROOT" in stripped
                and legacy_token in stripped
            ):
                lines[index] = f"{_LEGACY_ROOT_EXPORT_MARK}\n# {line.lstrip()}"
                changed = True
        if not changed:
            findings.append(
                DoctorFinding(
                    "ok", f"legacy-bootstrap:{rcname}", "no legacy root export"
                )
            )
            continue
        if not _is_writable(rcfile):
            findings.append(
                DoctorFinding(
                    "warn",
                    f"legacy-bootstrap:{rcname}",
                    f"{rcfile} is locked — cannot comment out the legacy export",
                )
            )
            continue
        backup = rcfile.with_name(rcfile.name + ".vibecrafted-legacy-bak")
        try:
            backup.write_text(content, encoding="utf-8")
            rcfile.write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            findings.append(
                DoctorFinding(
                    "warn", f"legacy-bootstrap:{rcname}", f"could not repair: {exc}"
                )
            )
            continue
        findings.append(
            DoctorFinding(
                "ok",
                f"legacy-bootstrap:{rcname}",
                f"commented out legacy VIBECRAFTED_ROOT export (backup: {backup.name})",
            )
        )

    if os.environ.get("VIBECRAFTED_ROOT", "").startswith(legacy_token):
        # .zshenv is read by EVERY zsh invocation (interactive or not); .zshrc
        # alone would leave non-interactive shells (make, docker exec) with the
        # image-baked legacy root.
        for rcname in (".zshenv", ".zshrc", ".bashrc"):
            rcfile = Path.home() / rcname
            try:
                existing = rcfile.read_text(encoding="utf-8") if rcfile.exists() else ""
                if _LEGACY_ROOT_UNSET_MARK in existing:
                    findings.append(
                        DoctorFinding(
                            "ok",
                            f"legacy-bootstrap:guard:{rcname}",
                            "unset guard already present",
                        )
                    )
                    continue
                with rcfile.open("a", encoding="utf-8") as handle:
                    handle.write(_LEGACY_ROOT_UNSET_BLOCK)
                findings.append(
                    DoctorFinding(
                        "ok",
                        f"legacy-bootstrap:guard:{rcname}",
                        "appended unset guard for the image-baked legacy root",
                    )
                )
            except OSError as exc:
                findings.append(
                    DoctorFinding(
                        "warn",
                        f"legacy-bootstrap:guard:{rcname}",
                        f"could not append unset guard: {exc}",
                    )
                )
        findings.append(
            DoctorFinding(
                "warn",
                "legacy-bootstrap:env",
                "VIBECRAFTED_ROOT still points at the legacy root in this shell — "
                "fresh shells now shed it via the rc guard; run "
                "`unset VIBECRAFTED_ROOT` to clear the current one",
            )
        )

    if _LEGACY_BOOTSTRAP_ROOT.is_dir():
        findings.append(
            DoctorFinding(
                "warn",
                "legacy-bootstrap:tree",
                f"legacy bootstrap tree left in place at {_LEGACY_BOOTSTRAP_ROOT} — "
                "archive or remove it manually once the canonical install is verified",
            )
        )
    else:
        findings.append(
            DoctorFinding("ok", "legacy-bootstrap:tree", "no legacy bootstrap tree")
        )
    return findings


def _doctor_launcher_source_root(store_path: Path) -> Path | None:
    current_link = vibecrafted_tools_home() / "vibecrafted-current"
    candidates: list[Path] = [Path(__file__).resolve().parent.parent]

    if current_link.exists():
        try:
            candidates.append(current_link.resolve())
        except OSError:
            pass

    for candidate in candidates:
        launcher = candidate / "scripts" / "vibecrafted"
        version = candidate / "VERSION"
        skills_dir = candidate / "skills"
        if launcher.is_file() and version.is_file() and skills_dir.is_dir():
            return candidate
    return None


def _doctor_fix_launchers(store_path: Path, state: InstallState) -> list[DoctorFinding]:
    source_root = _doctor_launcher_source_root(store_path)
    if source_root is None:
        return [
            DoctorFinding(
                "warn",
                "doctor-fix-launchers",
                "could not locate a default source root with scripts/vibecrafted",
            )
        ]

    try:
        _install_launcher(source_root, dry_run=False, update_rc=False)
        state.launcher_entries = _snapshot_launcher_entries()
        state.save(store_path)
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - surface repair failures
        return [
            DoctorFinding(
                "warn",
                "doctor-fix-launchers",
                f"launcher repair failed: {exc}",
            )
        ]

    return [
        DoctorFinding(
            "ok",
            "doctor-fix-launchers",
            f"refreshed launcher commands from {source_root}",
        )
    ]


def _run_smoke_command(
    command: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    expected_text: str | None = None,
) -> tuple[bool, str]:
    """Run a small runtime smoke command and capture a concise result."""
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, check=False
        )
    except OSError as exc:
        return False, str(exc)

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    detail = stdout or stderr or f"exit {result.returncode}"

    if result.returncode != 0:
        return False, detail

    if expected_text and expected_text not in stdout:
        return False, f"missing expected text: {expected_text}"

    return True, detail


def _clean_legacy_rc_entries(content: str) -> tuple[str, int]:
    import re

    lines = content.splitlines()
    kept = []
    skip_until = None
    removed = 0

    for cl in lines:
        stripped = cl.strip()

        # 1. Block cleanup
        if skip_until:
            removed += 1
            if skip_until in stripped:
                skip_until = None
            continue

        if stripped.startswith(
            ("# >>> VibeCraft", "# <<< VibeCraft", "# >>> 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝", "# <<< 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝")
        ):
            removed += 1
            skip_until = "VibeCraft" if "VibeCraft" in stripped else "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝"
            continue

        # 2. Known source lines
        if stripped.startswith("[[ -r ") and (
            "vc-skills" in stripped or "vetcoders" in stripped
        ):
            removed += 1
            continue
        if stripped.startswith("source ") and (
            "vc-skills" in stripped or "vetcoders" in stripped
        ):
            removed += 1
            continue

        # 3. Known exports
        if stripped.startswith(
            (
                "export VIBECRAFTED_ROOT",
                "export VIBECRAFT_ROOT",
                "export VIBECRAFTED_HOME",
                "export LOCTREE_NUDGE",
            )
        ):
            removed += 1
            continue
        if stripped.startswith("export PATH=") and (
            "vibecraft" in stripped.lower() and "/bin" in stripped.lower()
        ):
            removed += 1
            continue

        # 4. Known comments
        if stripped.startswith("#"):
            lower_comment = stripped.lower()
            if (
                any(
                    x in lower_comment
                    for x in [
                        "vetcoders shell helpers",
                        "vibecraft shell helpers",
                        "vibecrafted shell helpers",
                        "vibecraft launcher",
                        "vibecrafted launcher",
                        "vibecrafted. helper shim",
                        "vibecrafted. launcher",
                        "vibecrafted. shell helpers",
                    ]
                )
                or "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝" in stripped
            ):
                removed += 1
                continue

        kept.append(cl)

    joined = "\n".join(kept)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    if content.endswith("\n") and not joined.endswith("\n"):
        joined += "\n"
    if not joined:
        joined = ""

    # If the text changed, adjust removed count safely
    if joined != content and removed == 0:
        removed = 1

    return joined, removed


def _strip_rc_entry(
    content: str, line: str, comment: str | None = None
) -> tuple[str, int]:
    raw_lines = content.splitlines()
    kept: list[str] = []
    removed = 0
    idx = 0

    while idx < len(raw_lines):
        current = raw_lines[idx]
        stripped = current.strip()
        if comment and stripped == f"# {comment}":
            next_idx = idx + 1
            # allow empty lines in between comment and line
            while next_idx < len(raw_lines) and not raw_lines[next_idx].strip():
                next_idx += 1
            if next_idx < len(raw_lines) and raw_lines[next_idx].strip() == line:
                removed += next_idx - idx + 1
                idx = next_idx + 1
                continue
        if stripped == line:
            removed += 1
            idx += 1
            continue
        kept.append(current)
        idx += 1

    rebuilt = "\n".join(kept)
    if content.endswith("\n"):
        rebuilt += "\n"
    return rebuilt, removed


def _installer_managed_launcher_names() -> list[str]:
    return [
        "vibecrafted",
        "vibecraft",
        *LAUNCHER_WRAPPERS,
        *PYTHON_ENTRYPOINT_LAUNCHERS,
        *LEGACY_LAUNCHER_NAMES,
    ]


def _snapshot_helper_file(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_symlink():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return HELPER_SHIM_MARKER in text


def _snapshot_legacy_helper_link(path: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        target = Path(os.readlink(path))
    except OSError:
        return False
    if not target.is_absolute():
        target = path.parent / target
    return target == _helper_target_path()


def _snapshot_helper_files() -> list[str]:
    helper_files: list[str] = []
    helper_file = _helper_target_path()
    legacy_file = _helper_legacy_path()

    if _snapshot_helper_file(helper_file) or helper_file.exists():
        helper_files.append(str(helper_file))

    if (
        _snapshot_legacy_helper_link(legacy_file)
        or legacy_file.exists()
        and _snapshot_helper_file(legacy_file)
    ):
        helper_files.append(str(legacy_file))

    return helper_files


def _snapshot_launcher_entries() -> list[str]:
    launcher_entries: list[str] = []
    seen: set[tuple[str, str]] = set()
    for launcher_bin_dir in _launcher_bin_dirs():
        for name in _installer_managed_launcher_names():
            entry = launcher_bin_dir / name
            if not (entry.exists() or entry.is_symlink()):
                continue
            if _is_framework_managed_launcher(entry):
                key = _launcher_dir_key(launcher_bin_dir)
                if (key, name) not in seen:
                    launcher_entries.append(f"{key}/{name}")
                    seen.add((key, name))
    return launcher_entries


def snapshot_product_tool_state() -> dict[str, dict[str, str]]:
    """Record product dependency commands exactly where PATH resolves them.

    Loctree/AICX/vc-frame/etc. are foundation payload when the bundle vendors
    them for this platform. Missing bundle payloads remain external dependencies,
    so discovery still observes PATH and persists the fallback result.
    """
    product_tools: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for foundation in FOUNDATIONS:
        if foundation.name in seen:
            continue
        seen.add(foundation.name)
        found = foundation.is_installed()
        if found:
            product_tools[foundation.name] = {
                "path": found,
                "managed_by": "external-path",
                "required": str(bool(foundation.required)).lower(),
            }
        else:
            product_tools[foundation.name] = {
                "path": "",
                "managed_by": "missing",
                "required": str(bool(foundation.required)).lower(),
            }
    return product_tools


def _parse_manifest_launchers(
    raw_entries: Sequence[str],
) -> list[tuple[Path, Path]]:
    launcher_entries: list[tuple[Path, Path]] = []
    seen: set[tuple[str, str]] = set()

    for raw_entry in raw_entries:
        if "/" not in raw_entry:
            continue
        launcher_dir_key, name = raw_entry.split("/", 1)
        if not name or "/" in name:
            continue
        launcher_bin_dir = _launcher_dir_from_key(launcher_dir_key)
        if launcher_bin_dir is None:
            continue
        entry = launcher_bin_dir / name
        marker = (str(launcher_bin_dir), name)
        if marker in seen:
            continue
        seen.add(marker)
        launcher_entries.append((launcher_bin_dir, entry))

    return launcher_entries


def _rc_has_vibecrafted_bin_path(content: str) -> bool:
    return (
        ".local/bin" in content
        or "vibecrafted/bin" in content
        or ".vibecrafted/bin" in content
    )


HELPER_SHIM_MARKER = "# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. helper shim. Generated by install-shell.sh."

SKILL_WRAPPER_NAMES = [
    "decorate",
    "delegate",
    "dou",
    "followup",
    "hydrate",
    "implement",
    "intents",
    "justdo",
    "marbles",
    "ownership",
    "partner",
    "polarize",
    "prune",
    "release",
    "research",
    "review",
    "scaffold",
    "workflow",
]

LAUNCHER_WRAPPERS = [
    "vc-help",
    "vc-init",
    "vc-start",
    "vc-dashboard",
    "vc-cron",
    "vc-loop",
    "vc-paste",
    "vc-ship",
    "vc-dispatch",
    "vc-resume",
    "vc-agents",
    "telemetry",
    *[f"vc-{name}" for name in SKILL_WRAPPER_NAMES],
]

PYTHON_ENTRYPOINT_LAUNCHERS = [
    "vc-agents",
    "vc-audit",
    "vc-cron",
    "vc-decorate",
    "vc-delegate",
    "vc-dou",
    "vc-followup",
    "vc-hydrate",
    "vc-implement",
    "vc-intents",
    "vc-loop",
    "vc-marbles",
    "vc-ownership",
    "vc-partner",
    "vc-paste",
    "vc-polarize",
    "vc-prune",
    "vc-release",
    "vc-research",
    "vc-research-await",
    "vc-research-synthesize",
    "vc-review",
    "vc-sandbox",
    "vc-scaffold",
    "vc-ship",
    "vc-workflow",
    "vibecrafted",
    "vibecrafted-compact-hook",
    "vibecrafted-mcp",
    "vibecrafted-resume",
]

LEGACY_LAUNCHER_NAMES = [
    "marble-pack",
    "aicx-pack",
]

FRAMEWORK_LAUNCHER_MARKERS = (
    "vibecrafted",
    ".vibecrafted",
    "vc-agents",
    "vetcoders",
    "scripts/vibecraft",
)


def _launcher_bin_dirs() -> list[Path]:
    return [vibecrafted_launcher_bin()]


def _find_launcher_wrapper(name: str) -> Path | None:
    for launcher_bin_dir in _launcher_bin_dirs():
        candidate = launcher_bin_dir / name
        if candidate.exists() or candidate.is_symlink():
            return candidate
    return None


def _uninstall_rc_entries() -> list[tuple[str, str]]:
    entries = [
        (_shell_source_line(), "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell helpers"),
        (_shell_source_line(), "Vetcoders shell helpers"),
        (_old_zshrc_source_line(), "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell helpers"),
        (_old_zshrc_source_line(), "Vetcoders shell helpers"),
        (_launcher_path_line(), "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher"),
    ]
    entries.extend(
        (legacy_line, "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher")
        for legacy_line in _legacy_launcher_path_lines()
    )
    return entries


def _rc_has_framework_install_hints(rcfile: Path) -> bool:
    if not rcfile.exists():
        return False
    try:
        content = rcfile.read_text()
    except OSError:
        return False
    for line, comment in _uninstall_rc_entries():
        if line in content or (comment and f"# {comment}" in content):
            return True
    return False


def _launcher_dir_key(launcher_bin_dir: Path) -> str:
    if launcher_bin_dir == Path.home() / ".local" / "bin":
        return "local-bin"
    if launcher_bin_dir == vibecrafted_launcher_bin():
        return "local-bin"
    return (
        re.sub(r"[^a-z0-9]+", "-", str(launcher_bin_dir).lower()).strip("-")
        or "launcher-bin"
    )


def _launcher_dir_from_key(key: str) -> Path | None:
    mapping = {
        "local-bin": vibecrafted_launcher_bin(),
    }
    return mapping.get(key)


def _launcher_file_contains_framework_markers(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        payload = path.read_text(encoding="utf-8", errors="ignore")[:8192].lower()
    except OSError:
        return False
    return any(marker in payload for marker in FRAMEWORK_LAUNCHER_MARKERS)


def _is_framework_managed_launcher(entry: Path) -> bool:
    name = entry.name.lower()
    explicit_names = {
        "vibecrafted",
        "vibecraft",
        *[wrapper.lower() for wrapper in LAUNCHER_WRAPPERS],
        *[wrapper.lower() for wrapper in PYTHON_ENTRYPOINT_LAUNCHERS],
        *[legacy.lower() for legacy in LEGACY_LAUNCHER_NAMES],
    }
    if name in explicit_names:
        return True

    if entry.is_symlink():
        try:
            target_name = Path(os.readlink(entry)).name.lower()
        except OSError:
            target_name = ""
        if target_name in {"vibecrafted", "vibecraft"}:
            return True
        try:
            resolved = entry.resolve(strict=False)
        except OSError:
            resolved = None
        if resolved is not None:
            if resolved.name.lower() in {"vibecrafted", "vibecraft"}:
                return True
            if _launcher_file_contains_framework_markers(resolved):
                return True

    hinted_name = name.startswith(("vc-", "vibecraft")) or name.endswith("-pack")
    return bool(hinted_name and _launcher_file_contains_framework_markers(entry))


def _is_replaceable_framework_launcher(entry: Path) -> bool:
    if not (entry.exists() or entry.is_symlink()):
        return True
    if entry.is_symlink():
        try:
            target = Path(os.readlink(entry))
        except OSError:
            target = Path("")
        if target.name.lower() in {"vibecrafted", "vibecraft"}:
            return True
        try:
            resolved = entry.resolve(strict=False)
        except OSError:
            resolved = None
        if resolved is not None and _launcher_file_contains_framework_markers(resolved):
            return True
    return _launcher_file_contains_framework_markers(entry)


def collect_installed_launchers() -> list[tuple[Path, Path]]:
    launchers: list[tuple[Path, Path]] = []
    for launcher_bin_dir in _launcher_bin_dirs():
        if not launcher_bin_dir.exists():
            continue
        for entry in sorted(launcher_bin_dir.iterdir()):
            if not (entry.is_symlink() or entry.is_file()):
                continue
            if _is_framework_managed_launcher(entry):
                launchers.append((launcher_bin_dir, entry))
    return launchers


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
    "agy-implement",
    "agy-plan",
    "agy-review",
    "agy-research",
    "agy-prompt",
    "agy-observe",
    "agy-implement",
    "agy-plan",
    "agy-review",
    "agy-research",
    "agy-prompt",
    "agy-observe",
    "junie-implement",
    "junie-plan",
    "junie-review",
    "junie-research",
    "junie-prompt",
    "junie-observe",
    "skills-sync",
    "agy-keychain-set",
    "agy-keychain-get",
    "agy-keychain-clear",
]


@dataclass
class HelperConflict:
    file: Path
    function: str
    line_num: int


def scan_helper_conflicts() -> dict[Path, list[HelperConflict]]:
    """Scan shell config files for existing helper function definitions."""
    default = _helper_target_path()
    conflicts: dict[Path, list[HelperConflict]] = {}

    search_dirs = []
    config_base = xdg_config_home()
    for subdir in ("vetcoders", "zsh"):
        candidate = config_base / subdir
        if candidate.is_dir():
            search_dirs.append(candidate)

    files_to_scan: list[Path] = []
    for d in search_dirs:
        files_to_scan.extend(d.glob("*.sh"))
        files_to_scan.extend(d.glob("*.zsh"))
    for rcfile in (".zshrc", ".bashrc"):
        rc = Path.home() / rcfile
        if rc.exists():
            files_to_scan.append(rc)

    for fpath in files_to_scan:
        if fpath.resolve() == default.resolve():
            continue  # Skip our own file
        try:
            lines = fpath.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for fn in KNOWN_HELPER_FUNCTIONS:
                # Match function definitions: "func_name()" or "func_name ()"
                if stripped.startswith((f"{fn}()", f"{fn} ()")):
                    if fpath not in conflicts:
                        conflicts[fpath] = []
                    conflicts[fpath].append(
                        HelperConflict(file=fpath, function=fn, line_num=i)
                    )

    return conflicts


def report_helper_conflicts(
    conflicts: dict[Path, list[HelperConflict]], interactive: bool
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
            "  These files already contain non-𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. content — installer will NOT edit them."
        )
    )

    if not interactive:
        print(
            yellow(
                "  Non-interactive mode: installing the default helper file alongside."
            )
        )
        print(yellow("  Clean up duplicates in the files above manually."))
        return True

    choice = ask_choice(
        "  How should we handle it?",
        [
            "Skip helper install and keep the current setup",
            "Install the default helper file alongside and clean up duplicates later",
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


_RSYNC_EXCLUDES = {".DS_Store", ".backup", ".loctree"}


def _copytree_skill(src: Path, dst: Path, mirror: bool = False) -> None:
    """Pure-Python fallback when rsync is not available."""
    if mirror and dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in _RSYNC_EXCLUDES:
            continue
        target = dst / item.name
        if item.is_dir():
            _copytree_skill(item, target, mirror=False)
        else:
            shutil.copy2(str(item), str(target))


def rsync_skill(
    src: Path, dst: Path, dry_run: bool = False, mirror: bool = False
) -> None:
    """Sync a single skill directory. Uses rsync when available, shutil otherwise."""
    if dry_run:
        return
    # A symlinked store (portable CI wires vibecrafted-current -> the source
    # checkout) makes src and dst the same directory. rsync would churn, and the
    # shutil fallback would copy a file onto itself (or rmtree the source under
    # --mirror); skip the self-sync entirely.
    if dst.exists() and src.resolve() == dst.resolve():
        return
    dst.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync"):
        cmd = [
            "rsync",
            "-az",
            "--exclude",
            ".DS_Store",
            "--exclude",
            ".backup",
            "--exclude",
            ".loctree",
        ]
        if mirror:
            cmd.append("--delete")
        cmd += [str(src) + "/", str(dst) + "/"]
        # Capture rsync stderr — do NOT discard it. When this sync fails the
        # operator needs the real reason (exit 23 "could not make way", exit
        # 11/12 "No space left on device", a dangling symlink, a permission
        # error), not an opaque "could not refresh staged tools".
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    else:
        _copytree_skill(src, dst, mirror=mirror)


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


_TOOLS_HANDOFF_SCHEMA = "vibecrafted.tools-handoff.v1"
_TOOLS_INSTALL_LEASE_ENV = "VIBECRAFTED_INSTALL_LEASE_FD"
_TOOLS_INSTALL_LEASE_TIMEOUT_ENV = "VIBECRAFTED_INSTALL_LOCK_TIMEOUT"
_TOOLS_INSTALL_LEASE_DEFAULT_SECONDS = 180.0
_TOOLS_GENERATIONS_TO_KEEP = 3


def _tools_handoff_path(current_link: Path) -> Path:
    return current_link.parent / ".vibecrafted-current-handoff.json"


def _tools_install_lease_path(current_link: Path) -> Path:
    return current_link.parent / ".vibecrafted-install.lock"


def _tools_handoff_file(shared_home: Path) -> Path:
    return _tools_handoff_path(_current_tools_link(shared_home))


def _tools_install_timeout(timeout_seconds: float | None) -> float:
    if timeout_seconds is None:
        raw = os.environ.get(
            _TOOLS_INSTALL_LEASE_TIMEOUT_ENV,
            str(_TOOLS_INSTALL_LEASE_DEFAULT_SECONDS),
        )
        try:
            timeout_seconds = float(raw)
        except ValueError as exc:
            raise ValueError(
                f"{_TOOLS_INSTALL_LEASE_TIMEOUT_ENV} must be a finite "
                f"non-negative number, got {raw!r}"
            ) from exc
    if not math.isfinite(timeout_seconds) or timeout_seconds < 0:
        raise ValueError(
            "tools install lease timeout must be a finite non-negative number"
        )
    return timeout_seconds


def _validate_tools_lease_descriptor(descriptor: int, lock_path: Path) -> None:
    try:
        opened = os.fstat(descriptor)
        named = os.stat(lock_path, follow_symlinks=False)
    except OSError as exc:
        raise OSError(
            f"inherited tools install lease is unavailable at {lock_path}"
        ) from exc
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_uid != os.geteuid()
        or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise OSError(
            f"inherited tools install lease does not own the regular file {lock_path}"
        )


def _tools_lease_owner(descriptor: int) -> str:
    try:
        raw = os.pread(descriptor, 4096, 0).decode("utf-8", errors="replace").strip()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return "owner metadata unavailable"
    if not isinstance(payload, dict):
        return "owner metadata unavailable"
    pid = payload.get("pid", "unknown")
    operation = payload.get("operation", "unknown")
    started_at = payload.get("started_at", "unknown")
    return f"pid={pid}, operation={operation}, started_at={started_at}"


def _write_tools_lease_owner(descriptor: int, operation: str) -> None:
    encoded = (
        json.dumps(
            {
                "pid": os.getpid(),
                "operation": operation,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    os.ftruncate(descriptor, 0)
    os.lseek(descriptor, 0, os.SEEK_SET)
    view = memoryview(encoded)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("could not persist tools install lease owner")
        view = view[written:]
    os.fsync(descriptor)


@contextmanager
def _tools_install_lease(
    current_link: Path,
    *,
    timeout_seconds: float | None = None,
    operation: str = "runtime-publish",
) -> Iterator[int]:
    """Serialize runtime publication and Python-tool/service reconciliation."""
    lock_path = _tools_install_lease_path(current_link)
    inherited_raw = os.environ.get(_TOOLS_INSTALL_LEASE_ENV)
    if inherited_raw:
        try:
            inherited = int(inherited_raw)
        except ValueError as exc:
            raise OSError(
                f"invalid inherited tools install lease descriptor: {inherited_raw!r}"
            ) from exc
        _validate_tools_lease_descriptor(inherited, lock_path)
        try:
            fcntl.flock(inherited, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OSError(
                "inherited tools install lease descriptor does not own the lock"
            ) from exc
        yield inherited
        return

    timeout = _tools_install_timeout(timeout_seconds)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        lock_path,
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    acquired = False
    try:
        _validate_tools_lease_descriptor(descriptor, lock_path)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    owner = _tools_lease_owner(descriptor)
                    raise TimeoutError(
                        "another Vibecrafted installer still owns "
                        f"{lock_path} ({owner}); waited {timeout:.2f}s"
                    )
                time.sleep(min(0.1, remaining))
        _write_tools_lease_owner(descriptor, operation)
        yield descriptor
    finally:
        if acquired:
            try:
                os.ftruncate(descriptor, 0)
                os.fsync(descriptor)
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def run_with_tools_install_lease(
    shared_home: Path,
    argv: Sequence[str],
) -> int:
    """Run ``argv`` while retaining the install lease across all child work."""
    if not argv:
        raise ValueError("tools install lease requires a command")
    current_link = _current_tools_link(shared_home)
    try:
        with _tools_install_lease(
            current_link,
            operation="publish-uv-service-reconcile",
        ) as descriptor:
            os.set_inheritable(descriptor, True)
            environment = os.environ.copy()
            environment[_TOOLS_INSTALL_LEASE_ENV] = str(descriptor)
            result = subprocess.run(
                list(argv),
                check=False,
                close_fds=False,
                env=environment,
            )
            return result.returncode
    except TimeoutError as exc:
        print(f"[install-tools] FATAL: {exc}", file=sys.stderr)
        return 75
    except ValueError as exc:
        print(
            f"[install-tools] FATAL: invalid installer lease policy: {exc}",
            file=sys.stderr,
        )
        return 64
    except OSError as exc:
        print(
            f"[install-tools] FATAL: could not hold installer lease: {exc}",
            file=sys.stderr,
        )
        return 126


def _symlink_target(path: Path) -> Path | None:
    if not path.is_symlink():
        return None
    raw_target = Path(os.readlink(path))
    if not raw_target.is_absolute():
        raw_target = path.parent / raw_target
    return raw_target.resolve(strict=False)


def _atomic_symlink(target: Path, link: Path) -> None:
    """Publish ``link`` in one rename without ever removing its old target."""
    canonical_target = target.resolve(strict=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() and not link.is_symlink():
        raise OSError(
            f"cannot atomically publish over non-symlink runtime root: {link}"
        )
    temporary = link.parent / (f".{link.name}.tmp-{os.getpid()}-{os.urandom(6).hex()}")
    relative_target = os.path.relpath(canonical_target, link.parent)
    try:
        temporary.symlink_to(relative_target, target_is_directory=True)
        os.replace(temporary, link)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def _atomic_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (f".{path.name}.tmp-{os.getpid()}-{os.urandom(6).hex()}")
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            view = memoryview(encoded.encode("utf-8"))
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def _read_tools_handoff_path(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != _TOOLS_HANDOFF_SCHEMA
        or payload.get("state") not in {"prepared", "rolled-back", "complete"}
        or not isinstance(payload.get("old_target"), str)
        or not isinstance(payload.get("new_target"), str)
    ):
        return None
    return payload


def _read_tools_handoff(shared_home: Path) -> dict[str, Any] | None:
    return _read_tools_handoff_path(_tools_handoff_file(shared_home))


def sync_control_plane_tree(
    src: Path,
    dst: Path,
    dry_run: bool = False,
    mirror: bool = False,
    *,
    install_version: str | None = None,
) -> Path:
    """Publish a complete immutable runtime generation through a symlink swap.

    ``dst`` is the stable ``vibecrafted-current`` pointer, never a mutable
    generation directory.  Staging, validation, and version stamping all happen
    before the sole publication operation (``os.replace`` on the symlink).
    """
    if dry_run:
        return dst
    with _tools_install_lease(dst, operation=f"runtime-publish:{src}"):
        return _sync_control_plane_tree_locked(
            src,
            dst,
            mirror=mirror,
            install_version=install_version,
        )


def _sync_control_plane_tree_locked(
    src: Path,
    dst: Path,
    *,
    mirror: bool,
    install_version: str | None,
) -> Path:
    _ = mirror  # staged runtime is always an exact distribution payload
    if dst.exists() and not dst.is_symlink():
        raise OSError(
            f"refusing non-atomic in-place runtime upgrade at {dst}; "
            "vibecrafted-current must be a symlink pointer"
        )

    token = f"{os.getpid()}-{os.urandom(6).hex()}"
    version_slug = (
        re.sub(
            r"[^A-Za-z0-9._+-]+",
            "-",
            (install_version or "local").strip(),
        ).strip("-")
        or "local"
    )
    staging = dst.parent / f".{dst.name}.staging-{token}"
    generation = dst.parent / f"vibecrafted-generation-{version_slug}-{token}"
    old_candidate = _symlink_target(dst)
    pending = _read_tools_handoff_path(_tools_handoff_path(dst))
    if (
        pending is not None
        and pending["state"] == "prepared"
        and old_candidate == Path(pending["new_target"]).resolve(strict=False)
    ):
        pending_old = pending["old_target"]
        old_target = (
            Path(pending_old).resolve(strict=False)
            if pending_old and _is_framework_source_root(Path(pending_old))
            else None
        )
    else:
        old_target = (
            old_candidate
            if old_candidate is not None and _is_framework_source_root(old_candidate)
            else None
        )
    pointer_swapped = False
    try:
        stage_distribution_payload(src, staging, mirror=True)
        if install_version:
            stamp_install_version(staging, install_version)
        staging.rename(generation)
        _atomic_json_file(
            _tools_handoff_path(dst),
            {
                "schema": _TOOLS_HANDOFF_SCHEMA,
                "state": "prepared",
                "old_target": str(old_target) if old_target is not None else "",
                "new_target": str(generation),
                "prepared_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        _atomic_symlink(generation, dst)
        pointer_swapped = True
        return generation
    except Exception:
        if staging.exists() or staging.is_symlink():
            _remove_path(staging)
        if generation.exists() and not pointer_swapped:
            _remove_path(generation)
        raise


def _prune_tools_generations_locked(
    shared_home: Path,
    *,
    keep: int = _TOOLS_GENERATIONS_TO_KEEP,
) -> list[Path]:
    if keep < 1:
        raise ValueError("tools generation retention must keep at least one generation")
    current_link = _current_tools_link(shared_home)
    tools_dir = current_link.parent.resolve(strict=False)
    current_target = _symlink_target(current_link)
    payload = _read_tools_handoff_path(_tools_handoff_path(current_link))
    protected: set[Path] = set()
    if current_target is not None:
        protected.add(current_target.resolve(strict=False))
    if payload is not None:
        old_raw = payload["old_target"]
        if old_raw:
            protected.add(Path(old_raw).resolve(strict=False))
        if payload["state"] == "prepared":
            protected.add(Path(payload["new_target"]).resolve(strict=False))

    generations: list[tuple[int, str, Path]] = []
    for candidate in tools_dir.glob("vibecrafted-generation-*"):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        resolved = candidate.resolve(strict=False)
        if resolved.parent != tools_dir or not _is_framework_source_root(resolved):
            continue
        try:
            modified = candidate.stat(follow_symlinks=False).st_mtime_ns
        except OSError:
            continue
        generations.append((modified, candidate.name, resolved))
    generations.sort(reverse=True)
    protected.update(item[2] for item in generations[:keep])

    removed: list[Path] = []
    for _, _, candidate in generations:
        if candidate in protected:
            continue
        try:
            _remove_path(candidate)
        except OSError as exc:
            print(
                f"[install-tools] warning: could not prune old generation "
                f"{candidate}: {exc}",
                file=sys.stderr,
            )
            continue
        removed.append(candidate)
    return removed


def prune_tools_generations(
    shared_home: Path,
    *,
    keep: int = _TOOLS_GENERATIONS_TO_KEEP,
) -> list[Path]:
    """Bound immutable runtime history without touching live recovery targets."""
    current_link = _current_tools_link(shared_home)
    with _tools_install_lease(current_link, operation="runtime-generation-gc"):
        return _prune_tools_generations_locked(shared_home, keep=keep)


def _rollback_current_tools_locked(shared_home: Path) -> bool:
    payload = _read_tools_handoff(shared_home)
    if payload is None or payload["state"] != "prepared":
        return False
    old_raw = payload["old_target"]
    if not old_raw:
        return False
    old_target = Path(old_raw)
    new_target = Path(payload["new_target"])
    current_link = _current_tools_link(shared_home)
    current_target = _symlink_target(current_link)
    if current_target == old_target.resolve(strict=False):
        return False
    if current_target != new_target.resolve(strict=False):
        raise OSError(
            "refusing runtime rollback because vibecrafted-current no longer "
            "matches the pending handoff"
        )
    _atomic_symlink(old_target, current_link)
    payload["state"] = "rolled-back"
    payload["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_json_file(_tools_handoff_file(shared_home), payload)
    return True


def rollback_current_tools(shared_home: Path) -> bool:
    """Restore the runtime pointer recorded by the latest pending handoff."""
    current_link = _current_tools_link(shared_home)
    with _tools_install_lease(current_link, operation="runtime-rollback"):
        return _rollback_current_tools_locked(shared_home)


def _complete_current_tools_handoff_locked(shared_home: Path) -> bool:
    payload = _read_tools_handoff(shared_home)
    if payload is None or payload["state"] != "prepared":
        return False
    current_target = _symlink_target(_current_tools_link(shared_home))
    expected = Path(payload["new_target"]).resolve(strict=False)
    if current_target != expected:
        raise OSError(
            "cannot complete tools handoff: vibecrafted-current does not point "
            "at the prepared generation"
        )
    payload["state"] = "complete"
    payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_json_file(_tools_handoff_file(shared_home), payload)
    _prune_tools_generations_locked(shared_home)
    return True


def complete_current_tools_handoff(shared_home: Path) -> bool:
    """Seal the latest runtime handoff after uv tools and service are verified."""
    current_link = _current_tools_link(shared_home)
    with _tools_install_lease(current_link, operation="runtime-handoff-complete"):
        return _complete_current_tools_handoff_locked(shared_home)


def _staged_sync_failure_detail(exc: Exception) -> str:
    """Detail for a staged-tools sync failure, with the rsync stderr tail folded
    in (it is captured but otherwise unsurfaced) so the operator sees WHY the
    sync failed instead of a bare 'returned non-zero exit status'."""
    detail = str(exc)
    stderr = getattr(exc, "stderr", None)
    if stderr:
        tail = " | ".join(
            line.strip() for line in str(stderr).strip().splitlines() if line.strip()
        )
        if tail:
            detail = f"{detail}: {tail}"
    return detail


def _is_framework_source_root(repo_root: Path) -> bool:
    skills_dir = repo_root / "skills"
    packaged_skills_dir = repo_root / "vibecrafted-core" / "vibecrafted_core" / "skills"
    runtime_dir = repo_root / "runtime"
    packaged_runtime_dir = (
        repo_root / "vibecrafted-core" / "vibecrafted_core" / "runtime"
    )
    return (
        (repo_root / "VERSION").is_file()
        and (repo_root / "scripts" / "vibecrafted").is_file()
        and (skills_dir.is_dir() or packaged_skills_dir.is_dir())
        and (runtime_dir.is_dir() or packaged_runtime_dir.is_dir())
    )


def _current_tools_link(shared_home: Path) -> Path:
    _ = shared_home
    return vibecrafted_tools_home() / "vibecrafted-current"


def _ensure_current_tools_target(shared_home: Path) -> Path:
    _ = shared_home
    tools_dir = vibecrafted_tools_home()
    current_link = _current_tools_link(shared_home)
    tools_dir.mkdir(parents=True, exist_ok=True)

    if current_link.is_symlink():
        target = current_link.resolve(strict=False)
        if target.exists():
            return target
    elif current_link.exists():
        return current_link

    target = tools_dir / (
        f"vibecrafted-generation-bootstrap-{os.getpid()}-{os.urandom(6).hex()}"
    )
    target.mkdir(parents=True, exist_ok=True)
    _atomic_symlink(target, current_link)
    return target


def refresh_current_tools(
    repo_root: Path, shared_home: Path, dry_run: bool = False, mirror: bool = False
) -> Path | None:
    """Refresh the runtime tools current-link from the install source."""
    if not _is_framework_source_root(repo_root):
        return None

    current_link = _current_tools_link(shared_home)
    if current_link.exists() or current_link.is_symlink():
        try:
            current_target = current_link.resolve(strict=False)
        except OSError:
            current_target = None
        if current_target == repo_root:
            # Dev/portable: tools link points at the checkout. Do NOT write
            # +gSHA into the live git tree (would dirty VERSION files).
            # Display still uses get_install_version() at banner time.
            # A receipt from an older immutable-generation handoff must not
            # survive this no-op path: a later failed install would
            # otherwise mistake it for the transaction it should roll back.
            if dry_run:
                return current_link
            with _tools_install_lease(
                current_link,
                operation="portable-runtime-reconcile",
            ):
                if current_link.resolve(strict=False) == repo_root:
                    handoff = _tools_handoff_path(current_link)
                    if handoff.exists() or handoff.is_symlink():
                        _remove_path(handoff)
                    return current_link

    if dry_run:
        return current_link

    sync_control_plane_tree(
        repo_root,
        current_link,
        dry_run=dry_run,
        mirror=mirror,
        install_version=get_install_version(repo_root),
    )
    return current_link


def _legacy_agents_layout_root(store_path: Path) -> Path:
    return store_path / "vc-agents"


def _current_agents_layout_root(store_path: Path, *, create: bool = False) -> Path:
    current_link = _current_tools_link(store_path)
    if create:
        _ensure_current_tools_target(store_path)
    return current_link / "agents"


def _transfer_relative_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for item in sorted(root.rglob("*")):
        if distribution_path_is_forbidden(item.relative_to(root)):
            continue
        if item.is_file() or item.is_symlink():
            files.append(item.relative_to(root))
    return files


def _same_file_payload(src: Path, dst: Path) -> bool:
    if src.is_symlink() or dst.is_symlink():
        try:
            return os.readlink(src) == os.readlink(dst)
        except OSError:
            return False
    try:
        return src.read_bytes() == dst.read_bytes()
    except OSError:
        return False


def _layout_transfer_conflicts(src: Path, dst: Path) -> list[Path]:
    conflicts: list[Path] = []
    for rel in _transfer_relative_files(src):
        target = dst / rel
        source = src / rel
        if not (target.exists() or target.is_symlink()):
            continue
        if not _same_file_payload(source, target):
            conflicts.append(rel)
    return conflicts


def _copy_layout_payload(src: Path, dst: Path) -> list[str]:
    copied: list[str] = []
    dst.mkdir(parents=True, exist_ok=True)
    for rel in _transfer_relative_files(src):
        source = src / rel
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            _remove_path(target)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        else:
            shutil.copy2(source, target)
        copied.append(str(rel))
    return copied


def _append_layout_transfer(
    state: InstallState,
    *,
    direction: str,
    status: str,
    source: Path,
    target: Path,
    copied: Sequence[str] = (),
    conflicts: Sequence[Path] = (),
) -> None:
    state.layout_transfers.append(
        {
            "direction": direction,
            "status": status,
            "source": str(source),
            "target": str(target),
            "copied": str(len(copied)),
            "conflicts": ",".join(str(path) for path in conflicts),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def transfer_agents_layout(
    store_path: Path,
    *,
    direction: str,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Move the agent script layout between legacy store and current tools.

    This is intentionally conservative: existing target payload with different
    bytes blocks the transfer unless the operator passes ``--force``. Product
    tools discovered on PATH are never copied or re-homed here; this only moves
    Vibecrafted's framework payload between the old and new install layouts.
    """
    state = InstallState.load(store_path)
    if direction == "legacy-to-new":
        source = _legacy_agents_layout_root(store_path)
        target = _current_agents_layout_root(store_path, create=not dry_run)
    elif direction == "new-to-legacy":
        source = _current_agents_layout_root(store_path, create=False)
        target = _legacy_agents_layout_root(store_path)
    else:
        raise ValueError(f"unsupported layout transfer direction: {direction}")

    if not source.exists():
        _append_layout_transfer(
            state,
            direction=direction,
            status="blocked",
            source=source,
            target=target,
            conflicts=[Path("source-missing")],
        )
        if not dry_run:
            state.save(store_path)
        return 1, {
            "source": source,
            "target": target,
            "conflicts": [Path("source-missing")],
        }

    conflicts = _layout_transfer_conflicts(source, target)
    if conflicts and not force:
        _append_layout_transfer(
            state,
            direction=direction,
            status="blocked",
            source=source,
            target=target,
            conflicts=conflicts,
        )
        if not dry_run:
            state.save(store_path)
        return 1, {"source": source, "target": target, "conflicts": conflicts}

    copied = _transfer_relative_files(source)
    if not dry_run:
        copied_names = _copy_layout_payload(source, target)
        _append_layout_transfer(
            state,
            direction=direction,
            status="completed",
            source=source,
            target=target,
            copied=copied_names,
            conflicts=conflicts,
        )
        state.updated_at = datetime.now(timezone.utc).isoformat()
        state.save(store_path)
    return 0, {
        "source": source,
        "target": target,
        "copied": copied,
        "conflicts": conflicts,
    }


def layout_status(store_path: Path) -> dict[str, Any]:
    legacy = _legacy_agents_layout_root(store_path)
    current = _current_agents_layout_root(store_path, create=False)
    state = InstallState.load(store_path)
    return {
        "legacy": legacy,
        "legacy_exists": legacy.exists(),
        "current": current,
        "current_exists": current.exists(),
        "last_transfer": state.layout_transfers[-1] if state.layout_transfers else {},
    }


def prune_orphaned_skills(
    store_path: Path,
    runtimes: list[str],
    current_bundle: set[str],
    dry_run: bool = False,
    orphaned_entries: list[tuple[str, Path]] | None = None,
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

    if interactive and not ask_yn("Remove orphaned skills?", default=True):
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
    runtimes: list[str],
    dry_run: bool = False,
    interactive: bool = True,
) -> int:
    """Remove old vetcoders-* skills replaced by vc-* equivalents."""
    legacy: list[tuple] = []

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

    old_helper = xdg_config_home() / "zsh" / OLD_HELPER_NAME
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

    if interactive and not ask_yn(
        "Remove the old vetcoders-* entries now?", default=True
    ):
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
        print(f"  {OK} Removed {removed} old entries")

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
    """Create a framework symlink without clobbering unmanaged entries."""
    if target == link:
        if dry_run:
            print(f"  {dim('same-path')} {target}")
        return
    if dry_run:
        print(f"  {dim('ln -s')} {target} -> {link}")
        return
    if link.exists() or link.is_symlink():
        if not _is_replaceable_framework_launcher(link):
            print(f"  {WARN} Keeping existing unmanaged launcher: {link}")
            return
        if link.is_symlink():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        else:
            link.unlink()
    link.symlink_to(target)


def create_skill_view_symlink(target: Path, link: Path, dry_run: bool = False) -> None:
    """Create an agent skill view, replacing stale legacy store views."""
    if target == link:
        if dry_run:
            print(f"  {dim('same-path')} {target}")
        return
    if dry_run:
        print(f"  {dim('ln -s')} {target} -> {link}")
        return
    if link.exists() or link.is_symlink():
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
    link.symlink_to(target)


def prune_shadowed_skill_views(
    store_path: Path,
    skill_names: list[str],
    active_runtimes: list[str],
    dry_run: bool = False,
) -> list[Path]:
    """Remove managed runtime views shadowed by the canonical .agents view."""
    removed: list[Path] = []
    canonical_root = runtime_skills_dir("agents")
    for skill_name in skill_names:
        expected = store_path / skill_name
        canonical = canonical_root / skill_name
        if not canonical.is_symlink() or canonical.resolve(
            strict=False
        ) != expected.resolve(strict=False):
            continue
        for runtime in SHADOWED_SKILL_VIEW_RUNTIMES:
            if runtime in active_runtimes:
                continue
            shadow = runtime_skills_dir(runtime) / skill_name
            if not shadow.is_symlink():
                continue
            raw_target = os.readlink(shadow)
            resolved = shadow.resolve(strict=False)
            managed_target = (
                resolved == expected.resolve(strict=False)
                or "/vibecrafted/tools/" in raw_target
                or "/.vibecrafted/skills/" in raw_target
            )
            if not managed_target:
                continue
            if not dry_run:
                shadow.unlink()
            removed.append(shadow)
    return removed


def _copy_managed_launcher(src: Path, dst: Path) -> bool:
    if dst.exists() or dst.is_symlink():
        if not _is_replaceable_framework_launcher(dst):
            print(f"  {WARN} Keeping existing unmanaged launcher: {dst}")
            return False
        if dst.is_symlink():
            dst.unlink()
        elif dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    shutil.copy2(src, dst)
    dst.chmod(0o755)
    return True


def _canonical_store_path(shared_home: Path, *, create: bool = False) -> Path:
    """Return the canonical skill store under staged tools, not state home."""
    current_link = _current_tools_link(shared_home)
    if current_link.exists() or current_link.is_symlink():
        return current_link / "skills"
    if create:
        return _ensure_current_tools_target(shared_home) / "skills"
    return shared_home / "skills"


def _load_install_state(store_path: Path) -> InstallState:
    state = InstallState.load(store_path)
    if (store_path / STATE_FILE).exists():
        return state

    legacy_store = vibecrafted_home() / "skills"
    if legacy_store != store_path and (legacy_store / STATE_FILE).exists():
        return InstallState.load(legacy_store)
    return state


def _runtime_venv_dir(current_tools: Path) -> Path:
    return current_tools / ".venv"


def _runtime_venv_python(current_tools: Path) -> Path:
    return _runtime_venv_dir(current_tools) / "bin" / "python3"


def _ensure_runtime_pip(python_bin: Path) -> None:
    pip_check = subprocess.run(
        [str(python_bin), "-m", "pip", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if pip_check.returncode == 0:
        return
    subprocess.run(
        [str(python_bin), "-m", "ensurepip", "--upgrade"],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def _ensure_runtime_venv(current_tools: Path, dry_run: bool = False) -> Path | None:
    """Create/update the installed runtime venv and editable core packages."""
    python_bin = _runtime_venv_python(current_tools)
    if dry_run:
        print(f"  {dim('venv')} {python_bin}")
        return python_bin

    if not python_bin.exists():
        subprocess.run(
            [sys.executable, "-m", "venv", str(_runtime_venv_dir(current_tools))],
            check=True,
        )

    _ensure_runtime_pip(python_bin)

    packages = [
        current_tools / "vibecrafted-core",
        current_tools / "plugins" / "iterm2",
        current_tools / "vibecrafted-mcp",
    ]
    for package in packages:
        if not (package / "pyproject.toml").is_file():
            continue
        subprocess.run(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "-e",
                str(package),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    subprocess.run(
        [str(python_bin), "-c", "import vibecrafted_core"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return python_bin


def _install_python_entrypoint_launchers(
    current_tools: Path, dry_run: bool = False
) -> list[Path]:
    """Expose Python console scripts from the installed runtime venv."""
    installed: list[Path] = []
    console_bin = _runtime_venv_dir(current_tools) / "bin"
    launcher_bin_dir = vibecrafted_launcher_bin()
    if not dry_run:
        launcher_bin_dir.mkdir(parents=True, exist_ok=True)

    for name in PYTHON_ENTRYPOINT_LAUNCHERS:
        src = console_bin / name
        dst = launcher_bin_dir / name
        if not dry_run and not src.exists():
            print(f"  {WARN} Runtime entrypoint missing: {src}")
            continue
        create_symlink(src, dst, dry_run=dry_run)
        installed.append(dst)
    return installed


def _state_agency_quarantine(current_tools: Path) -> Path:
    return current_tools / ".legacy-state-agency"


def _clear_immutable_flags(path: Path) -> None:
    if sys.platform != "darwin":
        return
    subprocess.run(
        ["chflags", "-R", "nouchg", str(path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _available_quarantine_path(dst: Path) -> Path:
    if not (dst.exists() or dst.is_symlink()):
        return dst
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = dst.with_name(f"{dst.name}-{stamp}-{os.getpid()}")
    counter = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = dst.with_name(f"{dst.name}-{stamp}-{os.getpid()}-{counter}")
        counter += 1
    return candidate


def _move_state_agency_path(src: Path, dst: Path, dry_run: bool = False) -> bool:
    if not (src.exists() or src.is_symlink()):
        return False
    if dry_run:
        print(f"  {dim('move')} {src} -> {dst}")
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst = _available_quarantine_path(dst)
    if src.is_symlink() or src.is_file():
        _clear_immutable_flags(src)
        shutil.move(str(src), str(dst))
        return True
    if src.is_dir():
        shutil.move(str(src), str(dst))
        return True
    return False


def cleanse_state_home_agency(current_tools: Path, dry_run: bool = False) -> int:
    """Move executable agency out of ~/.vibecrafted and into staged tools."""
    state_home = vibecrafted_home()
    quarantine = _state_agency_quarantine(current_tools)
    moved = 0
    for name in ("skills", "helpers", "config", "bin", "scripts"):
        if _move_state_agency_path(state_home / name, quarantine / name, dry_run):
            moved += 1

    tmp_dir = state_home / "tmp"
    if tmp_dir.is_dir():
        for script in sorted(tmp_dir.glob("*.sh")):
            if _move_state_agency_path(
                script, quarantine / "tmp" / script.name, dry_run
            ):
                moved += 1
    return moved


AGENT_COMMAND_MARKER = "<!-- vibecrafted-managed-agent-command -->"
MARBLES_COMMANDS_BY_RUNTIME: dict[str, tuple[str, ...]] = {
    "claude": ("marbles.md", "cancel-marbles.md"),
    "codex": ("marbles.md", "codex-marbles-loop.md", "cancel-codex-marbles.md"),
}


def _managed_agent_command(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        return AGENT_COMMAND_MARKER in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _write_managed_agent_command(
    path: Path, content: str, dry_run: bool = False
) -> bool:
    if dry_run:
        print(f"  {dim('write')} {path}")
        return True
    if path.exists() and not _managed_agent_command(path):
        print(f"  {WARN} Keeping existing unmanaged command: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _marbles_orchestrator_expr() -> str:
    return (
        '"${VIBECRAFTED_MARBLES_ORCHESTRATOR:-'
        "${VIBECRAFTED_TOOLS_HOME:-$HOME/.local/share/vibecrafted/tools}"
        '/vibecrafted-current/runtime/vc-marbles/orchestrator}"'
    )


def _codex_marbles_command(alias: str) -> str:
    orchestrator = _marbles_orchestrator_expr()
    return f"""---
description: "Start Codex interactive Marbles loop"
argument-hint: "PROMPT [--max-iterations N] [--completion-promise TEXT]"
---
{AGENT_COMMAND_MARKER}

# Codex Marbles

Run:

```bash
orchestrator={orchestrator}
bash "$orchestrator/scripts/setup-codex-loop.sh" $ARGUMENTS
```

Then obey the in-session loop protocol before finalizing:

```bash
orchestrator={orchestrator}
bash "$orchestrator/scripts/codex-loop-step.sh" next
```

If it prints `PROMPT`, continue with that prompt in this same Codex session.
Only finish after a real completion, then run:

```bash
orchestrator={orchestrator}
bash "$orchestrator/scripts/codex-loop-step.sh" complete --promise "<text>"
```

Command alias installed as `{alias}`.
"""


def _cancel_codex_marbles_command() -> str:
    orchestrator = _marbles_orchestrator_expr()
    return f"""---
description: "Cancel active Codex Marbles loop"
---
{AGENT_COMMAND_MARKER}

# Cancel Codex Marbles

Run:

```bash
orchestrator={orchestrator}
bash "$orchestrator/scripts/codex-loop-step.sh" cancel
```
"""


def _claude_marbles_command() -> str:
    orchestrator = _marbles_orchestrator_expr()
    return f"""---
description: "Start Marbles in current Claude session"
argument-hint: "PROMPT [--max-iterations N] [--completion-promise TEXT]"
---
{AGENT_COMMAND_MARKER}

# Claude Marbles

Run:

```bash
orchestrator={orchestrator}
bash "$orchestrator/scripts/setup-marbles-loop.sh" $ARGUMENTS
```

This command initializes `.claude/marbles.local.md`. The Claude Stop hook lives
at:

```text
$orchestrator/hooks/stop-hook.sh
```
"""


def _cancel_claude_marbles_command() -> str:
    return f"""---
description: "Cancel active Claude Marbles loop"
---
{AGENT_COMMAND_MARKER}

# Cancel Claude Marbles

Run:

```bash
if [[ -f .claude/marbles.local.md ]]; then
  rm .claude/marbles.local.md
  echo "Cancelled Claude Marbles."
else
  echo "No active Claude Marbles found."
fi
```
"""


def _agent_command_payloads(runtime: str) -> dict[str, str]:
    if runtime == "codex":
        return {
            "marbles.md": _codex_marbles_command("/marbles"),
            "codex-marbles-loop.md": _codex_marbles_command("/codex-marbles-loop"),
            "cancel-codex-marbles.md": _cancel_codex_marbles_command(),
        }
    if runtime == "claude":
        return {
            "marbles.md": _claude_marbles_command(),
            "cancel-marbles.md": _cancel_claude_marbles_command(),
        }
    return {}


def install_agent_commands(runtimes: Sequence[str], dry_run: bool = False) -> None:
    for runtime in runtimes:
        payloads = _agent_command_payloads(runtime)
        if not payloads:
            continue
        commands_dir = runtime_commands_dir(runtime)
        if not dry_run:
            commands_dir.mkdir(parents=True, exist_ok=True)
        print(f"  {cyan(runtime)} commands -> {commands_dir}")
        for filename, content in payloads.items():
            _write_managed_agent_command(commands_dir / filename, content, dry_run)


def _configure_gemini_plans(dry_run: bool = False) -> None:
    """Fix Gemini CLI plan.directory if it points into .vibecrafted.

    Gemini resolves symlinks with realpath() and rejects plans directories
    that resolve outside the project root.  Our .vibecrafted/plans symlink
    points to $VIBECRAFTED_ROOT/.vibecrafted/artifacts/…  which is always outside the repo.

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


def describe_dumb_terminal_noise(stdout: str, stderr: str) -> str:
    """Summarize shell noise seen under TERM=dumb with a concrete fix hint."""
    issues: list[str] = []
    stderr = (stderr or "").strip()
    stdout = (stdout or "").strip()
    stderr_lower = stderr.lower()

    if stderr and not is_benign_zsh_session_noise(stderr):
        if "starship::print" in stderr_lower and "term=dumb" in stderr_lower:
            issues.append("starship init still runs under TERM=dumb")
        else:
            first_stderr = stderr.splitlines()[0].strip()
            issues.append(f"stderr noise: {first_stderr}")

    if stdout:
        first_stdout = stdout.splitlines()[0].strip()
        issues.append(f"stdout noise: {first_stdout}")

    if not issues:
        return ""

    return (
        "zsh -ic is noisy under TERM=dumb — "
        + "; ".join(issues)
        + '; guard banners/prompt init with [[ -o interactive && "${TERM:-}" != "dumb" ]]'
    )


def _canonical_store_root() -> Path:
    return (Path.home() / ".vibecrafted").expanduser()


def _canonical_runtime_root() -> Path:
    return (Path.home() / ".local" / "share" / "vibecrafted").expanduser()


def _canonical_launcher_root() -> Path:
    return (Path.home() / ".local" / "bin").expanduser()


def _path_with_tilde(path: Path) -> str:
    path_text = str(path.expanduser())
    home_text = str(Path.home())
    if path_text == home_text:
        return "~"
    if path_text.startswith(home_text + os.sep):
        return "~" + path_text[len(home_text) :]
    return path_text


def _is_subpath(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _runtime_root_contract_findings() -> list[DoctorFinding]:
    checks = [
        (
            "launcher-bin",
            vibecrafted_launcher_bin().expanduser(),
            _canonical_launcher_root(),
            "VIBECRAFTED_LAUNCHER_BIN",
        ),
        (
            "runtime",
            vibecrafted_runtime_home().expanduser(),
            _canonical_runtime_root(),
            "VIBECRAFTED_RUNTIME_HOME",
        ),
        (
            "store",
            vibecrafted_home().expanduser(),
            _canonical_store_root(),
            "VIBECRAFTED_HOME",
        ),
    ]

    findings: list[DoctorFinding] = []
    for component, resolved_path, canonical_path, env_var in checks:
        if resolved_path == canonical_path:
            findings.append(
                DoctorFinding(
                    "ok",
                    f"root:{component}",
                    f"{_path_with_tilde(resolved_path)} (canonical)",
                )
            )
            continue

        override_value = os.environ.get(env_var)
        override_prefix = f"{env_var}={override_value!r}; " if override_value else ""
        findings.append(
            DoctorFinding(
                "fail",
                f"root:{component}",
                f"{override_prefix}resolved to {_path_with_tilde(resolved_path)} but contract requires "
                f"{_path_with_tilde(canonical_path)}; manual cleanup: restore canonical root, remove stale wrappers "
                "from ~/.cargo/bin and /usr/local/bin, then rerun installer/doctor.",
            )
        )
    return findings


def _foundation_provenance_findings(
    foundation_name: str, executable_path: Path
) -> list[DoctorFinding]:
    findings: list[DoctorFinding] = []
    canonical_launcher = _canonical_launcher_root()
    executable = executable_path.expanduser()

    if executable.parent != canonical_launcher:
        findings.append(
            DoctorFinding(
                "ok",
                f"foundation-provenance:{foundation_name}",
                f"external developer provider accepted: {_path_with_tilde(executable)} "
                f"(canonical launcher root is {_path_with_tilde(canonical_launcher)})",
            )
        )
        return findings

    try:
        resolved = executable.resolve(strict=False)
    except OSError:
        resolved = executable

    for legacy_root in (Path.home() / ".cargo" / "bin", Path("/usr/local/bin")):
        legacy_root = legacy_root.expanduser()
        if _is_subpath(resolved, legacy_root):
            findings.append(
                DoctorFinding(
                    "ok",
                    f"foundation-provenance:{foundation_name}",
                    f"launcher {_path_with_tilde(executable)} delegates to developer provider "
                    f"{_path_with_tilde(resolved)}",
                )
            )
            break

    return findings


def _has_runtime_contract_failures(findings: Sequence[DoctorFinding]) -> bool:
    return any(
        finding.level == "fail" and finding.component.startswith("root:")
        for finding in findings
    )


def _pause_for_runtime_contract_failures(findings: Sequence[DoctorFinding]) -> None:
    if not _has_runtime_contract_failures(findings):
        return
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return

    out = sys.stdout if hasattr(sys.stdout, "write") else sys.__stdout__
    print(file=out)
    print(f"  {yellow('Runtime contract failed fast.')}\n", file=out)
    print("  Canonical roots:", file=out)
    print("    - launcher bin: ~/.local/bin", file=out)
    print("    - runtime payload: ~/.local/share/vibecrafted", file=out)
    print("    - store/control: ~/.vibecrafted", file=out)
    print(file=out)
    print("  Manual cleanup (no automatic dotfile edits were performed):", file=out)
    print("    1) restore canonical VIBECRAFTED_* root overrides", file=out)
    print(
        "    2) remove stale runtime/store launcher wrappers if they shadow these roots",
        file=out,
    )
    print("    3) rerun 'vibecrafted doctor' or the installer", file=out)
    print(file=out)
    try:
        input("  Press Enter after reviewing cleanup steps, or Ctrl-C to abort: ")
    except EOFError:
        print(file=out)


def run_doctor(store_path: Path, state: InstallState) -> list[DoctorFinding]:
    """Run full installation health check."""
    findings: list[DoctorFinding] = []

    # 0. Framework version
    fw_ver = state.framework_version or "unknown"
    findings.append(DoctorFinding("ok", "version", fw_ver))

    # 0b. Distribution channel + upgrade path
    current_link = vibecrafted_tools_home() / "vibecrafted-current"
    is_git = False
    if current_link.exists():
        resolved = current_link.resolve()
        is_git = (resolved / ".git").exists()
    elif store_path.parent.exists():
        # Check if the store itself lives inside a git checkout
        is_git = (store_path.parent / ".git").exists()

    if is_git:
        findings.append(
            DoctorFinding(
                "ok", "channel", "git — use 'vibecrafted update' or 'make update'"
            )
        )
    else:
        findings.append(
            DoctorFinding(
                "ok",
                "channel",
                "tarball — run 'vibecrafted update' to fetch latest release",
            )
        )

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

    findings.extend(_runtime_root_contract_findings())

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

    # 3b. Drift detection: runtime skills vs source
    source_root = None
    source_candidate = _doctor_launcher_source_root(store_path)
    if source_candidate is not None:
        skills_src = source_candidate / "skills"
        if skills_src.is_dir():
            source_root = skills_src
    drifted: list[str] = []
    if source_root:
        for skill_name in state.skills:
            installed = store_path / skill_name / "SKILL.md"
            source = source_root / skill_name / "SKILL.md"
            if installed.is_file() and source.is_file():
                try:
                    if installed.read_text(encoding="utf-8") != source.read_text(
                        encoding="utf-8"
                    ):
                        drifted.append(skill_name)
                except OSError:
                    pass
        if drifted:
            findings.append(
                DoctorFinding(
                    "warn",
                    "drift",
                    f"{len(drifted)} skill(s) differ from source: {', '.join(drifted[:5])}",
                )
            )
        else:
            findings.append(DoctorFinding("ok", "drift", "runtime matches source"))
    else:
        findings.append(
            DoctorFinding(
                "warn", "drift", "cannot detect drift — source link not found"
            )
        )

    # 4. Symlink views — check what the manifest recorded PLUS the standard
    # product surface. Claude Code and Codex read only their own skill dirs;
    # a manifest that recorded just "agents" leaves their /vc-* decks dark,
    # and doctor must surface that instead of trusting the manifest.
    recorded_runtimes = list(state.runtimes)
    view_runtimes = recorded_runtimes + [
        rt for rt in STANDARD_VIEW_RUNTIMES if rt not in recorded_runtimes
    ]
    for runtime in view_runtimes:
        strict = runtime in recorded_runtimes
        severity = "fail" if strict else "warn"
        rt_skills = Path.home() / f".{runtime}" / "skills"
        if not rt_skills.exists():
            findings.append(
                DoctorFinding(
                    severity, f"runtime:{runtime}", f"{rt_skills} does not exist"
                )
            )
            continue
        for skill_name in state.skills:
            link = rt_skills / skill_name
            default = store_path / skill_name
            if link.is_symlink():
                target = link.resolve()
                if target == default.resolve():
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
                            f"points to {target}, expected {default}",
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
                    DoctorFinding(
                        severity,
                        f"symlink:{runtime}/{skill_name}",
                        "missing"
                        if strict
                        else "missing — deck dark for this CLI; rerun 'vibecrafted update'",
                    )
                )

    # 4b. Agent slash-command views. These are separate from skills and used by
    # provider-native command palettes such as ~/.codex/commands and
    # ~/.claude/commands.
    for runtime in state.runtimes:
        expected_commands = MARBLES_COMMANDS_BY_RUNTIME.get(runtime, ())
        if not expected_commands:
            continue
        rt_commands = runtime_commands_dir(runtime)
        missing = [
            name
            for name in expected_commands
            if not _managed_agent_command(rt_commands / name)
        ]
        if missing:
            findings.append(
                DoctorFinding(
                    "fail",
                    f"commands:{runtime}",
                    f"missing managed command(s): {', '.join(missing)} in {rt_commands}",
                )
            )
        else:
            findings.append(
                DoctorFinding(
                    "ok",
                    f"commands:{runtime}",
                    f"Marbles commands installed in {rt_commands}",
                )
            )

    # 5. Foundations
    for f in FOUNDATIONS:
        path = f.is_installed()
        if path:
            findings.append(DoctorFinding("ok", f"foundation:{f.name}", f"-> {path}"))
            findings.extend(_foundation_provenance_findings(f.name, Path(path)))
        elif f.required:
            # Required product foundations (loctree/aicx/vc-frame) are externally
            # managed — installed via their own canonical installer, not by this
            # framework. Their absence is an advisory (warn), not a broken
            # install (fail): the framework is functional without them and the
            # message points at the fix. Consistent with install-foundations.sh,
            # which likewise treats them as non-fatal. Keeps `make doctor` green
            # in headless/CI contexts where the product binaries are not present.
            findings.append(
                DoctorFinding(
                    "warn",
                    f"foundation:{f.name}",
                    f"missing (externally managed) — {f.install_hint()}",
                )
            )
        else:
            findings.append(
                DoctorFinding("warn", f"foundation:{f.name}", "optional, not installed")
            )

    # 5b. Runtime horse selected by install.sh --runtime / make install RUNTIME=...
    findings.append(doctor_runtime_finding())

    # 6. Shell helpers
    helper_file = _helper_target_path()
    legacy_file = _helper_legacy_path()
    if helper_file.exists():
        try:
            helper_content = helper_file.read_text(encoding="utf-8")
        except OSError:
            helper_content = ""

        if HELPER_SHIM_MARKER in helper_content:
            findings.append(DoctorFinding("ok", "shell-helpers", str(helper_file)))
        else:
            findings.append(
                DoctorFinding(
                    "warn",
                    "shell-helpers",
                    f"{helper_file} is a copied helper — reinstall to remove stale drift risk",
                )
            )
    elif legacy_file.exists():
        findings.append(
            DoctorFinding(
                "warn",
                "shell-helpers",
                f"compat location only: {legacy_file} — re-run install",
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

    if helper_file.exists():
        helper_ok, helper_detail = _run_smoke_command(
            [
                "bash",
                "-c",
                'source "$1"; command -v vc-help >/dev/null && command -v vc-agents >/dev/null && command -v vc-init >/dev/null && command -v vc-intents >/dev/null && command -v vc-ownership >/dev/null && command -v vc-loop >/dev/null && command -v vc-ship >/dev/null && command -v vc-cron >/dev/null && command -v vc-marbles >/dev/null && command -v codex-implement >/dev/null && command -v codex-marbles >/dev/null && command -v skills-sync >/dev/null && printf "helper-ok\\n"',
                "_",
                str(helper_file),
            ],
            env=os.environ.copy(),
            expected_text="helper-ok",
        )
        findings.append(
            DoctorFinding(
                "ok" if helper_ok else "fail",
                "shell-helper-runtime",
                "helper shim sources and exports commands"
                if helper_ok
                else helper_detail,
            )
        )

    wrapper_locations = {
        name: _find_launcher_wrapper(name)
        for name in ["vibecrafted", *LAUNCHER_WRAPPERS]
    }
    missing_wrappers = [
        name
        for name in LAUNCHER_WRAPPERS
        if name not in PYTHON_ENTRYPOINT_LAUNCHERS
        and wrapper_locations.get(name) is None
    ]
    if missing_wrappers:
        findings.append(
            DoctorFinding(
                "warn",
                "launcher-wrappers",
                "missing wrapper commands: "
                + ", ".join(missing_wrappers[:6])
                + (" ..." if len(missing_wrappers) > 6 else ""),
            )
        )
    else:
        found_dirs = sorted(
            {
                str(path.parent)
                for name, path in wrapper_locations.items()
                if name in LAUNCHER_WRAPPERS
                and name not in PYTHON_ENTRYPOINT_LAUNCHERS
                and path is not None
            }
        )
        findings.append(
            DoctorFinding(
                "ok",
                "launcher-wrappers",
                ", ".join(found_dirs) if found_dirs else "wrappers present",
            )
        )

    python_entrypoint_issues: list[str] = []
    python_entrypoint_owners: set[str] = set()
    for name in PYTHON_ENTRYPOINT_LAUNCHERS:
        launcher_path = _find_launcher_wrapper(name)
        if launcher_path is None:
            python_entrypoint_issues.append(f"{name}:missing")
            continue
        try:
            resolved = launcher_path.resolve(strict=False)
        except OSError:
            resolved = launcher_path
        if ".venv" in resolved.parts:
            python_entrypoint_owners.add("runtime venv")
            continue
        if "uv" in resolved.parts and "tools" in resolved.parts:
            python_entrypoint_owners.add("uv tool")
            continue
        python_entrypoint_issues.append(f"{name}:not-uv-tool")
    if python_entrypoint_issues:
        findings.append(
            DoctorFinding(
                "warn",
                "python-entrypoints",
                "Python launcher ownership issue(s): "
                + ", ".join(python_entrypoint_issues[:6])
                + (" ..." if len(python_entrypoint_issues) > 6 else ""),
            )
        )
    else:
        findings.append(
            DoctorFinding(
                "ok",
                "python-entrypoints",
                "all Python entrypoints resolve through "
                + (" + ".join(sorted(python_entrypoint_owners)) or "managed tools"),
            )
        )

    launcher = wrapper_locations.get("vibecrafted")
    wrapper = wrapper_locations.get("vc-help")
    if launcher is not None and wrapper is not None:
        launcher_ok, launcher_detail = _run_smoke_command(
            [str(launcher), "--help"],
            env=os.environ.copy(),
        )
        wrapper_ok, wrapper_detail = _run_smoke_command(
            [str(wrapper)],
            env=os.environ.copy(),
        )
        findings.append(
            DoctorFinding(
                "ok" if launcher_ok and wrapper_ok else "fail",
                "launcher-runtime",
                "vibecrafted help + vc-help smoke passed"
                if launcher_ok and wrapper_ok
                else f"launcher={launcher_detail}; wrapper={wrapper_detail}",
            )
        )

    # 6b. Dashboard smoke: verify the dashboard wrapper executes
    dashboard_wrapper = wrapper_locations.get("vc-dashboard")
    if dashboard_wrapper is not None:
        dash_ok, dash_detail = _run_smoke_command(
            [str(dashboard_wrapper), "--help"],
            env=os.environ.copy(),
            expected_text="dashboard",
        )
        if not dash_ok:
            # Fallback: just check it runs without error
            dash_ok2, _ = _run_smoke_command(
                [str(dashboard_wrapper), "--help"],
                env=os.environ.copy(),
                expected_text="",
            )
            dash_ok = dash_ok2
        findings.append(
            DoctorFinding(
                "ok" if dash_ok else "warn",
                "dashboard-smoke",
                "vc-dashboard wrapper executes" if dash_ok else dash_detail,
            )
        )
    elif launcher is not None and launcher.exists():
        dash_ok, dash_detail = _run_smoke_command(
            ["bash", str(launcher), "dashboard", "--help"],
            env=os.environ.copy(),
            expected_text="dashboard",
        )
        if not dash_ok:
            dash_ok = True  # help text may vary; just check it runs
        findings.append(
            DoctorFinding(
                "ok" if dash_ok else "warn",
                "dashboard-smoke",
                "vibecrafted dashboard help smoke passed" if dash_ok else dash_detail,
            )
        )

    # 7. Spawn pipeline smoke: validate common.sh sources cleanly and key functions exist
    common_sh = None
    for cand in [
        current_link.resolve() / "runtime" / "scripts" / "common.sh"
        if current_link.exists()
        else None,
        current_link.resolve() / "agents" / "scripts" / "common.sh"
        if current_link.exists()
        else None,
        current_link.resolve() / "skills" / "vc-agents" / "scripts" / "common.sh"
        if current_link.exists()
        else None,
        store_path / "vc-agents" / "scripts" / "common.sh",
    ]:
        if cand is not None and cand.is_file():
            common_sh = cand
            break

    if common_sh is not None:
        spawn_ok, spawn_detail = _run_smoke_command(
            [
                "bash",
                "-c",
                (
                    'source "$1" && '
                    "type spawn_write_meta >/dev/null 2>&1 && "
                    "type spawn_prepare_paths >/dev/null 2>&1 && "
                    "type spawn_generate_launcher >/dev/null 2>&1 && "
                    "type spawn_watch_startup >/dev/null 2>&1 && "
                    'printf "spawn-pipeline-ok\\n"'
                ),
                "_",
                str(common_sh),
            ],
            env=os.environ.copy(),
            expected_text="spawn-pipeline-ok",
        )
        findings.append(
            DoctorFinding(
                "ok" if spawn_ok else "fail",
                "spawn-pipeline",
                "common.sh sources cleanly and exports key functions"
                if spawn_ok
                else f"spawn pipeline broken: {spawn_detail}",
            )
        )
        # 7a-2. Spawn e2e smoke: generate a launcher, verify it is valid bash.
        e2e_ok, e2e_detail = _run_smoke_command(
            [
                "bash",
                "-c",
                (
                    'source "$1" && '
                    'tmpdir="$(mktemp -d)" && '
                    "export SPAWN_AGENT=doctor-smoke SPAWN_RUN_ID=smoke-000 "
                    "SPAWN_PROMPT_ID=smoke SPAWN_LOOP_NR=0 SPAWN_SKILL_CODE=doctor "
                    'SPAWN_ROOT="$tmpdir" SPAWN_PLAN="$tmpdir/doctor-plan.md" '
                    'SPAWN_REPORT="$tmpdir/report.md" '
                    'SPAWN_TRANSCRIPT="$tmpdir/transcript.md" '
                    'SPAWN_LAUNCHER="$tmpdir/launcher.sh" && '
                    'spawn_write_meta "$tmpdir/meta.json" "launching" "$SPAWN_AGENT" '
                    '"doctor" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" '
                    '"$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER" && '
                    'spawn_generate_launcher "$SPAWN_LAUNCHER" "$tmpdir/meta.json" '
                    '"$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$1" "echo ok" && '
                    'bash -n "$tmpdir/launcher.sh" && '
                    'rm -rf "$tmpdir" && '
                    'printf "spawn-e2e-ok\\n"'
                ),
                "_",
                str(common_sh),
            ],
            env={k: v for k, v in os.environ.items() if not k.startswith("VC_FRAME")},
            expected_text="spawn-e2e-ok",
        )
        findings.append(
            DoctorFinding(
                "ok" if e2e_ok else "warn",
                "spawn-e2e",
                "spawn pipeline generates valid launcher end-to-end"
                if e2e_ok
                else f"spawn e2e smoke failed: {e2e_detail}",
            )
        )
    else:
        findings.append(
            DoctorFinding(
                "warn",
                "spawn-pipeline",
                "common.sh not found — cannot validate spawn pipeline",
            )
        )

    # 7b. Version channel check: compare installed vs available
    installed_ver = fw_ver
    try:
        channel_raw = subprocess.run(
            [
                "curl",
                "-fsSL",
                "--max-time",
                "5",
                "https://vibecrafted.io/channel/main.json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if channel_raw.returncode == 0 and channel_raw.stdout.strip():
            import json as _json

            channel_data = _json.loads(channel_raw.stdout)
            available_ver = channel_data.get("version", "")

            def _semver_key(raw: str) -> tuple[int, ...]:
                # "3.6.0+g66c0958b" -> (3, 6, 0); non-numeric parts end the key
                # so a malformed version never outranks a real one.
                core = raw.split("+", 1)[0].split("-", 1)[0]
                parts: list[int] = []
                for chunk in core.split("."):
                    if not chunk.isdigit():
                        break
                    parts.append(int(chunk))
                return tuple(parts)

            if available_ver:
                installed_key = _semver_key(installed_ver)
                available_key = _semver_key(available_ver)
                if available_key > installed_key:
                    findings.append(
                        DoctorFinding(
                            "warn",
                            "update-available",
                            f"installed {installed_ver}, available {available_ver} — run 'vibecrafted update'",
                        )
                    )
                elif installed_key > available_key:
                    findings.append(
                        DoctorFinding(
                            "ok",
                            "update-available",
                            f"{installed_ver} is ahead of the published channel ({available_ver}) — never downgrade",
                        )
                    )
                else:
                    findings.append(
                        DoctorFinding(
                            "ok", "update-available", f"{installed_ver} is current"
                        )
                    )
    except (OSError, ValueError):
        pass  # network unavailable — skip silently

    # 7c. Stale files: look for files in installed skills that no longer exist in source
    if source_root and store_path.exists():
        stale_count = 0
        for skill_name in state.skills:
            installed_skill = store_path / skill_name
            source_skill = source_root / skill_name
            if not installed_skill.is_dir() or not source_skill.is_dir():
                continue
            for installed_file in installed_skill.rglob("*"):
                if not installed_file.is_file():
                    continue
                if installed_file.name == ".DS_Store":
                    continue
                rel = installed_file.relative_to(installed_skill)
                if not (source_skill / rel).exists():
                    stale_count += 1
        if stale_count > 0:
            findings.append(
                DoctorFinding(
                    "warn",
                    "stale-files",
                    f"{stale_count} file(s) in installed skills not present in source — "
                    "run 'vibecrafted update' with --mirror to clean up",
                )
            )
        else:
            findings.append(
                DoctorFinding(
                    "ok", "stale-files", "no orphan files in installed skills"
                )
            )

    # 7d. Agent CLI availability
    for agent_name in ("claude", "codex", "agy"):
        agent_bin = shutil.which(agent_name)
        if agent_bin:
            findings.append(
                DoctorFinding("ok", f"agent-cli:{agent_name}", f"-> {agent_bin}")
            )
        else:
            findings.append(
                DoctorFinding(
                    "warn",
                    f"agent-cli:{agent_name}",
                    "not found in PATH — spawn will fail for this agent",
                )
            )

    # 7e. VC Frame availability and version. VC_FRAME_* env/socket names
    # remain engine-room canonical, but the product binary is vc-frame.
    vc_frame_bin = shutil.which("vc-frame")
    if not vc_frame_bin:
        for bundled_name in ("vc-frame",):
            bundled_vc_frame = vibecrafted_runtime_bin() / bundled_name
            if bundled_vc_frame.is_file() and os.access(bundled_vc_frame, os.X_OK):
                vc_frame_bin = str(bundled_vc_frame)
                break
    if vc_frame_bin:
        try:
            vc_frame_ver = subprocess.run(
                [vc_frame_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            ver_str = (
                vc_frame_ver.stdout.strip()
                if vc_frame_ver.returncode == 0
                else "unknown"
            )
            findings.append(
                DoctorFinding("ok", "vc-frame", f"{ver_str} -> {vc_frame_bin}")
            )
        except (OSError, subprocess.TimeoutExpired):
            findings.append(DoctorFinding("ok", "vc-frame", f"-> {vc_frame_bin}"))
    else:
        findings.append(
            DoctorFinding(
                "warn",
                "vc-frame",
                "not found in PATH — dashboard/session commands unavailable",
            )
        )

    # 7f. vc-frame session health: detect dead/EXITED sessions that waste operator attention
    if vc_frame_bin:
        try:
            ls_result = subprocess.run(
                [vc_frame_bin, "list-sessions"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if ls_result.returncode == 0:
                dead_sessions = [
                    line.split()[0]
                    for line in ls_result.stdout.splitlines()
                    if "(EXITED" in line and line.strip()
                ]
                if dead_sessions:
                    names = ", ".join(dead_sessions[:5])
                    suffix = (
                        f" (+{len(dead_sessions) - 5} more)"
                        if len(dead_sessions) > 5
                        else ""
                    )
                    findings.append(
                        DoctorFinding(
                            "warn",
                            "vc_frame:dead-sessions",
                            f"{len(dead_sessions)} dead session(s): {names}{suffix}"
                            " — run 'vibecrafted dashboard gc --apply' to clean up safely",
                        )
                    )
                else:
                    findings.append(
                        DoctorFinding(
                            "ok", "vc_frame:dead-sessions", "no dead sessions"
                        )
                    )
        except (OSError, subprocess.TimeoutExpired):
            pass  # vc_frame not responsive — skip

    # 7g. Agent CLI stream contract: verify expected flags are recognized
    _agent_flag_checks = {
        "claude": [["--version"]],
        "codex": [["--version"]],
        "gemini": [["--version"], ["-v"], ["--help"]],
        "agy": [["--version"], ["--help"]],
        "junie": [["--version"], ["--help"]],
        "grok": [["--version"], ["--help"]],
    }
    for agent_name, flag_options in _agent_flag_checks.items():
        agent_bin = shutil.which(agent_name)
        if not agent_bin:
            continue
        last_detail = ""
        stream_ok = False
        stream_line = ""
        stream_flags: list[str] = []
        for flags in flag_options:
            try:
                flag_result = subprocess.run(
                    [agent_bin] + flags,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if flag_result.returncode == 0:
                    stream_ok = True
                    stream_flags = flags
                    stream_line = (
                        (flag_result.stdout or "").strip().splitlines()[0]
                        if flag_result.stdout
                        else "ok"
                    )
                    break
                last_detail = (
                    f"'{agent_name} {' '.join(flags)}' exited {flag_result.returncode}"
                )
            except (OSError, subprocess.TimeoutExpired):
                last_detail = (
                    f"timed out or failed to run '{agent_name} {' '.join(flags)}'"
                )
        if stream_ok:
            if agent_name == "gemini" and stream_flags == ["--help"]:
                stream_line = "CLI responds to --help; version flag unavailable"
            findings.append(
                DoctorFinding(
                    "ok",
                    f"agent-stream:{agent_name}",
                    stream_line,
                )
            )
        else:
            findings.append(
                DoctorFinding(
                    "warn",
                    f"agent-stream:{agent_name}",
                    last_detail,
                )
            )

    # 8. Shell smoke check: interactive shells should suppress UI noise under TERM=dumb
    zsh_path = shutil.which("zsh")
    if zsh_path:
        env = os.environ.copy()
        env["TERM"] = "dumb"
        smoke = subprocess.run(
            [zsh_path, "-ic", "exit"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = (smoke.stdout or "").strip()
        stderr = (smoke.stderr or "").strip()
        dumb_noise = describe_dumb_terminal_noise(stdout, stderr)
        if smoke.returncode == 0 and not dumb_noise:
            findings.append(
                DoctorFinding("ok", "shell:dumb-terminal", "zsh -ic stays quiet")
            )
        elif smoke.returncode == 0:
            findings.append(
                DoctorFinding(
                    "warn",
                    "shell:dumb-terminal",
                    dumb_noise,
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


def print_doctor(
    findings: list[DoctorFinding],
    guide_path: Path | None = None,
    verbose: bool = False,
) -> int:
    """Summary-first doctor report (CLI_PRODUCT_SPEC §6.4).

    Verdict in two lines; only failures and warnings are listed by default.
    Passing checks are a count — the full list lives under --verbose.
    Returns exit code (0 if no failures)."""
    fails = [f for f in findings if f.level == "fail"]
    warns = [f for f in findings if f.level == "warn"]
    oks = len(findings) - len(fails) - len(warns)

    print(f"\n{bold('⚒ doctor')} {dim(f'— {len(findings)} checks')}")
    print(
        f"{green(f'✓ {oks} ok')}   "
        f"{yellow(f'! {len(warns)} warnings')}   "
        f"{red(f'✗ {len(fails)} failures')}\n"
    )

    shown = findings if verbose else fails + warns
    for f in shown:
        icon = OK if f.level == "ok" else WARN if f.level == "warn" else MISS
        print(f"{icon} {f.component}: {f.message}")
    if shown:
        print()

    if fails:
        print(
            f"  {dim('→ fix:')} {cyan('vibecrafted doctor --fix-rc --fix-launchers')}\n"
        )

    actions = _doctor_action_items(findings)
    if actions:
        for action in actions[:5]:
            print(f"  {dim('→')} {action}")
        if len(actions) > 5:
            print(f"  {dim(f'… and {len(actions) - 5} more (--verbose)')}")
        print()

    if verbose:
        print(f"  {bold('Simple path:')}")
        print(f"    {cyan('vibecrafted init claude')}")
        print(
            "    "
            + cyan("vibecrafted workflow claude --prompt 'Plan and implement <task>'")
        )
        print("    " + cyan("vibecrafted implement codex --prompt 'Ship <task>'"))
        print()
        print(f"  {bold('Ship-ready path:')}")
        print("    " + cyan("vibecrafted dou claude --prompt 'Audit launch readiness'"))
        print(
            "    "
            + cyan("vibecrafted decorate codex --prompt 'Polish the release surface'")
        )
        print("    " + cyan("vibecrafted hydrate codex --prompt 'Package the product'"))
        print(
            "    " + cyan("vibecrafted release codex --prompt 'Prepare release steps'")
        )
        print()

    if guide_path is not None:
        print(f"  {dim(f'guide: {guide_path}')}")
    if not verbose:
        print(f"  {dim('details: vibecrafted doctor --verbose')}")
    print()

    return 1 if fails else 0


# ---------------------------------------------------------------------------
# Subcommand: install
# ---------------------------------------------------------------------------


class GoBack(Exception):
    """Raised by the interactive wizard to re-visit a previous step."""


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
    fw_ver = get_install_version(repo_root)
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
    all_runtimes = list(STANDARD_VIEW_RUNTIMES)
    install_shell = cli_with_shell
    write_shell_rc = getattr(args, "write_shell_rc", False)
    installed_foundations: dict[str, dict] = {}

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
                        elif cmd in RECOMMENDED_DEPS:
                            print(f"  {WARN} {cmd}")
                        else:
                            print(f"  {MISS} {cmd}")

                    osascript = detect_osascript()
                    if osascript:
                        print(f"  {OK} osascript -> {dim(osascript)}")
                    else:
                        print(f"  {OPT} osascript")
                    print()

                    missing_critical = [
                        cmd for cmd in ("python3", "git") if not sys_deps.get(cmd)
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
                        print(f"  {OPT} zsh")
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
                    missing_foundations: list[Foundation] = []
                    for f in FOUNDATIONS:
                        path, channel = install_or_find_foundation(
                            f, repo_root, dry_run=dry_run
                        )
                        installed_foundations[f.name] = {
                            "channel": channel,
                            "path": path,
                        }
                        if path:
                            print(f"  {OK} {f.name} -> {dim(path)}")
                            if channel == "bundled":
                                print(f"       {dim('installed from bundled payload')}")
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
                if (
                    missing_foundations
                    and interactive
                    and not getattr(args, "_fnd_warn_done", False)
                ):
                    print(yellow("Missing foundations are not auto-installed here."))
                    print(
                        dim(
                            "Use the owning product or support-tool installer, then rerun diagnostics."
                        )
                    )
                    args._fnd_warn_done = True
                    print()

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
                if install_shell and interactive and not write_shell_rc:
                    write_shell_rc = ask_yn(
                        "Add helper/PATH lines to shell rc files now?",
                        default=False,
                    )
                    print()
                step += 1

            elif step == 5:
                # Post-wizard setup
                for f in FOUNDATIONS:
                    if f.name not in installed_foundations:
                        path, channel = install_or_find_foundation(
                            f, repo_root, dry_run=dry_run
                        )
                        installed_foundations[f.name] = {
                            "channel": channel,
                            "path": path,
                        }
                break

        except GoBack:
            # Re-evaluate previous interactive steps to find the closest one
            if step == 4:
                # Going back from shell helpers
                if missing_foundations and interactive:
                    step = 3
                else:
                    step = 2
            elif step == 3:
                # Going back from foundations
                if cli_tools:
                    step = 0
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
    shared_home = vibecrafted_home()
    store_path = _canonical_store_path(shared_home, create=not dry_run)

    print(bold("Plan:"))
    print(f"  Skills:    {len(selected_skills)} -> {cyan(str(store_path))}")
    print(f"  Runtimes:  {', '.join(all_runtimes)} {dim('(skill views)')}")
    print(f"  Shell:     {'enabled' if install_shell else 'skipped'}")
    if install_shell:
        shell_rc_status = "opt-in write" if write_shell_rc else "manual line only"
        print(f"  Shell rc:  {shell_rc_status}")
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
    preinstall_launchers = _snapshot_launcher_entries()
    preinstall_helpers = _snapshot_helper_files() if install_shell else []
    backup_ts = create_backup(
        store_path,
        all_runtimes,
        selected_skills,
        orphaned_entries=orphaned_entries,
        launcher_entries=preinstall_launchers,
        helper_entries=preinstall_helpers,
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

    skills_dir = source_skills_root(repo_root)
    for name in selected_skills:
        src = skills_dir / name
        dst = store_path / name
        print(f"  {dim('->')} {name}")
        rsync_skill(src, dst, dry_run=dry_run, mirror=mirror)
    for rule in sync_skill_root_rules(skills_dir, store_path, dry_run=dry_run):
        print(f"  {dim('->')} {rule}")
    print()

    # --- Execute: staged control plane ---
    print(bold("Refreshing staged control plane..."))
    try:
        current_tools = refresh_current_tools(
            repo_root, shared_home, dry_run=dry_run, mirror=mirror
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"  {dim(_staged_sync_failure_detail(exc))}")
        err_line("could not refresh staged tools", "rerun `vibecrafted update`")
        return 1
    if current_tools is None:
        print(f"  {WARN} Source is not a full framework checkout; staged tools skipped")
    elif dry_run:
        print(f"  {dim('would sync')} {repo_root} -> {current_tools}")
    else:
        print(f"  {OK} {current_tools}")
    print()

    # --- Execute: symlink views ---
    print(bold("Linking agent views..."))
    for rt in all_runtimes:
        rt_skills = Path.home() / f".{rt}" / "skills"
        if not dry_run:
            rt_skills.mkdir(parents=True, exist_ok=True)
        print(f"  {cyan(rt)} -> {rt_skills}")
        for rule in sync_skill_root_rules(skills_dir, rt_skills, dry_run=dry_run):
            print(f"    {dim('->')} {rule}")
        for name in selected_skills:
            default = store_path / name
            link = rt_skills / name
            create_skill_view_symlink(default, link, dry_run=dry_run)
    for shadow in prune_shadowed_skill_views(
        store_path, selected_skills, all_runtimes, dry_run=dry_run
    ):
        print(f"  {dim('removed shadow')} {shadow}")
    print()

    # --- Execute: agent command surfaces ---
    print(bold("Installing agent commands..."))
    install_agent_commands(all_runtimes, dry_run=dry_run)
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

    # --- Prune old vetcoders-* skills ---
    prune_legacy_skills(
        store_path, all_runtimes, dry_run=dry_run, interactive=interactive
    )

    # --- Execute: clean compat and duplicate RC entries ---
    if write_shell_rc:
        for rcname in (".bashrc", ".zshrc"):
            rcfile = Path.home() / rcname
            if rcfile.exists():
                rc_content = rcfile.read_text()
                if not _is_writable(rcfile):
                    print(f"  {WARN} {rcfile} is locked — cannot clean old entries")
                    continue
                cleaned_rc, removed_rc = _clean_legacy_rc_entries(rc_content)
                if removed_rc > 0 and not dry_run:
                    rcfile.write_text(cleaned_rc)
                    print(f"  {OK} Cleaned {removed_rc} old entries from {rcname}")
                elif removed_rc > 0:
                    print(
                        f"  {dim('would clean')} {removed_rc} old entries from {rcname}"
                    )

    # --- Execute: shell helpers ---
    if install_shell:
        print(bold("Installing shell helper..."))
        shell_script = repo_root / "runtime" / "scripts" / "install-shell.sh"
        if shell_script.exists():
            shell_cmd = ["bash", str(shell_script), "--source", str(repo_root)]
            if write_shell_rc:
                shell_cmd.append("--write-rc")
            if dry_run:
                shell_cmd.append("--dry-run")
            subprocess.run(shell_cmd, check=False)
        else:
            print(f"  {WARN} Shell installer not found: {shell_script}")
        print()

    # --- Execute: vibecrafted launcher ---
    _install_launcher(repo_root, dry_run, update_rc=write_shell_rc)
    if current_tools is not None:
        moved_agency = cleanse_state_home_agency(current_tools, dry_run=dry_run)
        if moved_agency:
            print(f"  {OK} Moved {moved_agency} state-home agency payload(s)")
        else:
            print(f"  {OK} State home has no agency payloads to move")
        print()

    # --- Fix Gemini plan.directory if it points into .vibecrafted ---
    _configure_gemini_plans(dry_run)

    # --- Save state ---
    now = datetime.now(timezone.utc).isoformat()
    state = InstallState(
        installed_at=now,
        updated_at=now,
        framework_version=get_install_version(repo_root),
        repo_commit=get_repo_commit(repo_root),
        repo_url=get_repo_url(repo_root),
        skills=selected_skills,
        runtimes=all_runtimes,
        launcher_entries=_snapshot_launcher_entries(),
        helper_files=_snapshot_helper_files() if install_shell else [],
        foundations=installed_foundations,
        product_tools=snapshot_product_tool_state(),
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
        _pause_for_runtime_contract_failures(findings)
        guide_path = write_start_here_guide(store_path, state, findings)
        # Print only failures and warnings
        issues = [finding for finding in findings if finding.level != "ok"]
        if issues:
            for finding in issues:
                icon = WARN if finding.level == "warn" else MISS
                print(f"  {icon} {finding.component}: {finding.message}")
        else:
            print(f"  {OK} All checks passed")
        print(f"  {OK} Start-here guide saved to {guide_path}")
    print()

    # --- Done: compact one-screen summary ---
    _print_unicode_summary(repo_root, store_path, skills)
    return 0


def _uv_tool_shim() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "uv" / "tools" / "vibecrafted" / "bin" / "vibecrafted"


def _launcher_symlink_target(repo_root: Path) -> Path:
    """Resolve what ~/.local/bin/vibecrafted should point at.

    The uv-tool shim wins when it exists (full `make install` lane). A
    python-only install (CI skill-loader, bare `vetcoders_install.py install`)
    has no shim yet — pointing at it would leave a dangling launcher that
    doctor rightly fails. Fall back to the staged deck, then the source deck,
    so the installed launcher always executes.
    """
    shim = _uv_tool_shim()
    if shim.exists():
        return shim
    staged_deck = (
        vibecrafted_tools_home()
        / "vibecrafted-current"
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "deck"
        / "vibecrafted"
    )
    if staged_deck.exists():
        return staged_deck
    return repo_root / "scripts" / "vibecrafted"


def _install_launcher(repo_root: Path, dry_run: bool, update_rc: bool = False) -> None:
    """Install vibecrafted launcher to portable and compat bin surfaces."""
    launcher_src = repo_root / "scripts" / "vibecrafted"
    if launcher_src.exists():
        if not dry_run:
            legacy_redirect_src = repo_root / "scripts" / "vibecraft"
            canonical_bin_dir = vibecrafted_launcher_bin()
            canonical_bin_dir.mkdir(parents=True, exist_ok=True)
            canonical_launcher = canonical_bin_dir / "vibecrafted"

            # Target 1: the uv-tool shim wins ~/.local/bin/vibecrafted when it
            # exists; otherwise the staged/source deck keeps the launcher live
            # (see _launcher_symlink_target). Never copy the deck over the name.
            shim = _launcher_symlink_target(repo_root)
            if canonical_launcher.exists() or canonical_launcher.is_symlink():
                if canonical_launcher.is_symlink():
                    try:
                        link_target = Path(os.readlink(canonical_launcher))
                    except OSError:
                        link_target = Path("")
                    if link_target != shim:
                        canonical_launcher.unlink()
                        create_symlink(shim, canonical_launcher)
                else:
                    canonical_launcher.unlink()
                    create_symlink(shim, canonical_launcher)
            else:
                create_symlink(shim, canonical_launcher)

            canonical_legacy = canonical_bin_dir / "vibecraft"
            if legacy_redirect_src.exists():
                _copy_managed_launcher(legacy_redirect_src, canonical_legacy)

            for launcher_bin_dir in _launcher_bin_dirs():
                launcher_bin_dir.mkdir(parents=True, exist_ok=True)
                launcher_dst = launcher_bin_dir / "vibecrafted"
                if launcher_dst != canonical_launcher:
                    create_symlink(canonical_launcher, launcher_dst)
                for wrapper in LAUNCHER_WRAPPERS:
                    if wrapper in PYTHON_ENTRYPOINT_LAUNCHERS:
                        continue
                    create_symlink(Path("vibecrafted"), launcher_bin_dir / wrapper)
                # Replace old vibecraft binary with a thin redirect
                legacy_dst = launcher_bin_dir / "vibecraft"
                if legacy_redirect_src.exists() and legacy_dst != canonical_legacy:
                    create_symlink(canonical_legacy, legacy_dst)
        else:
            for launcher_bin_dir in _launcher_bin_dirs():
                shim = _launcher_symlink_target(repo_root)
                create_symlink(shim, launcher_bin_dir / "vibecrafted", dry_run=True)
                for wrapper in LAUNCHER_WRAPPERS:
                    if wrapper in PYTHON_ENTRYPOINT_LAUNCHERS:
                        continue
                    create_symlink(
                        Path("vibecrafted"), launcher_bin_dir / wrapper, dry_run=True
                    )
        # Ensure $HOME/.local/bin is in PATH via shell rc files only when the
        # caller has explicit consent. Otherwise leave a copyable instruction.
        canonical_path_line = _launcher_path_line()
        path_lines = [canonical_path_line, *_legacy_launcher_path_lines()]
        path_comment = "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher"
        if update_rc:
            for rcname in (".bashrc", ".zshrc"):
                rcfile = Path.home() / rcname
                if rcfile.exists():
                    content = rcfile.read_text()
                    cleaned = content
                    removed = 0
                    for path_line in path_lines:
                        cleaned, removed_now = _strip_rc_entry(
                            cleaned, path_line, path_comment
                        )
                        removed += removed_now
                    has_path = _rc_has_vibecrafted_bin_path(cleaned)
                    changed = removed > 0
                    if not has_path:
                        if cleaned and not cleaned.endswith("\n"):
                            cleaned += "\n"
                        cleaned += f"\n# {path_comment}\n{canonical_path_line}\n"
                        changed = True
                    if changed and not dry_run:
                        rcfile.write_text(cleaned)
        else:
            print("  Shell rc files unchanged. To expose launchers, add:")
            print(f"    {canonical_path_line}")
        print()


def _print_unicode_summary(
    repo_root: Path, store_path: Path, skills: list[Path], out=None
) -> None:
    """Print the unicode summary box. If out is given, write there instead of stdout."""
    _out = out or sys.stdout
    fw_ver_display = get_install_version(repo_root)
    skill_count = len(skills)
    current_runtime = _current_tools_link(store_path) / "runtime"

    def _agent_spawn_present(agent: str) -> bool:
        # Spawn scripts live in the staged control-plane runtime; the legacy
        # vc-agents store layout is kept only as a back-compat fallback.
        return (current_runtime / "scripts" / f"{agent}_spawn.sh").exists() or (
            store_path / "vc-agents" / "scripts" / f"{agent}_spawn.sh"
        ).exists()

    agent_list = " \u00b7 ".join(
        a for a in ("claude", "codex", "gemini") if _agent_spawn_present(a)
    )
    shell_str = _helper_surface_label()
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
        f"\u2713 Guide        {start_here_path()}",
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
    fw_ver = get_install_version(repo_root)

    shared_home = vibecrafted_home()
    store_path = _canonical_store_path(shared_home, create=not dry_run)
    log_path = shared_home / "install.log"

    # --- Discover skills (before redirecting stdout) ---
    skills = discover_skills(repo_root)
    if not skills:
        print(red("No skills found in repo."))
        return 1

    skill_names = [s.name for s in skills]
    selected_skills = list(skill_names)
    all_runtimes = list(STANDARD_VIEW_RUNTIMES)
    install_shell = cli_with_shell
    write_shell_rc = getattr(args, "write_shell_rc", False)
    installed_foundations: dict[str, dict] = {}

    # --- System check (critical deps — must fail visibly) ---
    sys_deps = detect_system_deps()
    missing_critical = [cmd for cmd in ("python3", "git") if not sys_deps.get(cmd)]
    if missing_critical:
        print(red(f"  Missing critical dependencies: {', '.join(missing_critical)}"))
        print("  Install them before continuing.")
        return 1

    # --- All verbose output goes to log; compact lines go to real stdout.
    # --debug tees the full transaction log onto stdout as well. ---
    debug = getattr(args, "debug", False)
    with compact_logging(log_path, quiet=not debug) as out:
        # Log header
        print(f"𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Installer v{fw_ver} — compact mode")
        print(f"Source: {repo_root}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print()
        _compact_checkpoint(
            out,
            1,
            "Introduction",
            (
                f"Source  {repo_root}",
                f"Log     {log_path}",
            ),
        )

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
            path, channel = install_or_find_foundation(f, repo_root, dry_run=dry_run)
            installed_foundations[f.name] = {
                "channel": channel,
                "path": path,
            }
            print(
                f"  {f.name}: {path or 'not installed'} [{channel}] {'(required)' if f.required else '(optional)'}"
            )
        print()
        detected_agents = [
            rt for rt in ("claude", "codex", "gemini") if available_runtimes.get(rt)
        ]
        _compact_checkpoint(
            out,
            2,
            "Diagnostics and Plan",
            (
                f"Plan   {len(selected_skills)} skills · agents {', '.join(detected_agents) or 'none'} · shell {'on' if install_shell else 'off'}",
                f"Into   {store_path}",
            ),
        )

        # Backup
        print("Backup:")
        _compact_checkpoint(out, 3, "Installation")
        orphaned_entries = collect_orphaned_skills(
            store_path, all_runtimes, set(selected_skills)
        )
        preinstall_launchers = _snapshot_launcher_entries()
        preinstall_helpers = _snapshot_helper_files() if install_shell else []
        backup_ts = create_backup(
            store_path,
            all_runtimes,
            selected_skills,
            orphaned_entries=orphaned_entries,
            launcher_entries=preinstall_launchers,
            helper_entries=preinstall_helpers,
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
        skills_dir = source_skills_root(repo_root)
        # One live counter line (§6.6), per-skill detail stays in the log.
        total_skills = len(selected_skills)
        for idx, name in enumerate(selected_skills, 1):
            src = skills_dir / name
            dst = store_path / name
            print(f"  -> {name}")
            if _compact_status_is_live(out):
                frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
                _compact_line(
                    out, dim(frame), "Skills", f"installing {idx}/{total_skills}"
                )
            rsync_skill(src, dst, dry_run=dry_run, mirror=mirror)
        for rule in sync_skill_root_rules(skills_dir, store_path, dry_run=dry_run):
            print(f"  -> {rule}")
        print()

        print("Refreshing staged control plane:")
        try:
            current_tools = refresh_current_tools(
                repo_root, shared_home, dry_run=dry_run, mirror=mirror
            )
        except (
            OSError,
            subprocess.CalledProcessError,
            DistributionManifestError,
        ) as exc:
            print(f"  FAILED: {_staged_sync_failure_detail(exc)}")
            _clear_compact_status(out)
            err_line(
                "could not refresh staged tools",
                "rerun `vibecrafted update`",
                str(log_path),
            )
            return 1
        if current_tools is None:
            print("  skipped: source is not a full framework checkout")
            _compact_line(out, WARN, "Tools", "staged control plane skipped")
        elif dry_run:
            print(f"  would sync: {repo_root} -> {current_tools}")
            _compact_line(out, SKIP, "Tools", "dry run")
        else:
            print(f"  synced: {repo_root} -> {current_tools}")
            _compact_line(out, green("\u2713"), "Tools", "staged current refreshed")
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
            for rule in sync_skill_root_rules(skills_dir, rt_skills, dry_run=dry_run):
                print(f"    -> {rule}")
            for name in selected_skills:
                default = store_path / name
                link = rt_skills / name
                create_skill_view_symlink(default, link, dry_run=dry_run)
        for shadow in prune_shadowed_skill_views(
            store_path, selected_skills, all_runtimes, dry_run=dry_run
        ):
            print(f"  removed shadow: {shadow}")
        print()

        print("Installing agent commands:")
        install_agent_commands(all_runtimes, dry_run=dry_run)
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

        # Clean compat RC entries only after explicit rc-write consent.
        if write_shell_rc:
            for rcname in (".bashrc", ".zshrc"):
                rcfile = Path.home() / rcname
                if rcfile.exists():
                    rc_content = rcfile.read_text()
                    if not _is_writable(rcfile):
                        continue
                    cleaned_rc, removed_rc = _clean_legacy_rc_entries(rc_content)
                    if removed_rc > 0 and not dry_run:
                        rcfile.write_text(cleaned_rc)

        # Shell helpers
        if install_shell:
            print("Installing shell helper:")
            shell_script = repo_root / "runtime" / "scripts" / "install-shell.sh"
            if shell_script.exists():
                shell_cmd = ["bash", str(shell_script), "--source", str(repo_root)]
                if write_shell_rc:
                    shell_cmd.append("--write-rc")
                if dry_run:
                    shell_cmd.append("--dry-run")
                result = subprocess.run(
                    shell_cmd, capture_output=True, text=True, check=False
                )
                # Log the shell installer output
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            else:
                print(f"  Shell installer not found: {shell_script}")
            print()

        _compact_line(
            out,
            green("\u2713"),
            "Helpers",
            _helper_surface_label(),
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
        _install_launcher(repo_root, dry_run, update_rc=write_shell_rc)
        if current_tools is not None:
            moved_agency = cleanse_state_home_agency(current_tools, dry_run=dry_run)
            print(f"  state agency moved: {moved_agency}")
            _compact_line(
                out,
                green("\u2713"),
                "State home",
                "agency-free" if not moved_agency else f"moved {moved_agency}",
            )

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
            launcher_entries=_snapshot_launcher_entries(),
            helper_files=_snapshot_helper_files() if install_shell else [],
            foundations=installed_foundations,
            product_tools=snapshot_product_tool_state(),
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
            _pause_for_runtime_contract_failures(findings)
            guide_path = write_start_here_guide(store_path, state, findings)
            issues = [finding for finding in findings if finding.level != "ok"]
            if issues:
                for finding in issues:
                    print(f"  [{finding.level}] {finding.component}: {finding.message}")
                # Surface critical issues on compact output too
                critical = [finding for finding in issues if finding.level == "fail"]
                if critical:
                    _clear_compact_status(out)
                    err_line(
                        "install verification found failures",
                        "vibecrafted doctor",
                        str(log_path),
                    )
            else:
                print("  All checks passed")
            print(f"  Start-here guide: {guide_path}")
        print()

    # --- Finish card (CLI_PRODUCT_SPEC §6.1): result, key facts, one next step. ---
    _clear_compact_status(sys.stdout)
    _compact_checkpoint(sys.stdout, 4, "Onboarding")
    fw_ver_display = get_install_version(repo_root)
    store_display = str(vibecrafted_home()).replace(str(Path.home()), "~")
    agent_str = " ".join(agent_names) if agent_names else "none"
    missing_fnd = [f for f in FOUNDATIONS if f.required and not f.is_installed()]

    # NB: keep the unicode escapes OUT of f-string expression parts \u2014 a
    # backslash inside `{...}` is a SyntaxError on Python < 3.12, and this
    # project supports >=3.11. Build the pieces first, then interpolate.
    check_mark = green("\u2713")
    product_banner = bold(
        f"\U0001d685\U0001d692\U0001d68b\U0001d68e\U0001d68c\U0001d69b\U0001d68a"
        f"\U0001d68f\U0001d69d\U0001d68e\U0001d68d. {fw_ver_display} installed"
    )
    print()
    print(f"  {check_mark} {product_banner}")
    print()
    print(
        f"    skills {len(selected_skills)} \u00b7 agents {agent_str} \u00b7 store {store_display}"
    )
    if missing_fnd:
        names = " · ".join(f.name for f in missing_fnd)
        print(f"    {WARN} foundations missing: {names} — vibecrafted doctor")
    print()
    print(f"    → {cyan('vibecrafted init claude')}       {dim('start here')}")
    print(f"    → {cyan('vibecrafted doctor')}            {dim('verify')}")
    print()

    return 0


def cmd_install(args: argparse.Namespace) -> int:
    repo_root = Path(args.source).resolve()
    if not repo_root.is_dir():
        err_line(f"repo root not found: {repo_root}")
        return 1

    # Strict modes (CLI_PRODUCT_SPEC §3.5): compact is the default; --verbose
    # restores the per-step narration; --compact is retired (silent no-op).
    # An attended TTY without --non-interactive keeps the consent wizard,
    # which lives in the verbose flow.
    verbose = getattr(args, "verbose", False) or getattr(args, "advanced", False)
    interactive = _IS_TTY and not args.non_interactive

    if verbose or interactive:
        return _cmd_install_verbose(args, repo_root)
    return _cmd_install_compact(args, repo_root)


# ---------------------------------------------------------------------------
# Subcommand: doctor
# ---------------------------------------------------------------------------


def _known_bundle_names() -> list[str]:
    """Skill names this installer manages. Used to scope doctor checks."""
    # Try to discover from repo checkout next to this script
    script_dir = Path(__file__).resolve().parent
    repo_candidate = script_dir.parent
    if (repo_candidate / ".git").is_dir():
        return [s.name for s in discover_skills(repo_candidate)]
    return []


def cmd_doctor(args: argparse.Namespace) -> int:
    shared_home = vibecrafted_home()
    store_path = _canonical_store_path(shared_home)
    state = _load_install_state(store_path)
    has_manifest = bool(state.skills)

    if getattr(args, "fix_rc", False):
        for finding in _doctor_fix_rc_files():
            icon = OK if finding.level == "ok" else WARN
            print(f"  {icon} {finding.component}: {finding.message}")
    if getattr(args, "fix_launchers", False):
        for finding in _doctor_fix_launchers(store_path, state):
            icon = OK if finding.level == "ok" else WARN
            print(f"  {icon} {finding.component}: {finding.message}")
    if getattr(args, "fix_legacy_bootstrap", False):
        for finding in _doctor_fix_legacy_bootstrap():
            icon = OK if finding.level == "ok" else WARN
            print(f"  {icon} {finding.component}: {finding.message}")

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
            if (
                entry.name.startswith("vc-")
                and entry.name not in bundle
                and (entry / "SKILL.md").exists()
            ):
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

    guide_path = write_start_here_guide(store_path, state, findings)
    exit_code = print_doctor(
        findings, guide_path=guide_path, verbose=getattr(args, "verbose", False)
    )
    _pause_for_runtime_contract_failures(findings)
    return exit_code


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

    print(f"\n{bold('𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Skills Bundle')}")
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
# Subcommand: layout
# ---------------------------------------------------------------------------


def cmd_layout(args: argparse.Namespace) -> int:
    store_path = vibecrafted_home() / "skills"
    action = getattr(args, "action", "status")
    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)

    if action == "status":
        status = layout_status(store_path)
        print(f"\n{bold('Vibecrafted layout transfer status')}\n")
        print(
            f"  legacy:  {status['legacy']} ({'exists' if status['legacy_exists'] else 'missing'})"
        )
        print(
            f"  current: {status['current']} ({'exists' if status['current_exists'] else 'missing'})"
        )
        if status["last_transfer"]:
            last = status["last_transfer"]
            print(
                "  last:    "
                f"{last.get('direction', 'unknown')} "
                f"{last.get('status', 'unknown')} "
                f"{last.get('updated_at', '')}"
            )
        else:
            print("  last:    none")
        print()
        return 0

    direction = {
        "migrate": "legacy-to-new",
        "rollback": "new-to-legacy",
    }.get(action)
    if direction is None:
        print(red(f"Unknown layout action: {action}"))
        return 1

    exit_code, result = transfer_agents_layout(
        store_path,
        direction=direction,
        dry_run=dry_run,
        force=force,
    )
    source = result["source"]
    target = result["target"]
    conflicts = result.get("conflicts") or []
    if exit_code == 0:
        copied = result.get("copied") or []
        verb = "would transfer" if dry_run else "transferred"
        print(f"{OK} layout {verb} {len(copied)} files")
        print(f"  from: {source}")
        print(f"  to:   {target}")
        return 0

    print(f"{WARN} layout transfer blocked")
    print(f"  from: {source}")
    print(f"  to:   {target}")
    for conflict in conflicts:
        print(f"  conflict: {conflict}")
    if conflicts and not force:
        print(dim("  Re-run with --force only if this target is Vibecrafted-managed."))
    return 1


# ---------------------------------------------------------------------------
# Subcommand: uninstall
# ---------------------------------------------------------------------------


def _managed_tools_entry(path: Path) -> bool:
    return (
        path.name == "vibecrafted-current"
        or path.name.startswith("vibecrafted-")
        or path.name.startswith(".incoming-")
    )


def _build_uninstall_inventory(
    *,
    shared_home: Path,
    store_path: Path,
    state_file: Path,
    skill_names: Sequence[str],
    runtimes: Sequence[str],
    helper_paths: Sequence[Path],
    launchers: Sequence[tuple[Path, Path]],
    rc_cleanup_targets: Sequence[Path],
) -> list[ManagedPath]:
    records: list[ManagedPath] = []
    seen: dict[str, int] = {}

    def add(kind: str, path: Path, action: str = "remove", reason: str = "") -> None:
        normalized = path.expanduser()
        if action != "remove-if-empty" and not _path_present(normalized):
            return
        key = str(normalized)
        existing = seen.get(key)
        if existing is not None:
            if records[existing].action == "preserve" and action != "preserve":
                records[existing] = ManagedPath(kind, normalized, action, reason)
            return
        seen[key] = len(records)
        records.append(ManagedPath(kind, normalized, action, reason))

    resolved_store = store_path.resolve(strict=False)
    managed_tools_root = vibecrafted_tools_home().resolve(strict=False)
    legacy_store_root = (shared_home / "skills").resolve(strict=False)
    store_is_managed = _is_subpath(resolved_store, managed_tools_root) or _is_subpath(
        resolved_store, legacy_store_root
    )
    if store_is_managed:
        for name in skill_names:
            add("shared-skill", store_path / name)
        add("install-state", state_file)
    elif _path_present(store_path):
        add(
            "external-store",
            resolved_store,
            "preserve",
            "current link resolves outside the managed tools root",
        )
    for runtime in runtimes:
        runtime_skills = Path.home() / f".{runtime}" / "skills"
        for name in skill_names:
            add("agent-view", runtime_skills / name)
    for helper in helper_paths:
        add("shell-helper", helper)
    for _launcher_dir, launcher in launchers:
        add("launcher", launcher)
    for rcfile in rc_cleanup_targets:
        add("shell-rc", rcfile, "edit", "remove Vibecrafted-managed lines only")

    add("install-log", shared_home / "install.log")
    add("start-guide", start_here_path())

    tools_roots = [vibecrafted_tools_home(), shared_home / "tools"]
    unique_tools_roots: list[Path] = []
    for tools_root in tools_roots:
        if tools_root in unique_tools_roots:
            continue
        unique_tools_roots.append(tools_root)
        if tools_root.is_dir():
            for entry in sorted(tools_root.iterdir(), key=lambda item: item.name):
                if _managed_tools_entry(entry):
                    add("staged-payload", entry)
                else:
                    add(
                        "tools-sibling",
                        entry,
                        "preserve",
                        "not a Vibecrafted-managed payload name",
                    )
            add(
                "tools-root",
                tools_root,
                "remove-if-empty",
                "shared parent remains when unrelated entries exist",
            )

    runtime_bin = vibecrafted_runtime_bin()
    if runtime_bin.is_dir():
        children = sorted(runtime_bin.iterdir(), key=lambda item: item.name)
        if children:
            for child in children:
                add(
                    "runtime-bin",
                    child,
                    "preserve",
                    "binary ownership is product-managed outside installer state",
                )
        else:
            add("runtime-bin", runtime_bin, "preserve", "empty runtime binary root")

    runtime_home = vibecrafted_runtime_home()
    if runtime_home.is_dir():
        for child in sorted(runtime_home.iterdir(), key=lambda item: item.name):
            if child in {vibecrafted_tools_home(), runtime_bin}:
                continue
            add(
                "runtime-data",
                child,
                "preserve",
                "runtime data is not proven installer-owned",
            )

    uv_tools_root = Path(
        os.environ.get("UV_TOOL_DIR", str(xdg_data_home() / "uv" / "tools"))
    ).expanduser()
    for name in ("vibecrafted", "vibecrafted-core", "vibecrafted-mcp"):
        add(
            "uv-tool",
            uv_tools_root / name,
            "preserve",
            "uv owns this environment; remove it with `uv tool uninstall`",
        )

    for name in ("artifacts", "control_plane", "logs"):
        add(
            "operator-data",
            shared_home / name,
            "preserve",
            "operator history/data is retained intentionally",
        )
    return records


def _print_uninstall_inventory(inventory: Sequence[ManagedPath]) -> None:
    print(bold("Managed teardown inventory:"))
    for record in inventory:
        verb = {
            "remove": "remove",
            "edit": "edit",
            "remove-if-empty": "remove if empty",
            "preserve": "preserve",
        }[record.action]
        suffix = f" — {record.reason}" if record.reason else ""
        print(f"  {verb:15} {record.kind}: {record.path}{suffix}")
    print()


def _edit_rc_file(record: ManagedPath, *, dry_run: bool) -> tuple[bool, str]:
    rcfile = record.path
    if not _is_writable(rcfile):
        return False, "locked; launcher/source hints remain"
    content = rcfile.read_text(encoding="utf-8")
    changed = False
    for line, comment in _uninstall_rc_entries():
        content, removed = _strip_rc_entry(content, line, comment)
        changed = changed or removed > 0
    if changed and not dry_run:
        rcfile.write_text(content, encoding="utf-8")
    return changed, ""


def _apply_uninstall_inventory(
    inventory: Sequence[ManagedPath], *, dry_run: bool
) -> tuple[list[ManagedPath], list[ManagedPath], list[str]]:
    applied: list[ManagedPath] = []
    preserved = [record for record in inventory if record.action == "preserve"]
    failures: list[str] = []

    removals = sorted(
        (record for record in inventory if record.action == "remove"),
        key=lambda item: (-len(item.path.parts), str(item.path)),
    )
    for record in removals:
        if not _path_present(record.path):
            continue
        if dry_run:
            applied.append(record)
            continue
        try:
            _remove_path(record.path)
            applied.append(record)
        except OSError as exc:
            failures.append(f"{record.path}: {exc}")

    for record in (item for item in inventory if item.action == "edit"):
        try:
            changed, reason = _edit_rc_file(record, dry_run=dry_run)
        except OSError as exc:
            failures.append(f"{record.path}: {exc}")
            continue
        if changed:
            applied.append(record)
        elif reason:
            preserved.append(ManagedPath(record.kind, record.path, "preserve", reason))

    for record in (item for item in inventory if item.action == "remove-if-empty"):
        if not record.path.is_dir():
            continue
        try:
            is_empty = not any(record.path.iterdir())
            if not is_empty:
                preserved.append(
                    ManagedPath(
                        record.kind,
                        record.path,
                        "preserve",
                        "contains intentionally preserved or unrelated entries",
                    )
                )
            elif dry_run:
                applied.append(record)
            else:
                record.path.rmdir()
                applied.append(record)
        except OSError as exc:
            failures.append(f"{record.path}: {exc}")
    return applied, preserved, failures


def cmd_uninstall(args: argparse.Namespace) -> int:
    shared_home = vibecrafted_home()
    store_path = _canonical_store_path(shared_home)
    state = _load_install_state(store_path)
    state_file = store_path / STATE_FILE
    dry_run = args.dry_run
    bundle = set(_known_bundle_names())
    helper_file = _helper_target_path()
    legacy_file = _helper_legacy_path()
    has_state = state_file.exists()

    # Default to manifest-tracked files for restore-safe uninstall;
    # fall back to discovery heuristics only when we don't have installer state.
    if state.helper_files:
        helper_paths = [Path(p) for p in state.helper_files if Path(p).exists()]
    elif has_state and not (state.skills or state.runtimes or state.launcher_entries):
        helper_paths = []
    else:
        helper_paths = [hf for hf in (helper_file, legacy_file) if hf.exists()]

    if state.launcher_entries:
        launchers = _parse_manifest_launchers(state.launcher_entries)
    else:
        launchers = collect_installed_launchers()

    rc_cleanup_targets = [
        Path.home() / rcname
        for rcname in (".zshrc", ".bashrc")
        if _rc_has_framework_install_hints(Path.home() / rcname)
    ]

    # Use manifest if available, otherwise use bundle names
    skill_names = state.skills if has_state else [n for n in bundle]
    runtimes = (
        state.runtimes
        if has_state
        else [rt for rt in SYMLINK_TARGET_CHOICES if runtime_skills_dir(rt).exists()]
    )

    inventory = _build_uninstall_inventory(
        shared_home=shared_home,
        store_path=store_path,
        state_file=state_file,
        skill_names=skill_names,
        runtimes=runtimes,
        helper_paths=helper_paths,
        launchers=launchers,
        rc_cleanup_targets=rc_cleanup_targets,
    )
    has_work = any(
        record.action in {"remove", "edit"}
        or (
            record.action == "remove-if-empty"
            and record.path.is_dir()
            and not any(record.path.iterdir())
        )
        for record in inventory
    )

    print(f"\n{bold('𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Uninstall')}\n")

    if not has_work:
        print(
            dim(
                "Nothing to uninstall — no managed payloads, skills, launchers, helpers, or shell hooks found."
            )
        )
        preserved = [record for record in inventory if record.action == "preserve"]
        if preserved:
            print("  Preserved intentionally:")
            for record in preserved:
                print(f"    {record.path} — {record.reason}")
        print()
        return 0

    _print_uninstall_inventory(inventory)

    if _IS_TTY and not dry_run:
        if not ask_yn("Remove the installed 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. bundle?", default=False):
            print("Uninstall cancelled.")
            return 0
        print()

    backup_ts = None
    if not dry_run:
        print(bold("Saving external restore kit..."))
        backup_ts = create_teardown_backup(inventory)
        if backup_ts:
            print(f"  {OK} {_backup_root(store_path) / backup_ts}")
        print()

    applied, preserved, failures = _apply_uninstall_inventory(
        inventory, dry_run=dry_run
    )
    if dry_run:
        print("Would remove or edit:")
        for record in applied:
            print(f"  {record.kind}: {record.path}")
        if preserved:
            print("Preserved intentionally:")
            for record in preserved:
                print(f"  {record.kind}: {record.path} — {record.reason}")
        print()
        return 0

    if failures:
        print(red(bold("Uninstall incomplete.")))
        for failure in failures:
            print(f"  {failure}")
        if backup_ts:
            print(f"  Restore with: {_restore_command(backup_ts)}")
        print()
        return 1

    print(green(bold("Removed managed paths:")))
    for record in applied:
        print(f"  {record.kind}: {record.path}")
    if preserved:
        print("Preserved intentionally:")
        for record in preserved:
            print(f"  {record.kind}: {record.path} — {record.reason}")
    if backup_ts:
        backup_path = _backup_root(store_path) / backup_ts
        print(f"Backup preserved: {backup_path}")
        print("Restore:")
        print(f"  {_restore_command(backup_ts)}")
    print(green(bold("Uninstall complete.")))
    print()
    return 0


# ---------------------------------------------------------------------------
# Subcommand: restore
# ---------------------------------------------------------------------------


def cmd_restore(args: argparse.Namespace) -> int:
    shared_home = vibecrafted_home()
    store_path = _canonical_store_path(shared_home)
    dry_run = args.dry_run
    backup_root = _backup_root(store_path)

    print(f"\n{bold('𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Restore')}\n")

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

    teardown_manifest = backup_dir / RESTORE_MANIFEST_FILE
    teardown_restore = backup_dir / RESTORE_SCRIPT_FILE
    if teardown_manifest.is_file() and teardown_restore.is_file():
        manifest = json.loads(teardown_manifest.read_text(encoding="utf-8"))
        if dry_run:
            for item in manifest.get("items", []):
                print(f"  {dim('restore')} {item.get('path', '')}")
            print()
            return 0
        result = subprocess.run([sys.executable, str(teardown_restore)], check=False)
        return result.returncode

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
        # Try new name first, then compat path
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

    launcher_backup = backup_dir / "launchers"
    if launcher_backup.is_dir():
        print(bold("Restoring launcher commands..."))
        for key_dir in sorted(launcher_backup.iterdir()):
            if not key_dir.is_dir():
                continue
            launcher_bin_dir = _launcher_dir_from_key(key_dir.name)
            if launcher_bin_dir is None:
                print(f"  {WARN} Unknown launcher backup target: {key_dir.name}")
                continue
            launcher_bin_dir.mkdir(parents=True, exist_ok=True)
            for entry in sorted(key_dir.iterdir()):
                if not (entry.is_dir() or entry.is_symlink() or entry.is_file()):
                    continue
                dst = launcher_bin_dir / entry.name
                if dry_run:
                    print(f"  {dim('restore')} {dst}")
                else:
                    _restore_path_from_backup(entry, dst)
                    if dst.is_file() and not dst.is_symlink():
                        dst.chmod(0o755)
                    print(f"  {OK} {dst}")
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


def main(argv: Sequence[str] | None = None) -> int:
    default_source = detect_repo_root()

    parser = argparse.ArgumentParser(
        prog="vc-install",
        description="𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. installer — the founders' framework for shipping software with AI agents.",
    )
    sub = parser.add_subparsers(dest="command")

    # install
    p_install = sub.add_parser(
        "install", help="Install the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework bundle"
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
        "--write-shell-rc",
        action="store_true",
        help="Opt in to writing helper/PATH lines to shell rc files",
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
        help=(
            "Delete extra files in installed skill dirs and staged tools "
            "(rsync --delete)"
        ),
    )
    p_install.add_argument(
        "--compact",
        action="store_true",
        help=argparse.SUPPRESS,  # retired: compact is the default (kept as no-op)
    )
    p_install.add_argument(
        "--verbose",
        action="store_true",
        help="Per-step narration on stdout instead of the compact view",
    )
    p_install.add_argument(
        "--debug",
        action="store_true",
        help="Raw subprocess output on stdout (everything the log gets)",
    )

    # doctor
    p_doctor = sub.add_parser("doctor", help="Verify installation health")
    p_doctor.add_argument(
        "--verbose",
        action="store_true",
        help="List every check, including passing ones",
    )
    p_doctor.add_argument(
        "--fix-rc",
        action="store_true",
        help="Repair old shell startup lines and restore default helper/PATH hints before verifying",
    )
    p_doctor.add_argument(
        "--fix-launchers",
        action="store_true",
        help="Refresh vibecrafted, vc-help, and vc-* wrappers from the installed/current source before verifying",
    )
    p_doctor.add_argument(
        "--fix-legacy-bootstrap",
        action="store_true",
        help="Neutralize retired /opt/vibecrafted bootstrap roots: comment out VIBECRAFTED_ROOT exports in shell rc files (with backup) and report the leftover tree — never deletes it",
    )

    # list
    p_list = sub.add_parser(
        "list",
        help="Show available 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. skills and the runtime substrate beneath them",
    )
    p_list.add_argument(
        "--source", default=default_source, help="Repo root (default: auto-detect)"
    )

    # layout transfer
    p_layout = sub.add_parser(
        "layout",
        help="Transfer agent runtime payload between legacy and current install layouts",
    )
    p_layout.add_argument(
        "action",
        choices=("status", "migrate", "rollback"),
        nargs="?",
        default="status",
        help="status, migrate legacy->current, or rollback current->legacy",
    )
    p_layout.add_argument(
        "--dry-run", "-n", action="store_true", help="Show what would be done"
    )
    p_layout.add_argument(
        "--force",
        action="store_true",
        help="Overwrite conflicting target files; only use for Vibecrafted-managed payload",
    )

    # uninstall
    p_uninstall = sub.add_parser(
        "uninstall", help="Remove 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. skills, views, launchers, and helpers"
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
    elif args.command == "layout":
        return cmd_layout(args)
    elif args.command == "uninstall":
        return cmd_uninstall(args)
    elif args.command == "restore":
        return cmd_restore(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
