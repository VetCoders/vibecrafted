"""Package-data accessors for frontier / vc-frame config assets.

Canonical sources live at the monorepo root ``config/vc-frame/``. Hatch
force-includes that tree into ``vibecrafted_core/config/vc-frame`` at build
time so pip/pipx wheels carry the full set. Checkout runs fall back to the
repo-root tree so dev never needs a copy.
"""

from __future__ import annotations

from pathlib import Path

from .package_resources import resource_path


def _repo_root_config() -> Path | None:
    """Return ``<repo>/config/vc-frame`` when running from a source checkout.

    Walks parent directories looking for a monorepo layout; returns ``None``
    when no matching ``config/vc-frame/config.kdl`` is found (packaged install).
    """
    # vibecrafted_core/frontier_assets.py → package dir → vibecrafted-core → repo
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "vc-frame"
        if (candidate / "config.kdl").is_file() and (
            parent / "vibecrafted-core"
        ).is_dir():
            return candidate
        # Also accept monorepo root that has config/vc-frame next to pyproject
        if (
            (candidate / "config.kdl").is_file()
            and (parent / "pyproject.toml").is_file()
            and (parent / "vibecrafted_core").is_dir() is False
        ):
            # vibecrafted-core/pyproject.toml case handled above via vibecrafted-core parent
            pass
    # Direct: package in vibecrafted-core/vibecrafted_core
    package_root = here.parent  # vibecrafted_core
    core_root = package_root.parent  # vibecrafted-core
    monorepo = core_root.parent
    for base in (monorepo, core_root, package_root.parent.parent):
        candidate = base / "config" / "vc-frame"
        if (candidate / "config.kdl").is_file():
            return candidate
    return None


def vc_frame_config_source() -> Path:
    """Resolve the directory that holds the shipped ``config/vc-frame`` tree.

    Preference order:
    1. Packaged data under ``vibecrafted_core/config/vc-frame`` (wheel/sdist install).
    2. Repo-root ``config/vc-frame`` when running from a Living Tree checkout.
    """
    try:
        packaged = resource_path("config", "vc-frame")
        if packaged.is_dir() and (packaged / "config.kdl").is_file():
            return packaged
    except FileNotFoundError:
        pass

    repo = _repo_root_config()
    if repo is not None:
        return repo

    raise FileNotFoundError(
        "vc-frame config source not found: neither packaged "
        "vibecrafted_core/config/vc-frame nor repo config/vc-frame is available"
    )


def vc_frame_config_kdl() -> Path:
    """Return the resolved ``config.kdl`` path, raising if it is missing."""
    path = vc_frame_config_source() / "config.kdl"
    if not path.is_file():
        raise FileNotFoundError(f"missing config.kdl under {vc_frame_config_source()}")
    return path
