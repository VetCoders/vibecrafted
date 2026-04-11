"""Sequential trust-building installer runner.

Reads an ``install.toml`` manifest describing a sequence of install phases,
and replays each one with:

    • a per-phase reason block (trust-building)
    • an explicit consent prompt
    • cargo/uv-style sticky bottom progress during execution
    • optionally: streamed subprocess output above the bar (`--verbose`)
    • a curated summary at the end

Universal: works for Python/Rust/any repo because it only orchestrates
subprocess commands declared in the manifest. It never knows what the
commands do.

Distribution:
    uv tool install ~/Libraxis/vetcoders-tools/installer --force

Usage:
    vetcoders-installer install.toml
    vetcoders-installer install.toml --yes
    vetcoders-installer install.toml --dry-run
    vetcoders-installer install.toml --verbose
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    HAS_RICH = True
except ModuleNotFoundError:  # pragma: no cover - soft fallback path
    HAS_RICH = False


__version__ = "0.1.0"
TOOL_NAME = "vetcoders-installer"


# ---------------------------------------------------------------------------
# Manifest model
# ---------------------------------------------------------------------------


@dataclass
class Phase:
    key: str
    label: str
    reason: str
    cmd: list[str]
    cwd: Path
    optional: bool = False

    @property
    def reason_lines(self) -> list[str]:
        return [ln.rstrip() for ln in self.reason.strip().splitlines()]

    def matches(self, name: str) -> bool:
        name = name.lower()
        return name == self.key.lower() or name == self.label.lower()


@dataclass
class Manifest:
    title: str
    version: str
    log_pattern: Optional[str]
    persist: bool
    phases: list[Phase]
    path: Path

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        raw = path.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
        repo_root = path.parent.resolve()

        title = str(data.get("title", "Installer"))
        version = _resolve_version(data, repo_root)
        log_pattern = data.get("log")
        persist = bool(data.get("persist", False))

        phases_data = data.get("phase", [])
        if not isinstance(phases_data, list):
            raise ValueError("install.toml: [[phase]] must be an array of tables")

        phases: list[Phase] = []
        for i, pd in enumerate(phases_data):
            label = str(pd.get("label", f"Phase {i + 1}"))
            key = str(
                pd.get("key") or label.lower().replace(" ", "_").replace("&", "and")
            )
            reason = str(pd.get("reason", ""))
            cmd = pd.get("cmd")
            if not cmd or not isinstance(cmd, list):
                raise ValueError(f"install.toml: phase '{label}' has no 'cmd' (list)")
            cwd_raw = pd.get("cwd")
            cwd = (repo_root / cwd_raw).resolve() if cwd_raw else repo_root
            phases.append(
                Phase(
                    key=key,
                    label=label,
                    reason=reason,
                    cmd=[str(x) for x in cmd],
                    cwd=cwd,
                    optional=bool(pd.get("optional", False)),
                )
            )

        return cls(
            title=title,
            version=version,
            log_pattern=log_pattern,
            persist=persist,
            phases=phases,
            path=path.resolve(),
        )


def _resolve_version(data: dict[str, Any], repo_root: Path) -> str:
    """Extract version from explicit value, VERSION file, or regex over a file."""
    if "version" in data:
        return str(data["version"])
    version_file = data.get("version_file")
    if not version_file:
        return ""
    vf_path = (repo_root / version_file).resolve()
    if not vf_path.exists():
        return ""
    content = vf_path.read_text(encoding="utf-8")
    pattern = data.get("version_pattern")
    if pattern:
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1)
        return ""
    # No pattern: take the first non-empty line.
    for line in content.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


# ---------------------------------------------------------------------------
# Console abstraction — Rich when available, plain fallback otherwise
# ---------------------------------------------------------------------------


class _PlainConsole:
    """Minimal drop-in for rich.console.Console when rich is unavailable."""

    def print(self, *args: Any, **_kwargs: Any) -> None:  # noqa: D401
        msg = " ".join(str(a) for a in args)
        msg = re.sub(r"\[/?[a-zA-Z0-9 #_]+\]", "", msg)
        print(msg)

    def rule(self, title: str = "", **_kwargs: Any) -> None:
        cleaned = re.sub(r"\[/?[a-zA-Z0-9 #_]+\]", "", title)
        bar = "─" * max(4, 60 - len(cleaned) - 2)
        print(f"\n── {cleaned} {bar}" if cleaned else "\n" + ("─" * 60))


def _make_console() -> Any:
    return Console() if HAS_RICH else _PlainConsole()


def _line_style(line: str) -> str:
    """Heuristic dim colour for streamed subprocess output lines."""
    stripped = line.lstrip()
    low = stripped.lower()
    if stripped.startswith(("✓", "✔", "[ok]")) or low.startswith(("ok ", "ok:")):
        return "dim green"
    if stripped.startswith(("✗", "✘", "[fail]", "[error]")) or low.startswith(
        ("error", "fail", "fatal")
    ):
        return "dim red"
    if stripped.startswith(("[warn]", "[warning]")) or low.startswith(
        ("warn", "warning")
    ):
        return "dim yellow"
    return "dim"


# ---------------------------------------------------------------------------
# Consent prompt
# ---------------------------------------------------------------------------


def consent(console: Any, label: str, optional: bool, auto_yes: bool) -> str:
    """Return one of 'yes', 'skip', 'quit'.

    Uses ``console.input()`` when Rich is available — it pauses the Live
    display (Progress bar) automatically while the prompt is shown, so the
    consent line never collides with the sticky bar renderer.
    """
    if auto_yes:
        return "yes"

    if optional:
        hint = "Enter=yes, s=skip, q=quit"
    else:
        hint = "Enter=yes, n/q=cancel"

    # Leading newline separates the consent prompt from whatever Rich just
    # rendered (typically the sticky progress bar), so the question never
    # sits flush against the bar.
    prompt_plain = f"\n   {hint}  ❯ Apply {label}? "
    prompt_rich = f"\n   [dim]{hint}[/]  [bold]❯[/] Apply {label}? "

    try:
        if HAS_RICH and hasattr(console, "input"):
            raw = console.input(prompt_rich).strip().lower()
        else:
            raw = input(prompt_plain).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "quit"

    if raw in ("", "y", "yes"):
        return "yes"
    if raw in ("s", "skip") and optional:
        return "skip"
    if raw in ("n", "no", "q", "quit"):
        return "quit"
    # Unknown → treat as yes (default) to stay out of the user's way
    return "yes"


# ---------------------------------------------------------------------------
# Phase runner
# ---------------------------------------------------------------------------


def run_phase(
    console: Any,
    phase: Phase,
    progress: Any,
    task_id: Any,
    log_handle: Optional[Any],
    verbose: bool,
) -> int:
    """Execute one phase; stream stdout to progress 'cur' field + optional history.

    Returns the subprocess exit code.
    """
    if HAS_RICH and progress is not None:
        progress.update(task_id, cur="starting…")

    try:
        proc = subprocess.Popen(
            phase.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(phase.cwd),
        )
    except FileNotFoundError as exc:
        console.print(f"  [red]✗ command not found: {exc}[/]")
        return 127

    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        if not line:
            continue

        if log_handle is not None:
            log_handle.write(raw)
            log_handle.flush()

        if HAS_RICH and progress is not None:
            progress.update(task_id, cur=line[-72:])

        if verbose:
            style = _line_style(line)
            console.print(f"  [{style}]{line}[/]")

    proc.wait()
    return proc.returncode


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------


def _print_title(console: Any, manifest: Manifest) -> None:
    if manifest.version:
        title = f"{manifest.title} v{manifest.version}"
    else:
        title = manifest.title
    console.print()
    console.print(f"[bold yellow]{title}[/]")
    console.print()


def _print_reason_block(console: Any, phase: Phase) -> None:
    console.print(
        f"[bold cyan]{phase.label}[/]"
        + (" [dim](optional)[/]" if phase.optional else "")
    )
    console.print()
    for line in phase.reason_lines:
        console.print(f"  [dim]{line}[/]")
    console.print()


def _print_summary(
    console: Any,
    manifest: Manifest,
    results: list[tuple[str, str, int]],
    log_path: Optional[Path],
) -> None:
    if not results:
        return
    console.rule("[dim]summary[/]")
    widest = max(len(label) for label, _, _ in results)
    for label, state, _rc in results:
        if state == "ok":
            icon = "[green]✓[/]"
        elif state.startswith("warn"):
            icon = "[yellow]![/]"
        elif state in ("skipped", "cancelled"):
            icon = "[yellow]·[/]"
        else:
            icon = "[red]✗[/]"
        console.print(f"  {icon} {label:<{widest}}  [dim]{state}[/]")
    console.print()
    if log_path:
        console.print(f"  [dim]Log: {log_path}[/]")


def _print_cleanup_notice(console: Any, manifest: Manifest, cleanup_flag: bool) -> None:
    """Tell the user whether the tool will persist or how to remove it."""
    if manifest.persist:
        console.print(
            "  [dim]Installer tool stays installed (manifest: persist=true).[/]"
        )
        return
    if cleanup_flag:
        return  # handled via execvp in main()
    console.print()
    console.print(
        "  [dim]This manifest does not require the installer tool to persist.[/]"
    )
    console.print(f"  [dim]Remove it with:[/] [bold]uv tool uninstall {TOOL_NAME}[/]")


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _open_log(manifest: Manifest) -> tuple[Optional[Path], Optional[Any]]:
    if not manifest.log_pattern:
        return None, None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    expanded = os.path.expanduser(manifest.log_pattern.format(ts=ts))
    log_path = Path(expanded)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path, open(log_path, "w", encoding="utf-8", buffering=1)


def _filter_phases(
    phases: list[Phase],
    only: list[str],
    skip: list[str],
) -> list[Phase]:
    result = list(phases)
    if only:
        result = [p for p in result if any(p.matches(n) for n in only)]
    if skip:
        result = [p for p in result if not any(p.matches(n) for n in skip)]
    return result


def run(
    manifest: Manifest,
    *,
    auto_yes: bool,
    dry_run: bool,
    verbose: bool,
    only: list[str],
    skip: list[str],
) -> int:
    console = _make_console()
    _print_title(console, manifest)

    phases = _filter_phases(manifest.phases, only, skip)
    if not phases:
        console.print("[yellow]No phases selected.[/]")
        return 0

    if dry_run:
        console.print("[dim]Dry run — no commands will execute.[/]")
        console.print()
        for phase in phases:
            _print_reason_block(console, phase)
            console.print(f"  [dim]→ {' '.join(phase.cmd)}[/]")
            console.print(f"  [dim]  cwd: {phase.cwd}[/]")
            console.print()
        return 0

    # Log is opened silently and surfaced only in the final summary — we do
    # not announce it up front, the wizard greeting stays clean.
    log_path, log_handle = _open_log(manifest)

    results: list[tuple[str, str, int]] = []
    exit_code = 0

    try:
        if HAS_RICH:
            progress = Progress(
                SpinnerColumn(style="yellow"),
                TextColumn("[bold]{task.description:<18}[/]"),
                BarColumn(bar_width=24),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                TextColumn("[dim]{task.fields[cur]}[/]"),
                console=console,
                transient=False,
                expand=False,
            )
            task_id: Any = None
        else:
            progress = None
            task_id = None

        # Use Progress as its own context — Rich internally drives a Live
        # display and allows console.print() to scroll above the sticky bar.
        progress_ctx = progress if HAS_RICH else _NullContext()
        with progress_ctx:
            if HAS_RICH:
                task_id = progress.add_task(
                    "pending", total=len(phases), cur="awaiting consent"
                )

            for idx, phase in enumerate(phases):
                _print_reason_block(console, phase)

                if HAS_RICH:
                    progress.update(
                        task_id, description=phase.label, cur="awaiting consent"
                    )

                verdict = consent(console, phase.label, phase.optional, auto_yes)
                if verdict == "quit":
                    console.print("\n  [yellow]Cancelled — no further changes.[/]\n")
                    results.append((phase.label, "cancelled", 0))
                    break
                if verdict == "skip":
                    console.print("  [yellow]· skipped[/]\n")
                    results.append((phase.label, "skipped", 0))
                    if HAS_RICH:
                        progress.update(task_id, advance=1, cur="skipped")
                    continue

                rc = run_phase(console, phase, progress, task_id, log_handle, verbose)

                if HAS_RICH:
                    progress.update(
                        task_id,
                        advance=1,
                        cur="✓ done" if rc == 0 else f"✗ exit {rc}",
                    )

                if rc == 0:
                    results.append((phase.label, "ok", 0))
                    console.print(f"  [green]✓[/] {phase.label}\n")
                elif phase.optional:
                    results.append((phase.label, f"warn (exit {rc})", rc))
                    console.print(
                        f"  [yellow]! optional phase failed (exit {rc}) — continuing[/]\n"
                    )
                else:
                    results.append((phase.label, f"failed (exit {rc})", rc))
                    console.print(f"  [red]✗ {phase.label} failed (exit {rc})[/]")
                    if log_path:
                        console.print(f"  [dim]See log: {log_path}[/]")
                    exit_code = rc
                    break
    finally:
        if log_handle is not None:
            log_handle.close()

    _print_summary(console, manifest, results, log_path)
    return exit_code


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


# ---------------------------------------------------------------------------
# Self-removal
# ---------------------------------------------------------------------------


def _self_uninstall_and_exit(rc: int) -> None:
    """Replace the current process with ``uv tool uninstall vetcoders-installer``.

    Using execvp means the Python interpreter (which is *this* tool's runtime)
    terminates cleanly, and the replacement shell kills the package files.
    No mid-run self-corruption.
    """
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        print(
            f"\n  Could not locate `uv` on PATH — remove the tool manually:\n"
            f"    uv tool uninstall {TOOL_NAME}",
            file=sys.stderr,
        )
        sys.exit(rc)
    # Fire-and-forget: the child shell runs after exec, current process is replaced.
    # rc is lost in execvp; we rely on prior `run()` to have signalled errors already.
    os.execvp(uv_bin, [uv_bin, "tool", "uninstall", TOOL_NAME])


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Sequential trust-building installer runner (manifest-driven).",
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to an install.toml manifest",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Auto-approve every phase (automation mode).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned phases and reasons without running any command.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Stream subprocess output above the sticky bottom bar.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help="Only run phases whose key or label matches NAME (repeatable).",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="NAME",
        help="Skip phases whose key or label matches NAME (repeatable).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="After a successful run, self-uninstall via `uv tool uninstall` "
        "(only if the manifest does not set persist=true).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{TOOL_NAME} {__version__}",
    )
    return parser


def main() -> int:
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except AttributeError:
        pass

    parser = _build_parser()
    args = parser.parse_args()

    manifest_path: Path = args.manifest.expanduser().resolve()
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = Manifest.load(manifest_path)
    except Exception as exc:
        print(f"error: failed to parse {manifest_path}: {exc}", file=sys.stderr)
        return 2

    # Automation fallback: if not a TTY, force --yes so the tool can be used
    # in cron / curl | sh / CI without hanging on input().
    auto_yes = args.yes or not _is_interactive()

    try:
        rc = run(
            manifest,
            auto_yes=auto_yes,
            dry_run=args.dry_run,
            verbose=args.verbose,
            only=args.only,
            skip=args.skip,
        )
    except KeyboardInterrupt:
        print("\n  Cancelled.")
        return 130

    # Decide whether to self-uninstall.
    if rc == 0 and not args.dry_run and not manifest.persist and args.cleanup:
        _self_uninstall_and_exit(rc)

    # Otherwise print cleanup guidance (if applicable).
    if rc == 0 and not args.dry_run:
        console = _make_console()
        _print_cleanup_notice(console, manifest, args.cleanup)

    return rc


if __name__ == "__main__":
    sys.exit(main())
