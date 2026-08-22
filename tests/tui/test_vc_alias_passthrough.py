"""Structural + zsh gates for public vc-* thin aliases.

Proves the shipped shell sources (not a reimplementation) define mappable
vc-* entrypoints as pass-throughs to `command vibecrafted <verb>`, and that
interactive zsh --help does not invent resume/work launches.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

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
    # start/dashboard MUST implement launch locally (no full-verb passthrough
    # re-entry: Python→deck→helper→Python fork-bombs).
    assert "_vetcoders_launch_dashboard" in text
    assert not re.search(r"vc-start\(\)\s*\{\s*_vetcoders_vc_passthrough start", text)
    assert not re.search(
        r"vc-dashboard\(\)\s*\{\s*_vetcoders_vc_passthrough dashboard", text
    )
    start_body = text.split("vc-start()")[1].split("vc-frontier-paths")[0]
    # Only --help may call into the deck; bare start must launch dashboard.
    # The help touch goes through the guarded passthrough so DECK_BIN/test-mode
    # resolution holds even here — never a bare `command vibecrafted`.
    assert "_vetcoders_launch_dashboard operator" in start_body
    assert "_vetcoders_vc_passthrough start --help" in start_body
    assert re.search(r"command vibecrafted start\s+\"\$@\"", start_body) is None
    assert re.search(r"_vetcoders_vc_passthrough start\s+\"\$@\"", start_body) is None


def test_resume_is_local_helper_not_deck_reentry() -> None:
    """vc-resume must call _vetcoders_resume_agent, not re-enter the deck."""
    text = MARBLES.read_text(encoding="utf-8")
    body = text.split("vc-resume()")[1].split("codex-marbles")[0]
    assert "_vetcoders_resume_agent" in body
    # Help-only deck touch is OK; full-arg passthrough is the fork bomb.
    assert "command vibecrafted resume --help" in body
    assert re.search(r"command vibecrafted resume\s+\"\$@\"", body) is None


def test_vc_alias_matrix_script_exists_and_is_executable_gate() -> None:
    assert MATRIX.is_file()
    body = MATRIX.read_text(encoding="utf-8")
    assert "zsh -ic" in body
    assert "vc-research" in body or "research" in body
    assert "MAPPABLE" in body
    assert "STANDALONE" in body


def test_sync_script_covers_both_deck_paths() -> None:
    """Install sync must project the packaged owner to both launcher paths."""
    script = REPO_ROOT / "scripts" / "sync-vc-alias-runtime.sh"
    assert script.is_file()
    body = script.read_text(encoding="utf-8")
    assert (
        'CANONICAL_DECK="$ROOT/vibecrafted-core/vibecrafted_core/deck/vibecrafted"'
        in body
    )
    assert 'CHECKOUT_MIRROR="$ROOT/scripts/vibecrafted"' in body
    assert 'cp -f "$CANONICAL_DECK" "$CHECKOUT_MIRROR"' in body
    assert 'cp -f "$CHECKOUT_MIRROR" "$CANONICAL_DECK"' not in body
    assert 'copy_one "$CANONICAL_DECK" "$GEN/scripts/vibecrafted"' in body
    assert "runtime/shell/lib/dispatch.sh" in body
    assert "runtime/shell/lib/marbles.sh" in body


def test_interactive_zsh_resume_help_does_not_create_runs(tmp_path: Path) -> None:
    """Real user path: zsh -ic 'vc-resume --help' must not mint control-plane runs."""
    if shutil.which("zsh") is None:
        # The test provisions its own HOME/ZDOTDIR/control plane, but it cannot
        # provision the shell itself. Missing zsh used to surface as a raw
        # FileNotFoundError, which reads like a product failure on a
        # contributor box that simply has no zsh. In CI it stays a hard
        # failure: every job that runs this suite installs zsh on purpose
        # (portable.yml) or ships it (macOS), so a missing binary there means
        # the image regressed and the coverage silently vanished — exactly the
        # green-washing this repo refuses.
        if os.environ.get("CI"):
            pytest.fail("zsh is missing from a CI image that must provide it")
        pytest.skip("zsh is not installed on this host")
    home = tmp_path / "home"
    home.mkdir()
    vibecrafted_home = home / ".vibecrafted"
    control_plane = vibecrafted_home / "control_plane"
    # Both halves of the control plane, not just the projection: the runtime
    # WRITES a minted run to runtime_runs/<id>/ (resolve_run probes it first
    # and calls artifacts/ the legacy location), while runs/<id>.json is the
    # projected snapshot. Watching only runs/ can pass while --help mints a run
    # the runtime can see — a green gate over the exact bug it exists to catch.
    runs_dir = control_plane / "runs"
    runtime_runs_dir = control_plane / "runtime_runs"
    runs_dir.mkdir(parents=True)
    runtime_runs_dir.mkdir(parents=True)

    def minted() -> set[str]:
        return {
            f"{directory.name}/{entry.name}"
            for directory in (runs_dir, runtime_runs_dir)
            for entry in directory.iterdir()
        }

    shell_entry = (
        REPO_ROOT
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "runtime"
        / "shell"
        / "vetcoders.zsh"
    )
    (home / ".zshrc").write_text(
        f'export PATH="{REPO_ROOT / "scripts"}:$PATH"\nsource "{shell_entry}"\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "ZDOTDIR": str(home),
            "VIBECRAFTED_HOME": str(vibecrafted_home),
            "VIBECRAFTED_ROOT": str(REPO_ROOT),
        }
    )
    before = minted()
    result = subprocess.run(
        ["zsh", "-ic", "vc-resume --help"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    after = minted()
    assert result.returncode == 0, result.stderr
    assert "Resume" in result.stdout or "resume" in result.stdout
    assert before == after, f"new runs from --help: {after - before}"
