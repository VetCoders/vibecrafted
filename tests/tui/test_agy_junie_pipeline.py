from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "scripts" / "vibecrafted"
SPAWN_DIR = REPO_ROOT / "runtime" / "scripts"


def _write_plan(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    plan = tmp_path / "plan.md"
    plan.write_text(
        "---\nrun_id: test\nagent: test\nstatus: prompt\n---\n\nDo the bounded task.\n",
        encoding="utf-8",
    )
    return plan


def _dry_run_launcher(tmp_path: Path, agent: str) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    plan = _write_plan(tmp_path)
    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(tmp_path / "home" / ".vibecrafted")

    result = subprocess.run(
        [
            "bash",
            str(SPAWN_DIR / f"{agent}_spawn.sh"),
            "--dry-run",
            "--runtime",
            "headless",
            "--root",
            str(root),
            str(plan),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    marker = "Dry run mode: launcher generated only: "
    launcher_lines = [
        line.removeprefix(marker)
        for line in result.stdout.splitlines()
        if line.startswith(marker)
    ]
    assert launcher_lines
    launcher = Path(launcher_lines[-1])
    assert launcher.is_file()
    return launcher


def test_command_deck_accepts_agy_junie_and_grok_help() -> None:
    for agent in ("agy", "junie", "grok"):
        result = subprocess.run(
            [str(LAUNCHER), agent, "--help"],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert f"Plan-based helper modes for {agent}." in result.stdout
        assert "implement <plan.md>" in result.stdout
        assert "await     --last" in result.stdout


def test_agy_spawn_dry_run_uses_antigravity_print_contract(tmp_path: Path) -> None:
    launcher = _dry_run_launcher(tmp_path, "agy")
    text = launcher.read_text(encoding="utf-8")

    assert "SPAWN_AGENT=agy" in text
    assert "agy --print --dangerously-skip-permissions --add-dir" in text
    assert "--print-timeout 30m" in text
    assert " < " in text
    assert '"$(cat ' not in text
    assert "Agy completed without writing a standalone report file" in text
    assert "Agy failed before writing a standalone report file" in text
    assert "pipeline_status=65" not in text


def test_junie_spawn_dry_run_uses_project_task_contract(tmp_path: Path) -> None:
    launcher = _dry_run_launcher(tmp_path, "junie")
    text = launcher.read_text(encoding="utf-8")

    assert "SPAWN_AGENT=junie" in text
    assert "junie --project=" in text
    assert "--task=" in text
    assert "--skip-update-check" in text


def test_grok_spawn_dry_run_uses_prompt_file_contract(tmp_path: Path) -> None:
    launcher = _dry_run_launcher(tmp_path, "grok")
    text = launcher.read_text(encoding="utf-8")

    assert "SPAWN_AGENT=grok" in text
    assert "grok --cwd" in text
    assert "--permission-mode bypassPermissions" in text
    assert "--prompt-file" in text


def test_dry_run_meta_records_new_agents(tmp_path: Path) -> None:
    for agent in ("agy", "junie", "grok"):
        launcher = _dry_run_launcher(tmp_path / agent, agent)
        meta_line = next(
            line
            for line in launcher.read_text(encoding="utf-8").splitlines()
            if line.startswith("meta=")
        )
        meta_path = Path(meta_line.split("=", 1)[1].strip().strip("'\""))
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        assert payload["agent"] == agent
