"""Filesystem layout for vibecrafted's runtime homes, staged tools, and launchers.

Every path here is env-overridable (``VIBECRAFTED_HOME`` / ``XDG_*`` / etc.) so
callers never hardcode a user's layout; ``resolve_env_path`` is the shared knob.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

ACTIVE_RUNTIME_SCHEMA = "vibecrafted.active-runtime.v1"


class GenerationResolutionError(RuntimeError):
    """Raised when active.json and vibecrafted-current disagree or neither exists."""


def is_windows() -> bool:
    """True on native Windows (not POSIX emulation that still sets ``win32``)."""
    return sys.platform == "win32"


def windows_profile_home() -> Path:
    """Operator profile root: ``USERPROFILE``, then ``HOME``, then ``Path.home()``."""
    for name in ("USERPROFILE", "HOME"):
        raw = str(os.environ.get(name, "")).strip()
        if raw:
            return Path(raw).expanduser()
    return Path.home()


def windows_local_app_data() -> Path:
    """``LOCALAPPDATA`` or ``<profile>\\AppData\\Local`` — never a hardcoded user."""
    raw = str(os.environ.get("LOCALAPPDATA", "")).strip()
    if raw:
        return Path(raw).expanduser()
    return windows_profile_home() / "AppData" / "Local"


def windows_roaming_app_data() -> Path:
    """``APPDATA`` or ``<profile>\\AppData\\Roaming``."""
    raw = str(os.environ.get("APPDATA", "")).strip()
    if raw:
        return Path(raw).expanduser()
    return windows_profile_home() / "AppData" / "Roaming"


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
    """VERSION stamped into the active generation (active.json, then current)."""
    try:
        generation = resolve_active_generation()
    except GenerationResolutionError:
        generation = vibecrafted_tools_home() / "vibecrafted-current"
    for candidate in (
        generation / "VERSION",
        generation / "vibecrafted-core" / "vibecrafted_core" / "VERSION",
        generation / "vibecrafted-core" / "VERSION",
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
    """``$XDG_CONFIG_HOME``, else native config home (``APPDATA`` on Windows)."""
    raw = os.environ.get("XDG_CONFIG_HOME")
    if raw:
        return Path(raw).expanduser()
    if is_windows():
        return windows_roaming_app_data()
    return (Path.home() / ".config").expanduser()


def xdg_data_home() -> Path:
    """``$XDG_DATA_HOME``, else native data home (``LOCALAPPDATA`` on Windows)."""
    raw = os.environ.get("XDG_DATA_HOME")
    if raw:
        return Path(raw).expanduser()
    if is_windows():
        return windows_local_app_data()
    return (Path.home() / ".local" / "share").expanduser()


def canonical_vibecrafted_home() -> Path:
    """OS default control-plane root, ignoring ``VIBECRAFTED_HOME``."""
    if is_windows():
        return canonical_vibecrafted_runtime_home() / "home"
    return Path.home() / ".vibecrafted"


def canonical_vibecrafted_runtime_home() -> Path:
    """OS default runtime home, ignoring ``VIBECRAFTED_RUNTIME_HOME`` / ``XDG_*``."""
    if is_windows():
        return windows_local_app_data() / "Vibecrafted"
    return Path.home() / ".local" / "share" / "vibecrafted"


def canonical_vibecrafted_launcher_bin() -> Path:
    """OS default launcher bin, ignoring ``VIBECRAFTED_LAUNCHER_BIN``."""
    if is_windows():
        return canonical_vibecrafted_runtime_home() / "bin"
    return Path.home() / ".local" / "bin"


def canonical_vibecrafted_product_config_home() -> Path:
    """OS default product config directory."""
    if is_windows():
        return windows_roaming_app_data() / "Vibecrafted"
    return Path.home() / ".config" / "vibecrafted"


def vibecrafted_product_config_home() -> Path:
    """``$XDG_CONFIG_HOME/vibecrafted`` or native ``APPDATA\\Vibecrafted``."""
    if os.environ.get("XDG_CONFIG_HOME"):
        return xdg_config_home() / "vibecrafted"
    if is_windows():
        return canonical_vibecrafted_product_config_home()
    return xdg_config_home() / "vibecrafted"


def vibecrafted_home() -> Path:
    """``$VIBECRAFTED_HOME`` or the platform control-plane root."""
    if os.environ.get("VIBECRAFTED_HOME"):
        return Path(os.environ["VIBECRAFTED_HOME"]).expanduser()
    return canonical_vibecrafted_home()


def vibecrafted_backups_home() -> Path:
    """Where the installer stashes pre-install backups, under the home root."""
    return vibecrafted_home() / "backups" / "installer"


def vibecrafted_runtime_home() -> Path:
    """``$VIBECRAFTED_RUNTIME_HOME`` or the platform runtime home."""
    if os.environ.get("VIBECRAFTED_RUNTIME_HOME"):
        return Path(os.environ["VIBECRAFTED_RUNTIME_HOME"]).expanduser()
    if os.environ.get("XDG_DATA_HOME"):
        return xdg_data_home() / "vibecrafted"
    if is_windows():
        return canonical_vibecrafted_runtime_home()
    return xdg_data_home() / "vibecrafted"


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


def resolve_operator_launch_root(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Root for `vibecrafted review` and siblings when the operator is at $HOME.

    App shells often start in the home directory. A selected WES workspace is
    the product root; reviewing `$HOME` is never a useful default.
    """

    environ = os.environ if env is None else env
    here = (cwd or Path.cwd()).expanduser().resolve()
    raw_home = str(environ.get("HOME") or "").strip()
    home = Path(raw_home).expanduser().resolve() if raw_home else Path.home().resolve()
    workspace = str(environ.get("VIBECRAFTED_WORKSPACE_ROOT") or "").strip()
    in_git = (here / ".git").exists() or any(
        (parent / ".git").exists() for parent in here.parents
    )
    if workspace and (here == home or not in_git):
        selected = Path(workspace).expanduser().resolve()
        if selected.is_dir():
            return selected
    return here


def is_operator_home_root(
    root: str | Path,
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    """True when ``root`` is the operator home directory (never a useful launch)."""

    environ = os.environ if env is None else env
    raw_home = str(environ.get("HOME") or "").strip()
    home = Path(raw_home).expanduser().resolve() if raw_home else Path.home().resolve()
    try:
        return Path(root).expanduser().resolve() == home
    except OSError:
        return False


def vibecrafted_launcher_bin() -> Path:
    """``$VIBECRAFTED_LAUNCHER_BIN`` or the platform launcher directory."""
    if os.environ.get("VIBECRAFTED_LAUNCHER_BIN"):
        return Path(os.environ["VIBECRAFTED_LAUNCHER_BIN"]).expanduser()
    return canonical_vibecrafted_launcher_bin()


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
    raw_runtime_home = str(env.get("VIBECRAFTED_RUNTIME_HOME", "")).strip()
    raw_runtime_bin = str(env.get("VIBECRAFTED_RUNTIME_BIN", "")).strip()
    if raw_runtime_home:
        runtime_home = Path(raw_runtime_home).expanduser()
    elif is_windows():
        if raw_xdg_data:
            runtime_home = Path(raw_xdg_data).expanduser() / "vibecrafted"
        else:
            raw_local = str(env.get("LOCALAPPDATA", "")).strip()
            if raw_local:
                runtime_home = Path(raw_local).expanduser() / "Vibecrafted"
            else:
                profile = str(env.get("USERPROFILE") or raw_home or "").strip()
                root = Path(profile).expanduser() if profile else Path.home()
                runtime_home = root / "AppData" / "Local" / "Vibecrafted"
    else:
        xdg_data = (
            Path(raw_xdg_data).expanduser() if raw_xdg_data else home / ".local/share"
        )
        runtime_home = xdg_data / "vibecrafted"
    runtime_bin = (
        Path(raw_runtime_bin).expanduser() if raw_runtime_bin else runtime_home / "bin"
    )
    if is_windows():
        system_root = Path(
            env.get("SystemRoot") or os.environ.get("SystemRoot") or r"C:\Windows"
        )
        launcher = (
            Path(env["VIBECRAFTED_LAUNCHER_BIN"]).expanduser()
            if str(env.get("VIBECRAFTED_LAUNCHER_BIN", "")).strip()
            else runtime_home / "bin"
        )
        candidates = (
            runtime_bin,
            launcher,
            system_root / "System32",
            system_root,
        )
    else:
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


def active_runtime_pointer(runtime_home: Path | None = None) -> Path:
    """Path to the one active-generation JSON pointer."""
    return (runtime_home or vibecrafted_runtime_home()) / "active.json"


def current_generation_projection(runtime_home: Path | None = None) -> Path:
    """Filesystem projection of the active generation (symlink or junction)."""
    tools = (
        vibecrafted_tools_home()
        if runtime_home is None
        else resolve_env_path("VIBECRAFTED_TOOLS_HOME", runtime_home / "tools")
    )
    return tools / "vibecrafted-current"


def _read_active_runtime_root(pointer: Path, runtime_home: Path) -> Path | None:
    if pointer.is_symlink():
        raise GenerationResolutionError("active.json must not be a symlink")
    if not pointer.is_file():
        return None
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise GenerationResolutionError(
            f"active runtime pointer is unreadable: {pointer}"
        )
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != ACTIVE_RUNTIME_SCHEMA
        or not isinstance(payload.get("runtime_root"), str)
        or not payload["runtime_root"]
    ):
        raise GenerationResolutionError(f"active runtime pointer is invalid: {pointer}")
    generation = Path(payload["runtime_root"]).expanduser()
    if not generation.is_absolute():
        raise GenerationResolutionError("active runtime_root must be absolute")
    try:
        resolved = generation.resolve(strict=True)
        home = runtime_home.resolve(strict=False)
    except OSError as exc:
        raise GenerationResolutionError(
            f"active runtime_root cannot be resolved: {exc}"
        ) from exc
    if resolved != home and home not in resolved.parents:
        raise GenerationResolutionError(
            f"active runtime_root escapes runtime home: {resolved}"
        )
    return resolved


def _is_generation_pointer(path: Path) -> bool:
    """True for a unix symlink or a Windows directory junction."""
    if path.is_symlink():
        return True
    junction = getattr(path, "is_junction", None)
    if junction is None:
        return False
    try:
        return bool(junction())
    except OSError:
        return False


def resolve_active_generation(runtime_home: Path | None = None) -> Path:
    """Return the one installed generation. ``active.json`` is authority.

    ``tools/vibecrafted-current`` is a projection. When both exist they must
    name the same directory; disagreement is split-brain and fail-closed.
    """
    home = (runtime_home or vibecrafted_runtime_home()).expanduser()
    pointer = active_runtime_pointer(home)
    current = current_generation_projection(home)
    active_root = _read_active_runtime_root(pointer, home) if pointer.exists() else None
    current_root: Path | None = None
    pointer_present = current.exists() or current.is_symlink()
    if pointer_present:
        if not _is_generation_pointer(current):
            raise GenerationResolutionError(
                f"{current} is not an atomic generation pointer"
            )
        try:
            current_root = current.resolve(strict=True)
        except OSError as exc:
            raise GenerationResolutionError(
                f"cannot resolve current runtime generation: {exc}"
            ) from exc
    if active_root is not None and current_root is not None:
        if active_root != current_root:
            raise GenerationResolutionError(
                f"split-brain: active.json names {active_root} but "
                f"vibecrafted-current names {current_root}"
            )
        return active_root
    if active_root is not None:
        return active_root
    if current_root is not None:
        if is_windows():
            raise GenerationResolutionError(
                "vibecrafted-current exists without active.json"
            )
        return current_root
    raise GenerationResolutionError("no active Runtime Pack generation")


def launcher_name(name: str) -> str:
    """Public launcher filename on this platform (``.cmd`` on Windows)."""
    if is_windows() and not name.lower().endswith((".cmd", ".bat", ".exe")):
        return f"{name}.cmd"
    return name

