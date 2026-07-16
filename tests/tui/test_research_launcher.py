from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"
RESEARCH_SKILL = REPO_ROOT / "skills" / "vc-research" / "SKILL.md"


def write_research_config(config_home: Path, agents: list[str]) -> None:
    config_dir = config_home / "vibecrafted"
    config_dir.mkdir(parents=True, exist_ok=True)
    quoted_agents = ", ".join(f'"{agent}"' for agent in agents)
    (config_dir / "config.toml").write_text(
        textwrap.dedent(
            f"""\
            [runtime.picking.research]
            default_agents = [{quoted_agents}]
            """
        ),
        encoding="utf-8",
    )


def write_runtime_research_yaml(vibecrafted_home: Path, agents: list[str]) -> None:
    config_dir = vibecrafted_home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    lanes = "\n".join(f"  - agent: {agent}" for agent in agents)
    (config_dir / "research.yaml").write_text(f"lanes:\n{lanes}\n", encoding="utf-8")


def test_vc_research_help_is_pure_help() -> None:
    result = subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-research --help'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Configurable triple-agent research swarm launcher" in result.stdout
    assert "Positional agents override the YAML lane set" in result.stdout
    assert "uno|duo|trio <agent...>" in result.stdout
    assert "Agent picking policy (explicit, fail-closed):" in result.stdout
    assert "Research swarm launched" not in result.stdout
    assert "command not found" not in result.stdout
    assert "command not found" not in result.stderr


def test_vc_research_positional_agent_launches_one_lane(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                f'vc-research codex --runtime headless --root "{root}" '
                '--prompt "Check auth providers"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Research override (codex) prepared" in result.stdout
    assert "command not found" not in result.stdout
    assert "command not found" not in result.stderr


def test_vc_research_uno_launches_one_requested_agent(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "vc-research uno codex --runtime headless "
                f'--root "{root}" --prompt "zbadaj tylko jeden tor"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Research override (codex) prepared" in result.stdout
    assert "Research swarm prepared" not in result.stdout

    run_id_match = re.search(r"run_id=(rsch-[^)]+)", result.stdout)
    run_dir_match = re.search(r"Run directory: (.+)", result.stdout)
    assert run_id_match is not None, result.stdout
    assert run_dir_match is not None, result.stdout
    run_id = run_id_match.group(1)
    run_dir = Path(run_dir_match.group(1))

    assert sorted(p.name for p in (run_dir / "logs").glob("*.meta.json")) == [
        "codex.meta.json",
    ]
    assert sorted(p.name for p in (run_dir / "tmp").glob("*_launch.sh")) == [
        "codex_launch.sh",
    ]
    assert not list((run_dir / "reports").glob("*.md"))

    meta = json.loads((run_dir / "logs" / "codex.meta.json").read_text())
    assert meta["run_id"] == run_id
    assert meta["agent"] == "codex"
    assert meta["skill_code"] == "rsch"
    assert meta["mode"] == "research"
    assert meta["report"] == str(run_dir / "reports" / "codex.md")

    summary = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "- Codex:" in summary
    assert "- Claude:" not in summary
    assert "- Junie:" not in summary


def test_vc_research_trio_honors_operator_selection(tmp_path: Path) -> None:
    """`trio claude agy junie` must launch EXACTLY those lanes, even when
    config.toml declares different default_agents. This is the incident test:
    the explicit operator selection was once silently replaced by the config
    default swarm."""
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    config_home = tmp_path / "xdg"
    write_research_config(config_home, ["agy", "codex", "claude"])

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(config_home)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "vc-research trio claude agy junie --runtime headless "
                f'--root "{root}" --prompt "YC teaser brief"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (
        "Research lanes: claude agy junie (source: positional-override)"
        in result.stdout
    )
    run_dir_match = re.search(r"Run directory: (.+)", result.stdout)
    assert run_dir_match is not None, result.stdout
    run_dir = Path(run_dir_match.group(1))
    assert sorted(p.name for p in (run_dir / "logs").glob("*.meta.json")) == [
        "agy.meta.json",
        "claude.meta.json",
        "junie.meta.json",
    ]


def test_vc_research_unknown_token_fails_closed(tmp_path: Path) -> None:
    """A stray token must abort the launch instead of being silently routed
    into the prompt while the swarm falls back to config defaults."""
    root = tmp_path / "repo"
    root.mkdir()
    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(tmp_path / "home" / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "vc-research tris claude agy --runtime headless "
                f'--root "{root}" --prompt "YC teaser brief"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "unknown agent or token" in result.stderr
    assert "prepared" not in result.stdout
    assert "launched" not in result.stdout


def test_vc_research_arity_keyword_must_match_agent_count(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(tmp_path / "home" / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "vc-research duo claude --runtime headless "
                f'--root "{root}" --prompt "one agent is not a duo"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "duo expects exactly 2 agent(s), got 1" in result.stderr
    assert "prepared" not in result.stdout


def test_vc_research_duplicate_agent_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(tmp_path / "home" / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "vc-research claude claude --runtime headless "
                f'--root "{root}" --prompt "same lane twice"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "agent claude given twice" in result.stderr


def test_vc_research_config_selection_announces_source(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    config_home = tmp_path / "xdg"
    write_research_config(config_home, ["agy", "codex", "claude"])

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(config_home)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "vc-research --runtime headless "
                f'--root "{root}" --prompt "who picked these lanes"'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    lanes_match = re.search(r"Research lanes: (.+) \(source: (.+)\)", result.stdout)
    assert lanes_match is not None, result.stdout
    assert lanes_match.group(1) == "agy codex claude"
    assert lanes_match.group(2).endswith("config.toml")


def test_vc_research_reads_runtime_owned_yaml(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    write_runtime_research_yaml(crafted_home, ["codex", "agy"])

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                f'vc-research --runtime headless --root "{root}" --prompt "yaml lanes"'
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
    assert sorted(p.name for p in (run_dir / "logs").glob("*.meta.json")) == [
        "agy.meta.json",
        "codex.meta.json",
    ]


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
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")

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
    config_home = tmp_path / "xdg"
    write_research_config(config_home, ["grok", "codex", "agy"])

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(config_home)
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
        "agy.meta.json",
        "codex.meta.json",
        "grok.meta.json",
    ]
    assert sorted(p.name for p in (run_dir / "tmp").glob("*_launch.sh")) == [
        "agy_launch.sh",
        "codex_launch.sh",
        "grok_launch.sh",
    ]
    assert not list(run_dir.parent.parent.glob("reports/*rsch*.meta.json"))
    assert not list(run_dir.parent.parent.glob("tmp/vc-research-*"))

    for agent in ("grok", "codex", "agy"):
        meta = json.loads((run_dir / "logs" / f"{agent}.meta.json").read_text())
        assert meta["run_id"] == run_id
        assert meta["skill_code"] == "rsch"
        assert meta["mode"] == "research"
        assert meta["report"] == str(run_dir / "reports" / f"{agent}.md")
        assert meta["transcript"] == str(run_dir / "logs" / f"{agent}.transcript.log")
        assert meta["launcher"] == str(run_dir / "tmp" / f"{agent}_launch.sh")
        assert str(meta["input"]).startswith(str(run_dir / "plans"))

    codex_launcher = (run_dir / "tmp" / "codex_launch.sh").read_text(encoding="utf-8")
    assert "--raw" not in codex_launcher
    assert ".raw.jsonl" not in codex_launcher

    await_env = env.copy()
    await_env["VIBECRAFTED_ROOT"] = str(root)
    await_env["VIBECRAFTED_AWAIT_STORE_DIR"] = str(run_dir.parent.parent)
    await_result = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "runtime" / "scripts" / "await.sh"),
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


def test_runtime_picking_manifest_keeps_mainstream_default_researchers() -> None:
    manifest = tomllib.loads((REPO_ROOT / "install.toml").read_text(encoding="utf-8"))

    assert manifest["runtime"]["picking"]["research"]["default_agents"] == [
        "claude",
        "codex",
        "agy",
    ]
    assert "grok" in manifest["runtime"]["picking"]["research"]["fallback_agents"]


def test_vc_research_skill_documents_read_only_source_repo_contract() -> None:
    payload = RESEARCH_SKILL.read_text(encoding="utf-8")

    assert "## Research Safety" in payload
    assert "read-only" in payload
    assert "for the source repository" in payload
    assert "No source mutation" in payload
    assert "No git writes" in payload
    assert "No stage, commit, amend" in payload
    assert "$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/" in payload
