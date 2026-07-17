from __future__ import annotations

from pathlib import Path
from typing import Any

_PACKAGE = "vibecrafted_core"


def _package_files() -> Any:
    module = __import__("importlib.resources", fromlist=["files"])
    return module.files(_PACKAGE)


def resource_path(*parts: str) -> Path:
    resource = _package_files().joinpath(*parts)
    path = Path(str(resource))
    if path.exists():
        return path
    joined = "/".join(parts) or _PACKAGE
    raise FileNotFoundError(f"vibecrafted package resource missing: {joined}")


def package_root() -> Path:
    return resource_path()


def runtime_path() -> Path:
    return resource_path("runtime")


def skills_path() -> Path:
    return resource_path("skills")


def schemas_path() -> Path:
    return resource_path("schemas")


def deck_path() -> Path:
    return resource_path("deck", "vibecrafted")
