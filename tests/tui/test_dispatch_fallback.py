from __future__ import annotations

import os
import shutil
import stat
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


def _stub_deck(bin_dir: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    deck = bin_dir / "vibecrafted"
    deck.write_text('#!/usr/bin/env bash\necho "deck:$*"\nexit 0\n', encoding="utf-8")
    deck.chmod(deck.stat().st_mode | stat.S_IEXEC)
    return deck


def _run_shell(
    shell: str, script: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shell, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _fallback_env(bin_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    deck = bin_dir / "vibecrafted"
    # Never let a fallback test discover the operator's live launcher.
    env["VIBECRAFTED_DECK_BIN"] = str(deck) if deck.is_file() else ""
    return env


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_vc_wrapper_falls_back_to_deck_when_wrapper_missing(
    shell: str, tmp_path: Path
) -> None:
    # Simulates the measured headless failure (exit 127): vc-* function exists
    # but _vetcoders_skill_wrapper does not (version skew / partial load).
    # The wrapper must degrade to the standalone deck instead of dying.
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} not available")
    bin_dir = tmp_path / "bin"
    _stub_deck(bin_dir)
    script = (
        f'source "{DISPATCH}" 2>/dev/null || true; '
        "unset -f _vetcoders_skill_wrapper 2>/dev/null; "
        "vc-justdo codex --prompt hi"
    )
    result = _run_shell(shell, script, _fallback_env(bin_dir))
    assert result.returncode == 0, result.stderr
    # ADR-0001: justdo is its own skill id — the deck receives "justdo"
    # verbatim, never the old implement alias.
    assert "deck:justdo codex --prompt hi" in result.stdout


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_vc_wrapper_reports_cleanly_when_no_deck_available(
    shell: str, tmp_path: Path
) -> None:
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} not available")
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    script = (
        f'source "{DISPATCH}" 2>/dev/null || true; '
        "unset -f _vetcoders_skill_wrapper 2>/dev/null; "
        "vc-justdo codex --prompt hi"
    )
    result = _run_shell(shell, script, _fallback_env(empty_bin))
    assert result.returncode == 127
    assert "helper layer is not loaded" in result.stderr


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_test_mode_never_discovers_the_operator_deck(
    shell: str, tmp_path: Path
) -> None:
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} not available")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    live_deck = bin_dir / "vibecrafted"
    live_deck.write_text(
        "#!/bin/sh\nprintf 'unsafe-live-deck\\n'\n",
        encoding="utf-8",
    )
    live_deck.chmod(live_deck.stat().st_mode | stat.S_IEXEC)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["VIBECRAFTED_TEST_MODE"] = "1"
    env.pop("VIBECRAFTED_DECK_BIN", None)
    script = (
        f'source "{DISPATCH}" 2>/dev/null || true; '
        "unset -f _vetcoders_skill_wrapper 2>/dev/null; "
        "vc-justdo codex --prompt hi"
    )

    result = _run_shell(shell, script, env)

    assert result.returncode == 127
    assert "unsafe-live-deck" not in result.stdout
    assert "helper layer is not loaded" in result.stderr


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_vc_justdo_symlink_help_works_headless(shell: str, tmp_path: Path) -> None:
    # Plan verifier (VC-vbcr-stabilize-030): non-interactive `vc-justdo --help`
    # through the installed-style symlink must exit 0 with sensible output.
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} not available")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "vc-justdo").symlink_to(REPO_ROOT / "scripts" / "vibecrafted")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["HOME"] = str(tmp_path / "home")
    result = _run_shell(shell, "vc-justdo --help", env)
    assert result.returncode == 0, result.stderr
    assert "implement" in result.stdout
