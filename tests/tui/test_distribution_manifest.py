from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import distribution_manifest as manifest


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_REQUIRED = {
    "VERSION",
    "LICENSE",
    "README.md",
    "Makefile",
    "install.sh",
    "install.ps1",
    "install.toml",
    "scripts/distribution_manifest.py",
    "scripts/vetcoders_install.py",
    "scripts/runtime_paths.py",
    "scripts/vibecrafted",
    "runtime/scripts",
    "runtime/shell/lib",
    "skills",
    "vibecrafted-core/pyproject.toml",
    "vibecrafted-core/vibecrafted_core/VERSION",
    "vibecrafted-core/vibecrafted_core/deck/vibecrafted",
    "vibecrafted-core/vibecrafted_core/runtime",
    "vibecrafted-core/vibecrafted_core/skills",
    "vibecrafted-mcp/pyproject.toml",
    "plugins/iterm2/pyproject.toml",
    "vibecrafted-app/Cargo.toml",
    "vibecrafted-server/Cargo.toml",
}


def _minimal_payload(root: Path) -> None:
    for relative in manifest.REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n", encoding="utf-8")
    for relative in manifest.REQUIRED_DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)


def test_manifest_names_complete_runtime_and_forbidden_junk() -> None:
    declared = set(manifest.REQUIRED_FILES) | set(manifest.REQUIRED_DIRECTORIES)

    assert EXPECTED_REQUIRED <= declared
    assert {
        ".DS_Store",
        ".gitignore",
        ".prettierignore",
        ".dockerignore",
        "package-lock.json",
        "CONTRIBUTING.md",
        ".loctree",
        ".backup",
        "tests",
        ".github",
    } <= manifest.FORBIDDEN_COMPONENTS


def test_stage_payload_filters_junk_and_mirrors_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "payload"
    _minimal_payload(source)
    (source / "scripts" / "keep.py").write_text("keep\n", encoding="utf-8")
    (source / "scripts" / ".DS_Store").write_text("junk\n", encoding="utf-8")
    (source / "scripts" / "tests").mkdir()
    (source / "scripts" / "tests" / "test_dev.py").write_text(
        "junk\n", encoding="utf-8"
    )
    (source / ".gitignore").write_text("junk\n", encoding="utf-8")
    destination.mkdir()
    (destination / "orphan.txt").write_text("stale\n", encoding="utf-8")

    manifest.stage_payload(source, destination, mirror=True)

    manifest.validate_payload(destination)
    assert (destination / "scripts" / "keep.py").is_file()
    assert not (destination / "scripts" / ".DS_Store").exists()
    assert not (destination / "scripts" / "tests").exists()
    assert not (destination / ".gitignore").exists()
    assert not (destination / "orphan.txt").exists()


def test_validate_payload_reports_missing_and_forbidden_paths(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    _minimal_payload(payload)
    (payload / "VERSION").unlink()
    (payload / "scripts" / "nested").mkdir()
    (payload / "scripts" / "nested" / ".DS_Store").write_text(
        "junk\n", encoding="utf-8"
    )

    with pytest.raises(manifest.ManifestError) as exc_info:
        manifest.validate_payload(payload)

    message = str(exc_info.value)
    assert "missing required path: VERSION" in message
    assert "forbidden path: scripts/nested/.DS_Store" in message


def test_stage_payload_rejects_symlink_that_escapes_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _minimal_payload(source)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (source / "scripts" / "escape").symlink_to(outside)

    with pytest.raises(manifest.ManifestError, match="symlink escapes payload"):
        manifest.stage_payload(source, tmp_path / "payload", mirror=True)


def test_manifest_cli_check_is_loud_and_nonzero_for_junk(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    _minimal_payload(payload)
    (payload / "package-lock.json").write_text("{}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "distribution_manifest.py"),
            "check",
            "--root",
            str(payload),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "forbidden path: package-lock.json" in result.stderr
