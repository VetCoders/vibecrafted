#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import queue
import select
import shutil
import subprocess
import sys
import termios
import textwrap
import threading
import tty
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

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
    from runtime_paths import (
        read_version_file,
        xdg_config_home,
        vibecrafted_home,
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
    from scripts.runtime_paths import (
        read_version_file,
        xdg_config_home,
        vibecrafted_home,
    )

STEP_MIN = 0
STEP_MAX = 5
STEP_COUNT = STEP_MAX + 1
DIAGNOSTICS_STEP = 3
CHECKLIST_STEP = 4
INSTALL_STEP = 5

STEP_LABELS = {
    0: "welcome",
    1: "explain",
    2: "listing",
    3: "diagnostics",
    4: "checklist",
    5: "installation",
}

CATEGORY_LABELS = {
    "frameworks": "Frameworks",
    "foundations": "Foundations",
    "toolchains": "Toolchains",
    "agents": "Agents",
    "additional_tools": "Additional tools",
}

CATEGORY_ORDER = tuple(CATEGORY_LABELS)
FOUNDATION_COMMANDS = ("loctree-mcp", "aicx-mcp", "prview", "screenscribe")
TOOLCHAIN_COMMANDS = ("python3", "node", "git", "rsync")
AGENT_COMMANDS = ("claude", "codex", "gemini")
ADDITIONAL_TOOL_COMMANDS = ("mise", "starship", "atuin", "zoxide")
INSTALL_OUTPUT_TAIL = 18
READ_KEY_TIMEOUT = 0.1
DEFAULT_RENDER_WIDTH = 57


def default_source_dir() -> str:
    return str(Path(__file__).resolve().parent.parent)


def read_framework_version(source_dir: str) -> str:
    return read_version_file(source_dir)


def framework_store_dir() -> Path:
    return vibecrafted_home() / "skills"


def helper_layer_path() -> Path:
    return xdg_config_home() / "vetcoders" / "vc-skills.sh"


def install_log_path() -> Path:
    return vibecrafted_home() / "install.log"


def start_here_path() -> Path:
    return vibecrafted_home() / "START_HERE.md"


def runtime_skill_views() -> dict[str, Path]:
    home = Path.home()
    return {
        "agents": home / ".agents" / "skills",
        "claude": home / ".claude" / "skills",
        "codex": home / ".codex" / "skills",
        "gemini": home / ".gemini" / "skills",
    }


def installer_script_path(source_dir: str) -> Path:
    return Path(source_dir).resolve() / "scripts" / "vetcoders_install.py"


def build_install_command(source_dir: str) -> list[str]:
    installer_path = installer_script_path(source_dir)
    if not installer_path.exists():
        raise FileNotFoundError(f"Installer not found at {installer_path}")
    return [
        sys.executable,
        str(installer_path),
        "install",
        "--source",
        str(Path(source_dir).resolve()),
        "--with-shell",
        "--compact",
        "--non-interactive",
    ]


def _command_check(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    return {
        "label": name,
        "found": bool(path),
        "detail": path or f"{name} not found on PATH",
        "kind": "command",
    }


def _path_check(
    label: str, path: Path, *, found: bool | None = None, detail: str | None = None
) -> dict[str, Any]:
    is_found = path.exists() if found is None else found
    return {
        "label": label,
        "found": is_found,
        "detail": detail or str(path),
        "kind": "path",
    }


def _framework_checks() -> dict[str, dict[str, Any]]:
    store_dir = framework_store_dir()
    helper_file = helper_layer_path()
    skills = []
    if store_dir.is_dir():
        skills = sorted(
            child.name
            for child in store_dir.iterdir()
            if child.is_dir() and child.name.startswith("vc-")
        )

    binary_path = shutil.which("vibecraft") or shutil.which("vibecrafted")

    active_views = []
    for runtime, path in runtime_skill_views().items():
        if not path.is_dir():
            continue
        entries = [entry.name for entry in path.iterdir()]
        if entries:
            active_views.append(f"{runtime} ({len(entries)})")

    return {
        "workflows": _path_check(
            "workflows",
            store_dir,
            found=bool(skills),
            detail=f"{len(skills)} installed skill directories in {store_dir}"
            if skills
            else f"No installed skill directories in {store_dir}",
        ),
        "helpers": _path_check(
            "helpers",
            helper_file,
            detail=str(helper_file)
            if helper_file.exists()
            else f"Missing helper file at {helper_file}",
        ),
        "binaries": {
            "label": "binaries",
            "found": bool(binary_path),
            "detail": binary_path or "vibecraft/vibecrafted not found on PATH",
            "kind": "command",
        },
        "symlinks": {
            "label": "symlinks",
            "found": bool(active_views),
            "detail": ", ".join(active_views)
            if active_views
            else "No runtime skill views detected in $HOME/.agents, $HOME/.claude, $HOME/.codex, or $HOME/.gemini",
            "kind": "path",
        },
    }


def run_diagnostics() -> dict[str, dict[str, dict[str, Any]]]:
    """Check: frameworks, foundations, toolchains, agents, tools."""
    diagnostics: dict[str, dict[str, dict[str, Any]]] = {}
    diagnostics["frameworks"] = _framework_checks()
    diagnostics["foundations"] = {
        name: _command_check(name) for name in FOUNDATION_COMMANDS
    }
    diagnostics["toolchains"] = {
        name: _command_check(name) for name in TOOLCHAIN_COMMANDS
    }
    diagnostics["agents"] = {name: _command_check(name) for name in AGENT_COMMANDS}
    diagnostics["additional_tools"] = {
        name: _command_check(name) for name in ADDITIONAL_TOOL_COMMANDS
    }
    return diagnostics


def summarize_diagnostics(
    diagnostics: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[str], list[str], dict[str, list[str]]]:
    found_items: list[str] = []
    missing_items: list[str] = []
    needs_install: dict[str, list[str]] = {}

    for category in CATEGORY_ORDER:
        missing_in_category: list[str] = []
        for name, entry in diagnostics.get(category, {}).items():
            label = entry.get("label", name)
            flat_label = f"{CATEGORY_LABELS[category]}: {label}"
            if entry.get("found"):
                found_items.append(flat_label)
            else:
                missing_items.append(flat_label)
                missing_in_category.append(label)
        if missing_in_category:
            needs_install[category] = missing_in_category

    return found_items, missing_items, needs_install


@dataclass
class InstallerState:
    step: int = 0
    diagnostics: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    consent_given: bool = False
    install_running: bool = False
    install_output: list[str] = field(default_factory=list)
    needs_install: dict[str, list[str]] = field(default_factory=dict)
    found_items: list[str] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    diagnostics_ran: bool = False
    diagnostics_running: bool = False
    diagnostics_output: list[str] = field(default_factory=list)
    details_view: bool = False
    should_quit: bool = False
    status_message: str = ""
    source_dir: str = field(default_factory=default_source_dir)
    version: str = ""
    install_command: list[str] = field(default_factory=list)
    install_exit_code: int | None = None
    install_completed: bool = False
    install_result: subprocess.CompletedProcess[str] | None = field(
        default=None, repr=False
    )
    install_error: str | None = None
    _install_queue: queue.Queue[tuple[str, str]] = field(
        default_factory=queue.Queue, init=False, repr=False
    )
    _install_thread: threading.Thread | None = field(
        default=None, init=False, repr=False
    )
    _install_process: subprocess.Popen[str] | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.step = clamp_step(self.step)
        if not self.version:
            self.version = read_framework_version(self.source_dir)

    @property
    def step_label(self) -> str:
        return STEP_LABELS.get(self.step, f"step-{self.step}")

    @property
    def can_go_back(self) -> bool:
        return self.step > STEP_MIN and not self.install_running

    @property
    def can_go_forward(self) -> bool:
        if self.install_running:
            return False
        if self.step == CHECKLIST_STEP:
            return True
        if self.step >= INSTALL_STEP:
            return False
        return True

    @property
    def current_install_tail(self) -> list[str]:
        if not self.install_output:
            return []
        return self.install_output[-INSTALL_OUTPUT_TAIL:]


def clamp_step(step: int) -> int:
    return max(STEP_MIN, min(STEP_MAX, step))


def refresh_diagnostics(state: InstallerState) -> InstallerState:
    state.diagnostics_running = True
    state.diagnostics_output = [
        "Checking frameworks...",
        "Checking foundations...",
        "Checking toolchains...",
        "Checking agent CLIs...",
        "Checking additional tools...",
    ]
    state.diagnostics = run_diagnostics()
    state.found_items, state.missing_items, state.needs_install = summarize_diagnostics(
        state.diagnostics
    )
    state.diagnostics_output.extend(
        f"{CATEGORY_LABELS[category]}: "
        f"{sum(1 for entry in state.diagnostics.get(category, {}).values() if entry.get('found'))}/"
        f"{len(state.diagnostics.get(category, {}))} present"
        for category in CATEGORY_ORDER
    )
    state.diagnostics_ran = True
    state.diagnostics_running = False
    state.status_message = f"Diagnostics complete: {len(state.found_items)} found, {len(state.missing_items)} missing."
    return state


def run_install(source_dir: str) -> subprocess.CompletedProcess[str]:
    """Call vetcoders_install.py install --compact."""
    command = build_install_command(source_dir)
    return subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _install_worker(
    source_dir: str,
    event_queue: queue.Queue[tuple[str, str]],
    process_setter: Callable[[subprocess.Popen[str] | None], None],
) -> None:
    command = build_install_command(source_dir)
    stdout_lines: list[str] = []
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        process_setter(process)
        event_queue.put(("started", " ".join(command)))
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.rstrip("\n")
            stdout_lines.append(clean)
            event_queue.put(("line", clean))
        return_code = process.wait()
        event_queue.put(("returncode", str(return_code)))
        event_queue.put(("stdout", "\n".join(stdout_lines)))
    except Exception as exc:  # pragma: no cover - defensive path
        event_queue.put(("error", str(exc)))
    finally:
        process_setter(None)


def start_install(state: InstallerState) -> InstallerState:
    if state.install_running or state.install_completed:
        return state
    state.install_output = []
    state.install_error = None
    state.install_exit_code = None
    state.install_completed = False
    try:
        state.install_command = build_install_command(state.source_dir)
    except FileNotFoundError as exc:
        state.install_error = str(exc)
        state.install_exit_code = -1
        state.install_completed = True
        state.install_running = False
        state.status_message = str(exc)
        return state
    state.install_running = True
    state.status_message = "Running compact installer..."
    state._install_queue = queue.Queue()

    def _set_process(process: subprocess.Popen[str] | None) -> None:
        state._install_process = process

    worker = threading.Thread(
        target=_install_worker,
        args=(state.source_dir, state._install_queue, _set_process),
        daemon=True,
        name="installer-tui-install",
    )
    state._install_thread = worker
    worker.start()
    return state


def pump_install_output(state: InstallerState) -> bool:
    changed = False
    while True:
        try:
            kind, payload = state._install_queue.get_nowait()
        except queue.Empty:
            break

        changed = True
        if kind == "started":
            state.status_message = "Installer subprocess started."
        elif kind == "line":
            state.install_output.append(payload)
        elif kind == "returncode":
            state.install_exit_code = int(payload)
            state.install_running = False
            state.install_completed = True
            if state.install_exit_code == 0:
                state.status_message = "Installation finished successfully."
            else:
                state.status_message = (
                    f"Installation exited with code {state.install_exit_code}."
                )
        elif kind == "stdout":
            state.install_result = subprocess.CompletedProcess(
                args=state.install_command,
                returncode=state.install_exit_code
                if state.install_exit_code is not None
                else -1,
                stdout=payload,
            )
        elif kind == "error":
            state.install_running = False
            state.install_completed = True
            state.install_error = payload
            state.install_exit_code = -1
            state.status_message = f"Installation failed to start: {payload}"
    return changed


def goto_step(state: InstallerState, step: int) -> InstallerState:
    state.step = clamp_step(step)
    if state.step >= DIAGNOSTICS_STEP and not state.diagnostics_ran:
        refresh_diagnostics(state)
    if (
        state.step == INSTALL_STEP
        and state.consent_given
        and not state.install_running
        and not state.install_completed
    ):
        start_install(state)
    return state


def handle_key(state: InstallerState, key: str | None) -> InstallerState:
    """Arrow/Enter/q navigation."""
    if key is None:
        return state

    if key == "tab":
        state.details_view = not state.details_view
        return state

    if key in {"q", "escape"}:
        if state.install_running:
            state.status_message = "Install is still running; wait for it to finish."
            return state
        state.should_quit = True
        return state

    if key in {"left", "backspace"}:
        if state.install_running:
            state.status_message = (
                "Back navigation is disabled while install is running."
            )
            return state
        return goto_step(state, state.step - 1)

    if key not in {"right", "enter"}:
        return state

    if state.step < DIAGNOSTICS_STEP:
        return goto_step(state, state.step + 1)

    if state.step == DIAGNOSTICS_STEP:
        if not state.diagnostics_ran:
            refresh_diagnostics(state)
        return goto_step(state, CHECKLIST_STEP)

    if state.step == CHECKLIST_STEP:
        state.consent_given = True
        state.status_message = "Install approved. Launching installer..."
        return goto_step(state, INSTALL_STEP)

    if state.step == INSTALL_STEP:
        if state.install_running:
            state.status_message = "Installer is already running."
            return state
        if state.install_completed:
            state.should_quit = True
            return state
        if not state.consent_given:
            state.status_message = "Review the checklist before starting install."
            return state
        return start_install(state)

    return state


@contextlib.contextmanager
def raw_terminal_mode(enabled: bool):
    if not enabled:
        yield
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_key(timeout: float = READ_KEY_TIMEOUT) -> str | None:
    if not sys.stdin.isatty():
        return None

    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None

    char = sys.stdin.read(1)
    if char in ("\n", "\r"):
        return "enter"
    if char == "\t":
        return "tab"
    if char in ("\x7f", "\b"):
        return "backspace"
    if char in {"q", "Q"}:
        return "q"
    if char == "\x03":
        raise KeyboardInterrupt
    if char != "\x1b":
        return char

    sequence = char
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], 0.01)
        if not ready:
            break
        sequence += sys.stdin.read(1)
        if sequence in {"\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"}:
            break

    return {
        "\x1b[A": "up",
        "\x1b[B": "down",
        "\x1b[C": "right",
        "\x1b[D": "left",
    }.get(sequence, "escape")


class SimpleConsole:
    def clear(self) -> None:
        if sys.stdout.isatty():
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

    def print(self, *parts: object) -> None:
        print(*parts)


def make_console() -> Any:
    try:
        from rich.console import Console
    except ImportError:
        return SimpleConsole()
    return Console()


def _render_width() -> int:
    width = shutil.get_terminal_size((DEFAULT_RENDER_WIDTH, 32)).columns
    return max(DEFAULT_RENDER_WIDTH, min(width - 2, 96))


def _print_wrapped(
    console: Any,
    text: str,
    width: int,
    *,
    indent: str = "  ",
    subsequent_indent: str | None = None,
) -> None:
    available = max(16, width - len(indent))
    lines = textwrap.wrap(
        text,
        width=available,
        initial_indent=indent,
        subsequent_indent=subsequent_indent or indent,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not lines:
        console.print(indent.rstrip())
        return
    for line in lines:
        console.print(line)


def _print_block(console: Any, width: int, lines: list[str]) -> None:
    for line in lines:
        _print_wrapped(console, line, width)


def _status_icon(found: bool) -> str:
    return "✔" if found else "𐄂"


def _trim_home(path: str) -> str:
    return path.replace(str(Path.home()), "~")


def _category_counts(state: InstallerState, category: str) -> tuple[int, int]:
    entries = list(state.diagnostics.get(category, {}).values())
    found = sum(1 for entry in entries if entry.get("found"))
    return found, len(entries)


def _render_box(console: Any, width: int, title: str, lines: list[str]) -> None:
    inner_width = max(24, width - 6)
    console.print(f"  ╔{'═' * inner_width}╗")
    title_line = f" {title}"[:inner_width]
    console.print(f"  ║{title_line.ljust(inner_width)}║")
    for raw in lines:
        wrapped = textwrap.wrap(
            raw,
            width=inner_width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        for line in wrapped:
            console.print(f"  ║{line.ljust(inner_width)}║")
    console.print(f"  ╚{'═' * inner_width}╝")


def _render_hero(console: Any, state: InstallerState, width: int) -> None:
    sep = brand_separator(width)
    console.print(sep)
    console.print(f"⚒ {VAPOR_HEADER} ⚒".center(width))
    console.print(brand_version_line(state.version).center(width))
    console.print(TAGLINE.center(width))
    console.print(sep)


def _render_footer(console: Any, width: int) -> None:
    sep = brand_separator(width)
    console.print(sep)
    console.print("⇅ Nav | ⏎ Next | ⌫ Back | ⇥ View | ⎋ Quit".center(width))
    console.print(FRAMEWORK_STAMP.center(width))
    console.print(sep)


def _render_welcome(console: Any, state: InstallerState, width: int) -> None:
    home_display = str(vibecrafted_home()).replace(str(Path.home()), "~")
    console.print("  Welcome")
    console.print("")
    _print_block(
        console,
        width,
        [
            f"{PRODUCT_LINE} This setup stages 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. inside {home_display} and prepares the framework for daily work with agent CLIs.",
            "Nothing outside your 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. home changes until you approve the install step.",
            "Each screen shows what changes, why it matters, and what stays reversible before we touch your shell or runtime views.",
            "If you need product context instead of setup context, the public surface lives at https://vibecrafted.io.",
        ],
    )


def _render_explain(console: Any, state: InstallerState, width: int) -> None:
    home_display = str(vibecrafted_home()).replace(str(Path.home()), "~")
    console.print("  How this setup works")
    console.print("")
    _print_block(
        console,
        width,
        [
            f"The framework keeps its control plane in {home_display} so the install stays isolated from the rest of your machine.",
            "If you enable shell helpers, we add one source line to your rc file. Frontier configs load as sidecars, not as a takeover of your personal prompt or session manager.",
            "This installer is here to be clear and predictable. It will not lecture you, but it will tell you what it is doing.",
        ],
    )
    console.print("")
    for key, meaning in (
        ("⇅", "Move between screens"),
        ("⏎", "Proceed"),
        ("⌫", "Go back"),
        ("⇥", "Toggle summary/details"),
        ("⎋", "Quit"),
    ):
        _print_wrapped(console, f"{key}  {meaning}", width, indent="    ")


def _render_listing(console: Any, state: InstallerState, width: int) -> None:
    console.print("  Install plan")
    console.print("")
    for idx, (title, detail) in enumerate(
        [
            (
                "Diagnostics",
                "Check the current framework surface, required foundations, toolchains, agent CLIs, and the prompt/history sidecars that ship with the control plane.",
            ),
            (
                "Install",
                "Stage skills, helper layer, launchers, runtime views, and shell integration if you enable it.",
            ),
            (
                "Verify",
                "Run doctor, save the manifest, and leave a readable install trail.",
            ),
            (
                "Recover",
                "Keep the log, backups, and uninstall path obvious from the first run.",
            ),
        ],
        start=1,
    ):
        _print_wrapped(console, f"{idx}. {title}", width)
        _print_wrapped(
            console, detail, width, indent="     ", subsequent_indent="     "
        )


def _render_diagnostics(console: Any, state: InstallerState, width: int) -> None:
    console.print("  Diagnostics")
    console.print("")
    progress_lines = []
    for category in CATEGORY_ORDER:
        found, total = _category_counts(state, category)
        progress_lines.append(
            f"{CATEGORY_LABELS[category]:<17} {found}/{total} present"
        )
    if state.status_message:
        progress_lines.append("")
        progress_lines.append(state.status_message)
    _render_box(console, width, "Environment scan", progress_lines)
    console.print("")
    for category in CATEGORY_ORDER:
        console.print(f"  {CATEGORY_LABELS[category]}:")
        entries = list(state.diagnostics.get(category, {}).values())
        if state.details_view:
            for entry in entries:
                label = entry.get("label", "?")
                detail = _trim_home(str(entry.get("detail", "")))
                _print_wrapped(
                    console,
                    f"{_status_icon(bool(entry.get('found')))} {label} — {detail}",
                    width,
                    indent="    ",
                    subsequent_indent="      ",
                )
        else:
            summary = " · ".join(
                f"{_status_icon(bool(entry.get('found')))} {entry.get('label', '?')}"
                for entry in entries
            )
            _print_wrapped(
                console, summary, width, indent="    ", subsequent_indent="    "
            )
        console.print("")


def _group_items(items: list[str]) -> list[str]:
    return sorted(items, key=lambda item: (item.split(":", 1)[0], item))


def _render_item_section(
    console: Any, width: int, title: str, items: list[str], *, icon: str, limit: int
) -> None:
    console.print(f"  {title}")
    shown = items if limit < 0 else items[:limit]
    if not shown:
        _print_wrapped(console, f"{icon} Nothing in this group.", width, indent="    ")
        return
    for item in _group_items(shown):
        _print_wrapped(
            console, f"{icon} {item}", width, indent="    ", subsequent_indent="      "
        )
    if limit >= 0 and len(items) > limit:
        _print_wrapped(
            console,
            f"... {len(items) - limit} more items hidden. Press ⇥ for full detail.",
            width,
            indent="    ",
            subsequent_indent="    ",
        )


def _render_checklist(console: Any, state: InstallerState, width: int) -> None:
    console.print("  Checklist")
    console.print("")
    _print_block(
        console,
        width,
        [
            "This is the last summary before we touch the install path. Found items stay as they are; missing items are what the install will stage or wire up now."
        ],
    )
    console.print("")
    limit = -1 if state.details_view else 8
    _render_item_section(
        console,
        width,
        "Already present",
        state.found_items,
        icon="✔",
        limit=limit,
    )
    console.print("")
    _render_item_section(
        console,
        width,
        "Install now",
        state.missing_items,
        icon="𐄂",
        limit=limit,
    )


def _render_installation(console: Any, state: InstallerState, width: int) -> None:
    console.print("  Installation")
    console.print("")
    header = "Live progress" if state.install_running else "Install status"
    progress_lines = [line for line in state.current_install_tail if line.strip()]
    if not progress_lines:
        if state.install_completed and state.install_exit_code == 0:
            progress_lines = [
                "Install finished cleanly.",
                state.status_message or "Ready.",
            ]
        elif state.install_error:
            progress_lines = [state.install_error]
        else:
            progress_lines = [state.status_message or "Waiting to start the installer."]
    _render_box(console, width, header, progress_lines)
    console.print("")
    _print_wrapped(
        console,
        f"Log: {_trim_home(str(install_log_path()))}",
        width,
        indent="  ",
        subsequent_indent="       ",
    )
    console.print("")
    pending = state.missing_items[:10]
    if pending and not state.install_completed:
        _render_item_section(
            console,
            width,
            "Install target",
            pending,
            icon="𐄂",
            limit=-1 if state.details_view else 10,
        )
    elif state.install_completed and state.install_exit_code == 0:
        _print_block(
            console,
            width,
            [
                "The installer finished. The manifest, backup state, doctor output, and START_HERE guide are already on disk.",
                f"Open {_trim_home(str(start_here_path()))} for the plain-language path. Use vibecrafted help for the command deck, vibecrafted doctor to verify again, and vibecrafted uninstall to reverse the install.",
            ],
        )


def _render_body(console: Any, state: InstallerState, width: int) -> None:
    {
        0: _render_welcome,
        1: _render_explain,
        2: _render_listing,
        3: _render_diagnostics,
        4: _render_checklist,
        5: _render_installation,
    }[state.step](console, state, width)


def _render_action(console: Any, state: InstallerState, width: int) -> None:
    if state.step == 0:
        action = "Press ⏎ Enter to proceed or ⎋ Esc to leave."
    elif state.step == CHECKLIST_STEP:
        action = "⏎ Install  |  ⌫ Back  |  ⇥ Details  |  ⎋ Quit"
    elif state.step == INSTALL_STEP and state.install_running:
        action = "Install running — wait for completion. Quit is disabled while files are changing."
    elif state.step == INSTALL_STEP and state.install_completed:
        action = "Installation complete. Press ⏎ to close."
    elif state.step == INSTALL_STEP:
        action = "⏎ Start install  |  ⌫ Back  |  ⇥ Details  |  ⎋ Quit"
    else:
        action = "⏎ Proceed  |  ⌫ Back  |  ⇥ Details  |  ⎋ Quit"
    console.print(brand_separator(width))
    _print_wrapped(console, action, width)
    if state.status_message and state.step != INSTALL_STEP:
        _print_wrapped(console, f"Status: {state.status_message}", width)


def render(state: InstallerState, console: Any) -> None:
    if hasattr(console, "clear"):
        console.clear()
    width = _render_width()
    _render_hero(console, state, width)
    _render_body(console, state, width)
    _render_action(console, state, width)
    console.print(FOOTER_BRANDING.center(width))
    _render_footer(console, width)


def main_loop(
    state: InstallerState | None = None, console: Any | None = None
) -> InstallerState:
    """Read key -> update state -> render (Gemini's job)."""
    state = state or InstallerState()
    console = console or make_console()

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if state.step >= DIAGNOSTICS_STEP and not state.diagnostics_ran:
        refresh_diagnostics(state)

    dirty = True
    rendered = False
    with raw_terminal_mode(interactive):
        while not state.should_quit:
            if pump_install_output(state):
                dirty = True

            if dirty:
                render(state, console)
                dirty = False
                rendered = True

            key = read_key(READ_KEY_TIMEOUT if interactive else 0.0)
            if key is None:
                if not interactive and not state.install_running:
                    break
                continue

            handle_key(state, key)
            dirty = True

    if not interactive and (dirty or not rendered):
        render(state, console)
    return state


def main() -> int:
    state = InstallerState()
    try:
        state = main_loop(state)
    except KeyboardInterrupt:
        return 130
    return state.install_exit_code or 0


if __name__ == "__main__":
    raise SystemExit(main())
