from __future__ import annotations

import os
from pathlib import Path


def read_version_file(root: str | Path) -> str:
    version_file = Path(root) / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"


def resolve_env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if raw:
        return Path(raw).expanduser()
    return default.expanduser()


def xdg_config_home() -> Path:
    return resolve_env_path("XDG_CONFIG_HOME", Path.home() / ".config")


def vibecrafted_home() -> Path:
    return resolve_env_path("VIBECRAFTED_HOME", Path.home() / ".vibecrafted")
