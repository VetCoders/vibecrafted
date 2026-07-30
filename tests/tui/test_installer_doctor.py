from __future__ import annotations

import shutil
import subprocess
from argparse import Namespace
from pathlib import Path

from vibecrafted_core.doctor import _vc_frame_delivery_findings
from vibecrafted_core.frontier_assets import vc_frame_config_source
from vibecrafted_core.vc_frame_delivery import stage_vc_frame_config
from vibecrafted_core.vc_frame_staging import (
    materialize_vc_frame_config,
    resolve_clipboard_command,
    resolve_pane_shell,
)

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


def test_install_foundation_from_bundle_copies_platform_payload(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "bundle"
    bin_dir = tmp_path / "bin"
    vendor_dir = repo_root / "bin" / "vendor" / "darwin-arm64"
    vendor_dir.mkdir(parents=True)
    monkeypatch.setattr(installer, "detect_vendor_platform", lambda: "darwin-arm64")

    foundations = [
        f
        for f in installer.FOUNDATIONS
        if f.name in installer.VENDORED_FOUNDATION_BINARIES
    ]
    assert {f.name for f in foundations} == {
        "aicx",
        "aicx-mcp",
        "loct",
        "loctree-mcp",
        "vc-frame",
    }

    for foundation in foundations:
        name = installer.VENDORED_FOUNDATION_BINARIES[foundation.name]
        _write_executable(
            vendor_dir / name,
            f"#!/usr/bin/env bash\nprintf '{name} 0.0.0-test\\n'\n",
        )

    installed = [
        installer.install_foundation_from_bundle(f, repo_root, bin_dir=bin_dir)
        for f in foundations
    ]

    assert {path.name for path in installed if path is not None} == {
        "aicx",
        "aicx-mcp",
        "loct",
        "loctree-mcp",
        "vc-frame",
    }
    for path in installed:
        assert path is not None
        assert path.is_file()
        assert path.stat().st_mode & 0o111
        assert subprocess.run([str(path), "--version"], check=False).returncode == 0


def test_install_foundation_from_bundle_ignores_platform_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "bundle"
    bin_dir = tmp_path / "bin"
    linux_dir = repo_root / "bin" / "vendor" / "linux-x64"
    linux_dir.mkdir(parents=True)
    _write_executable(
        linux_dir / "vc-frame",
        "#!/usr/bin/env bash\nprintf 'wrong platform\\n'\n",
    )
    monkeypatch.setattr(installer, "detect_vendor_platform", lambda: "darwin-arm64")
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    foundation = next(f for f in installer.FOUNDATIONS if f.name == "vc-frame")

    assert (
        installer.install_foundation_from_bundle(foundation, repo_root, bin_dir=bin_dir)
        is None
    )
    assert not (bin_dir / "vc-frame").exists()
    assert installer.install_or_find_foundation(foundation, repo_root) == (
        "",
        "not-installed",
    )


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
        f"# shellcheck shell=bash\n{installer.HELPER_SHIM_MARKER}\nvc-help() {{ :; }}\nvc-agents() {{ :; }}\nvc-init() {{ :; }}\nvc-intents() {{ :; }}\nvc-ownership() {{ :; }}\nvc-loop() {{ :; }}\nvc-ship() {{ :; }}\nvc-cron() {{ :; }}\nvc-marbles() {{ :; }}\ncodex-implement() {{ :; }}\ncodex-marbles() {{ :; }}\nskills-sync() {{ :; }}"
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


def test_run_doctor_flags_dark_standard_decks(tmp_path: Path, monkeypatch) -> None:
    """3.6.0 regression: the manifest recorded only 'agents', the installer
    pruned the claude/codex views, and doctor kept reporting ok. Doctor must
    surface dark standard decks even when the manifest never recorded them."""
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    store_path = crafted_home / "skills"
    skill = store_path / "vc-init"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# vc-init\n", encoding="utf-8")

    agents_view = home / ".agents" / "skills"
    agents_view.mkdir(parents=True)
    (agents_view / "vc-init").symlink_to(skill)

    state = installer.InstallState(
        framework_version="3.6.0",
        skills=["vc-init"],
        runtimes=["agents"],
    )
    state.save(store_path)

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setattr(installer, "FOUNDATIONS", [])

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["runtime:claude"].level == "warn"
    assert indexed["runtime:codex"].level == "warn"
    assert indexed["symlink:agents/vc-init"].level == "ok"


def test_print_doctor_default_is_summary_first_and_bounded(
    capsys, tmp_path: Path
) -> None:
    """CLI_PRODUCT_SPEC §6.4: verdict in two lines, passing checks are a
    count (never lines), details live behind --verbose."""
    findings = [
        installer.DoctorFinding("ok", "store", "ready"),
        installer.DoctorFinding("ok", "launcher", "ready"),
        installer.DoctorFinding("warn", "loctree", "missing — optional foundation"),
    ]

    exit_code = installer.print_doctor(findings, guide_path=tmp_path / "START_HERE.md")

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "doctor" in output
    assert "3 checks" in output
    assert "2 ok" in output
    assert "1 warnings" in output
    assert "0 failures" in output
    # warnings are listed; passing checks are a count, not lines
    assert "loctree: missing" in output
    assert "store: ready" not in output
    assert "details: vibecrafted doctor --verbose" in output
    assert "START_HERE.md" in output


def test_print_doctor_verbose_lists_every_check_and_golden_paths(
    capsys, tmp_path: Path
) -> None:
    findings = [installer.DoctorFinding("ok", "store", "ready")]

    exit_code = installer.print_doctor(
        findings, guide_path=tmp_path / "START_HERE.md", verbose=True
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "store: ready" in output
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
    assert "store: missing" in output
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
        f"# shellcheck shell=bash\n{installer.HELPER_SHIM_MARKER}\nvc-help() {{ :; }}\nvc-agents() {{ :; }}\nvc-init() {{ :; }}\nvc-intents() {{ :; }}\nvc-ownership() {{ :; }}\nvc-loop() {{ :; }}\nvc-ship() {{ :; }}\nvc-cron() {{ :; }}\nvc-marbles() {{ :; }}\ncodex-implement() {{ :; }}\ncodex-marbles() {{ :; }}\nskills-sync() {{ :; }}"
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


def test_run_doctor_uses_bundled_vc_frame_when_not_on_path(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    store_path = crafted_home / "skills"
    vc_frame = runtime_home / "bin" / "vc-frame"

    store_path.mkdir(parents=True)
    vc_frame.parent.mkdir(parents=True)
    _write_executable(
        vc_frame,
        '#!/usr/bin/env bash\nif [[ "$1" == "--version" ]]; then echo \'vc-frame 0.test\'; else exit 0; fi\n',
    )

    state = installer.InstallState(framework_version="1.5.0")
    state.save(store_path)

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)

    findings = installer.run_doctor(store_path, state)
    indexed = {finding.component: finding for finding in findings}

    assert indexed["vc-frame"].level == "ok"
    assert str(vc_frame) in indexed["vc-frame"].message


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
        "#!/usr/bin/env bash\ncase \"${1:-}\" in\n  --help) echo 'gemini help'; exit 0 ;;\n  *) exit 1 ;;\nesac"
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
        f"# shellcheck shell=bash\n{installer.HELPER_SHIM_MARKER}\nvc-help() {{ :; }}\nvc-agents() {{ :; }}\nvc-init() {{ :; }}\nvc-intents() {{ :; }}\nvc-ownership() {{ :; }}\nvc-loop() {{ :; }}\nvc-ship() {{ :; }}\nvc-cron() {{ :; }}\nvc-marbles() {{ :; }}\ncodex-implement() {{ :; }}\ncodex-marbles() {{ :; }}\nskills-sync() {{ :; }}"
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
    (home / ".local" / "share" / "uv" / "tools" / "vibecrafted" / "bin").mkdir(
        parents=True
    )
    _write_executable(
        home
        / ".local"
        / "share"
        / "uv"
        / "tools"
        / "vibecrafted"
        / "bin"
        / "vibecrafted",
        "#!/usr/bin/env bash\nprintf 'uv-tool vibecrafted shim\\n'\n",
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
    assert (launcher_bin / "vc-init").is_symlink()
    assert (launcher_bin / "vc-start").is_symlink()
    assert not (crafted_home / "bin" / "vc-init").exists()
    assert not (crafted_home / "bin" / "vc-start").exists()

    refreshed_state = installer.InstallState.load(current_link / "skills")
    assert any(entry.endswith("/vc-init") for entry in refreshed_state.launcher_entries)
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
        cargo_bin / "vc-frame", "#!/usr/bin/env bash\nprintf 'vc-frame-dev\\n'\n"
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
                name="vc-frame",
                description="VC Frame multi-agent terminal workspace surface",
                channels=["canonical"],
                packages={
                    "canonical": "curl -fsSL https://vibecrafted.io/install.sh | bash",
                },
                verify_cmd="vc-frame --version",
            ),
        ],
    )

    product_tools = installer.snapshot_product_tool_state()

    assert product_tools["loct"]["path"] == str(cargo_bin / "loct")
    assert product_tools["loct"]["managed_by"] == "external-path"
    assert product_tools["vc-frame"]["path"] == str(cargo_bin / "vc-frame")
    assert not (launcher_bin / "loct").exists()
    assert not (launcher_bin / "vc-frame").exists()

    state = installer.InstallState(product_tools=product_tools)
    state.save(store_path)
    loaded = installer.InstallState.load(store_path)

    assert loaded.product_tools["loct"]["path"] == str(cargo_bin / "loct")
    assert loaded.product_tools["vc-frame"]["path"] == str(cargo_bin / "vc-frame")


def test_product_tool_discovery_prefers_vc_frame_for_vc_frame_key(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    cargo_bin = home / ".cargo" / "bin"
    cargo_bin.mkdir(parents=True)

    _write_executable(
        cargo_bin / "vc-frame", "#!/usr/bin/env bash\nprintf 'vc-frame-dev\\n'\n"
    )
    _write_executable(
        cargo_bin / "vc-frame", "#!/usr/bin/env bash\nprintf 'vc_frame-dev\\n'\n"
    )

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)
    monkeypatch.setenv("PATH", str(cargo_bin))
    monkeypatch.setattr(
        installer,
        "FOUNDATIONS",
        [
            installer.Foundation(
                name="vc-frame",
                description="VC Frame multi-agent terminal workspace surface",
                channels=["canonical"],
                packages={
                    "canonical": "curl -fsSL https://vibecrafted.io/install.sh | bash",
                },
                verify_cmd="vc-frame --version",
            ),
        ],
    )

    product_tools = installer.snapshot_product_tool_state()

    assert product_tools["vc-frame"]["path"] == str(cargo_bin / "vc-frame")


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
    installed_deck = (
        runtime_home
        / "tools"
        / "vibecrafted-current"
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "deck"
        / "vibecrafted"
    )
    installed_deck.parent.mkdir(parents=True, exist_ok=True)
    _write_executable(
        installed_deck,
        (REPO_ROOT / "scripts" / "vibecrafted").read_text(encoding="utf-8"),
    )

    installer._install_launcher(source_root, dry_run=False, update_rc=False)

    assert unmanaged.read_text(encoding="utf-8").endswith(
        "my dev wrapper must survive\\n'\n"
    )
    assert not unmanaged.is_symlink()
    assert (launcher_bin / "vc-help").is_symlink()


def test_install_python_entrypoint_launchers_replace_managed_shell_wrappers(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    current_tools = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    console_bin = current_tools / ".venv" / "bin"
    launcher_bin = home / ".local" / "bin"
    console_bin.mkdir(parents=True)
    launcher_bin.mkdir(parents=True)

    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)

    for name in installer.PYTHON_ENTRYPOINT_LAUNCHERS:
        _write_executable(
            console_bin / name,
            f"#!{console_bin / 'python3'}\nprint('runtime {name}')\n",
        )
    (launcher_bin / "vibecrafted").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (launcher_bin / "vc-agents").symlink_to("vibecrafted")

    installed = installer._install_python_entrypoint_launchers(current_tools)

    assert len(installed) == len(installer.PYTHON_ENTRYPOINT_LAUNCHERS)
    vc_agents = launcher_bin / "vc-agents"
    assert vc_agents.is_symlink()
    assert vc_agents.resolve(strict=False) == console_bin / "vc-agents"
    assert (launcher_bin / "vibecrafted-resume").resolve(strict=False) == (
        console_bin / "vibecrafted-resume"
    )


def test_doctor_executes_vibecrafted_launcher_without_bash() -> None:
    installer_text = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(
        encoding="utf-8"
    )

    launcher_smoke = installer_text.split(
        'launcher = wrapper_locations.get("vibecrafted")', 1
    )[1].split("# 6b. Dashboard smoke", 1)[0]

    assert '["bash", str(launcher)' not in launcher_smoke
    assert '["bash", str(wrapper)' not in launcher_smoke
    assert '[str(launcher), "--help"]' in launcher_smoke
    assert "[str(wrapper)]" in launcher_smoke


def test_doctor_executes_dashboard_wrapper_without_bash() -> None:
    installer_text = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(
        encoding="utf-8"
    )

    dashboard_smoke = installer_text.split("# 6b. Dashboard smoke", 1)[1].split(
        "# 6c. vc-frame", 1
    )[0]

    assert '["bash", str(dashboard_wrapper)' not in dashboard_smoke
    assert '[str(dashboard_wrapper), "--help"]' in dashboard_smoke


def test_cleanse_state_home_agency_moves_only_executable_payloads(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    current_tools = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    _pin_canonical_runtime_roots(monkeypatch, home, crafted_home)

    for name in ("skills", "helpers", "config", "bin", "scripts"):
        payload = crafted_home / name
        payload.mkdir(parents=True)
        (payload / "payload.txt").write_text(name, encoding="utf-8")
    tmp_dir = crafted_home / "tmp"
    tmp_dir.mkdir(parents=True)
    (tmp_dir / "marbles.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_dir / "note.txt").write_text("state", encoding="utf-8")
    (crafted_home / "artifacts").mkdir(parents=True)

    moved = installer.cleanse_state_home_agency(current_tools)

    assert moved == 6
    for name in ("skills", "helpers", "config", "bin", "scripts"):
        assert not (crafted_home / name).exists()
        assert (
            current_tools / ".legacy-state-agency" / name / "payload.txt"
        ).read_text(encoding="utf-8") == name
    assert not (tmp_dir / "marbles.sh").exists()
    assert (tmp_dir / "note.txt").is_file()
    assert (crafted_home / "artifacts").is_dir()
    assert (current_tools / ".legacy-state-agency" / "tmp" / "marbles.sh").is_file()


def test_ensure_runtime_pip_bootstraps_when_missing(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append([str(part) for part in cmd])
        if cmd[2] == "pip" and cmd[3] == "--version":
            return subprocess.CompletedProcess(cmd, 1)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    installer._ensure_runtime_pip(tmp_path / "python3")

    assert calls == [
        [str(tmp_path / "python3"), "-m", "pip", "--version"],
        [str(tmp_path / "python3"), "-m", "ensurepip", "--upgrade"],
    ]


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
        f"# shellcheck shell=bash\n{installer.HELPER_SHIM_MARKER}\nvc-help() {{ :; }}\ncodex-implement() {{ :; }}\ncodex-marbles() {{ :; }}\nskills-sync() {{ :; }}"
        + "\n",
        encoding="utf-8",
    )

    (scripts_dir / "common.sh").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\nspawn_write_meta() { local meta_path="$1"; local status="$2"; printf "%s\\n" "$status" > "$meta_path"; }\nspawn_prepare_paths() { :; }\nspawn_watch_startup() { :; }\nspawn_generate_launcher() { local launcher="$1"; local _meta="$2"; local _report="$3"; local _transcript="$4"; local common="$5"; local command="$6"; cat > "$launcher" <<EOF\n#!/usr/bin/env bash\nset -euo pipefail\nsource "$common"\n$command\nEOF\n}'
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
        f"# shellcheck shell=bash\n{installer.HELPER_SHIM_MARKER}\nvc-help() {{ :; }}"
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
        f'# existing user config\n{installer._old_zshrc_source_line()}\n{installer._shell_source_line()}\nexport VIBECRAFTED_HOME="$HOME/.vibecrafted"\n{installer._launcher_path_line()}'
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


# --- W3-A vc-frame config delivery (plan vcframe-config-delivery) ---


def _seed_complete_vibecrafted_runtime(tools: Path) -> Path:
    runtime = tools / "vibecrafted-local"
    (runtime / "vibecrafted-core").mkdir(parents=True)
    (runtime / "runtime" / "scripts").mkdir(parents=True)
    (runtime / "Makefile").write_text("install:\n", encoding="utf-8")
    materialize_vc_frame_config(
        vc_frame_config_source(),
        runtime / "runtime" / "generated" / "vc-frame",
        pane_shell=resolve_pane_shell(),
        clipboard_command=resolve_clipboard_command(),
    )
    current = tools / "vibecrafted-current"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.symlink_to(runtime.name)
    return runtime


def test_vc_frame_delivery_healthy_store_view_ok(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_vibecrafted_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    stage_vc_frame_config(
        home=home, tools_home=tools, version="doc1", prefer_repo=False
    )
    findings = _vc_frame_delivery_findings(home=home, tools_home=tools)
    view = [f.level for f in findings if f.component == "vc-frame:view"]
    assert "fail" not in view, findings


def test_vc_frame_delivery_dev_checkout_does_not_require_runtime_generation(
    tmp_path, monkeypatch
):
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", "1")
    stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="dev",
        prefer_repo=True,
    )

    findings = _vc_frame_delivery_findings(home=home, tools_home=tools)

    assert not any(
        finding.level == "fail" and finding.component == "vc-frame:runtime"
        for finding in findings
    )
    assert any(
        finding.component == "vc-frame:channel"
        and "dev-checkout preferred" in finding.message
        for finding in findings
    )


def test_vc_frame_delivery_stale_file_fails_view(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    view = home / ".config" / "vc-frame"
    view.mkdir(parents=True)
    (view / "config.kdl").write_text('theme "choinka"\n', encoding="utf-8")
    (view / "layouts").mkdir()
    (view / "themes").mkdir()
    findings = _vc_frame_delivery_findings(home=home, tools_home=tools)
    fails = [
        f for f in findings if f.component == "vc-frame:view" and f.level == "fail"
    ]
    assert fails
    assert any("vibecrafted update" in f.message for f in fails)


def test_vc_frame_delivery_dangling_frontier_fails(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    z = home / ".config" / "vetcoders" / "frontier" / "zellij"
    z.mkdir(parents=True)
    bad = z / "x.kdl"
    bad.symlink_to("./nope.kdl")
    findings = _vc_frame_delivery_findings(home=home, tools_home=tools)
    zf = [f for f in findings if f.component == "frontier:zombies"]
    assert zf and zf[0].level == "fail"


def test_vc_frame_delivery_pane_shell_warn_when_zsh_missing_and_layouts_unsubstituted(
    tmp_path, monkeypatch
):
    """zsh-less PATH + layouts still command=\"zsh\" → vc-frame:pane-shell warn."""
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    # Unsubstituted layouts (dev-style view pointing at raw kdl with zsh)
    view = home / ".config" / "vc-frame"
    layouts = view / "layouts"
    layouts.mkdir(parents=True)
    (view / "config.kdl").write_text(
        'theme "monochrome"\ndefault_shell "zsh"\ncopy_command "pbcopy"\n',
        encoding="utf-8",
    )
    (view / "themes").mkdir()
    (layouts / "research.kdl").write_text(
        'pane command="zsh"\npane command="zsh"\n', encoding="utf-8"
    )
    (layouts / "operator.kdl").write_text(
        'pane command="bash" { args "-lc" "exec /bin/zsh -l" }\n',
        encoding="utf-8",
    )
    # PATH with only bash
    bash = shutil.which("bash")
    assert bash
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "bash").symlink_to(bash)
    findings = _vc_frame_delivery_findings(
        home=home, tools_home=tools, path_env=str(fake)
    )
    pane = [f for f in findings if f.component == "vc-frame:pane-shell"]
    assert pane, findings
    assert pane[0].level == "warn"
    assert "zsh" in pane[0].message
    assert "pbcopy" in pane[0].message
