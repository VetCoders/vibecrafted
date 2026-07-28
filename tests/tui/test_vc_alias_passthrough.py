"""Structural + zsh gates for public vc-* thin aliases.

Proves the shipped shell sources (not a reimplementation) define mappable
vc-* entrypoints as pass-throughs to `command vibecrafted <verb>`, and that
interactive zsh --help does not invent resume/work launches.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCH = (
    REPO_ROOT
    / "vibecrafted-core"
    / "vibecrafted_core"
    / "runtime"
    / "shell"
    / "lib"
    / "dispatch.sh"
)
MARBLES = (
    REPO_ROOT
    / "vibecrafted-core"
    / "vibecrafted_core"
    / "runtime"
    / "shell"
    / "lib"
    / "marbles.sh"
)
MATRIX = REPO_ROOT / "tests" / "shell" / "vc_alias_matrix.sh"


def test_dispatch_defines_passthrough_helper() -> None:
    text = DISPATCH.read_text(encoding="utf-8")
    assert "_vetcoders_vc_passthrough()" in text
    assert "command vibecrafted" in text
    # justdo must not route to implement (ADR-0001 split-brain)
    assert re.search(
        r"vc-justdo\(\)\s*\{\s*_vetcoders_vc_passthrough justdo",
        text,
    )
    assert "vc-justdo() { _vetcoders_command_dispatch justdo implement" not in text
    # research must not call legacy _vetcoders_research
    assert re.search(
        r"vc-research\(\)\s*\{\s*_vetcoders_vc_passthrough research",
        text,
    )
    assert "vc-research() { _vetcoders_research" not in text
    # start/dashboard/help are deck verbs, not raw vc-frame help
    assert re.search(r"vc-start\(\)\s*\{\s*_vetcoders_vc_passthrough start", text)
    assert re.search(
        r"vc-dashboard\(\)\s*\{\s*_vetcoders_vc_passthrough dashboard", text
    )


def test_resume_is_deck_passthrough_not_parser() -> None:
    text = MARBLES.read_text(encoding="utf-8")
    assert "command vibecrafted resume" in text
    # Old side-effecting body must not remain as the public entrypoint.
    assert (
        "_vetcoders_resume_agent"
        not in text.split("vc-resume()")[1].split("codex-marbles")[0]
    )


def test_vc_alias_matrix_script_exists_and_is_executable_gate() -> None:
    assert MATRIX.is_file()
    body = MATRIX.read_text(encoding="utf-8")
    assert "zsh -ic" in body
    assert "vc-research" in body or "research" in body
    assert "MAPPABLE" in body
    assert "STANDALONE" in body


def test_sync_script_covers_both_deck_paths() -> None:
    """Install sync must copy scripts/vibecrafted AND packaged deck twin."""
    script = REPO_ROOT / "scripts" / "sync-vc-alias-runtime.sh"
    assert script.is_file()
    body = script.read_text(encoding="utf-8")
    assert "scripts/vibecrafted" in body
    assert "vibecrafted_core/deck/vibecrafted" in body
    assert "runtime/shell/lib/dispatch.sh" in body
    assert "runtime/shell/lib/marbles.sh" in body


def test_interactive_zsh_resume_help_does_not_create_runs(tmp_path: Path) -> None:
    """Real user path: zsh -ic 'vc-resume --help' must not mint control-plane runs."""
    runs_dir = Path.home() / ".vibecrafted" / "control_plane" / "runs"
    if not runs_dir.is_dir():
        # No control plane in this environment — structural tests still hold.
        return
    before = {p.name for p in runs_dir.iterdir()}
    result = subprocess.run(
        ["zsh", "-ic", "vc-resume --help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    after = {p.name for p in runs_dir.iterdir()}
    assert result.returncode == 0, result.stderr
    assert "Resume" in result.stdout or "resume" in result.stdout
    assert before == after, f"new runs from --help: {after - before}"
