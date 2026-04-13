import pytest
import sys
from pathlib import Path

from scripts import installer_tui
from scripts import vetcoders_install
from scripts.runtime_paths import read_version_file


def test_read_framework_version_reads_version_file(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("9.9.9\n", encoding="utf-8")

    assert installer_tui.read_framework_version(str(tmp_path)) == "9.9.9"


def test_read_framework_version_returns_unknown_when_missing(tmp_path: Path) -> None:
    assert installer_tui.read_framework_version(str(tmp_path)) == "unknown"


def test_runtime_paths_reads_framework_version(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("3.2.1\n", encoding="utf-8")

    assert read_version_file(tmp_path) == "3.2.1"


def test_build_install_command_includes_compact_noninteractive_flags(
    tmp_path: Path,
) -> None:
    installer_path = tmp_path / "scripts" / "vetcoders_install.py"
    installer_path.parent.mkdir()
    installer_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    command = installer_tui.build_install_command(str(tmp_path))

    assert command[0] == sys.executable
    assert command[1] == str(installer_path)
    assert command[2:] == [
        "install",
        "--source",
        str(tmp_path.resolve()),
        "--with-shell",
        "--compact",
        "--non-interactive",
    ]


def test_build_install_command_raises_when_installer_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        installer_tui.build_install_command(str(tmp_path))


def test_installer_tui_vibecrafted_home_expands_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    portable_vc = tmp_path / "portable-vc"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(portable_vc))

    assert installer_tui.vibecrafted_home() == portable_vc
    assert installer_tui.framework_store_dir() == portable_vc / "skills"
    assert installer_tui.install_log_path() == portable_vc / "install.log"


def test_vetcoders_install_env_paths_expand_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    portable_vc = tmp_path / "portable-vc"
    portable_config = tmp_path / "portable-config"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(portable_vc))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(portable_config))

    assert vetcoders_install.vibecrafted_home() == portable_vc
    assert (
        vetcoders_install._helper_target_path()
        == portable_config / "vetcoders" / "vc-skills.sh"
    )
    assert (
        vetcoders_install._helper_legacy_path()
        == portable_config / "zsh" / "vc-skills.zsh"
    )


def test_helper_surface_label_prefers_canonical_helper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    assert vetcoders_install._helper_surface_label() == "not installed"

    legacy = home / ".config" / "zsh" / "vc-skills.zsh"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# legacy\n", encoding="utf-8")
    assert vetcoders_install._helper_surface_label() == "legacy zsh"

    canonical = home / ".config" / "vetcoders" / "vc-skills.sh"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")
    assert vetcoders_install._helper_surface_label(zsh_available=True) == "bash + zsh"


def test_helper_surface_label_reports_bash_only_when_zsh_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    canonical = home / ".config" / "vetcoders" / "vc-skills.sh"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")

    assert vetcoders_install._helper_surface_label(zsh_available=False) == "bash only"


def test_detect_system_deps_includes_optional_shells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = {
        "python3": "/usr/bin/python3",
        "git": "/usr/bin/git",
        "rsync": "/usr/bin/rsync",
        "zsh": "/bin/zsh",
    }

    monkeypatch.setattr(
        vetcoders_install.shutil,
        "which",
        lambda cmd: paths.get(cmd),
    )

    assert vetcoders_install.detect_system_deps() == paths


def test_strip_rc_entry_removes_duplicate_launcher_blocks() -> None:
    path_line = vetcoders_install._launcher_path_line()
    content = (
        f"# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher\n{path_line}\n"
        f"{path_line}\n"
        'export PATH="$HOME/.cargo/bin:$PATH"\n'
    )

    cleaned, removed = vetcoders_install._strip_rc_entry(
        content, path_line, "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher"
    )

    assert removed == 3
    assert path_line not in cleaned
    assert "cargo/bin" in cleaned


def test_install_launcher_dedupes_zshrc_path_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    repo_root = tmp_path / "repo"
    launcher_src = repo_root / "scripts" / "vibecrafted"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"

    launcher_src.parent.mkdir(parents=True)
    launcher_src.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    home.mkdir()

    path_line = vetcoders_install._launcher_path_line()
    zshrc.write_text(
        f"# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher\n{path_line}\n{path_line}\n",
        encoding="utf-8",
    )
    bashrc.write_text("", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))

    vetcoders_install._install_launcher(repo_root, dry_run=False)

    zshrc_content = zshrc.read_text(encoding="utf-8")
    assert zshrc_content.count(path_line) == 1
    assert zshrc_content.count("# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher") == 1
    assert (home / ".local" / "bin" / "vibecrafted").exists()
    for launcher_bin in (home / ".local" / "bin", home / ".vibecrafted" / "bin"):
        for wrapper_name in (
            "vc-help",
            "vc-start",
            "vc-dashboard",
            "vc-resume",
            "telemetry",
        ):
            wrapper_path = launcher_bin / wrapper_name
            assert wrapper_path.is_symlink()
            assert wrapper_path.readlink() == Path("vibecrafted")


def test_pipeline_category_describes_release_not_removed_ship_skill() -> None:
    description = vetcoders_install.SKILL_CATEGORIES["pipeline"]["description"]

    assert "release" in description
    assert "ship" not in description
