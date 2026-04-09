from __future__ import annotations

import shutil
from pathlib import Path

from scripts import vetcoders_install as installer


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_run_doctor_smokes_helper_and_launcher_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    config_home = home / ".config"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    launcher_bin = home / ".local" / "bin"
    helper_dir = config_home / "vetcoders"

    store_path.mkdir(parents=True)
    launcher_bin.mkdir(parents=True)
    helper_dir.mkdir(parents=True)

    helper_file = helper_dir / "vc-skills.sh"
    helper_file.write_text(
        "\n".join(
            [
                "# shellcheck shell=bash",
                installer.HELPER_SHIM_MARKER,
                "vc-help() { :; }",
                "codex-implement() { :; }",
                "codex-marbles() { :; }",
                "skills-sync() { :; }",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _write_executable(
        launcher_bin / "vibecrafted",
        "#!/usr/bin/env bash\nprintf '𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. help ok\\n'\n",
    )
    (launcher_bin / "vc-help").symlink_to("vibecrafted")

    state = installer.InstallState(
        framework_version="1.2.1",
        shell_helpers=True,
    )
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: None if name == "zsh" else shutil.which(name),
    )

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["shell-helper-runtime"].level == "ok"
    assert indexed["launcher-runtime"].level == "ok"

    guide_path = installer.write_start_here_guide(store_path, state, findings)
    guide_text = guide_path.read_text(encoding="utf-8")
    assert "vibecrafted init claude" in guide_text
    assert "vibecrafted dou claude" in guide_text
    assert "Dashboard is optional" in guide_text


def test_print_doctor_surfaces_simple_and_release_paths(capsys, tmp_path: Path) -> None:
    findings = [installer.DoctorFinding("ok", "store", "ready")]

    exit_code = installer.print_doctor(findings, guide_path=tmp_path / "START_HERE.md")

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Simple path:" in output
    assert "vibecrafted init claude" in output
    assert "Ship-ready path:" in output
    assert "vibecrafted hydrate codex" in output
    assert "vibecrafted release codex" in output
    assert "START_HERE.md" in output


def test_describe_dumb_terminal_noise_flags_starship_and_stdout() -> None:
    detail = installer.describe_dumb_terminal_noise(
        """
       ○ ○○ ○○○ ○○○○
        """,
        "[ERROR] - (starship::print): Under a 'dumb' terminal (TERM=dumb).",
    )

    assert "starship init still runs under TERM=dumb" in detail
    assert "stdout noise:" in detail
    assert '[[ -o interactive && "${TERM:-}" != "dumb" ]]' in detail
