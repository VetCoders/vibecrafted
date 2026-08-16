"""Filesystem layout for vibecrafted's runtime homes, staged tools, and launchers.

Every path here is env-overridable (``VIBECRAFTED_HOME`` / ``XDG_*`` / etc.) so
callers never hardcode a user's layout; ``resolve_env_path`` is the shared knob.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
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


def agent_tool_search_path(environment: Mapping[str, str] | None = None) -> str:
    """Return the canonical allowlisted PATH for detached provider processes.

    Launchd and other supervisors intentionally provide a minimal environment.
    Provider discovery must therefore not depend on interactive shell startup,
    but it must also not trust arbitrary inherited PATH entries.  Keep this in
    lockstep with ``runtime/scripts/lib/util.sh:spawn_prepend_agent_tool_paths``.
    """

    env = os.environ if environment is None else environment
    raw_home = str(env.get("HOME", "")).strip()
    home = Path(raw_home).expanduser() if raw_home else Path.home()
    raw_xdg_data = str(env.get("XDG_DATA_HOME", "")).strip()
    xdg_data = (
        Path(raw_xdg_data).expanduser() if raw_xdg_data else home / ".local/share"
    )
    raw_runtime_home = str(env.get("VIBECRAFTED_RUNTIME_HOME", "")).strip()
    runtime_home = (
        Path(raw_runtime_home).expanduser()
        if raw_runtime_home
        else xdg_data / "vibecrafted"
    )
    raw_runtime_bin = str(env.get("VIBECRAFTED_RUNTIME_BIN", "")).strip()
    runtime_bin = (
        Path(raw_runtime_bin).expanduser() if raw_runtime_bin else runtime_home / "bin"
    )
    candidates = (
        runtime_bin,
        home / ".local/bin",
        home / ".cargo/bin",
        home / "tools/scripts",
        Path("/opt/homebrew/bin"),
        Path("/opt/homebrew/sbin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
        Path("/usr/sbin"),
        Path("/sbin"),
    )
    resolved: list[str] = []
    for candidate in candidates:
        text = str(candidate)
        if candidate.is_dir() and text not in resolved:
            resolved.append(text)
    return os.pathsep.join(resolved)
