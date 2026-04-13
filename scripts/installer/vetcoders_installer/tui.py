"""Textual TUI app for the installer wizard."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical
from textual.widgets import Static, Checkbox


def _trim_home(path: str) -> str:
    return path.replace(str(Path.home()), "~")


def run_manifest_diagnostics(manifest: Any) -> dict[str, dict[str, dict[str, Any]]]:
    diags: dict[str, dict[str, dict[str, Any]]] = {}
    if not manifest or not manifest.diagnostics:
        return diags

    # Generic diagnostics from manifest
    cats = manifest.diagnostics.get("categories", [])
    cmds = manifest.diagnostics.get("commands", {})
    paths = manifest.diagnostics.get("paths", {})

    for cat in cats:
        diags[cat] = {}
        for cmd in cmds.get(cat, []):
            cmd_path = shutil.which(cmd)
            diags[cat][cmd] = {
                "label": cmd,
                "found": bool(cmd_path),
                "detail": cmd_path or f"{cmd} not found on PATH",
                "kind": "command",
            }
        for name, path_str in paths.get(cat, {}).items():
            if isinstance(path_str, list):
                # Multiple paths, assume it's symlinks check
                active = []
                for p in path_str:
                    expanded = os.path.expandvars(os.path.expanduser(p))
                    if Path(expanded).is_dir() and list(Path(expanded).iterdir()):
                        active.append(expanded)
                diags[cat][name] = {
                    "label": name,
                    "found": bool(active),
                    "detail": ", ".join(active)
                    if active
                    else f"No items found in {name}",
                    "kind": "path",
                }
            else:
                expanded = os.path.expandvars(os.path.expanduser(path_str))
                diags[cat][name] = {
                    "label": name,
                    "found": Path(expanded).exists(),
                    "detail": expanded,
                    "kind": "path",
                }
    return diags


def summarize_diagnostics(
    diags: dict[str, dict[str, dict[str, Any]]], manifest: Any
) -> tuple[list[str], list[str], dict[str, list[str]]]:
    found_items = []
    missing_items = []
    needs_install = {}

    if not manifest or not manifest.diagnostics:
        return found_items, missing_items, needs_install

    cats = manifest.diagnostics.get("categories", [])
    labels = manifest.diagnostics.get("labels", {})

    for cat in cats:
        missing_in_cat = []
        for name, entry in diags.get(cat, {}).items():
            label = entry.get("label", name)
            flat_label = f"{labels.get(cat, cat)}: {label}"
            if entry.get("found"):
                found_items.append(flat_label)
            else:
                missing_items.append(flat_label)
                missing_in_cat.append(label)
        if missing_in_cat:
            needs_install[cat] = missing_in_cat

    return found_items, missing_items, needs_install


class InstallerIntroApp(App):
    """Multi-screen installer wizard."""

    CSS = """
    #header {
        dock: top;
        height: auto;
        background: $surface;
        padding: 0 1;
    }
    #scroll-area {
        height: 1fr;
    }
    #content-container {
        padding: 0 5 1 5;
    }
    #footer {
        dock: bottom;
        height: auto;
        background: $surface;
        padding: 0 1;
    }
    .check-item {
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
    }
    """

    BINDINGS = [
        Binding("enter", "next_screen", "Proceed", show=True),
        Binding("backspace", "prev_screen", "Back", show=True),
        Binding("escape", "quit_installer", "Quit", show=True),
        Binding("q", "quit_installer", "Quit", show=False),
        Binding("tab", "toggle_details", "Details", show=True),
        Binding("up", "scroll_up", show=False),
        Binding("down", "scroll_down", show=False),
    ]

    def action_scroll_up(self) -> None:
        self.query_one("#scroll-area", VerticalScroll).scroll_up()

    def action_scroll_down(self) -> None:
        self.query_one("#scroll-area", VerticalScroll).scroll_down()

    def __init__(
        self,
        screens: list[tuple[str, str, str]],
        version: str,
        source_dir: Path,
        advanced: bool = False,
        manifest: Any = None,
    ) -> None:
        super().__init__()
        self._screens = screens
        self._version = version
        self._source_dir = source_dir
        self._advanced = advanced
        self._current = 0
        self.result: str = "quit"

        self.manifest = manifest
        self.details_view = False

        # State
        self.diagnostics_done = False
        self.diagnostics_results: dict[str, dict[str, dict[str, Any]]] = {}
        self.found_items: list[str] = []
        self.missing_items: list[str] = []
        self.needs_install: dict[str, list[str]] = {}
        self.selected_items: set[str] = set()

        self.install_running = False
        self.install_done = False
        self.install_exit_code: int | None = None
        self.install_log: list[str] = []
        self.install_error: str | None = None

        self._diag_msg = "Starting..."

    def compose(self) -> ComposeResult:
        yield Static(id="header", markup=False)
        with VerticalScroll(id="scroll-area"):
            yield Vertical(id="content-container")
        yield Static(id="footer", markup=False)

    async def on_mount(self) -> None:
        await self._render_screen()

    def action_toggle_details(self) -> None:
        self.details_view = not self.details_view
        if self._current in (3, 4):
            self.call_later(self._render_content)

    async def _render_screen(self) -> None:
        idx = min(self._current, len(self._screens) - 1)
        header, content, footer = self._screens[idx]

        # Override headers/footers using branding if available
        if self.manifest and getattr(self.manifest, "branding", None):
            pass  # Currently keeping exactly what the screens provided

        self.query_one("#header", Static).update(header)
        self.query_one("#footer", Static).update(footer)

        await self._render_content()
        self.query_one("#scroll-area", VerticalScroll).scroll_home(animate=False)

    async def _render_content(self) -> None:
        container = self.query_one("#content-container", Vertical)
        await container.query("*").remove()

        if self._current in (0, 1, 2):
            await container.mount(Static(self._screens[self._current][1], markup=False))
        elif self._current == 3:
            await container.mount(Static(self._build_step_3(), markup=True))
            if not self.diagnostics_done and not getattr(self, "_diag_started", False):
                self._diag_started = True
                self.run_diagnostics()
        elif self._current == 4:
            if self._advanced:
                await self._mount_step_4_advanced(container)
            else:
                await container.mount(Static(self._build_step_4_static(), markup=True))
        elif self._current == 5:
            await container.mount(Static(self._build_step_5(), markup=True))
            if not self.install_running and not self.install_done:
                self.run_install()
        elif self._current == 6:
            await container.mount(Static(self._build_step_6(), markup=True))

    def _build_step_3(self) -> str:
        lines = []
        lines.append("  [bold]Diagnostics[/bold]\n")

        lines.append("  ╔════════════════════════════════════════════════════╗")
        msg = f"{self._diag_msg:<50}"
        lines.append(f"  ║ {msg} ║")
        lines.append("  ╚════════════════════════════════════════════════════╝\n")

        if self.diagnostics_done:
            cats = []
            labels = {}
            if self.manifest and getattr(self.manifest, "diagnostics", None):
                cats = self.manifest.diagnostics.get("categories", [])
                labels = self.manifest.diagnostics.get("labels", {})

            for category in cats:
                lines.append(f"  {labels.get(category, category)}:")
                entries = list(self.diagnostics_results.get(category, {}).values())
                if self.details_view:
                    for entry in entries:
                        label = entry.get("label", "?")
                        detail = _trim_home(str(entry.get("detail", "")))
                        icon = (
                            "[green]✔[/green]" if entry.get("found") else "[red]𐄂[/red]"
                        )
                        lines.append(f"    {icon} {label} — {detail}")
                else:
                    parts = []
                    for entry in entries:
                        icon = (
                            "[green]✔[/green]" if entry.get("found") else "[red]𐄂[/red]"
                        )
                        parts.append(f"{icon} {entry.get('label', '?')}")
                    if parts:
                        lines.append("    " + " · ".join(parts))
                    else:
                        lines.append("    [dim]None[/dim]")
                lines.append("")

        return "\n".join(lines)

    @work(exclusive=True, thread=True)
    def run_diagnostics(self) -> None:
        self.app.call_from_thread(self._update_diag_msg, "Running diagnostics...")
        diags = run_manifest_diagnostics(self.manifest)
        self.app.call_from_thread(self._finish_diagnostics, diags)

    def _update_diag_msg(self, msg: str) -> None:
        self._diag_msg = msg
        if self._current == 3:
            self._update_static_content(self._build_step_3())

    def _finish_diagnostics(self, diags) -> None:
        self.diagnostics_results = diags
        self.found_items, self.missing_items, self.needs_install = (
            summarize_diagnostics(diags, self.manifest)
        )
        self.selected_items = set(self.missing_items)  # All selected by default
        self.diagnostics_done = True
        self._diag_msg = "Complete."
        if self._current == 3:
            self._update_static_content(self._build_step_3())
            self.action_next_screen()

    def _update_static_content(self, text: str) -> None:
        try:
            widget = self.query_one("#content-container > Static", Static)
            widget.update(text)
        except Exception:
            pass

    def _build_step_4_static(self) -> str:
        lines = ["[bold]  Results[/bold]\n"]
        lines.append("  [bold]Already have[/bold] (no action needed)")
        if not self.found_items:
            lines.append("    [dim]None[/dim]")
        for item in self.found_items:
            lines.append(f"    [green]✔[/green] {item}")

        lines.append("\n  [bold]Need to install[/bold]")
        if not self.missing_items:
            lines.append("    [dim]None[/dim]")
        for item in self.missing_items:
            lines.append(f"    [red]𐄂[/red] {item}")
        return "\n".join(lines)

    async def _mount_step_4_advanced(self, container: Vertical) -> None:
        await container.mount(
            Static(
                "[bold]  Results (Advanced Mode)[/bold]\n\n  [bold]Already have[/bold] (no action needed)",
                markup=True,
            )
        )
        if not self.found_items:
            await container.mount(Static("    [dim]None[/dim]", markup=True))
        for item in self.found_items:
            await container.mount(Static(f"    [green]✔[/green] {item}", markup=True))

        await container.mount(
            Static("\n  [bold]Need to install[/bold] (Space to toggle)", markup=True)
        )
        if not self.missing_items:
            await container.mount(Static("    [dim]None[/dim]", markup=True))
        for item in self.missing_items:
            cb = Checkbox(item, value=item in self.selected_items, classes="check-item")
            await container.mount(cb)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.label is None:
            return
        item = str(event.checkbox.label)
        if event.checkbox.value:
            self.selected_items.add(item)
        else:
            self.selected_items.discard(item)

    def _build_step_5(self) -> str:
        lines = ["  [bold]Installation[/bold]\n"]

        lines.append("  ╔════════════════════════════════════════════════════╗")
        tail = self.install_log[-3:] if self.install_log else []
        if not tail:
            if self.install_done:
                if self.install_exit_code == 0:
                    tail = ["Finished cleanly."]
                else:
                    tail = [self.install_error or "Failed."]
            else:
                tail = ["Starting..."]

        for line in tail:
            lines.append(f"  ║ {line[-50:]: <50} ║")
        lines.append("  ╚════════════════════════════════════════════════════╝\n")

        for item in self.missing_items:
            if item in self.selected_items:
                icon = (
                    "[green]✔[/green]"
                    if self.install_done and self.install_exit_code == 0
                    else "[dim]𐄂[/dim]"
                )
                lines.append(f"    {icon} {item}")
            else:
                lines.append(f"    [dim]- {item} (skipped)[/dim]")

        return "\n".join(lines)

    @work(exclusive=True, thread=True)
    def run_install(self) -> None:
        self.install_running = True

        # Loop through manifest phases
        if not self.manifest or not self.manifest.phases:
            self.app.call_from_thread(self._finish_install, 0, None)
            return

        exit_code = 0
        err = None
        for phase in self.manifest.phases:
            # We skip "diagnostics" phase in the install loop, because
            # this TUI handles diagnostics via step 3 natively
            if phase.key == "diagnostics":
                continue

            cmd = phase.cmd
            cwd = phase.cwd
            self.app.call_from_thread(self._add_install_log, f"Running: {phase.label}")

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(cwd),
                )
                assert process.stdout is not None
                for line in process.stdout:
                    clean = line.rstrip("\n")
                    self.app.call_from_thread(self._add_install_log, clean)

                rc = process.wait()
                if rc != 0 and not phase.optional:
                    exit_code = rc
                    err = f"Phase {phase.label} failed with exit {rc}"
                    break
            except Exception as exc:
                exit_code = -1
                err = str(exc)
                break

        self.app.call_from_thread(self._finish_install, exit_code, err)

    def _add_install_log(self, line: str) -> None:
        self.install_log.append(line)
        if len(self.install_log) > 20:
            self.install_log.pop(0)
        if self._current == 5:
            self._update_static_content(self._build_step_5())

    def _finish_install(self, rc: int, err: str | None) -> None:
        self.install_running = False
        self.install_done = True
        self.install_exit_code = rc
        self.install_error = err
        if self._current == 5:
            self._update_static_content(self._build_step_5())
            self.action_next_screen()

    def _build_step_6(self) -> str:
        lines = []
        if self.install_exit_code == 0:
            lines.append("  [bold green]Installation complete.[/bold green]\n")
        else:
            lines.append("  [bold red]Installation failed.[/bold red]\n")
            lines.append(f"  Exit code: {self.install_exit_code}")
            if self.install_error:
                lines.append(f"  Error: {self.install_error}")
            lines.append("")

        next_steps = []
        if self.manifest and getattr(self.manifest, "branding", None):
            next_steps = self.manifest.branding.get("next_steps", [])
            tagline = self.manifest.branding.get("footer_tagline", "")
        else:
            tagline = ""

        if next_steps:
            for step in next_steps:
                lines.append(
                    f"  {step.get('label', 'Step')}:    [bold]{step.get('cmd', '')}[/bold]  [dim]({step.get('desc', '')})[/dim]"
                )

        if tagline:
            lines.append(f"\n  {tagline}\n")

        lines.append("  Press Enter to exit installer...")
        return "\n".join(lines)

    # -- Actions bound to keys ----------------------------------------------

    def action_next_screen(self) -> None:
        if self._current == 3 and not self.diagnostics_done:
            return
        if self._current == 5 and not self.install_done:
            return

        if self._current < 6:
            self._current += 1
            self.call_later(self._render_screen)
        else:
            self.result = "complete"
            self.exit()

    def action_prev_screen(self) -> None:
        if self._current in (3, 5, 6):
            return
        if self._current > 0:
            self._current -= 1
            self.call_later(self._render_screen)

    def action_quit_installer(self) -> None:
        if self._current == 5 and self.install_running:
            return
        self.result = "quit"
        self.exit()
