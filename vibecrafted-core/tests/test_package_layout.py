from __future__ import annotations

import tomllib
from pathlib import Path


def test_pyproject_publishes_vibecrafted_distribution_with_package_data() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert data["project"]["name"] == "vibecrafted"
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "vibecrafted_core"
    ]
    artifacts = set(data["tool"]["hatch"]["build"]["artifacts"])
    assert "vibecrafted_core/runtime/**" in artifacts
    assert "vibecrafted_core/skills/**" in artifacts
    assert "vibecrafted_core/deck/vibecrafted" in artifacts


def test_package_carries_runtime_skills_and_command_deck() -> None:
    package_root = Path(__file__).resolve().parents[1] / "vibecrafted_core"

    assert (package_root / "runtime" / "scripts" / "await.sh").is_file()
    assert (
        package_root / "runtime" / "workflows" / "prune" / "default_prompt.md"
    ).is_file()
    assert (package_root / "skills" / "vc-justdo" / "SKILL.md").is_file()
    assert (package_root / "deck" / "vibecrafted").is_file()
