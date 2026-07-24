"""Tests for iTerm2 Dynamic Profile generator and runtime installer."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from vibecrafted_iterm2 import iterm2_profiles as profiles

# --------------------------------------------------------------------- helpers


def test_hex_to_iterm2_six_digit() -> None:
    out = profiles.hex_to_iterm2("#ff6b6b")
    assert out["Color Space"] == "sRGB"
    assert out["Alpha Component"] == 1.0
    assert round(out["Red Component"], 3) == 1.0
    assert round(out["Green Component"], 3) == round(0x6B / 255, 3)


def test_hex_to_iterm2_three_digit() -> None:
    out = profiles.hex_to_iterm2("fff")
    assert out["Red Component"] == 1.0
    assert out["Green Component"] == 1.0
    assert out["Blue Component"] == 1.0


def test_hex_to_iterm2_alpha_override() -> None:
    out = profiles.hex_to_iterm2("#000000", alpha=0.5)
    assert out["Alpha Component"] == 0.5


def test_hex_to_iterm2_invalid_length() -> None:
    with pytest.raises(ValueError):
        profiles.hex_to_iterm2("#ff")


def test_stable_guid_is_deterministic() -> None:
    a = profiles.stable_guid("repo", "vibecrafted")
    b = profiles.stable_guid("repo", "vibecrafted")
    assert a == b


def test_stable_guid_distinguishes_inputs() -> None:
    a = profiles.stable_guid("repo", "vibecrafted")
    b = profiles.stable_guid("repo", "sample")
    c = profiles.stable_guid("mesh", "vibecrafted")
    assert a != b
    assert a != c
    assert b != c


# --------------------------------------------------------------------- ProfileSpec


def test_profilespec_minimal_fields() -> None:
    spec = profiles.ProfileSpec(name="Test", namespace="test", parent=None)
    out = spec.to_iterm2_profile()
    assert out["Name"] == "Test"
    assert "Guid" in out
    assert out["Tags"] == []
    assert "Dynamic Profile Parent Name" not in out


def test_profilespec_with_parent_inheritance() -> None:
    spec = profiles.ProfileSpec(name="Child", namespace="repo", parent="Vibecrafted")
    out = spec.to_iterm2_profile()
    assert out["Dynamic Profile Parent Name"] == "Vibecrafted"


def test_profilespec_tab_color_sets_use_flag() -> None:
    spec = profiles.ProfileSpec(
        name="Tabby", namespace="t", parent=None, tab_color="#ff0000"
    )
    out = spec.to_iterm2_profile()
    assert out["Use Tab Color"] is True
    assert "Tab Color" in out


def test_profilespec_custom_command_format() -> None:
    spec = profiles.ProfileSpec(
        name="Shell",
        namespace="example",
        parent=None,
        custom_command="echo ready",
    )
    out = spec.to_iterm2_profile()
    assert out["Custom Command"] == "Yes"
    assert out["Command"] == "echo ready"


def test_profilespec_extras_merge() -> None:
    spec = profiles.ProfileSpec(
        name="Extras",
        namespace="e",
        parent=None,
        extras={"Custom Foo": True, "Triggers": [{"regex": "^x"}]},
    )
    out = spec.to_iterm2_profile()
    assert out["Custom Foo"] is True
    assert out["Triggers"] == [{"regex": "^x"}]


# --------------------------------------------------------------------- document


def test_build_profiles_document_shape() -> None:
    doc = profiles.build_profiles_document()
    assert "Profiles" in doc
    assert isinstance(doc["Profiles"], list)
    assert len(doc["Profiles"]) == len(profiles.PROFILE_SPECS)


def test_build_profiles_document_includes_vibecrafted_profile() -> None:
    doc = profiles.build_profiles_document()
    first = doc["Profiles"][0]
    assert first["Name"] == "Vibecrafted"
    assert "Dynamic Profile Parent Name" not in first


def test_build_profiles_document_all_have_guid_and_name() -> None:
    doc = profiles.build_profiles_document()
    guids = set()
    for p in doc["Profiles"]:
        assert "Guid" in p
        assert "Name" in p
        guids.add(p["Guid"])
    # GUIDs must be unique
    assert len(guids) == len(doc["Profiles"])


def test_build_profiles_document_installs_one_generic_profile() -> None:
    doc = profiles.build_profiles_document()
    names = {p["Name"] for p in doc["Profiles"]}
    assert names == {"Vibecrafted"}


def test_build_profiles_document_includes_managed_triggers() -> None:
    doc = profiles.build_profiles_document()
    trigger_rows = doc["Profiles"][0]["Triggers"]
    assert len(trigger_rows) == 6
    assert all(row["name"].startswith("vibecrafted:") for row in trigger_rows)


def test_no_profile_names_carry_legacy_experimental_prefix() -> None:
    """GA (v1.8.0+) drops the ``[experimental]`` prefix everywhere."""
    doc = profiles.build_profiles_document()
    for p in doc["Profiles"]:
        assert not p["Name"].startswith("[experimental]"), (
            f"profile {p['Name']!r} still carries legacy [experimental] prefix"
        )


def test_generated_profiles_do_not_ship_plugin_machine_defaults() -> None:
    doc = profiles.build_profiles_document()
    forbidden = ("dra" + "gon", "sztudio", "silver", "div0")
    payload = json.dumps(doc)
    for literal in forbidden:
        assert literal not in payload


def test_all_profile_names_use_vibecrafted_namespace() -> None:
    doc = profiles.build_profiles_document()
    for p in doc["Profiles"]:
        assert p["Name"] == "Vibecrafted"


def test_generated_profile_has_no_parent_reference() -> None:
    doc = profiles.build_profiles_document()
    for p in doc["Profiles"]:
        assert "Dynamic Profile Parent Name" not in p


def test_serialize_is_valid_json_with_trailing_newline() -> None:
    doc = profiles.build_profiles_document()
    text = profiles.serialize(doc)
    assert text.endswith("\n")
    reparsed = json.loads(text)
    assert reparsed == doc


# --------------------------------------------------------------------- install


def test_install_writes_to_target(tmp_path: Path) -> None:
    target = profiles.install_profiles(target_dir=tmp_path, filename="test.json")
    assert target == tmp_path / "test.json"
    assert target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert "Profiles" in payload


def test_install_idempotent_no_overwrite(tmp_path: Path) -> None:
    first = profiles.install_profiles(target_dir=tmp_path, filename="test.json")
    second = profiles.install_profiles(target_dir=tmp_path, filename="test.json")
    assert first == second


def test_install_refuses_overwrite_without_force(tmp_path: Path) -> None:
    target = tmp_path / "test.json"
    target.write_text(
        '{"Profiles": [{"Name": "Other", "Guid": "x"}]}\n', encoding="utf-8"
    )
    with pytest.raises(FileExistsError):
        profiles.install_profiles(target_dir=tmp_path, filename="test.json")


def test_install_force_creates_backup(tmp_path: Path) -> None:
    target = tmp_path / "test.json"
    original = '{"Profiles": [{"Name": "Other", "Guid": "x"}]}\n'
    target.write_text(original, encoding="utf-8")
    profiles.install_profiles(target_dir=tmp_path, filename="test.json", force=True)
    backup = tmp_path / "test.json.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original


def test_install_force_is_idempotent_without_backup_for_identical_payload(
    tmp_path: Path,
) -> None:
    target = profiles.install_profiles(target_dir=tmp_path, filename="test.json")
    profiles.install_profiles(target_dir=tmp_path, filename="test.json", force=True)
    assert target.exists()
    assert not (tmp_path / "test.json.bak").exists()


def test_install_force_skips_backup_when_disabled(tmp_path: Path) -> None:
    target = tmp_path / "test.json"
    target.write_text('{"Profiles": []}\n', encoding="utf-8")
    profiles.install_profiles(
        target_dir=tmp_path, filename="test.json", force=True, backup=False
    )
    assert not (tmp_path / "test.json.bak").exists()


def test_uninstall_removes_existing(tmp_path: Path) -> None:
    target = profiles.install_profiles(target_dir=tmp_path, filename="test.json")
    assert target.exists()
    removed = profiles.uninstall_profiles(target_dir=tmp_path, filename="test.json")
    assert removed
    assert not target.exists()


def test_uninstall_returns_false_when_missing(tmp_path: Path) -> None:
    removed = profiles.uninstall_profiles(target_dir=tmp_path, filename="test.json")
    assert not removed


def test_default_install_dir_in_application_support() -> None:
    target = profiles.default_install_dir()
    assert target.parts[-3:] == ("Application Support", "iTerm2", "DynamicProfiles")
    assert target.is_absolute()


# --------------------------------------------------------------------- CLI


def test_cli_show_emits_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = profiles._cli(["show"])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert "Profiles" in parsed


def test_cli_path_prints_default(capsys: pytest.CaptureFixture[str]) -> None:
    rc = profiles._cli(["path"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "DynamicProfiles" in captured.out


def test_cli_help_includes_operations(capsys: pytest.CaptureFixture[str]) -> None:
    rc = profiles._cli(["--help"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "install" in captured.out
    assert "uninstall" in captured.out
    assert "refresh" in captured.out
    assert "migrate-from-experimental" in captured.out


def test_module_cli_help_runs_without_import_warning() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-Werror",
            "-m",
            "vibecrafted_iterm2.iterm2_profiles",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Usage: python -m vibecrafted_iterm2.iterm2_profiles" in result.stdout
    assert "RuntimeWarning" not in result.stderr


def test_cli_help_drops_experimental_framing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """GA: help text must not advertise the module as ``[experimental]``."""
    rc = profiles._cli(["--help"])
    captured = capsys.readouterr()
    assert rc == 0
    # Allowed: the literal subcommand name ``migrate-from-experimental``.
    # Forbidden: framing the surface itself as experimental.
    lower = captured.out.lower()
    assert "[experimental]" not in lower
    assert "experimental layer" not in lower


def test_cli_unknown_op_returns_2() -> None:
    assert profiles._cli(["nope"]) == 2


def test_cli_path_uses_ga_filename(capsys: pytest.CaptureFixture[str]) -> None:
    rc = profiles._cli(["path"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.rstrip().endswith("vibecrafted.json")
    assert "experimental" not in captured.out


# --------------------------------------------------------------------- migration


def _write_legacy_fixture(target_dir: Path) -> Path:
    """Create a v1.7-style vibecrafted-experimental.json fixture."""
    legacy = target_dir / profiles.LEGACY_EXPERIMENTAL_FILENAME
    legacy_doc = {
        "Profiles": [
            {
                "Name": "[experimental] Vibecrafted Legacy",
                "Guid": "legacy-parent-guid",
                "Tags": ["plugin", "parent"],
            },
            {
                "Name": "[experimental] Vibecrafted / Classic",
                "Guid": "legacy-classic-guid",
                "Tags": ["plugin", "mesh", "ssh"],
                "Dynamic Profile Parent Name": "[experimental] Vibecrafted Legacy",
            },
            {
                "Name": "[experimental] Vibecrafted / Project",
                "Guid": "legacy-vibecrafted-guid",
                "Tags": ["plugin", "repo", "framework"],
                "Dynamic Profile Parent Name": "[experimental] Vibecrafted Legacy",
            },
        ]
    }
    legacy.write_text(json.dumps(legacy_doc, indent=2) + "\n", encoding="utf-8")
    return legacy


def test_migrate_from_experimental_renames_file_and_preserves_guids(
    tmp_path: Path,
) -> None:
    legacy = _write_legacy_fixture(tmp_path)
    result = profiles.migrate_from_experimental(target_dir=tmp_path)

    new_path = tmp_path / profiles.DEFAULT_FILENAME

    assert result.status == "migrated"
    assert result.migrated_profiles == 3
    assert new_path.exists()
    assert not legacy.exists()

    new_doc = json.loads(new_path.read_text(encoding="utf-8"))
    guids = [p["Guid"] for p in new_doc["Profiles"]]
    assert guids == [
        "legacy-parent-guid",
        "legacy-classic-guid",
        "legacy-vibecrafted-guid",
    ]


def test_migrate_from_experimental_cleans_profile_names(tmp_path: Path) -> None:
    _write_legacy_fixture(tmp_path)
    profiles.migrate_from_experimental(target_dir=tmp_path)

    new_doc = json.loads(
        (tmp_path / profiles.DEFAULT_FILENAME).read_text(encoding="utf-8")
    )
    names = [p["Name"] for p in new_doc["Profiles"]]
    assert names == [
        "Vibecrafted Legacy",
        "Vibecrafted / Classic",
        "Vibecrafted / Project",
    ]
    for p in new_doc["Profiles"]:
        assert not p["Name"].startswith("[experimental]")


def test_migrate_from_experimental_rewrites_parent_references(
    tmp_path: Path,
) -> None:
    _write_legacy_fixture(tmp_path)
    profiles.migrate_from_experimental(target_dir=tmp_path)

    new_doc = json.loads(
        (tmp_path / profiles.DEFAULT_FILENAME).read_text(encoding="utf-8")
    )
    for p in new_doc["Profiles"]:
        if "Dynamic Profile Parent Name" in p:
            assert p["Dynamic Profile Parent Name"] == "Vibecrafted Legacy"


def test_migrate_from_experimental_creates_bak_backup(tmp_path: Path) -> None:
    legacy = _write_legacy_fixture(tmp_path)
    original = legacy.read_text(encoding="utf-8")
    result = profiles.migrate_from_experimental(target_dir=tmp_path)

    assert result.backup_file is not None
    backup = tmp_path / (profiles.LEGACY_EXPERIMENTAL_FILENAME + ".bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original


def test_migrate_from_experimental_backup_disabled(tmp_path: Path) -> None:
    _write_legacy_fixture(tmp_path)
    result = profiles.migrate_from_experimental(target_dir=tmp_path, backup=False)

    assert result.backup_file is None
    backup = tmp_path / (profiles.LEGACY_EXPERIMENTAL_FILENAME + ".bak")
    assert not backup.exists()


def test_migrate_from_experimental_idempotent_when_already_migrated(
    tmp_path: Path,
) -> None:
    """Second invocation on a migrated tree is a clean no-op."""
    _write_legacy_fixture(tmp_path)
    profiles.migrate_from_experimental(target_dir=tmp_path)
    new_path = tmp_path / profiles.DEFAULT_FILENAME
    payload_before = new_path.read_text(encoding="utf-8")

    second = profiles.migrate_from_experimental(target_dir=tmp_path)
    assert second.status == "already-migrated"
    assert second.migrated_profiles == 0
    assert new_path.read_text(encoding="utf-8") == payload_before


def test_migrate_from_experimental_nothing_to_migrate(tmp_path: Path) -> None:
    """No legacy file, no new file → ``nothing-to-migrate``."""
    result = profiles.migrate_from_experimental(target_dir=tmp_path)
    assert result.status == "nothing-to-migrate"
    assert result.migrated_profiles == 0
    assert not (tmp_path / profiles.DEFAULT_FILENAME).exists()


def test_cli_migrate_from_experimental(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI subcommand wires up the migration helper end-to-end."""
    _write_legacy_fixture(tmp_path)
    monkeypatch.setattr(profiles, "default_install_dir", lambda: tmp_path)

    rc = profiles._cli(["migrate-from-experimental"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "migrated" in captured.out
    assert (tmp_path / profiles.DEFAULT_FILENAME).exists()
    assert not (tmp_path / profiles.LEGACY_EXPERIMENTAL_FILENAME).exists()


def test_cli_migrate_from_experimental_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Re-running the CLI command on an already-migrated tree is safe."""
    _write_legacy_fixture(tmp_path)
    monkeypatch.setattr(profiles, "default_install_dir", lambda: tmp_path)
    profiles._cli(["migrate-from-experimental"])
    capsys.readouterr()  # drain first run

    rc = profiles._cli(["migrate-from-experimental"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "already migrated" in captured.out


def test_cli_migrate_from_experimental_nothing_to_do(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(profiles, "default_install_dir", lambda: tmp_path)
    rc = profiles._cli(["migrate-from-experimental"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "nothing to migrate" in captured.out


def test_clean_profile_name_idempotent() -> None:
    assert (
        profiles._clean_profile_name("Vibecrafted / Classic") == "Vibecrafted / Classic"
    )


def test_clean_profile_name_strips_legacy_prefix() -> None:
    assert (
        profiles._clean_profile_name("[experimental] Vibecrafted / Classic")
        == "Vibecrafted / Classic"
    )
