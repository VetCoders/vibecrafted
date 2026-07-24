"""iTerm2 / locterm AutoLaunch plugin for vibecrafted.

This subpackage ships a separate-process iTerm2 plugin (AutoLaunch script,
StatusBarComponent, Triggers) that talks to the vibecrafted control plane
via the public events.jsonl stream. It does NOT import the rest of
``vibecrafted_core`` at runtime: the AutoLaunch script must boot inside
iTerm2's vendored Python sandbox, where only stdlib + the ``iterm2``
package are guaranteed.

GPL boundary: this code lives in vibecrafted (Apache-2.0-style proprietary)
and talks to iTerm2 / locterm (GPL v2) over a documented WebSocket API.
That is a clean GPL-aggregation boundary per FSF guidance — no static
linking, no source mixing, no derivative work claim.
"""

from __future__ import annotations

EVENTS_JSONL_RELPATH = "control_plane/events.jsonl"
SPAWN_UPDATE_KIND = "spawn-update"
STATUS_BAR_COMPONENT_ID = "io.vetcoders.vibecrafted.status"
DEFAULT_RECONNECT_BACKOFF = (1.0, 2.0, 4.0, 8.0, 16.0)
STDIO_LIMIT_BYTES = 16 * 1024 * 1024

__all__ = [
    "DEFAULT_RECONNECT_BACKOFF",
    "EVENTS_JSONL_RELPATH",
    "SPAWN_UPDATE_KIND",
    "STATUS_BAR_COMPONENT_ID",
    "STDIO_LIMIT_BYTES",
]
