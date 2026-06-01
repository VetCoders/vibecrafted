from __future__ import annotations

from argparse import Namespace
import shutil
from pathlib import Path

from scripts import vetcoders_install as installer

REPO_ROOT = Path(__file__).resolve().parents[2]


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
                "vc-agents() { :; }",
                "vc-init() { :; }",
                "vc-intents() { :; }",
                "vc-ownership() { :; }",
                "vc-loop() { :; }",
                "vc-marbles() { :; }",
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
    _real_which = shutil.which
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: None if name == "zsh" else _real_which(name),
    )

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["shell-helper-runtime"].level == "ok"
    assert indexed["launcher-runtime"].level == "ok"

    guide_path = installer.write_start_here_guide(store_path, state, findings)
    guide_text = guide_path.read_text(encoding="utf-8")
    assert "vibecrafted init claude" in guide_text
    assert "vibecrafted dou claude" in guide_text
    assert "vibecrafted decorate codex" in guide_text
    assert "Dashboard is optional" in guide_text


def test_print_doctor_surfaces_simple_and_release_paths(capsys, tmp_path: Path) -> None:
    findings = [installer.DoctorFinding("ok", "store", "ready")]

    exit_code = installer.print_doctor(findings, guide_path=tmp_path / "START_HERE.md")

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Simple path:" in output
    assert "vibecrafted init claude" in output
    assert "Ship-ready path:" in output
    assert "vibecrafted decorate codex" in output
    assert "vibecrafted hydrate codex" in output
    assert "vibecrafted release codex" in output
    assert "START_HERE.md" in output


def test_print_doctor_failure_hint_uses_vibecrafted_not_old_brand(
    capsys, tmp_path: Path
) -> None:
    findings = [installer.DoctorFinding("fail", "store", "missing")]

    exit_code = installer.print_doctor(findings, guide_path=tmp_path / "START_HERE.md")

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "vibecrafted doctor --fix-rc --fix-launchers" in output
    assert "vetcoders install" not in output


def test_run_doctor_includes_dashboard_smoke(tmp_path: Path, monkeypatch) -> None:
    """Doctor checks that 'vibecrafted dashboard ls' subcommand is functional."""
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
                "vc-agents() { :; }",
                "vc-init() { :; }",
                "vc-intents() { :; }",
                "vc-ownership() { :; }",
                "vc-loop() { :; }",
                "vc-marbles() { :; }",
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
    _write_executable(
        launcher_bin / "vc-dashboard",
        "#!/usr/bin/env bash\nprintf 'dashboard-ok\\n'\n",
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
    _real_which = shutil.which
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: None if name == "zsh" else _real_which(name),
    )

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert "dashboard-smoke" in indexed
    assert indexed["dashboard-smoke"].level == "ok"


def test_run_doctor_uses_bundled_zellij_when_not_on_path(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    zellij = crafted_home / "bin" / "zellij"

    store_path.mkdir(parents=True)
    zellij.parent.mkdir(parents=True)
    _write_executable(
        zellij,
        '#!/usr/bin/env bash\nif [[ "$1" == "--version" ]]; then echo \'zellij 0.test\'; else exit 0; fi\n',
    )

    state = installer.InstallState(framework_version="1.5.0")
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["zellij"].level == "ok"
    assert str(zellij) in indexed["zellij"].message


def test_run_doctor_accepts_gemini_help_when_version_flag_exits_nonzero(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    fake_bin = tmp_path / "bin"
    gemini = fake_bin / "gemini"

    store_path.mkdir(parents=True)
    fake_bin.mkdir()
    _write_executable(
        gemini,
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'case "${1:-}" in',
                "  --help) echo 'gemini help'; exit 0 ;;",
                "  *) exit 1 ;;",
                "esac",
            ]
        )
        + "\n",
    )

    state = installer.InstallState(framework_version="1.5.0")
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: str(gemini) if name == "gemini" else None,
    )

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["agent-stream:gemini"].level == "ok"
    assert "version flag unavailable" in indexed["agent-stream:gemini"].message


def test_run_doctor_finds_launchers_outside_local_bin(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    config_home = home / ".config"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    launcher_bin = crafted_home / "bin"
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
                "vc-agents() { :; }",
                "vc-init() { :; }",
                "vc-intents() { :; }",
                "vc-ownership() { :; }",
                "vc-loop() { :; }",
                "vc-marbles() { :; }",
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
    _write_executable(
        launcher_bin / "vc-dashboard",
        "#!/usr/bin/env bash\nprintf 'dashboard-ok\\n'\n",
    )
    for wrapper_name in installer.LAUNCHER_WRAPPERS:
        wrapper_path = launcher_bin / wrapper_name
        if not wrapper_path.exists():
            wrapper_path.symlink_to("vibecrafted")

    state = installer.InstallState(
        framework_version="1.2.1",
        shell_helpers=True,
    )
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    _real_which = shutil.which
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: None if name == "zsh" else _real_which(name),
    )

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["launcher-wrappers"].level == "ok"
    assert indexed["launcher-runtime"].level == "ok"
    assert indexed["dashboard-smoke"].level == "ok"


def test_cmd_doctor_fix_launchers_repairs_missing_wrappers(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    config_home = home / ".config"
    store_path = crafted_home / "skills"
    launcher_bin = home / ".local" / "bin"
    source_root = crafted_home / "tools" / "vibecrafted-main"
    current_link = crafted_home / "tools" / "vibecrafted-current"

    store_path.mkdir(parents=True)
    launcher_bin.mkdir(parents=True)
    (source_root / "scripts").mkdir(parents=True)
    (source_root / "skills").mkdir(parents=True)
    current_link.parent.mkdir(parents=True, exist_ok=True)
    current_link.symlink_to(source_root)

    _write_executable(
        source_root / "scripts" / "vibecrafted",
        (REPO_ROOT / "scripts" / "vibecrafted").read_text(encoding="utf-8"),
    )
    (source_root / "VERSION").write_text("1.4.1-test\n", encoding="utf-8")

    _write_executable(
        launcher_bin / "vibecrafted",
        "#!/usr/bin/env bash\nprintf 'stale launcher\\n'\n",
    )
    (launcher_bin / "vc-help").symlink_to("vibecrafted")

    state = installer.InstallState(framework_version="1.4.1-test")
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])

    exit_code = installer.cmd_doctor(Namespace(fix_rc=False, fix_launchers=True))

    assert exit_code == 0
    assert (launcher_bin / "vc-intents").is_symlink()
    assert (launcher_bin / "vc-ownership").is_symlink()
    assert (crafted_home / "bin" / "vc-intents").is_symlink()
    assert (crafted_home / "bin" / "vc-ownership").is_symlink()

    refreshed_state = installer.InstallState.load(store_path)
    assert any(
        entry.endswith("/vc-intents") for entry in refreshed_state.launcher_entries
    )
    findings = installer.run_doctor(store_path, refreshed_state)
    indexed = {finding.component: finding for finding in findings}
    assert indexed["launcher-wrappers"].level == "ok"


def test_run_doctor_ignores_ds_store_in_stale_file_check(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    skill_name = "vc-intents"
    installed_skill = store_path / skill_name
    source_skill = REPO_ROOT / "skills" / skill_name

    installed_skill.mkdir(parents=True)
    (installed_skill / "SKILL.md").write_text(
        (source_skill / "SKILL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (installed_skill / ".DS_Store").write_text("junk\n", encoding="utf-8")

    state = installer.InstallState(
        framework_version="1.4.1-test",
        skills=[skill_name],
    )
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["stale-files"].level == "ok"


def test_run_doctor_spawn_e2e_supplies_full_meta_arguments(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    config_home = home / ".config"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    helper_dir = config_home / "vetcoders"
    source_root = crafted_home / "tools" / "vibecrafted-main"
    current_link = crafted_home / "tools" / "vibecrafted-current"
    scripts_dir = source_root / "skills" / "vc-agents" / "scripts"

    store_path.mkdir(parents=True)
    helper_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    current_link.parent.mkdir(parents=True, exist_ok=True)
    current_link.symlink_to(source_root)

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

    (scripts_dir / "common.sh").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'spawn_write_meta() { local meta_path="$1"; local status="$2"; printf "%s\\n" "$status" > "$meta_path"; }',
                "spawn_prepare_paths() { :; }",
                "spawn_watch_startup() { :; }",
                'spawn_generate_launcher() { local launcher="$1"; local _meta="$2"; local _report="$3"; local _transcript="$4"; local common="$5"; local command="$6"; cat > "$launcher" <<EOF\n#!/usr/bin/env bash\nset -euo pipefail\nsource "$common"\n$command\nEOF\n}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state = installer.InstallState(
        framework_version="1.2.1",
        shell_helpers=False,
    )
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    _real_which = shutil.which
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: None if name == "zsh" else _real_which(name),
    )

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["spawn-pipeline"].level == "ok"
    assert indexed["spawn-e2e"].level == "ok"


def test_cmd_doctor_fix_rc_repairs_compat_shell_lines(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    config_home = home / ".config"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    launcher_bin = home / ".local" / "bin"
    helper_dir = config_home / "vetcoders"
    compat_helper_dir = config_home / "zsh"
    zshrc = home / ".zshrc"

    store_path.mkdir(parents=True)
    launcher_bin.mkdir(parents=True)
    helper_dir.mkdir(parents=True)
    compat_helper_dir.mkdir(parents=True)

    helper_file = helper_dir / "vc-skills.sh"
    helper_file.write_text(
        "\n".join(
            [
                "# shellcheck shell=bash",
                installer.HELPER_SHIM_MARKER,
                "vc-help() { :; }",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (compat_helper_dir / "vc-skills.zsh").write_text(
        "# compat helper\n", encoding="utf-8"
    )
    _write_executable(
        launcher_bin / "vibecrafted",
        "#!/usr/bin/env bash\nprintf '𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. help ok\\n'\n",
    )
    zshrc.write_text(
        "\n".join(
            [
                "# existing user config",
                installer._old_zshrc_source_line(),
                installer._shell_source_line(),
                'export VIBECRAFTED_HOME="$HOME/.vibecrafted"',
                installer._launcher_path_line(),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    findings = installer._doctor_fix_rc_files()

    assert any(
        finding.component == "rc-fix:.zshrc" and finding.level == "ok"
        for finding in findings
    )
    repaired = zshrc.read_text(encoding="utf-8")
    assert installer._old_zshrc_source_line() not in repaired
    assert 'export VIBECRAFTED_HOME="$HOME/.vibecrafted"' not in repaired
    assert repaired.count(installer._shell_source_line()) == 1
    assert repaired.count(installer._launcher_path_line()) == 1
    assert "# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell helpers" in repaired
    assert "# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. launcher" in repaired


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
