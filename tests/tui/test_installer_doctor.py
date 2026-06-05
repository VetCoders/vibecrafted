from __future__ import annotations

from argparse import Namespace
import shutil
from pathlib import Path

from scripts import vetcoders_install as installer

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _pin_canonical_runtime_roots(monkeypatch, home: Path, crafted_home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv(
        "VIBECRAFTED_RUNTIME_HOME",
        str(home / ".local" / "share" / "vibecrafted"),
    )
    monkeypatch.setenv("VIBECRAFTED_LAUNCHER_BIN", str(home / ".local" / "bin"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))


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

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
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

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
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
    runtime_home = home / ".local" / "share" / "vibecrafted"
    store_path = crafted_home / "skills"
    zellij = runtime_home / "bin" / "zellij"

    store_path.mkdir(parents=True)
    zellij.parent.mkdir(parents=True)
    _write_executable(
        zellij,
        '#!/usr/bin/env bash\nif [[ "$1" == "--version" ]]; then echo \'zellij 0.test\'; else exit 0; fi\n',
    )

    state = installer.InstallState(framework_version="1.5.0")
    state.save(store_path)

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
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

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
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

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
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
    runtime_home = home / ".local" / "share" / "vibecrafted"
    config_home = home / ".config"
    store_path = crafted_home / "skills"
    launcher_bin = home / ".local" / "bin"
    source_root = runtime_home / "tools" / "vibecrafted-main"
    current_link = runtime_home / "tools" / "vibecrafted-current"

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
        "#!/usr/bin/env bash\n# vibecrafted stale launcher\nprintf 'stale launcher\\n'\n",
    )
    (launcher_bin / "vc-help").symlink_to("vibecrafted")

    state = installer.InstallState(framework_version="1.4.1-test")
    state.save(store_path)

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])

    exit_code = installer.cmd_doctor(Namespace(fix_rc=False, fix_launchers=True))

    assert exit_code == 0
    assert (launcher_bin / "vc-intents").is_symlink()
    assert (launcher_bin / "vc-ownership").is_symlink()
    assert not (crafted_home / "bin" / "vc-intents").exists()
    assert not (crafted_home / "bin" / "vc-ownership").exists()

    refreshed_state = installer.InstallState.load(store_path)
    assert any(
        entry.endswith("/vc-intents") for entry in refreshed_state.launcher_entries
    )
    findings = installer.run_doctor(store_path, refreshed_state)
    indexed = {finding.component: finding for finding in findings}
    assert indexed["launcher-wrappers"].level == "ok"


def test_product_tool_discovery_records_path_without_rehoming(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    cargo_bin = home / ".cargo" / "bin"
    launcher_bin = home / ".local" / "bin"
    store_path.mkdir(parents=True)
    cargo_bin.mkdir(parents=True)
    launcher_bin.mkdir(parents=True)

    _write_executable(cargo_bin / "loct", "#!/usr/bin/env bash\nprintf 'loct-dev\\n'\n")
    _write_executable(
        cargo_bin / "zellij", "#!/usr/bin/env bash\nprintf 'zellij-dev\\n'\n"
    )

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("PATH", str(cargo_bin))
    monkeypatch.setattr(
        installer,
        "FOUNDATIONS",
        [
            installer.Foundation(
                name="loct",
                description="Loctree operator CLI short command",
                channels=["canonical"],
                packages={"canonical": "curl -fsSL https://loct.io/install.sh | sh"},
                verify_cmd="loct --version",
            ),
            installer.Foundation(
                name="zellij",
                description="Visible terminal workspace surface",
                channels=["brew", "cargo", "github"],
                packages={"cargo": "zellij"},
                verify_cmd="zellij --version",
            ),
        ],
    )

    product_tools = installer.snapshot_product_tool_state()

    assert product_tools["loct"]["path"] == str(cargo_bin / "loct")
    assert product_tools["loct"]["managed_by"] == "external-path"
    assert product_tools["zellij"]["path"] == str(cargo_bin / "zellij")
    assert not (launcher_bin / "loct").exists()
    assert not (launcher_bin / "zellij").exists()

    state = installer.InstallState(product_tools=product_tools)
    state.save(store_path)
    loaded = installer.InstallState.load(store_path)

    assert loaded.product_tools["loct"]["path"] == str(cargo_bin / "loct")
    assert loaded.product_tools["zellij"]["path"] == str(cargo_bin / "zellij")


def test_layout_migrate_promotes_legacy_agents_scripts_to_current_tools(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    store_path = crafted_home / "skills"
    legacy_agents = store_path / "vc-agents"
    legacy_scripts = legacy_agents / "scripts"
    legacy_scripts.mkdir(parents=True)
    (legacy_agents / "SKILL.md").write_text("legacy skill\n", encoding="utf-8")
    _write_executable(
        legacy_scripts / "codex_spawn.sh",
        "#!/usr/bin/env bash\nprintf 'legacy codex\\n'\n",
    )

    state = installer.InstallState(framework_version="1.5.0-legacy")
    state.save(store_path)
    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)

    exit_code = installer.cmd_layout(
        Namespace(action="migrate", dry_run=False, mirror=False, force=False)
    )

    current_agents = runtime_home / "tools" / "vibecrafted-current" / "agents"
    assert exit_code == 0
    assert (
        (current_agents / "scripts" / "codex_spawn.sh")
        .read_text(encoding="utf-8")
        .startswith("#!/usr/bin/env bash")
    )
    assert (current_agents / "SKILL.md").read_text(encoding="utf-8") == "legacy skill\n"

    loaded = installer.InstallState.load(store_path)
    assert loaded.layout_transfers[-1]["direction"] == "legacy-to-new"
    assert loaded.layout_transfers[-1]["status"] == "completed"
    assert loaded.layout_transfers[-1]["source"] == str(legacy_agents)
    assert loaded.layout_transfers[-1]["target"] == str(current_agents)


def test_layout_rollback_restores_new_agents_scripts_to_legacy_store(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    store_path = crafted_home / "skills"
    current_agents = runtime_home / "tools" / "vibecrafted-current" / "agents"
    current_scripts = current_agents / "scripts"
    current_scripts.mkdir(parents=True)
    (current_agents / "SKILL.md").write_text("new skill\n", encoding="utf-8")
    _write_executable(
        current_scripts / "claude_spawn.sh",
        "#!/usr/bin/env bash\nprintf 'new claude\\n'\n",
    )

    state = installer.InstallState(framework_version="2.0-new")
    state.save(store_path)
    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)

    exit_code = installer.cmd_layout(
        Namespace(action="rollback", dry_run=False, mirror=False, force=False)
    )

    legacy_agents = store_path / "vc-agents"
    assert exit_code == 0
    assert (
        (legacy_agents / "scripts" / "claude_spawn.sh")
        .read_text(encoding="utf-8")
        .startswith("#!/usr/bin/env bash")
    )
    assert (legacy_agents / "SKILL.md").read_text(encoding="utf-8") == "new skill\n"

    loaded = installer.InstallState.load(store_path)
    assert loaded.layout_transfers[-1]["direction"] == "new-to-legacy"
    assert loaded.layout_transfers[-1]["status"] == "completed"
    assert loaded.layout_transfers[-1]["source"] == str(current_agents)
    assert loaded.layout_transfers[-1]["target"] == str(legacy_agents)


def test_layout_transfer_refuses_unmanaged_target_conflict(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    store_path = crafted_home / "skills"
    legacy_agents = store_path / "vc-agents"
    legacy_scripts = legacy_agents / "scripts"
    legacy_scripts.mkdir(parents=True)
    _write_executable(
        legacy_scripts / "codex_spawn.sh",
        "#!/usr/bin/env bash\nprintf 'legacy codex\\n'\n",
    )
    current_scripts = (
        runtime_home / "tools" / "vibecrafted-current" / "agents" / "scripts"
    )
    current_scripts.mkdir(parents=True)
    _write_executable(
        current_scripts / "codex_spawn.sh",
        "#!/usr/bin/env bash\nprintf 'operator custom codex\\n'\n",
    )

    state = installer.InstallState(framework_version="1.5.0-legacy")
    state.save(store_path)
    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)

    exit_code = installer.cmd_layout(
        Namespace(action="migrate", dry_run=False, mirror=False, force=False)
    )

    assert exit_code == 1
    assert "operator custom codex" in (current_scripts / "codex_spawn.sh").read_text(
        encoding="utf-8"
    )
    loaded = installer.InstallState.load(store_path)
    assert loaded.layout_transfers[-1]["direction"] == "legacy-to-new"
    assert loaded.layout_transfers[-1]["status"] == "blocked"


def test_install_launcher_does_not_overwrite_unmanaged_dev_wrapper(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    launcher_bin = home / ".local" / "bin"
    source_root = runtime_home / "tools" / "vibecrafted-main"
    (source_root / "scripts").mkdir(parents=True)
    launcher_bin.mkdir(parents=True)

    _write_executable(
        source_root / "scripts" / "vibecrafted",
        (REPO_ROOT / "scripts" / "vibecrafted").read_text(encoding="utf-8"),
    )
    unmanaged = launcher_bin / "vc-research"
    _write_executable(
        unmanaged,
        "#!/usr/bin/env bash\nprintf 'my dev wrapper must survive\\n'\n",
    )

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)

    installer._install_launcher(source_root, dry_run=False, update_rc=False)

    assert unmanaged.read_text(encoding="utf-8").endswith(
        "my dev wrapper must survive\\n'\n"
    )
    assert not unmanaged.is_symlink()
    assert (launcher_bin / "vc-help").is_symlink()


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

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
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
    runtime_tools = home / ".local" / "share" / "vibecrafted" / "tools"
    store_path = crafted_home / "skills"
    helper_dir = config_home / "vetcoders"
    source_root = runtime_tools / "vibecrafted-main"
    current_link = runtime_tools / "vibecrafted-current"
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

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
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

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
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


def test_run_doctor_fail_fast_on_runtime_root_drift(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    store_path.mkdir(parents=True)

    state = installer.InstallState(framework_version="1.6.0")
    state.save(store_path)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home / ".legacy-vibecrafted"))
    monkeypatch.setenv(
        "VIBECRAFTED_RUNTIME_HOME",
        str(home / ".legacy-runtime"),
    )
    monkeypatch.setenv("VIBECRAFTED_LAUNCHER_BIN", str(home / ".legacy-bin"))
    monkeypatch.setattr(installer, "FOUNDATIONS", [])

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["root:store"].level == "fail"
    assert indexed["root:runtime"].level == "fail"
    assert indexed["root:launcher-bin"].level == "fail"
    assert "manual cleanup" in indexed["root:store"].message


def test_run_doctor_accepts_external_foundation_provider(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    store_path.mkdir(parents=True)

    state = installer.InstallState(framework_version="1.6.0")
    state.save(store_path)

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)

    loct_foundation = installer.Foundation(
        name="loct",
        description="Loctree operator CLI short command",
        channels=["canonical"],
        packages={"canonical": "curl -fsSL https://loct.io/install.sh | sh"},
        verify_cmd="loct --version",
    )
    monkeypatch.setattr(installer, "FOUNDATIONS", [loct_foundation])
    monkeypatch.setattr(
        installer.shutil,
        "which",
        lambda name: "/usr/local/bin/loct" if name == "loct" else None,
    )

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["foundation:loct"].level == "ok"
    assert indexed["foundation-provenance:loct"].level == "ok"
    assert (
        "external developer provider accepted"
        in indexed["foundation-provenance:loct"].message
    )


def test_install_agent_commands_makes_marbles_discoverable(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    store_path.mkdir(parents=True)

    for runtime in ("codex", "claude"):
        (home / f".{runtime}" / "skills").mkdir(parents=True)

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setattr(installer, "FOUNDATIONS", [])

    installer.install_agent_commands(["codex", "claude"])

    codex_commands = home / ".codex" / "commands"
    claude_commands = home / ".claude" / "commands"
    assert (codex_commands / "marbles.md").is_file()
    assert (codex_commands / "codex-marbles-loop.md").is_file()
    assert (codex_commands / "cancel-codex-marbles.md").is_file()
    assert (claude_commands / "marbles.md").is_file()
    assert (claude_commands / "cancel-marbles.md").is_file()
    assert "vibecrafted-managed-agent-command" in (
        codex_commands / "marbles.md"
    ).read_text(encoding="utf-8")

    state = installer.InstallState(
        framework_version="3.1.0",
        runtimes=["codex", "claude"],
    )
    state.save(store_path)

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["commands:codex"].level == "ok"
    assert indexed["commands:claude"].level == "ok"


def test_pause_for_runtime_contract_failures_prompts_interactively(monkeypatch) -> None:
    class _TTY:
        def isatty(self) -> bool:
            return True

    prompts: list[str] = []
    monkeypatch.setattr(installer.sys, "stdin", _TTY())
    monkeypatch.setattr(installer.sys, "stdout", _TTY())
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": prompts.append(prompt) or "",
    )

    installer._pause_for_runtime_contract_failures(
        [installer.DoctorFinding("fail", "root:store", "drift")]
    )

    assert prompts
    assert "Press Enter" in prompts[0]


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
