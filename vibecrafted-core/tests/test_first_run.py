"""first_run — the `[product]` table and the apply/summary contract.

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from vibecrafted_core import first_run
from vibecrafted_core.server_config import load_server_config


def _generation(runtime_home: Path) -> Path:
    root = (
        runtime_home
        / "releases"
        / "4.2.4+gaaaaaaaa"
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "skills"
    )
    for base in (root, root / "pl"):
        for name in ("vc-init", "vc-ship"):
            (base / name).mkdir(parents=True)
            (base / name / "SKILL.md").write_text(f"{name}\n")
        (base / "LIVING_TREE_RULE.md").write_text("canon\n")
    return root


def test_write_keeps_the_operators_server_table(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '# operator notes\n[server]\nbind_host = "100.64.0.7"\nport = 3025\n',
        encoding="utf-8",
    )
    decisions = first_run.ProductDecisions(
        agents=("claude", "codex"),
        skills_lang="pl",
        work_mode="worktrees",
        agent_permissions="bypass",
        decided_at="2026-08-23T12:00:00+00:00",
        version="4.2.4",
    )
    first_run.write(decisions, config)

    text = config.read_text(encoding="utf-8")
    assert text.startswith("# operator notes\n[server]\n")
    assert load_server_config(config).bind_host == "100.64.0.7"
    assert first_run.load(config) == decisions
    assert oct(config.stat().st_mode & 0o777) == "0o600"

    # a second write replaces the table in place, the server table is untouched
    later = first_run.ProductDecisions(agents=("claude",), decided_at="later")
    first_run.write(later, config)
    text = config.read_text(encoding="utf-8")
    assert text.count("[product]") == 1
    assert text.count("[server]") == 1
    assert first_run.load(config) == later
    assert load_server_config(config).port == 3025


def test_load_is_none_without_decisions_and_strict_with_bad_ones(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    assert first_run.load(config) is None
    config.write_text("[server]\nport = 1\n", encoding="utf-8")
    assert first_run.load(config) is None
    config.write_text('[product]\nagents = ["claude"]\nwork_mode = "yolo"\n')
    with pytest.raises(first_run.FirstRunError):
        first_run.load(config)
    with pytest.raises(first_run.FirstRunError):
        first_run.ProductDecisions(agents=("vim",)).validate()


def test_apply_writes_projects_and_summarises(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir()
    (home / ".local" / "bin").mkdir(parents=True)
    mcp = home / ".local" / "bin" / "vibecrafted-mcp"
    mcp.write_text("#!/bin/bash\n")
    mcp.chmod(0o755)
    runtime_home = home / ".local" / "share" / "vibecrafted"
    skills = _generation(runtime_home)
    config = home / ".config" / "vibecrafted" / "config.toml"

    decisions = first_run.ProductDecisions(
        agents=("claude",),
        skills_lang="pl",
        decided_at="2026-08-23T12:00:00+00:00",
        version="4.2.4",
    )
    summary = first_run.apply(
        decisions,
        skills_root=skills,
        runtime_home=runtime_home,
        home=home,
        config=config,
    )

    assert summary["ok"] is True
    assert summary["config"] == str(config)
    assert summary["skills"]["source"] == str(skills / "pl")
    assert summary["skills"]["per_agent"] == {"agents": 3, "claude": 3}
    assert summary["mcp"] == {"launcher": str(mcp), "present": True}
    assert os.readlink(home / ".claude" / "skills" / "vc-ship") == str(
        skills / "pl" / "vc-ship"
    )
    # codex was not chosen: nothing projected there
    assert not (home / ".codex" / "skills").exists()
    assert first_run.load(config).agents == ("claude",)


def test_cli_apply_and_show(tmp_path: Path, capsys, monkeypatch) -> None:
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    runtime_home = home / ".local" / "share" / "vibecrafted"
    skills = _generation(runtime_home)
    config = home / ".config" / "vibecrafted" / "config.toml"
    monkeypatch.setenv("VIBECRAFTED_RUNTIME_ROOT", str(skills.parents[2]))

    code = first_run.main(
        [
            "apply",
            "--agents",
            "codex",
            "--work-mode",
            "vm",
            "--permissions",
            "bypass",
            "--unattended",
            "--version",
            "4.2.4",
            "--home",
            str(home),
            "--runtime-home",
            str(runtime_home),
            "--config",
            str(config),
        ]
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["decisions"]["decided_by"] == "unattended-preset"
    assert summary["decisions"]["work_mode"] == "vm"
    assert summary["mcp"]["present"] is False
    assert (home / ".codex" / "skills" / "vc-init").is_symlink()

    assert first_run.main(["show", "--config", str(config)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["agents"] == ["codex"]
    assert shown["agent_permissions"] == "bypass"

    assert (
        first_run.main(
            ["apply", "--agents", "vim", "--home", str(home), "--config", str(config)]
        )
        == 2
    )


def test_permission_flags_follow_the_recorded_decision(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "config.toml"
    monkeypatch.delenv("VIBECRAFTED_AGENT_PERMISSIONS", raising=False)
    first_run._permissions_cache.clear()

    # nothing recorded: the pre-first-run behaviour (bypass) is kept
    assert first_run.agent_permissions_mode(config) == "bypass"
    assert first_run.permission_flags("claude", config) == [
        "--dangerously-skip-permissions"
    ]
    assert first_run.permission_flags("grok", config) == [
        "--permission-mode",
        "bypassPermissions",
    ]
    assert first_run.permission_flags("junie", config) == []

    first_run._permissions_cache.clear()
    first_run.write(
        first_run.ProductDecisions(agents=("claude",), agent_permissions="ask"), config
    )
    assert first_run.agent_permissions_mode(config) == "ask"
    assert first_run.permission_flags("claude", config) == []
    assert first_run.permission_flags("codex", config) == []

    # a dispatch can still override per run
    monkeypatch.setenv("VIBECRAFTED_AGENT_PERMISSIONS", "bypass")
    assert first_run.permission_flags("codex", config) == [
        "--dangerously-bypass-approvals-and-sandbox"
    ]


def test_cli_reapply_projects_from_the_record(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    runtime_home = home / ".local" / "share" / "vibecrafted"
    skills = _generation(runtime_home)
    config = home / ".config" / "vibecrafted" / "config.toml"
    common = [
        "--home",
        str(home),
        "--runtime-home",
        str(runtime_home),
        "--config",
        str(config),
        "--skills",
        str(skills),
    ]

    assert first_run.main(["reapply", *common]) == 3  # nothing recorded yet
    capsys.readouterr()
    first_run.write(
        first_run.ProductDecisions(agents=("claude",), skills_lang="pl"), config
    )
    assert first_run.main(["reapply", *common]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decisions"]["skills_lang"] == "pl"
    assert len(payload["linked"]) == 6  # 3 entries x (.agents + .claude)
    assert os.readlink(home / ".claude" / "skills" / "vc-ship") == str(
        skills / "pl" / "vc-ship"
    )
