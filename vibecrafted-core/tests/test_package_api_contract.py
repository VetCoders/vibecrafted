from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import pytest

import vibecrafted_core
from vibecrafted_core import workflows


def test_every_public_name_resolves() -> None:
    """`__all__` is the package contract; a broken hub import or stale lazy
    entry must surface here, not at a downstream caller's import site."""
    missing = []
    for name in vibecrafted_core.__all__:
        try:
            getattr(vibecrafted_core, name)
        except AttributeError:
            missing.append(name)
    assert not missing, f"names in __all__ that do not resolve: {missing}"


def test_lazy_workflow_exports_load_on_demand() -> None:
    # These live behind module.__getattr__ to keep CLI modules out of a bare
    # `import vibecrafted_core`; accessing one must materialize a real symbol.
    assert callable(vibecrafted_core.launch_workflow)
    assert callable(vibecrafted_core.vibecrafted_launcher)


def test_lazy_access_caches_into_module_globals() -> None:
    # Second access must return the same object the lazy loader cached.
    first = vibecrafted_core.normalize_launch_spec
    second = vibecrafted_core.normalize_launch_spec
    assert first is second


def test_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        vibecrafted_core.this_symbol_does_not_exist  # noqa: B018


def test_version_matches_distribution_metadata() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert vibecrafted_core.__version__ == data["project"]["version"]


def test_workflows_package_reexports_resolve() -> None:
    missing = [name for name in workflows.__all__ if not hasattr(workflows, name)]
    assert not missing, f"workflows.__all__ names that do not resolve: {missing}"


def test_supported_workflows_is_non_empty() -> None:
    assert workflows.SUPPORTED_WORKFLOWS, "SUPPORTED_WORKFLOWS must not be empty"


def test_package_import_is_idempotent() -> None:
    reloaded = importlib.import_module("vibecrafted_core")
    assert reloaded is vibecrafted_core
