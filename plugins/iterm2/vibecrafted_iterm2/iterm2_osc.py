"""iTerm2 OSC escape-code primitives.

Pure stdlib helpers that emit OSC 1337 / OSC 9 / OSC 8 / OSC 133 / OSC 4
sequences understood by iTerm2. The functions return the literal byte
strings; callers decide whether to print them, embed them in shell
commands, or write them to a file.

These primitives are independent of how a session was spawned — they work
inside any iTerm2 pane (vc_frame child, ssh remote, agent shell) as long as
stdout is attached to an iTerm2 terminal.

Status: **GA since v1.8.0 / 2026-05-12** (Plan 10, META_22). The function
signatures and the literal escape sequences they emit are a stable public
wire contract — callers across the framework (agent dashboards, OSC 8
hyperlink wrappers, custom dispatch surfaces) can rely on them without
defensive guards.

Reference: https://iterm2.com/documentation-escape-codes.html
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Literal

ESC = "\x1b"
BEL = "\x07"
OSC = ESC + "]"
ST = BEL  # OSC string terminator; ESC \ also valid


def _b64(value: str) -> str:
    """Base64-encode `value` as UTF-8 for OSC payload embedding."""
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


# --------------------------------------------------------------------- OSC 1337


def set_badge(text: str) -> str:
    """Set the iTerm2 badge to `text`.

    The badge is a large translucent label in the top-right of the pane.
    `text` may contain interpolated string syntax like ``\\(session.name)``
    if the session profile evaluates them; iTerm2 itself decodes the
    base64 payload as a UTF-8 string.
    """
    return f"{OSC}1337;SetBadgeFormat={_b64(text)}{ST}"


def set_profile(name: str) -> str:
    """Switch the current session to a profile by name."""
    return f"{OSC}1337;SetProfile={name}{ST}"


def set_user_var(key: str, value: str) -> str:
    """Set a user variable (visible as ``user.<key>`` in interpolated strings)."""
    return f"{OSC}1337;SetUserVar={key}={_b64(value)}{ST}"


def set_colors(key: str, value: str) -> str:
    """Adjust a session color slot.

    `key` is one of: fg, bg, bold, link, selbg, selfg, curbg, curfg,
    underline, tab, black, red, green, yellow, blue, magenta, cyan,
    white, br_black ... br_white, or `preset` (with `value` as a preset
    name) or `tab` (with `value` as `default` to clear).

    `value` formats accepted: RGB (3 hex digits), RRGGBB (6 hex digits),
    optionally prefixed with a colorspace like ``p3:`` or ``srgb:``.
    """
    return f"{OSC}1337;SetColors={key}={value}{ST}"


def set_mark() -> str:
    """Drop a navigable mark at the current cursor position (cmd-shift-J)."""
    return f"{OSC}1337;SetMark{ST}"


def steal_focus() -> str:
    """Bring iTerm2 to the foreground."""
    return f"{OSC}1337;StealFocus{ST}"


def clear_scrollback() -> str:
    """Erase the scrollback history of the current session."""
    return f"{OSC}1337;ClearScrollback{ST}"


def set_current_dir(path: str) -> str:
    """Inform iTerm2 of the current working directory (semantic history)."""
    return f"{OSC}1337;CurrentDir={path}{ST}"


def request_attention(mode: Literal["yes", "once", "no", "fireworks"] = "once") -> str:
    """Request user attention.

    `yes`       — bounce dock icon indefinitely until iTerm2 becomes key
    `once`      — bounce once
    `no`        — cancel a previous request
    `fireworks` — show the cursor-position firework animation
    """
    return f"{OSC}1337;RequestAttention={mode}{ST}"


def cursor_shape(shape: Literal[0, 1, 2]) -> str:
    """Set cursor shape: 0=block, 1=vertical bar, 2=underline."""
    return f"{OSC}1337;CursorShape={int(shape)}{ST}"


def highlight_cursor_line(enabled: bool) -> str:
    """Show or hide the cursor guide (horizontal rule under cursor)."""
    flag = "yes" if enabled else "no"
    return f"{OSC}1337;HighlightCursorLine={flag}{ST}"


# --------------------------------------------------------------------- Blocks


def block_start(block_id: str) -> str:
    """Mark the start of a foldable code block region."""
    return f"{OSC}1337;Block=id={block_id};attr=start{ST}"


def block_end(block_id: str) -> str:
    """Mark the end of a foldable code block region."""
    return f"{OSC}1337;Block=id={block_id};attr=end{ST}"


def update_block(block_id: str, action: Literal["fold", "unfold"]) -> str:
    """Fold or unfold a previously defined block (iTerm2 3.6.9+)."""
    return f"{OSC}1337;UpdateBlock=id={block_id};action={action}{ST}"


# --------------------------------------------------------------------- Buttons


def custom_button(code: int, icon: str) -> str:
    """Create a custom button in the tab title.

    When clicked, iTerm2 sends ``CSI ? 1337 ; <code> ~`` back to the
    running application. `icon` is an SF Symbol name (``star.fill``,
    ``checkmark.circle``, ``xmark.octagon``).
    """
    return f"{OSC}1337;Button=type=custom;code={int(code)};icon={icon}{ST}"


def invalidate_buttons() -> str:
    """Gray out all custom buttons (e.g. when leaving the relevant context)."""
    return f"{OSC}1337;Button=type=custom{ST}"


# --------------------------------------------------------------------- OSC 9 (notification + progress)


def post_notification(message: str) -> str:
    """Post a Notification Center alert with `message`."""
    return f"{OSC}9;{message}{ST}"


def progress(state: Literal[0, 1, 2, 3, 4], percent: int | None = None) -> str:
    """Drive the tab-title progress bar.

    state 0 — clear
    state 1 — success at `percent`
    state 2 — error (percent optional; omit for indeterminate error)
    state 3 — indeterminate (animated)
    state 4 — warning at `percent`
    """
    if state in (1, 4):
        if percent is None:
            raise ValueError(f"progress state {state} requires percent")
        return f"{OSC}9;4;{int(state)};{int(percent)}{ST}"
    if state == 2 and percent is not None:
        return f"{OSC}9;4;2;{int(percent)}{ST}"
    if state == 0:
        return f"{OSC}9;4;0{ST}"
    return f"{OSC}9;4;{int(state)}{ST}"


# --------------------------------------------------------------------- OSC 8 (hyperlinks)


def hyperlink(url: str, text: str, *, link_id: str | None = None) -> str:
    """Wrap `text` in an OSC 8 hyperlink to `url`.

    `link_id` groups adjacent links with the same URL so they highlight
    separately under cmd-hover.
    """
    params = f"id={link_id}" if link_id else ""
    open_seq = f"{OSC}8;{params};{url}{ST}"
    close_seq = f"{OSC}8;;{ST}"
    return f"{open_seq}{text}{close_seq}"


# --------------------------------------------------------------------- OSC 133 (FinalTerm shell integration)


def ftcs_prompt() -> str:
    """Mark start of shell prompt (FTCS_PROMPT)."""
    return f"{OSC}133;A{ST}"


def ftcs_command_start() -> str:
    """Mark end of prompt / start of user command (FTCS_COMMAND_START)."""
    return f"{OSC}133;B{ST}"


def ftcs_command_executed() -> str:
    """Mark start of command output (FTCS_COMMAND_EXECUTED)."""
    return f"{OSC}133;C{ST}"


def ftcs_command_finished(exit_code: int | None = None) -> str:
    """Mark end of command output, optionally with exit code (FTCS_COMMAND_FINISHED)."""
    if exit_code is None:
        return f"{OSC}133;D{ST}"
    return f"{OSC}133;D;{int(exit_code)}{ST}"


def remote_host(user: str, host: str) -> str:
    """Report user@host to iTerm2 (used by Automatic Profile Switching)."""
    return f"{OSC}1337;RemoteHost={user}@{host}{ST}"


# --------------------------------------------------------------------- OSC 4 (color reporting)


def report_color(index: int) -> str:
    """Request RGB report for color index `index`.

    iTerm2 extension: -1 reports default foreground, -2 reports default
    background. iTerm2 will respond on stdin with the same OSC 4 form
    containing the rgb triplet.
    """
    return f"{OSC}4;{int(index)};?{ST}"


# --------------------------------------------------------------------- Helpers / __main__


_ALL_BUILDERS: dict[str, tuple[Callable[..., str], list[str]]] = {
    "badge": (set_badge, ["text"]),
    "profile": (set_profile, ["name"]),
    "user-var": (set_user_var, ["key", "value"]),
    "colors": (set_colors, ["key", "value"]),
    "mark": (set_mark, []),
    "steal-focus": (steal_focus, []),
    "clear-scrollback": (clear_scrollback, []),
    "current-dir": (set_current_dir, ["path"]),
    "attention": (request_attention, ["mode"]),
    "cursor": (cursor_shape, ["shape"]),
    "cursor-line": (highlight_cursor_line, ["enabled"]),
    "block-start": (block_start, ["id"]),
    "block-end": (block_end, ["id"]),
    "block-update": (update_block, ["id", "action"]),
    "button": (custom_button, ["code", "icon"]),
    "buttons-invalidate": (invalidate_buttons, []),
    "notify": (post_notification, ["message"]),
    "progress": (progress, ["state", "percent"]),
    "hyperlink": (hyperlink, ["url", "text"]),
    "remote-host": (remote_host, ["user", "host"]),
    "ftcs-prompt": (ftcs_prompt, []),
    "ftcs-cmd-start": (ftcs_command_start, []),
    "ftcs-cmd-exec": (ftcs_command_executed, []),
    "ftcs-cmd-end": (ftcs_command_finished, []),
}


def _cli(argv: list[str]) -> int:
    """Dispatch a single OSC builder by name and print its escape sequence."""
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: python -m vibecrafted_iterm2.iterm2_osc <op> [args...]\n")
        print("Available ops:")
        for name, (_, params) in sorted(_ALL_BUILDERS.items()):
            sig = " ".join(f"<{p}>" for p in params)
            print(f"  {name} {sig}".rstrip())
        return 0
    op, *rest = argv
    if op not in _ALL_BUILDERS:
        print(f"unknown op: {op!r}", flush=True)
        return 2
    fn, params = _ALL_BUILDERS[op]
    if op in ("progress", "cursor"):
        # numeric coercion for these specifically
        if op == "progress":
            state = int(rest[0])
            pct = int(rest[1]) if len(rest) > 1 else None
            output = fn(state, pct)
        else:
            output = fn(int(rest[0]))
    elif op == "cursor-line":
        output = fn(rest[0].lower() in ("yes", "true", "1", "on"))
    elif op == "button":
        output = fn(int(rest[0]), rest[1])
    elif op == "ftcs-cmd-end":
        output = fn(int(rest[0])) if rest else fn()
    else:
        output = fn(*rest[: len(params)])
    print(output, end="", flush=True)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
