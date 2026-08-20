"""W2-A / W2-C: stage + wire + pane-shell substitution."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from vibecrafted_core.frontier_assets import vc_frame_config_source
from vibecrafted_core.vc_frame_delivery import (
    classify_view_path,
    stage_vc_frame_config,
    substitute_pane_shell,
    wire_vc_frame_config,
)
from vibecrafted_core.vc_frame_staging import (
    materialize_vc_frame_config,
    resolve_clipboard_command,
    resolve_pane_shell,
)


def _runtime_payload(runtime: Path) -> Path:
    return runtime / "vibecrafted-core" / "vibecrafted_core" / "runtime"


def _seed_complete_runtime(
    tools: Path,
    *,
    path_env: str | None = None,
    with_config: bool = True,
    publish: bool = True,
) -> Path:
    runtime = tools / "vibecrafted-full"
    (runtime / "vibecrafted-core").mkdir(parents=True)
    (_runtime_payload(runtime) / "scripts").mkdir(parents=True)
    (runtime / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
    (_runtime_payload(runtime) / "scripts" / "codex_spawn.sh").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )
    if with_config:
        materialize_vc_frame_config(
            vc_frame_config_source(),
            _runtime_payload(runtime) / "generated" / "vc-frame",
            pane_shell=resolve_pane_shell(path_env),
            clipboard_command=resolve_clipboard_command(path_env),
        )
    if publish:
        current = tools / "vibecrafted-current"
        current.parent.mkdir(parents=True, exist_ok=True)
        current.symlink_to(runtime)
    return runtime


def test_substitute_pane_shell_only_exact_command_zsh() -> None:
    text = 'pane command="zsh"\npane command="zsh-lookalike"\n'
    out = substitute_pane_shell(text, "bash")
    assert 'command="bash"' in out
    assert 'command="zsh-lookalike"' in out
    assert 'command="zsh"' not in out.replace("zsh-lookalike", "")


def test_substitute_noop_when_shell_is_zsh() -> None:
    text = 'command="zsh"'
    assert substitute_pane_shell(text, "zsh") == text


def test_stage_wires_view_through_current(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime = _seed_complete_runtime(tools)
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="3.6.0-test",
        dry_run=False,
        prefer_repo=False,
        path_env=os.environ.get("PATH", ""),
    )
    assert plan.channel == "store-current"
    current = tools / "vibecrafted-current"
    assert current.is_symlink()
    assert current.resolve() == runtime.resolve()
    generated = _runtime_payload(current) / "generated" / "vc-frame"
    assert (generated / "config.kdl").exists()
    # One config home: the view is a single directory symlink at the
    # generated tree (through vibecrafted-current), not a per-file farm.
    view = home / ".config" / "vc-frame"
    assert view.is_symlink()
    assert view.resolve() == generated.resolve()
    cfg = view / "config.kdl"
    assert cfg.is_file()
    text = cfg.read_text(encoding="utf-8")
    assert "theme" in text
    assert (view / "vc-composer.sh").is_file()
    # The frontier twin is dissolved, not wired.
    frontier = home / ".config" / "vetcoders" / "frontier" / "vc-frame"
    assert not frontier.exists()
    assert 'bind "Super e"' in text
    assert "support_kitty_keyboard_protocol true" in text


def test_stage_backs_up_stale_frontier_composer_and_dissolves_twin(
    tmp_path: Path, monkeypatch
) -> None:
    """STALE-FILE under the legacy frontier twin is preserved as a backup,
    never left to shadow package scripts — and the twin itself dissolves."""
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_runtime(tools)
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    frontier = home / ".config" / "vetcoders" / "frontier" / "vc-frame"
    frontier.mkdir(parents=True)
    stale = frontier / "vc-composer.sh"
    stale.write_text("#!/bin/sh\n# ancient\n", encoding="utf-8")
    stale.chmod(0o755)
    stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="3.6.0-test",
        dry_run=False,
        prefer_repo=False,
        path_env=os.environ.get("PATH", ""),
    )
    assert not stale.exists()
    backups = sorted(frontier.glob("vc-composer.sh.stale.*"))
    assert backups
    assert "ancient" in backups[0].read_text(encoding="utf-8")
    # The live view serves the packaged composer instead.
    view = home / ".config" / "vc-frame"
    body = (view / "vc-composer.sh").read_text(encoding="utf-8")
    assert "ancient" not in body


def test_wire_backs_up_foreign_view_dir_and_skips_foreign_frontier_links(
    tmp_path: Path, monkeypatch
) -> None:
    """A real view dir holding operator customization is displaced into a
    backup (never destroyed); foreign links under the twin are skipped."""
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime = _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    foreign = tmp_path / "checkout"
    (foreign / "layouts").mkdir(parents=True)
    (foreign / "layouts" / "operator.kdl").write_text(
        "foreign layout\n", encoding="utf-8"
    )
    user_view = home / ".config" / "vc-frame"
    frontier = home / ".config" / "vetcoders" / "frontier" / "vc-frame"
    user_view.mkdir(parents=True)
    frontier.mkdir(parents=True)
    (user_view / "layouts").symlink_to(foreign / "layouts")
    (frontier / "layouts").symlink_to(foreign / "layouts")

    wire_vc_frame_config(
        home=home,
        tools_home=tools,
        prefer_repo=False,
        force_frontier=True,
    )

    generated = _runtime_payload(runtime) / "generated" / "vc-frame"
    assert user_view.is_symlink()
    assert user_view.resolve() == generated.resolve()
    backups = sorted((home / ".config").glob("vc-frame.stale.*"))
    assert backups and (backups[0] / "layouts").is_symlink()
    # Foreign twin entries stay put; the twin dir survives because of them.
    assert (frontier / "layouts").is_symlink()
    assert (foreign / "layouts" / "operator.kdl").read_text(
        encoding="utf-8"
    ) == "foreign layout\n"


def test_wire_only_requires_pre_materialized_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_runtime(tools, with_config=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    with pytest.raises(RuntimeError, match="pre-materialized"):
        wire_vc_frame_config(home=home, tools_home=tools, prefer_repo=False)

    assert not (home / ".config" / "vc-frame").exists()


def test_wire_only_never_mutates_published_generation(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime = _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    stage_vc_frame_config(home=home, tools_home=tools, prefer_repo=False)
    generated = _runtime_payload(runtime) / "generated" / "vc-frame"
    before = {
        path.relative_to(generated): (
            "link"
            if path.is_symlink()
            else "dir"
            if path.is_dir()
            else path.read_bytes()
        )
        for path in sorted(generated.rglob("*"))
    }
    replace_observations: list[bool] = []
    original_replace = os.replace
    view = home / ".config" / "vc-frame"

    def observed_replace(source, destination) -> None:
        destination_path = Path(destination)
        if destination_path == view:
            replace_observations.append(
                destination_path.exists() or destination_path.is_symlink()
            )
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", observed_replace)
    wire_vc_frame_config(
        home=home,
        tools_home=tools,
        prefer_repo=False,
        force=True,
    )

    after = {
        path.relative_to(generated): (
            "link"
            if path.is_symlink()
            else "dir"
            if path.is_dir()
            else path.read_bytes()
        )
        for path in sorted(generated.rglob("*"))
    }
    assert after == before
    assert replace_observations
    assert all(replace_observations)


def test_wire_failure_restores_displaced_user_view(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    view = home / ".config" / "vc-frame"
    view.mkdir(parents=True)
    operator_cfg = view / "config.kdl"
    operator_cfg.write_text("operator config\n", encoding="utf-8")
    original_replace = os.replace

    def fail_view_publish(source, destination) -> None:
        if Path(destination) == view:
            raise OSError("injected view publish failure")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_view_publish)

    with pytest.raises(OSError, match="injected view publish failure"):
        wire_vc_frame_config(
            home=home,
            tools_home=tools,
            prefer_repo=False,
            force=True,
        )

    # The displaced dir (whole-dir STALE backup) is restored on failure.
    assert view.is_dir()
    assert not view.is_symlink()
    assert operator_cfg.read_text(encoding="utf-8") == "operator config\n"


def test_stage_keeps_mirrored_runtime_source_distinct_from_generated_view(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime = _seed_complete_runtime(tools, with_config=False, publish=False)
    source = runtime / "config" / "vc-frame"
    (source / "layouts").mkdir(parents=True)
    (source / "themes").mkdir()
    (source / "config.kdl").write_text(
        'theme "monochrome"\ndefault_shell "zsh"\n', encoding="utf-8"
    )
    (source / "layouts" / "operator.kdl").write_text(
        'pane command="zsh"\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        "vibecrafted_core.vc_frame_delivery.vc_frame_config_source",
        lambda: source,
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    materialize_vc_frame_config(
        source,
        _runtime_payload(runtime) / "generated" / "vc-frame",
        pane_shell="sh",
        clipboard_command=None,
    )
    current = tools / "vibecrafted-current"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.symlink_to(runtime)

    stage_vc_frame_config(
        home=home,
        tools_home=tools,
        prefer_repo=False,
        path_env=str(tmp_path / "empty-path"),
    )

    assert (source / "config.kdl").read_text(encoding="utf-8").startswith("theme")
    generated = _runtime_payload(runtime) / "generated" / "vc-frame"
    assert (generated / "config.kdl").is_file()
    assert (home / ".config" / "vc-frame" / "config.kdl").resolve() == (
        generated / "config.kdl"
    ).resolve()


def test_dry_run_mutates_nothing(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="dry",
        dry_run=True,
        prefer_repo=False,
    )
    assert plan.dry_run is True
    assert not (home / ".config" / "vc-frame").exists()
    assert not tools.exists() or not list(tools.iterdir())


def test_stage_refuses_to_create_a_config_only_runtime_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    with pytest.raises(RuntimeError, match="stage the full distribution"):
        stage_vc_frame_config(home=home, tools_home=tools, prefer_repo=False)

    assert not (tools / "vibecrafted-current").exists()


def test_regular_file_collision_gets_stale_backup(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    view = home / ".config" / "vc-frame"
    view.mkdir(parents=True)
    stale = view / "config.kdl"
    stale.write_text('theme "choinka"\n', encoding="utf-8")
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="bump1",
        prefer_repo=False,
    )
    # The whole legacy dir is displaced as one auditable backup.
    backups = sorted((home / ".config").glob("vc-frame.stale.*"))
    assert backups, plan.render()
    assert "choinka" in (backups[0] / "config.kdl").read_text(encoding="utf-8")
    assert view.is_symlink()
    assert "choinka" not in (view / "config.kdl").read_text(encoding="utf-8")


def test_same_second_rewires_never_overwrite_operator_backups(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setattr(
        "vibecrafted_core.vc_frame_delivery._timestamp",
        lambda: "20260726_120000",
    )
    view = home / ".config" / "vc-frame"

    view.mkdir(parents=True)
    (view / "config.kdl").write_text("first operator config\n", encoding="utf-8")
    stage_vc_frame_config(home=home, tools_home=tools, prefer_repo=False)
    # Operator reverts to a real dir again; the second pass must not clobber
    # the first same-second backup.
    view.unlink()
    view.mkdir(parents=True)
    (view / "config.kdl").write_text("second operator config\n", encoding="utf-8")
    stage_vc_frame_config(home=home, tools_home=tools, prefer_repo=False)

    backups = sorted((home / ".config").glob("vc-frame.stale.20260726_120000-*"))
    assert len(backups) == 2
    assert {(path / "config.kdl").read_text(encoding="utf-8") for path in backups} == {
        "first operator config\n",
        "second operator config\n",
    }


def test_foreign_symlink_is_preserved_without_force(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    operator_dir = tmp_path / "operator-vc-frame"
    operator_dir.mkdir()
    (operator_dir / "config.kdl").write_text(
        'theme "operator-custom"\n', encoding="utf-8"
    )
    (home / ".config").mkdir(parents=True)
    view = home / ".config" / "vc-frame"
    view.symlink_to(operator_dir)

    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="preserve-foreign",
        prefer_repo=False,
    )

    assert view.is_symlink()
    assert view.resolve() == operator_dir.resolve()
    assert (operator_dir / "config.kdl").read_text(
        encoding="utf-8"
    ) == 'theme "operator-custom"\n'
    assert any(
        action.kind == "skip"
        and action.path == str(view)
        and "foreign" in action.detail
        for action in plan.actions
    )


def test_foreign_symlink_is_replaced_with_force(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    operator_dir = tmp_path / "operator-vc-frame"
    operator_dir.mkdir()
    (operator_dir / "config.kdl").write_text(
        'theme "operator-custom"\n', encoding="utf-8"
    )
    (home / ".config").mkdir(parents=True)
    view = home / ".config" / "vc-frame"
    view.symlink_to(operator_dir)

    stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="replace-foreign",
        prefer_repo=False,
        force=True,
    )

    assert view.is_symlink()
    assert view.resolve() != operator_dir.resolve()
    assert (view / "config.kdl").is_file()
    assert (operator_dir / "config.kdl").read_text(
        encoding="utf-8"
    ) == 'theme "operator-custom"\n'


def test_config_refresh_preserves_runtime_pointer_and_view_paths(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime = _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    stage_vc_frame_config(home=home, tools_home=tools, version="vA", prefer_repo=False)
    view_cfg = home / ".config" / "vc-frame" / "config.kdl"
    path_a = str(view_cfg)
    stage_vc_frame_config(
        home=home, tools_home=tools, version="vB", prefer_repo=False, force=True
    )
    assert str(view_cfg) == path_a
    assert (tools / "vibecrafted-current").resolve() == runtime.resolve()
    assert (runtime / "Makefile").is_file()
    assert (runtime / "vibecrafted-core").is_dir()
    assert (_runtime_payload(runtime) / "scripts" / "codex_spawn.sh").is_file()
    assert view_cfg.resolve().is_file()


def test_stage_rewires_legacy_store_view_to_generated_assets(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime = _seed_complete_runtime(tools)
    legacy = runtime / "config" / "vc-frame"
    legacy.mkdir(parents=True)
    (legacy / "config.kdl").write_text('theme "legacy"\n', encoding="utf-8")
    view = home / ".config" / "vc-frame"
    view.mkdir(parents=True)
    (view / "config.kdl").symlink_to(legacy / "config.kdl")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    stage_vc_frame_config(home=home, tools_home=tools, prefer_repo=False)

    generated = _runtime_payload(runtime) / "generated" / "vc-frame" / "config.kdl"
    assert (view / "config.kdl").resolve() == generated.resolve()


def test_dev_mode_targets_checkout(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="dev",
        prefer_repo=True,
    )
    assert plan.channel == "dev-checkout"
    view_cfg = (home / ".config" / "vc-frame" / "config.kdl").resolve()
    # should land under repo config/vc-frame
    assert view_cfg.is_file()
    assert "config/vc-frame" in str(view_cfg).replace("\\", "/")


def test_pane_shell_substitution_on_stage_without_zsh(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    # PATH without zsh or a clipboard helper: expose only bash.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    bash = shutil.which("bash")
    assert bash is not None
    (fake_bin / "bash").symlink_to(bash)
    runtime = _seed_complete_runtime(tools, path_env=str(fake_bin))
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="noshell",
        prefer_repo=False,
        path_env=str(fake_bin),
    )
    staged_root = _runtime_payload(runtime) / "generated" / "vc-frame"
    staged = staged_root / "layouts"
    assert plan.pane_shell == "bash"
    research = (staged / "research.kdl").read_text(encoding="utf-8")
    assert 'command="zsh"' not in research
    assert f'command="{plan.pane_shell}"' in research
    all_kdl = "\n".join(
        path.read_text(encoding="utf-8") for path in staged_root.rglob("*.kdl")
    )
    assert 'default_shell "zsh"' not in all_kdl
    assert "exec zsh -l" not in all_kdl
    assert "exec /bin/zsh -l" not in all_kdl
    if plan.clipboard_command is None:
        assert 'copy_command "pbcopy"' not in all_kdl
        assert "pbcopy <" not in all_kdl


def test_classify_dangling(tmp_path: Path) -> None:
    link = tmp_path / "x"
    link.symlink_to(tmp_path / "missing-target")
    ch = classify_view_path(link, store_current=tmp_path / "store", checkout=None)
    assert ch == "DANGLING"


def test_wire_collapses_legacy_link_farm_and_dissolves_frontier_twin(
    tmp_path: Path, monkeypatch
) -> None:
    """The old world (per-file owned links in the view + a frontier twin)
    migrates in one pass to a single view symlink and no twin."""
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime = _seed_complete_runtime(tools)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    generated = _runtime_payload(runtime) / "generated" / "vc-frame"
    view = home / ".config" / "vc-frame"
    frontier = home / ".config" / "vetcoders" / "frontier" / "vc-frame"
    view.mkdir(parents=True)
    frontier.mkdir(parents=True)
    for name in ("config.kdl", "layouts", "themes", "vc-composer.sh"):
        (view / name).symlink_to(generated / name)
        (frontier / name).symlink_to(generated / name)

    stage_vc_frame_config(home=home, tools_home=tools, prefer_repo=False)

    assert view.is_symlink()
    assert view.resolve() == generated.resolve()
    assert not frontier.exists()
    # No stray backups: everything removed was an owned link.
    assert not list((home / ".config").glob("vc-frame.stale.*"))
