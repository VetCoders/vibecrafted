from __future__ import annotations

import importlib
import importlib.metadata
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import vibecrafted_core
from vibecrafted_core import workflows


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = REPO_ROOT / "vibecrafted-core"


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
    expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = CORE_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    packaged = (
        (CORE_ROOT / "vibecrafted_core" / "VERSION").read_text(encoding="utf-8").strip()
    )

    assert packaged == expected
    assert data["project"]["version"] == expected
    assert importlib.metadata.version("vibecrafted") == expected
    assert vibecrafted_core.__version__ == expected


def test_version_falls_back_to_installed_metadata(monkeypatch) -> None:
    monkeypatch.setattr(vibecrafted_core, "read_version_file", lambda _root: "unknown")
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "8.7.6")

    assert vibecrafted_core._resolve_installed_version() == "8.7.6"


def test_version_bump_updates_every_declared_projection(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    pyproject = tmp_path / "vibecrafted-core" / "pyproject.toml"
    packaged = tmp_path / "vibecrafted-core" / "vibecrafted_core" / "VERSION"
    pyproject.parent.mkdir(parents=True)
    packaged.parent.mkdir(parents=True)
    version_file.write_text("1.4.1\n", encoding="utf-8")
    pyproject.write_text(
        '[project]\nname = "fixture"\nversion = "1.4.1"\n', encoding="utf-8"
    )
    packaged.write_text("1.4.1\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "version_bump.py"),
            "minor",
            "--file",
            str(version_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert version_file.read_text(encoding="utf-8") == "1.5.0\n"
    assert (
        tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        == "1.5.0"
    )
    assert packaged.read_text(encoding="utf-8") == "1.5.0\n"


def test_version_bump_rejects_drift_without_partial_writes(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    pyproject = tmp_path / "vibecrafted-core" / "pyproject.toml"
    packaged = tmp_path / "vibecrafted-core" / "vibecrafted_core" / "VERSION"
    pyproject.parent.mkdir(parents=True)
    packaged.parent.mkdir(parents=True)
    version_file.write_text("1.4.1\n", encoding="utf-8")
    pyproject.write_text(
        '[project]\nname = "fixture"\nversion = "1.4.0"\n', encoding="utf-8"
    )
    packaged.write_text("1.4.1\n", encoding="utf-8")

    before = {
        path: path.read_text(encoding="utf-8")
        for path in (version_file, pyproject, packaged)
    }
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "version_bump.py"),
            "patch",
            "--file",
            str(version_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "version drift" in result.stderr.lower()
    assert {path: path.read_text(encoding="utf-8") for path in before} == before


def test_workflows_package_reexports_resolve() -> None:
    missing = [name for name in workflows.__all__ if not hasattr(workflows, name)]
    assert not missing, f"workflows.__all__ names that do not resolve: {missing}"


def test_supported_workflows_is_non_empty() -> None:
    assert workflows.SUPPORTED_WORKFLOWS, "SUPPORTED_WORKFLOWS must not be empty"


def test_package_import_is_idempotent() -> None:
    reloaded = importlib.import_module("vibecrafted_core")
    assert reloaded is vibecrafted_core
