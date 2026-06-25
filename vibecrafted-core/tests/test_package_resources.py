from __future__ import annotations

from pathlib import Path

import pytest

from vibecrafted_core import package_resources as pr


def test_package_root_is_the_installed_package_directory() -> None:
    root = pr.package_root()
    assert root.is_dir()
    assert root.name == "vibecrafted_core"


def test_resource_path_without_parts_resolves_to_package_root() -> None:
    assert pr.resource_path() == pr.package_root()


def test_runtime_path_points_at_bundled_runtime_tree() -> None:
    runtime = pr.runtime_path()
    assert runtime.is_dir()
    # Spot-check a known bundled script so a half-packaged wheel fails loudly.
    assert (runtime / "scripts" / "await.sh").is_file()


def test_skills_path_points_at_bundled_skills_tree() -> None:
    skills = pr.skills_path()
    assert skills.is_dir()
    assert (skills / "vc-justdo" / "SKILL.md").is_file()


def test_deck_path_points_at_the_command_deck_file() -> None:
    deck = pr.deck_path()
    assert deck.is_file()
    assert deck.name == "vibecrafted"


def test_missing_resource_raises_with_the_requested_path() -> None:
    with pytest.raises(FileNotFoundError) as excinfo:
        pr.resource_path("definitely", "not-here.xyz")
    # The joined request path must be in the message so install-drift is
    # debuggable from the exception alone.
    assert "definitely/not-here.xyz" in str(excinfo.value)


def test_resource_path_returns_path_instances() -> None:
    for getter in (pr.package_root, pr.runtime_path, pr.skills_path, pr.deck_path):
        assert isinstance(getter(), Path)
