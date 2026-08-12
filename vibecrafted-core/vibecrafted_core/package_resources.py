"""Resolve installed-package resource paths (runtime/skills/deck) via importlib."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PACKAGE = "vibecrafted_core"


def _package_files() -> Any:
    """Return the ``importlib.resources`` traversable root for this package."""
    module = __import__("importlib.resources", fromlist=["files"])
    return module.files(_PACKAGE)


def resource_path(*parts: str) -> Path:
    """Resolve a resource path under the installed package; raise if missing."""
    resource = _package_files().joinpath(*parts)
    path = Path(str(resource))
    if path.exists():
        return path
    joined = "/".join(parts) or _PACKAGE
    raise FileNotFoundError(f"vibecrafted package resource missing: {joined}")


def package_root() -> Path:
    """Root directory of the installed ``vibecrafted_core`` package."""
    return resource_path()


def runtime_path() -> Path:
    """Path to the bundled ``runtime`` resource directory."""
    return resource_path("runtime")


def skills_path() -> Path:
    """Path to the bundled ``skills`` resource directory."""
    return resource_path("skills")


def deck_path() -> Path:
    """Path to the bundled ``deck/vibecrafted`` resource directory."""
    return resource_path("deck", "vibecrafted")


def release_contract_paths() -> tuple[Path, Path, Path, Path]:
    """Return every package-owned release verifier/trust resource."""
    return (
        resource_path("walkaround_runner.py"),
        resource_path("schemas", "unified_product.schema.v1.json"),
        resource_path("trust", "release-policy.v1.json"),
        resource_path("trust", "vibecrafted-signing-v1.pub"),
    )
