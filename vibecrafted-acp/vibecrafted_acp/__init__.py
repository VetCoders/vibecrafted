"""ACP v1 adapter for the Vibecrafted evidence runtime."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("vibecrafted-acp")
except PackageNotFoundError:  # Source checkout without an installed wheel.
    __version__ = "3.6.0"

__all__ = ["__version__"]
