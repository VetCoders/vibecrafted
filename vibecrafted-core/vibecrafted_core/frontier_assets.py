"""Package-data accessors for the canonical vc-frame configuration tree."""

from __future__ import annotations

from pathlib import Path

from .package_resources import resource_path


def vc_frame_config_source() -> Path:
    """Resolve the directory that holds the shipped ``config/vc-frame`` tree.

    The package path is the one source owner in both a checkout and a wheel.
    """
    packaged = resource_path("config", "vc-frame")
    if packaged.is_dir() and (packaged / "config.kdl").is_file():
        return packaged
    raise FileNotFoundError(
        "vc-frame config source not found at vibecrafted_core/config/vc-frame"
    )


def vc_frame_config_kdl() -> Path:
    """Return the resolved ``config.kdl`` path, raising if it is missing."""
    path = vc_frame_config_source() / "config.kdl"
    if not path.is_file():
        raise FileNotFoundError(f"missing config.kdl under {vc_frame_config_source()}")
    return path
