from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
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
    "vibecrafted-app/Cargo.lock",
    "vibecrafted-server/Cargo.toml",
    "vibecrafted-server/Cargo.lock",
}


def _minimal_payload(root: Path) -> None:
    for relative in manifest.REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n", encoding="utf-8")
    for relative in manifest.REQUIRED_DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)
    for relative in manifest.REQUIRED_SURFACE_FILES.values():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"runtime sentinel for {relative}\n", encoding="utf-8")
    # The repo's top-level runtime/ and skills/ are symlinks into the canonical
    # package path; sshfs-backed mounts (colima containers) drop those symlinks
    # entirely. Mirror every aliased requirement under its canonical path so
    # fixtures can exercise the projection with real content behind it.
    for relative in manifest.REQUIRED_DIRECTORIES:
        parts = Path(relative).parts
        if parts and parts[0] in manifest.CANONICAL_PROJECTIONS:
            canonical = manifest.CANONICAL_PROJECTIONS[parts[0]]
            (root / canonical.joinpath(*parts[1:])).mkdir(parents=True, exist_ok=True)
    for relative in manifest.REQUIRED_SURFACE_FILES.values():
        parts = Path(relative).parts
        if parts and parts[0] in manifest.CANONICAL_PROJECTIONS:
            canonical = manifest.CANONICAL_PROJECTIONS[parts[0]]
            path = root / canonical.joinpath(*parts[1:])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"canonical sentinel for {relative}\n", encoding="utf-8")


def test_manifest_names_complete_runtime_and_forbidden_junk() -> None:
    declared = set(manifest.REQUIRED_FILES) | set(manifest.REQUIRED_DIRECTORIES)

    assert EXPECTED_REQUIRED <= declared
    assert set(manifest.REQUIRED_SURFACE_FILES) == set(manifest.REQUIRED_DIRECTORIES)
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


@pytest.mark.parametrize(
    ("surface", "sentinel"), manifest.REQUIRED_SURFACE_FILES.items()
)
def test_validate_payload_rejects_empty_required_runtime_surface(
    tmp_path: Path, surface: str, sentinel: str
) -> None:
    payload = tmp_path / "payload"
    _minimal_payload(payload)
    sentinel_path = payload / sentinel
    sentinel_path.unlink()

    with pytest.raises(manifest.ManifestError) as exc_info:
        manifest.validate_payload(payload)

    assert f"missing required runtime content: {surface} -> {sentinel}" in str(
        exc_info.value
    )


def test_forbidden_artifact_filter_is_safe_for_runtime_subtrees() -> None:
    assert not manifest.path_is_forbidden("SKILL.md")
    assert not manifest.path_is_forbidden("scripts/codex_spawn.sh")
    assert not manifest.path_is_forbidden("vibecrafted-app/Cargo.lock")
    assert not manifest.path_is_forbidden("vibecrafted-server/Cargo.lock")
    assert manifest.path_is_forbidden("Cargo.lock")
    assert manifest.path_is_forbidden("scratch/Cargo.lock")
    assert manifest.path_is_forbidden("tests/test_spawn.py")
    assert manifest.path_is_forbidden("scripts/__pycache__/helper.pyc")

    assert not manifest.path_is_included("SKILL.md")
    assert manifest.path_is_included("skills/vc-init/SKILL.md")


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


def test_stage_payload_projects_canonical_runtime_when_mount_hides_symlink(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "payload"
    _minimal_payload(source)
    shutil.rmtree(source / "runtime")

    manifest.stage_payload(source, destination, mirror=True)

    runtime_projection = destination / "runtime"
    assert runtime_projection.is_symlink()
    assert runtime_projection.readlink() == manifest.CANONICAL_RUNTIME
    assert (runtime_projection / "scripts" / "README.md").is_file()
    assert (runtime_projection / "shell" / "lib" / "core.sh").is_file()
    manifest.validate_payload(destination)


def test_stage_payload_projects_canonical_skills_when_mount_hides_symlink(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "payload"
    _minimal_payload(source)
    shutil.rmtree(source / "skills")

    manifest.stage_payload(source, destination, mirror=True)

    skills_projection = destination / "skills"
    assert skills_projection.is_symlink()
    assert skills_projection.readlink() == manifest.CANONICAL_SKILLS
    assert (skills_projection / "vc-init" / "SKILL.md").is_file()
    manifest.validate_payload(destination)


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


def test_walk_entries_prunes_forbidden_directories_before_descending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    descended: list[str] = []

    def fake_walk(root: Path, *, followlinks: bool):
        assert root == payload
        assert followlinks is False
        directory_names = ["scripts", ".git", "node_modules"]
        yield str(payload), directory_names, []
        descended.extend(directory_names)

    monkeypatch.setattr(manifest.os, "walk", fake_walk)

    assert list(manifest._walk_entries(payload)) == [
        payload / ".git",
        payload / "node_modules",
        payload / "scripts",
    ]
    assert descended == ["scripts"]


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


def test_archive_has_one_safe_root_and_validated_payload(tmp_path: Path) -> None:
    source = tmp_path / "source"
    archive_path = tmp_path / "vibecrafted-9.8.7.tar.gz"
    extracted = tmp_path / "extracted"
    _minimal_payload(source)
    (source / "scripts" / "keep.py").write_text("keep\n", encoding="utf-8")
    (source / "scripts" / ".DS_Store").write_text("junk\n", encoding="utf-8")

    manifest.create_archive(
        source,
        archive_path,
        root_name="vibecrafted-9.8.7",
    )

    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        assert names
        assert all(
            name == "vibecrafted-9.8.7" or name.startswith("vibecrafted-9.8.7/")
            for name in names
        )
        assert all(
            not name.startswith("/") and ".." not in Path(name).parts for name in names
        )
        assert not any(name.endswith(".DS_Store") for name in names)
        archive.extractall(extracted, filter="data")

    payload = extracted / "vibecrafted-9.8.7"
    manifest.validate_payload(payload)
    assert (payload / "scripts" / "keep.py").is_file()


def test_archive_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    _minimal_payload(source)

    manifest.create_archive(source, first, root_name="vibecrafted-test")
    manifest.create_archive(source, second, root_name="vibecrafted-test")

    assert first.read_bytes() == second.read_bytes()
