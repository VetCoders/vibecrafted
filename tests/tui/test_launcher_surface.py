from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _run_launcher_help(tmp_path: Path, *args: str) -> str:
    home = tmp_path / "home"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")

    result = subprocess.run(
        ["bash", "scripts/vibecrafted", *args],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return ANSI_RE.sub("", result.stdout)


def test_compact_help_uses_release_engine_contract(tmp_path: Path) -> None:
    output = _run_launcher_help(tmp_path, "help")

    assert "Release engine for AI-built software." in output
    assert "Ship AI-built software without the vibe hangover." in output
    assert "Skill inventory (18 live skills + 1 compatibility alias):" in output
    assert "Core: init · scaffold · workflow · implement" in output
    assert "Compatibility: justdo is a legacy alias for implement" in output
    assert 'vibecrafted implement codex --prompt "Ship <task>"' in output
    assert 'vibecrafted justdo codex --prompt "Ship <task>"' not in output
    assert "Founders' Framework" not in output
    assert 'vibecrafted implement codex --prompt "Ship the feature"' in output
    assert 'vibecrafted justdo codex --prompt "Ship the feature"' not in output
    assert 'vibecrafted decorate codex --prompt "Polish the release surface"' in output


def test_full_help_examples_keep_decorate_between_dou_and_hydrate(
    tmp_path: Path,
) -> None:
    output = _run_launcher_help(tmp_path, "help", "--full")

    assert "vibecrafted dou claude" in output
    assert "vibecrafted decorate codex" in output
    assert "vibecrafted hydrate codex" in output
    assert "justdo = legacy alias for implement" in output


def test_implement_help_is_canonical_and_names_legacy_alias(tmp_path: Path) -> None:
    output = _run_launcher_help(tmp_path, "implement", "--help")

    assert (
        "Autonomous end-to-end implementation with followup and marbles built in."
        in output
    )
    assert "vibecrafted implement <claude|codex|gemini> [flags]" in output
    assert "vc-implement <claude|codex|gemini> [flags]" in output
    assert "Legacy alias: vibecrafted justdo <claude|codex|gemini> [flags]" in output
    assert 'vibecrafted implement codex --prompt "Ship the feature"' in output


def test_review_and_followup_help_stay_semantically_separate(tmp_path: Path) -> None:
    review = _run_launcher_help(tmp_path, "review", "--help")
    followup = _run_launcher_help(tmp_path, "followup", "--help")

    assert "Bounded PR, branch, commit-range, or artifact-pack review" in review
    assert 'vibecrafted review codex --prompt "Review PR #14"' in review
    assert "Post-implementation direction audit" in followup
    assert (
        'vibecrafted followup codex --prompt "Audit post-implementation direction"'
        in followup
    )


def test_docs_skill_index_locks_command_semantics() -> None:
    skills = (REPO_ROOT / "docs" / "SKILLS.md").read_text(encoding="utf-8")
    workflows = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")

    assert (
        "`vc-implement` / `vibecrafted implement` is the official autonomous delivery"
        in skills
    )
    assert "`vc-justdo`" in skills
    assert "`justdo`    | `vibecrafted implement`" in skills
    assert (
        "Findings-first review over a bounded PR, branch, commit range, or artifact pack."
        in skills
    )
    assert "Post-implementation direction audit" in skills
    assert "`justdo` command and `vc-justdo` helper remain legacy aliases" in workflows
