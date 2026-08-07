"""Filesystem layout for vibecrafted's runtime homes, staged tools, and launchers.

Every path here is env-overridable (``VIBECRAFTED_HOME`` / ``XDG_*`` / etc.) so
callers never hardcode a user's layout; ``resolve_env_path`` is the shared knob.
"""

from __future__ import annotations

import os
from pathlib import Path


def read_version_file(root: str | Path) -> str:
    """Read ``<root>/VERSION`` verbatim, or ``"unknown"`` when it is absent."""
    version_file = Path(root) / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"


def version_is_stamped(version: str) -> bool:
    """Install contract: ``X.Y.Z+gSHORTSHA`` (see docs/INSTALL.md).

    Bare ``X.Y.Z`` is not an install identity — it is either an unstamped
    living-tree checkout or a broken editable install that must not win PATH.
    """
    if not version or version == "unknown":
        return False
    # Accept +gabc1234 style only (not arbitrary local labels).
    plus = version.find("+g")
    if plus < 0:
        return False
    sha = version[plus + 2 :]
    return bool(sha) and all(c in "0123456789abcdefABCDEF" for c in sha)


def read_staged_tools_version() -> str:
    """VERSION stamped by ``make install`` into tools/vibecrafted-current.

    Prefer the root VERSION, then the package-local file next to the staged
    ``vibecrafted_core`` package (mirrors how the live package reads itself).
    """
    current = vibecrafted_tools_home() / "vibecrafted-current"
    for candidate in (
        current / "VERSION",
        current / "vibecrafted-core" / "vibecrafted_core" / "VERSION",
        current / "vibecrafted-core" / "VERSION",
    ):
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8").strip()
            if text:
                return text
    return "unknown"


def resolve_env_path(name: str, default: Path) -> Path:
    """Return ``$name`` expanded to a ``Path`` if set, else the expanded default."""
    raw = os.environ.get(name)
    if raw:
        return Path(raw).expanduser()
    return default.expanduser()


def xdg_config_home() -> Path:
    """``$XDG_CONFIG_HOME`` or ``~/.config``."""
    return resolve_env_path("XDG_CONFIG_HOME", Path.home() / ".config")


def xdg_data_home() -> Path:
    """``$XDG_DATA_HOME`` or ``~/.local/share``."""
    return resolve_env_path("XDG_DATA_HOME", Path.home() / ".local" / "share")


def vibecrafted_home() -> Path:
    """``$VIBECRAFTED_HOME`` or ``~/.vibecrafted`` — the control-plane root."""
    if os.environ.get("VIBECRAFTED_HOME"):
        return Path(os.environ["VIBECRAFTED_HOME"]).expanduser()
    return Path.home() / ".vibecrafted"


def vibecrafted_backups_home() -> Path:
    """Where the installer stashes pre-install backups, under the home root."""
    return vibecrafted_home() / "backups" / "installer"


def vibecrafted_runtime_home() -> Path:
    """``$VIBECRAFTED_RUNTIME_HOME`` or ``<xdg_data_home>/vibecrafted``."""
    return resolve_env_path("VIBECRAFTED_RUNTIME_HOME", xdg_data_home() / "vibecrafted")


def vibecrafted_tools_home() -> Path:
    """``$VIBECRAFTED_TOOLS_HOME`` or ``<runtime_home>/tools`` — staged installs."""
    return resolve_env_path(
        "VIBECRAFTED_TOOLS_HOME",
        vibecrafted_runtime_home() / "tools",
    )


def vibecrafted_runtime_bin() -> Path:
    """``$VIBECRAFTED_RUNTIME_BIN`` or ``<runtime_home>/bin``."""
    return resolve_env_path(
        "VIBECRAFTED_RUNTIME_BIN", vibecrafted_runtime_home() / "bin"
    )


def vibecrafted_launcher_bin() -> Path:
    """``$VIBECRAFTED_LAUNCHER_BIN`` or ``~/.local/bin`` — where shims land on PATH."""
    return resolve_env_path("VIBECRAFTED_LAUNCHER_BIN", Path.home() / ".local" / "bin")
