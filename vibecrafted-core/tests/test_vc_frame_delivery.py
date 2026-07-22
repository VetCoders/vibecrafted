"""W2-A / W2-C: stage + wire + pane-shell substitution."""

from __future__ import annotations

import os
from pathlib import Path

from vibecrafted_core.vc_frame_delivery import (
    stage_vc_frame_config,
    substitute_pane_shell,
    classify_view_path,
)


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
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    # ensure zsh present so canonical retained (or force path)
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="3.6.0-test",
        dry_run=False,
        prefer_repo=False,
        path_env=os.environ.get("PATH", ""),
    )
    assert plan.channel == "store-current"
    view = home / ".config" / "vc-frame"
    cfg = view / "config.kdl"
    assert cfg.is_symlink() or cfg.is_file()
    resolved = cfg.resolve()
    assert resolved.is_file()
    text = resolved.read_text(encoding="utf-8")
    assert "theme" in text
    # through current
    current = tools / "vibecrafted-current"
    assert current.is_symlink()
    assert (current / "config" / "vc-frame" / "config.kdl").exists()


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


def test_regular_file_collision_gets_stale_backup(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
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
    backups = list(view.glob("config.kdl.stale.*"))
    assert backups, plan.render()
    assert "choinka" in backups[0].read_text(encoding="utf-8")
    assert "choinka" not in (view / "config.kdl").resolve().read_text(encoding="utf-8")


def test_foreign_symlink_is_preserved_without_force(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    operator_config = tmp_path / "operator-config.kdl"
    operator_config.write_text('theme "operator-custom"\n', encoding="utf-8")
    view = home / ".config" / "vc-frame"
    view.mkdir(parents=True)
    config_link = view / "config.kdl"
    config_link.symlink_to(operator_config)

    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="preserve-foreign",
        prefer_repo=False,
    )

    assert config_link.is_symlink()
    assert config_link.resolve() == operator_config.resolve()
    assert operator_config.read_text(encoding="utf-8") == 'theme "operator-custom"\n'
    assert any(
        action.kind == "skip"
        and action.path == str(config_link)
        and "foreign" in action.detail
        for action in plan.actions
    )


def test_foreign_symlink_is_replaced_with_force(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    operator_config = tmp_path / "operator-config.kdl"
    operator_config.write_text('theme "operator-custom"\n', encoding="utf-8")
    view = home / ".config" / "vc-frame"
    view.mkdir(parents=True)
    config_link = view / "config.kdl"
    config_link.symlink_to(operator_config)

    stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="replace-foreign",
        prefer_repo=False,
        force=True,
    )

    assert config_link.is_symlink()
    assert config_link.resolve() != operator_config.resolve()
    assert operator_config.read_text(encoding="utf-8") == 'theme "operator-custom"\n'


def test_version_flip_keeps_view_paths(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    stage_vc_frame_config(home=home, tools_home=tools, version="vA", prefer_repo=False)
    view_cfg = home / ".config" / "vc-frame" / "config.kdl"
    path_a = str(view_cfg)
    stage_vc_frame_config(
        home=home, tools_home=tools, version="vB", prefer_repo=False, force=True
    )
    assert str(view_cfg) == path_a
    assert (tools / "vibecrafted-vA").exists()
    assert (tools / "vibecrafted-vB").exists()
    # current points at vB
    assert (tools / "vibecrafted-current").resolve() == (
        tools / "vibecrafted-vB"
    ).resolve()
    assert view_cfg.resolve().is_file()


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
    # PATH without zsh: only /usr/bin (has bash on macOS/linux usually)
    minimal_path = "/usr/bin:/bin"
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="noshell",
        prefer_repo=False,
        path_env=minimal_path,
    )
    staged = tools / "vibecrafted-noshell" / "config" / "vc-frame" / "layouts"
    if plan.pane_shell == "zsh":
        # Host truly has zsh on minimal path — skip strict assert
        return
    research = (staged / "research.kdl").read_text(encoding="utf-8")
    assert 'command="zsh"' not in research
    assert f'command="{plan.pane_shell}"' in research


def test_classify_dangling(tmp_path: Path) -> None:
    link = tmp_path / "x"
    link.symlink_to(tmp_path / "missing-target")
    ch = classify_view_path(link, store_current=tmp_path / "store", checkout=None)
    assert ch == "DANGLING"
