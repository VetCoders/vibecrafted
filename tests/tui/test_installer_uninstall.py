from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from scripts import vetcoders_install as installer


def _write_executable(path: Path, body: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def _setup_installed_surface(
    tmp_path: Path, monkeypatch
) -> tuple[Path, Path, Path, Path, Path]:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    codex_skills = home / ".codex" / "skills"

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "_IS_TTY", False)

    store_path.mkdir(parents=True)
    codex_skills.mkdir(parents=True)

    skill_dir = store_path / "vc-init"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# test\n", encoding="utf-8")

    state = installer.InstallState(
        framework_version="9.9.9",
        skills=["vc-init"],
        runtimes=["codex"],
        shell_helpers=True,
    )
    state.save(store_path)

    (codex_skills / "vc-init").symlink_to(skill_dir)

    helper_file = installer._helper_target_path()
    helper_file.parent.mkdir(parents=True, exist_ok=True)
    helper_file.write_text("# helper shim\n", encoding="utf-8")

    zshrc = home / ".zshrc"
    path_line = installer._launcher_path_line()
    zshrc.write_text(
        f"# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher\n{path_line}\n",
        encoding="utf-8",
    )

    for launcher_bin_dir in installer._launcher_bin_dirs():
        launcher_bin_dir.mkdir(parents=True, exist_ok=True)
        _write_executable(
            launcher_bin_dir / "vibecrafted",
            "#!/usr/bin/env bash\nprintf 'launcher\\n'\n",
        )
        _write_executable(
            launcher_bin_dir / "vibecraft",
            "#!/usr/bin/env bash\nprintf 'legacy\\n'\n",
        )
        for wrapper_name in (
            "vc-help",
            "vc-workflow",
            "telemetry",
            "marble-pack",
            "aicx-pack",
        ):
            (launcher_bin_dir / wrapper_name).symlink_to("vibecrafted")
        _write_executable(
            launcher_bin_dir / "unrelated-tool",
            "#!/usr/bin/env bash\nprintf 'keep\\n'\n",
        )

    return home, crafted_home, store_path, helper_file, zshrc


def test_cmd_uninstall_removes_launchers_and_legacy_pack_wrappers(
    tmp_path: Path, monkeypatch
) -> None:
    home, crafted_home, store_path, helper_file, zshrc = _setup_installed_surface(
        tmp_path, monkeypatch
    )

    exit_code = installer.cmd_uninstall(Namespace(dry_run=False))

    assert exit_code == 0
    assert not helper_file.exists()
    assert installer._launcher_path_line() not in zshrc.read_text(encoding="utf-8")
    assert not (store_path / "vc-init").exists()
    assert not (home / ".codex" / "skills" / "vc-init").exists()

    backup_root = store_path / installer.BACKUP_DIR
    latest = (backup_root / "latest").read_text(encoding="utf-8").strip()
    assert (backup_root / latest / "launchers" / "local-bin" / "marble-pack").exists()
    assert (backup_root / latest / "launchers" / "portable-bin" / "aicx-pack").exists()

    for launcher_bin_dir in installer._launcher_bin_dirs():
        for removed_name in (
            "vibecrafted",
            "vibecraft",
            "vc-help",
            "vc-workflow",
            "telemetry",
            "marble-pack",
            "aicx-pack",
        ):
            assert not (launcher_bin_dir / removed_name).exists()
            assert not (launcher_bin_dir / removed_name).is_symlink()
        assert (launcher_bin_dir / "unrelated-tool").exists()

    assert not collect_names(installer.collect_installed_launchers())


def test_cmd_uninstall_prefers_manifest_tracked_launchers_and_helpers(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    local_bin = home / ".local" / "bin"
    runtime_skills = home / ".codex" / "skills"

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "_IS_TTY", False)

    store_path.mkdir(parents=True)
    runtime_skills.mkdir(parents=True)
    local_bin.mkdir(parents=True)

    skill_dir = store_path / "vc-init"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# test\n", encoding="utf-8")
    (runtime_skills / "vc-init").symlink_to(skill_dir)

    helper_file = installer._helper_target_path()
    helper_file.parent.mkdir(parents=True, exist_ok=True)
    helper_file.write_text("# helper shim\n", encoding="utf-8")
    manual_helper = installer._helper_legacy_path()
    manual_helper.parent.mkdir(parents=True, exist_ok=True)
    manual_helper.write_text("# user helper\n", encoding="utf-8")

    for launcher in ("vibecrafted", "vc-help", "vc-workflow", "telemetry"):
        if launcher == "vibecrafted":
            _write_executable(
                local_bin / launcher,
                "#!/usr/bin/env bash\nprintf 'launcher\\n'\n",
            )
        else:
            (local_bin / launcher).symlink_to("vibecrafted")

    (local_bin / "unrelated-tool").write_text("echo keep\n", encoding="utf-8")

    zshrc = home / ".zshrc"
    zshrc.write_text(
        f"# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher\n{installer._launcher_path_line()}\n",
        encoding="utf-8",
    )

    manifest_state = installer.InstallState(
        framework_version="9.9.9",
        skills=["vc-init"],
        runtimes=["codex"],
        launcher_entries=[f"{installer._launcher_dir_key(local_bin)}/vibecrafted"],
        helper_files=[str(helper_file)],
        shell_helpers=True,
    )
    manifest_state.save(store_path)

    exit_code = installer.cmd_uninstall(Namespace(dry_run=False))

    assert exit_code == 0
    assert not helper_file.exists()
    assert manual_helper.exists()
    assert not (local_bin / "vibecrafted").exists()
    assert (local_bin / "vc-help").is_symlink()
    assert (local_bin / "vc-workflow").is_symlink()
    assert installer._launcher_path_line() not in zshrc.read_text(encoding="utf-8")
    assert not (runtime_skills / "vc-init").exists()
    assert (local_bin / "unrelated-tool").exists()

    backup_root = store_path / installer.BACKUP_DIR
    latest = (backup_root / "latest").read_text(encoding="utf-8").strip()
    assert (backup_root / latest / "helpers" / "vc-skills.sh").exists()
    assert not (backup_root / latest / "launchers" / "local-bin" / "vc-help").exists()


def test_restore_roundtrip_recovers_launchers_and_runtime_symlinks(
    tmp_path: Path, monkeypatch
) -> None:
    home, crafted_home, store_path, helper_file, zshrc = _setup_installed_surface(
        tmp_path, monkeypatch
    )

    assert installer.cmd_uninstall(Namespace(dry_run=False)) == 0
    assert installer.cmd_restore(Namespace(dry_run=False)) == 0

    assert helper_file.exists()
    assert installer._launcher_path_line() in zshrc.read_text(encoding="utf-8")

    runtime_link = home / ".codex" / "skills" / "vc-init"
    assert runtime_link.is_symlink()
    assert runtime_link.readlink() == store_path / "vc-init"

    for launcher_bin_dir in installer._launcher_bin_dirs():
        assert (launcher_bin_dir / "vibecrafted").exists()
        assert (launcher_bin_dir / "vibecraft").exists()
        for restored_name in (
            "vc-help",
            "vc-workflow",
            "telemetry",
            "marble-pack",
            "aicx-pack",
        ):
            restored = launcher_bin_dir / restored_name
            assert restored.is_symlink()
            assert restored.readlink() == Path("vibecrafted")
        assert (launcher_bin_dir / "unrelated-tool").exists()

    restored_launchers = collect_names(installer.collect_installed_launchers())
    assert "marble-pack" in restored_launchers
    assert "aicx-pack" in restored_launchers
    assert "vibecrafted" in restored_launchers


def test_cmd_uninstall_cleans_launcher_only_surface_without_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "_IS_TTY", False)
    monkeypatch.setattr(installer, "_known_bundle_names", lambda: [])

    for launcher_bin_dir in installer._launcher_bin_dirs():
        launcher_bin_dir.mkdir(parents=True, exist_ok=True)
        _write_executable(
            launcher_bin_dir / "vibecrafted",
            "#!/usr/bin/env bash\nprintf 'launcher\\n'\n",
        )
        (launcher_bin_dir / "vc-help").symlink_to("vibecrafted")
        (launcher_bin_dir / "vc-workflow").symlink_to("vibecrafted")

    zshrc = home / ".zshrc"
    zshrc.write_text(
        f"# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher\n{installer._launcher_path_line()}\n",
        encoding="utf-8",
    )

    exit_code = installer.cmd_uninstall(Namespace(dry_run=False))

    assert exit_code == 0
    for launcher_bin_dir in installer._launcher_bin_dirs():
        assert not (launcher_bin_dir / "vibecrafted").exists()
        assert not (launcher_bin_dir / "vc-help").exists()
        assert not (launcher_bin_dir / "vc-workflow").exists()
    assert installer._launcher_path_line() not in zshrc.read_text(encoding="utf-8")

    backup_root = store_path / installer.BACKUP_DIR
    latest = (backup_root / "latest").read_text(encoding="utf-8").strip()
    assert (backup_root / latest / "launchers" / "local-bin" / "vibecrafted").exists()


def collect_names(entries: list[tuple[Path, Path]]) -> set[str]:
    return {entry.name for _, entry in entries}
