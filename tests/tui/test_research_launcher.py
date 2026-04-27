from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"
RESEARCH_SKILL = REPO_ROOT / "skills" / "vc-research" / "SKILL.md"


def test_vc_research_help_is_pure_help() -> None:
    result = subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-research --help'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Triple-agent research swarm launcher" in result.stdout
    assert "Do not pass an agent to vc-research." in result.stdout
    assert "Research swarm launched" not in result.stdout
    assert "command not found" not in result.stdout
    assert "command not found" not in result.stderr


def test_vc_research_rejects_agent_argument_without_helper_crash() -> None:
    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; vc-research codex --prompt "Check auth providers"',
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "vc-research is a triple-agent swarm launcher" in result.stderr
    assert "command not found" not in result.stdout
    assert "command not found" not in result.stderr


def test_vc_research_generated_worker_prompts_do_not_leak_launcher_semantics(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    plan = tmp_path / "research-plan.md"
    plan.write_text(
        textwrap.dedent(
            """\
            ---
            run_id: rsch-test
            agent: codex
            skill: vc-research
            status: in-progress
            ---

            # Research Plan: Prompt Hygiene

            ## Problem

            We need research workers to execute the plan directly.

            ## Questions

            1. Which prompt content reaches the worker?
            2. Which output file should receive the report?
            """
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                f'vc-research --runtime headless --root "{root}" --file "{plan}"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    run_dir_match = re.search(r"Run directory: (.+)", result.stdout)
    assert run_dir_match is not None, result.stdout
    run_dir = Path(run_dir_match.group(1))
    worker_prompts = sorted((run_dir / "tmp").glob("*_prompt.md"))
    assert len(worker_prompts) == 3
    assert not list((root / ".vibecrafted").glob("tmp/*_prompt.md"))

    forbidden = [
        "skill: vc-research",
        "Perform the vc-research skill",
        "Triple-agent research swarm",
        "vc-research is a triple-agent swarm launcher",
        "## VC Agents Worker Charter",
        "spawned vc-agents worker",
        "Do NOT invoke vc-agents",
        "do NOT launch another external fleet",
        "vc-why-matrix",
        "Codex Research Report Capture Contract",
        "For vc-research",
        "delegate",
        "delegation",
    ]
    for worker_prompt in worker_prompts:
        payload = worker_prompt.read_text(encoding="utf-8")
        assert "# Research Plan: Prompt Hygiene" in payload
        assert "Which prompt content reaches the worker?" in payload
        assert "Report path:" in payload
        for needle in forbidden:
            assert needle not in payload

    codex_payloads = [
        worker_prompt.read_text(encoding="utf-8")
        for worker_prompt in worker_prompts
        if "## Codex Report Write Contract" in worker_prompt.read_text(encoding="utf-8")
    ]
    assert len(codex_payloads) == 1
    assert "`codex exec --output-last-message`" in codex_payloads[0]
    assert (
        "write the COMPLETE markdown report to the exact `Report path`"
        in codex_payloads[0]
    )
    assert "using a shell command such as a heredoc" in codex_payloads[0]
    assert "must not be the only place where the report exists" in codex_payloads[0]


def test_vc_research_uses_run_scoped_artifact_layout(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    for key in (
        "VIBECRAFTED_RUN_ID",
        "VIBECRAFTED_RUN_LOCK",
        "VIBECRAFTED_STORE_DIR",
        "VIBECRAFTED_STORE_ROOT",
        "VIBECRAFTED_RESEARCH_RUN_DIR",
    ):
        env.pop(key, None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                f'vc-research --runtime headless --root "{root}" --prompt "zbadaj aicx"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    run_id_match = re.search(r"run_id=(rsch-[^)]+)", result.stdout)
    run_dir_match = re.search(r"Run directory: (.+)", result.stdout)
    assert run_id_match is not None, result.stdout
    assert run_dir_match is not None, result.stdout
    run_id = run_id_match.group(1)
    run_dir = Path(run_dir_match.group(1))

    assert run_dir.name == run_id
    assert run_dir.parent.name == "research"
    assert (run_dir / "summary.md").is_file()
    assert sorted(p.name for p in (run_dir / "logs").glob("*.meta.json")) == [
        "claude.meta.json",
        "codex.meta.json",
        "gemini.meta.json",
    ]
    assert sorted(p.name for p in (run_dir / "tmp").glob("*_launch.sh")) == [
        "claude_launch.sh",
        "codex_launch.sh",
        "gemini_launch.sh",
    ]
    assert not list(run_dir.parent.parent.glob("reports/*rsch*.meta.json"))
    assert not list(run_dir.parent.parent.glob("tmp/vc-research-*"))

    for agent in ("claude", "codex", "gemini"):
        meta = json.loads((run_dir / "logs" / f"{agent}.meta.json").read_text())
        assert meta["run_id"] == run_id
        assert meta["skill_code"] == "rsch"
        assert meta["mode"] == "research"
        assert meta["report"] == str(run_dir / "reports" / f"{agent}.md")
        assert meta["transcript"] == str(run_dir / "logs" / f"{agent}.transcript.log")
        assert meta["launcher"] == str(run_dir / "tmp" / f"{agent}_launch.sh")
        assert str(meta["input"]).startswith(str(run_dir / "plans"))

    codex_launcher = (run_dir / "tmp" / "codex_launch.sh").read_text(encoding="utf-8")
    assert str(run_dir / "logs" / "codex.transcript.raw.jsonl") in codex_launcher

    await_env = env.copy()
    await_env["VIBECRAFTED_ROOT"] = str(root)
    await_env["VIBECRAFTED_AWAIT_STORE_DIR"] = str(run_dir.parent.parent)
    await_result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "skills" / "vc-agents" / "scripts" / "await.sh"),
            "--research",
            "--run-id",
            run_id,
            "--describe",
        ],
        cwd=root,
        env=await_env,
        capture_output=True,
        text=True,
    )

    assert await_result.returncode == 0, await_result.stderr
    assert "tracks:  3" in await_result.stdout
    assert str(run_dir / "reports" / "codex.md") in await_result.stdout
    assert str(run_dir / "logs" / "codex.meta.json") in await_result.stdout


def test_vc_research_skill_documents_read_only_source_repo_contract() -> None:
    payload = RESEARCH_SKILL.read_text(encoding="utf-8")

    assert "## Research Safety" in payload
    assert "Research mode is read-only for the source repository" in payload
    assert "Do not stage, commit, amend" in payload
    assert "Do not edit repo source files" in payload
    assert "$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/" in payload
