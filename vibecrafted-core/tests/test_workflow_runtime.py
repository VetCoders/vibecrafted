from __future__ import annotations

import json
import os
from pathlib import Path

from vibecrafted_core import workflow_runtime


def _fake_agent(bin_dir: Path, name: str) -> None:
    path = bin_dir / name
    path.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\"\n"
        "cat\n"
        f"printf '[12:00:00] model: {name}-model\\n'\n"
        f"printf '[12:00:00] session: {name}-session\\n'\n"
        "printf '[12:00:01] tokens: 10 in (3 cached) / 5 out\\n'\n"
        "printf 'fake worker ok\\n'\n"
        'printf "%s\\n" "---" "status: completed" "---" "report for $0" > "$VIBECRAFTED_REPORT_PATH"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)


def _runtime_env(monkeypatch, tmp_path: Path, run_id: str) -> Path:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex", "gemini", "agy", "junie", "grok"):
        _fake_agent(bin_dir, name)
    for name in (
        "VIBECRAFTED_ARTIFACT_SLUG",
        "VIBECRAFTED_ARTIFACT_SUFFIX",
        "VIBECRAFTED_ARTIFACT_TS",
        "VIBECRAFTED_CANONICAL_REPORT_DIR",
        "VIBECRAFTED_RESEARCH_AGENTS",
        "VIBECRAFTED_TEE_OUTPUT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_RUN_ID", run_id)
    monkeypatch.setenv("VIBECRAFTED_REPORT_PATH", str(home / "parent.md"))
    monkeypatch.setenv("VIBECRAFTED_TRANSCRIPT_PATH", str(home / "parent.log"))
    monkeypatch.setenv("VIBECRAFTED_META_PATH", str(home / "parent.meta.json"))
    return home


def test_research_runtime_supervises_three_tracks(monkeypatch, tmp_path: Path) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-test")

    rc = workflow_runtime.main(
        ["research", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "vc-research supervised run" in report
    assert "Research Lane Selection" in report
    assert "agents: claude, codex, gemini" in report
    assert "research-claude" in report
    assert "research-codex" in report
    assert "research-gemini" in report
    assert "research-synthesis" in report
    assert "agent_session_id: claude-session" in report
    assert "agent_model: claude-model" in report
    assert "tokens: 10 in (3 cached) / 5 out" in report
    assert "claude --resume claude-session" in report
    assert (home / "rsch-test-children" / "research-claude.md").is_file()
    assert (home / "rsch-test-children" / "research-codex.md").is_file()
    assert (home / "rsch-test-children" / "research-gemini.md").is_file()
    assert (home / "rsch-test-children" / "research-synthesis.md").is_file()


def test_research_runtime_uses_user_configured_agents(
    monkeypatch, tmp_path: Path
) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-config")
    config_dir = tmp_path / "xdg" / "vibecrafted"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[runtime.picking.research]\ndefault_agents = ["grok", "codex", "gemini"]\n',
        encoding="utf-8",
    )

    rc = workflow_runtime.main(
        ["research", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    meta = (home / "parent.meta.json").read_text(encoding="utf-8")
    assert "agents: grok, codex, gemini" in report
    assert "research-grok" in report
    assert "research-codex" in report
    assert "research-gemini" in report
    assert "research-claude" not in report
    assert '"research_agents": [\n    "grok",\n    "codex",\n    "gemini"\n  ]' in meta


def test_research_runtime_writes_canonical_named_lane_artifacts(
    monkeypatch, tmp_path: Path
) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-canonical")
    canonical = (
        home / "artifacts" / "local" / "repo" / "2026_0613" / "reports" / "research"
    )
    monkeypatch.setenv("VIBECRAFTED_CANONICAL_REPORT_DIR", str(canonical))
    monkeypatch.setenv("VIBECRAFTED_ARTIFACT_TS", "2026-06-13")
    monkeypatch.setenv("VIBECRAFTED_ARTIFACT_SLUG", "acp-versus-native")
    monkeypatch.setenv("VIBECRAFTED_RESEARCH_AGENTS", "grok,codex")

    rc = workflow_runtime.main(
        [
            "research",
            "--root",
            str(tmp_path),
            "--prompt",
            "ACP versus native cli agent versus Plugin",
        ]
    )

    assert rc == 0
    assert (canonical / "2026-06-13_grok_acp-versus-native_report.md").is_file()
    assert (canonical / "2026-06-13_codex_acp-versus-native_report.md").is_file()
    assert (canonical / "2026-06-13_synthesis_acp-versus-native_report.md").is_file()
    assert (home / "parent.md").is_file()


def test_research_runtime_env_agents_override_user_config(
    monkeypatch, tmp_path: Path
) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-env")
    config_dir = tmp_path / "xdg" / "vibecrafted"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[runtime.picking.research]\ndefault_agents = ["claude", "codex", "gemini"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBECRAFTED_RESEARCH_AGENTS", "grok,codex")

    rc = workflow_runtime.main(
        ["research", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "source: env:VIBECRAFTED_RESEARCH_AGENTS" in report
    assert "agents: grok, codex" in report
    assert "research-grok" in report
    assert "research-codex" in report
    assert "research-gemini" not in report


def test_research_synthesis_waits_for_lane_meta_and_resumes_last_finisher(
    monkeypatch, tmp_path: Path
) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-layout")
    config_dir = tmp_path / "xdg" / "vibecrafted"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[runtime.picking.research]\ndefault_agents = ["grok", "codex"]\n',
        encoding="utf-8",
    )
    child_dir = home / "rsch-layout-children"
    child_dir.mkdir(parents=True)
    for agent, completed_at in (
        ("grok", "2026-06-13T10:00:00+00:00"),
        ("codex", "2026-06-13T10:01:00+00:00"),
    ):
        report = child_dir / f"research-{agent}.md"
        transcript = child_dir / f"research-{agent}.transcript.log"
        report.write_text("---\nstatus: completed\n---\n", encoding="utf-8")
        transcript.write_text("done\n", encoding="utf-8")
        (child_dir / f"research-{agent}.meta.json").write_text(
            json.dumps(
                {
                    "run_id": f"rsch-layout-research-{agent}",
                    "agent": agent,
                    "agent_session_id": f"{agent}-session",
                    "agent_model": f"{agent}-model",
                    "report": str(report),
                    "transcript": str(transcript),
                    "exit_code": 0,
                    "artifact_errors": [],
                    "resume_command": f"cd {tmp_path} && {agent} resume {agent}-session",
                    "completed_at": completed_at,
                }
            ),
            encoding="utf-8",
        )

    rc = workflow_runtime.main(
        ["research-synthesis", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "agents: grok, codex" in report
    assert "research-synthesis (codex)" in report
    assert "agent_session_id: codex-session" in report
    assert (child_dir / "research-synthesis.md").is_file()


def test_research_synthesis_recovers_legacy_lane_meta_without_exit_code(
    monkeypatch, tmp_path: Path
) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-legacy-meta")
    config_dir = tmp_path / "xdg" / "vibecrafted"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[runtime.picking.research]\ndefault_agents = ["grok"]\n',
        encoding="utf-8",
    )
    child_dir = home / "rsch-legacy-meta-children"
    child_dir.mkdir(parents=True)
    report = child_dir / "research-grok.md"
    transcript = child_dir / "research-grok.transcript.log"
    report.write_text("---\nstatus: completed\n---\nbody\n", encoding="utf-8")
    transcript.write_text("done\n", encoding="utf-8")
    (child_dir / "research-grok.meta.json").write_text(
        json.dumps(
            {
                "run_id": "rsch-legacy-meta-research-grok",
                "agent": "grok",
                "agent_session_id": "grok-session",
                "report": str(report),
                "transcript": str(transcript),
                "resume_command": f"cd {tmp_path} && grok --resume grok-session",
            }
        ),
        encoding="utf-8",
    )

    rc = workflow_runtime.main(
        ["research-synthesis", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    parent = (home / "parent.md").read_text(encoding="utf-8")
    assert "research-grok" in parent
    assert "exit_code: 0" in parent
    assert "research-synthesis (grok)" in parent


def test_research_synthesis_closes_when_lane_failed(
    monkeypatch, tmp_path: Path
) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-lane-failed")
    config_dir = tmp_path / "xdg" / "vibecrafted"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[runtime.picking.research]\ndefault_agents = ["grok", "codex"]\n',
        encoding="utf-8",
    )
    canonical = (
        home / "artifacts" / "local" / "repo" / "2026_0613" / "reports" / "research"
    )
    monkeypatch.setenv("VIBECRAFTED_CANONICAL_REPORT_DIR", str(canonical))
    monkeypatch.setenv("VIBECRAFTED_ARTIFACT_TS", "2026-06-13")
    monkeypatch.setenv("VIBECRAFTED_ARTIFACT_SLUG", "acp-versus-native")
    failed_report = canonical / "2026-06-13_grok_acp-versus-native_report.md"
    failed_report.parent.mkdir(parents=True, exist_ok=True)
    failed_report.write_text("---\nstatus: failed\n---\n", encoding="utf-8")
    (canonical / "2026-06-13_grok_acp-versus-native_report.transcript.log").write_text(
        "boom\n",
        encoding="utf-8",
    )
    (canonical / "2026-06-13_grok_acp-versus-native_report.meta.json").write_text(
        json.dumps(
            {
                "run_id": "rsch-lane-failed-research-grok",
                "agent": "grok",
                "report": str(failed_report),
                "exit_code": 1,
                "artifact_errors": ["worker_failed"],
                "completed_at": "2026-06-13T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    rc = workflow_runtime.main(
        ["research-synthesis", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 1
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "status: failed" in report
    assert "research-grok" in report
    assert "artifact_errors: worker_failed" in report


def test_research_synthesis_degrades_to_partial_success_on_quorum(
    monkeypatch, tmp_path: Path
) -> None:
    # Emil's first swarm: Codex + Grok dowiozły, Gemini padł. Większość (2/3)
    # ⇒ synteza z ocalałych i status partial_success, nie zawalenie całego runu.
    home = _runtime_env(monkeypatch, tmp_path, "rsch-partial")
    config_dir = tmp_path / "xdg" / "vibecrafted"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[runtime.picking.research]\ndefault_agents = ["grok", "codex", "gemini"]\n',
        encoding="utf-8",
    )
    child_dir = home / "rsch-partial-children"
    child_dir.mkdir(parents=True)

    for agent, completed_at in (
        ("grok", "2026-06-23T10:00:00+00:00"),
        ("codex", "2026-06-23T10:01:00+00:00"),
    ):
        report = child_dir / f"research-{agent}.md"
        transcript = child_dir / f"research-{agent}.transcript.log"
        report.write_text("---\nstatus: completed\n---\n", encoding="utf-8")
        transcript.write_text("done\n", encoding="utf-8")
        (child_dir / f"research-{agent}.meta.json").write_text(
            json.dumps(
                {
                    "run_id": f"rsch-partial-research-{agent}",
                    "agent": agent,
                    "agent_session_id": f"{agent}-session",
                    "agent_model": f"{agent}-model",
                    "report": str(report),
                    "transcript": str(transcript),
                    "exit_code": 0,
                    "artifact_errors": [],
                    "resume_command": f"cd {tmp_path} && {agent} resume {agent}-session",
                    "completed_at": completed_at,
                }
            ),
            encoding="utf-8",
        )

    failed_report = child_dir / "research-gemini.md"
    failed_report.write_text("---\nstatus: failed\n---\n", encoding="utf-8")
    (child_dir / "research-gemini.transcript.log").write_text(
        "boom\n", encoding="utf-8"
    )
    (child_dir / "research-gemini.meta.json").write_text(
        json.dumps(
            {
                "run_id": "rsch-partial-research-gemini",
                "agent": "gemini",
                "report": str(failed_report),
                "transcript": str(child_dir / "research-gemini.transcript.log"),
                "exit_code": 1,
                "artifact_errors": ["worker_failed"],
                "completed_at": "2026-06-23T10:02:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    rc = workflow_runtime.main(
        ["research-synthesis", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "status: partial_success" in report
    # synteza odpaliła z ostatniego ocalałego (codex), gemini odnotowany jako fail
    assert "research-synthesis (codex)" in report
    assert "research-gemini" in report
    assert "artifact_errors: worker_failed" in report
    assert (child_dir / "research-synthesis.md").is_file()


def test_research_runtime_tees_child_output(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    _runtime_env(monkeypatch, tmp_path, "rsch-visible")
    monkeypatch.setenv("VIBECRAFTED_TEE_OUTPUT", "1")

    rc = workflow_runtime.main(
        ["research", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "===== research:research-claude:claude =====" in out
    assert "===== research:research-codex:codex =====" in out
    assert "===== research:research-gemini:gemini =====" in out
    assert "===== research:research-synthesis:" in out
    assert "fake worker ok" in out


def test_marbles_runtime_supervises_loops(monkeypatch, tmp_path: Path) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "marb-test")

    rc = workflow_runtime.main(
        [
            "marbles",
            "--agent",
            "codex",
            "--root",
            str(tmp_path),
            "--prompt",
            "converge",
            "--count",
            "2",
            "--depth",
            "4",
        ]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "vc-marbles supervised run" in report
    assert "marbles-L1" in report
    assert "marbles-L2" in report
    assert "agent_session_id: codex-session" in report
    assert "agent_model: codex-model" in report
    assert "codex resume codex-session" in report
    assert (home / "marb-test-children" / "marbles-L1.md").is_file()
    assert (home / "marb-test-children" / "marbles-L2.md").is_file()
    l2_transcript = (
        home / "marb-test-children" / "marbles-L2.transcript.log"
    ).read_text(encoding="utf-8")
    assert "intentionally blind to prior marbles runs" in l2_transcript
    assert "Previous loop report" not in l2_transcript
    assert "marbles-L1.md" not in l2_transcript


def test_polarize_runtime_reuses_loop_with_polarize_identity(
    monkeypatch, tmp_path: Path
) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "plrz-test")

    rc = workflow_runtime.main(
        [
            "marbles",
            "--workflow",
            "polarize",
            "--agent",
            "codex",
            "--root",
            str(tmp_path),
            "--prompt",
            "cut excess",
            "--count",
            "1",
            "--depth",
            "4",
        ]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    prompt = (home / "plrz-test-children" / "polarize-L1.prompt.md").read_text(
        encoding="utf-8"
    )
    assert "vc-polarize supervised run" in report
    assert "polarize-L1" in report
    assert "- Skill: vc-polarize" in prompt
    assert "Polarize loop: L1/1. Depth target: 4." in prompt
    assert "Marbles loop" not in prompt
    assert "agent_model: codex-model" in report
    assert "codex resume codex-session" in report
    assert (home / "plrz-test-children" / "polarize-L1.md").is_file()
    transcript = (home / "plrz-test-children" / "polarize-L1.transcript.log").read_text(
        encoding="utf-8"
    )
    assert "intentionally blind to prior marbles runs" not in transcript
    assert "Previous loop report" not in transcript
    assert "marbles-L1.md" not in transcript
