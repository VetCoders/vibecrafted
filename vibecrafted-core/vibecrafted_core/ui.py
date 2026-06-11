"""𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shared CLI output contract (python side).

Mirror of scripts/lib/vc_ui.sh — keep the two in lockstep.

Contract (docs/CLI_PRODUCT_SPEC.md §3):
  - one spinner (braille, copper, 80 ms), one success line, one error shape
  - color only on a TTY, NO_COLOR honored, glyph is the prefix (no [error])
  - stage messages are verb + object: scanning · resolving · staging ·
    installing · finalizing
"""

from __future__ import annotations

import itertools
import os
import sys
import threading
from types import TracebackType

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPINNER_INTERVAL = 0.08

_TOKENS = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "copper": "\033[38;5;173m",
    "steel": "\033[38;5;247m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "red": "\033[31m",
    "reset": "\033[0m",
}


def _colors_enabled(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _tok(name: str, stream=None) -> str:
    return _TOKENS[name] if _colors_enabled(stream or sys.stdout) else ""


def stage(message: str) -> None:
    """One bounded stage line (the non-animated form)."""
    print(f"{_tok('copper')}▸{_tok('reset')} {message}")


def ok(result: str) -> None:
    """Success: one line, the key result only."""
    print(f"{_tok('green')}✓{_tok('reset')} {result}")


def warn(message: str) -> None:
    """Warning: one line, never apologetic."""
    print(f"{_tok('yellow')}!{_tok('reset')} {message}")


def err(what_failed: str, fix: str | None = None, log: str | None = None) -> None:
    """Error shape, always stderr: what failed · one fix · log path."""
    s = sys.stderr
    print(f"{_tok('red', s)}✗{_tok('reset', s)} {what_failed}", file=s)
    if fix:
        print(f"  {_tok('dim', s)}→ fix:{_tok('reset', s)} {fix}", file=s)
    if log:
        print(f"  {_tok('dim', s)}log: {log}{_tok('reset', s)}", file=s)


def next_step(command: str, hint: str = "") -> None:
    """Exactly one next step, dim."""
    suffix = f" {_tok('dim')}{hint}{_tok('reset')}" if hint else ""
    print(
        f"  {_tok('dim')}→ next:{_tok('reset')} "
        f"{_tok('cyan')}{command}{_tok('reset')}{suffix}"
    )


def bounded(items: list[str], limit: int = 8, head: int = 5) -> list[str]:
    """Lists longer than ``limit`` collapse to head + '… and N more (--full)'."""
    if len(items) <= limit:
        return list(items)
    return list(items[:head]) + [f"… and {len(items) - head} more (--full)"]


class Spinner:
    """Single-line stage spinner; the line is replaced on exit.

    On a TTY: braille frames, copper, 80 ms, rendered with \\r\\033[K.
    Non-TTY / NO_COLOR / CI: one ▸ stage line, nothing animated.

        with Spinner("scanning repo"):
            ...
    Success replaces the line via ``spinner.done("scanned repo")``;
    otherwise the stage line is cleared on exit.
    """

    def __init__(self, message: str, stream=None) -> None:
        self.message = message
        self.stream = stream or sys.stdout
        self._animated = _colors_enabled(self.stream)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "Spinner":
        if not self._animated:
            print(f"▸ {self.message}", file=self.stream, flush=True)
            return self
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def _spin(self) -> None:
        copper, reset = _TOKENS["copper"], _TOKENS["reset"]
        for frame in itertools.cycle(SPINNER_FRAMES):
            if self._stop.wait(SPINNER_INTERVAL):
                break
            self.stream.write(f"\r\033[K{copper}{frame}{reset} {self.message}")
            self.stream.flush()

    def _clear(self) -> None:
        if self._animated:
            self._stop.set()
            if self._thread:
                self._thread.join()
                self._thread = None
            self.stream.write("\r\033[K")
            self.stream.flush()

    def done(self, result: str) -> None:
        """Replace the spinner line with the success line."""
        self._clear()
        ok(result)

    def fail(
        self, what_failed: str, fix: str | None = None, log: str | None = None
    ) -> None:
        """Replace the spinner line with the error shape."""
        self._clear()
        err(what_failed, fix=fix, log=log)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._clear()
