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
    assert "Founders' Framework" not in output
    assert 'vibecrafted decorate codex --prompt "Polish the release surface"' in output


def test_full_help_examples_keep_decorate_between_dou_and_hydrate(
    tmp_path: Path,
) -> None:
    output = _run_launcher_help(tmp_path, "help", "--full")

    assert "vibecrafted dou claude" in output
    assert "vibecrafted decorate codex" in output
    assert "vibecrafted hydrate codex" in output
