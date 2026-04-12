"""Textual TUI app for the installer intro wizard.

Renders mockup screens from ``docs/installer/*.md`` with a sticky branded
header, scrollable content area, and sticky footer navigation bar.

The mockup markdown is pre-parsed into (header, content, footer) tuples
by ``_parse_mock_layers`` in ``__init__.py`` before being handed here.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static


class InstallerIntroApp(App):
    """Multi-screen intro wizard driven by mockup markdown layers."""

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
    #content {
        padding: 0 2;
    }
    #footer {
        dock: bottom;
        height: auto;
        background: $surface;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("enter", "next_screen", "Proceed", show=True),
        Binding("down", "next_screen", "Next", show=False),
        Binding("space", "next_screen", "Next", show=False),
        Binding("backspace", "prev_screen", "Back", show=True),
        Binding("up", "prev_screen", "Back", show=False),
        Binding("escape", "quit_installer", "Quit", show=True),
        Binding("q", "quit_installer", "Quit", show=False),
    ]

    def __init__(
        self,
        screens: list[tuple[str, str, str]],
        version: str,
    ) -> None:
        """Initialise with pre-parsed mockup layers.

        Parameters
        ----------
        screens:
            List of ``(header, content, footer)`` text tuples, one per
            intro step.  These are plain-text strings (unicode preserved)
            that must be rendered with ``markup=False``.
        version:
            Manifest version string (informational only -- interpolation
            already happened in ``_load_mock_screen``).
        """
        super().__init__()
        self._screens = screens
        self._version = version
        self._current = 0
        self.result: str = "quit"  # default if user closes window

    def compose(self) -> ComposeResult:
        yield Static(id="header", markup=False)
        yield VerticalScroll(Static(id="content", markup=False), id="scroll-area")
        yield Static(id="footer", markup=False)

    def on_mount(self) -> None:
        self._render_screen()

    # -- Screen rendering ---------------------------------------------------

    def _render_screen(self) -> None:
        """Push the current screen's layers into the three widget slots."""
        header, content, footer = self._screens[self._current]
        self.query_one("#header", Static).update(header)
        self.query_one("#content", Static).update(content)
        self.query_one("#footer", Static).update(footer)
        # Reset scroll position when switching screens.
        self.query_one("#scroll-area", VerticalScroll).scroll_home(animate=False)

    # -- Actions bound to keys ----------------------------------------------

    def action_next_screen(self) -> None:
        if self._current < len(self._screens) - 1:
            self._current += 1
            self._render_screen()
        else:
            self.result = "complete"
            self.exit()

    def action_prev_screen(self) -> None:
        if self._current > 0:
            self._current -= 1
            self._render_screen()

    def action_quit_installer(self) -> None:
        self.result = "quit"
        self.exit()
