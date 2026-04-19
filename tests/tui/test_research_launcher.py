from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"


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
