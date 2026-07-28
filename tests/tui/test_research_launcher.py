"""Public vc-research / vibecrafted research surface tests.

These assert the **deck/Python** contract after interactive zsh pass-through
(`vc-research` → `command vibecrafted research`). Legacy shell swarm layout
(`rsch-*` run dirs, `Research override (…) prepared`, uno|duo|trio keywords)
is intentionally not required on the public entrypoint.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"


def _env(tmp_path: Path, *, crafted_home: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    home = crafted_home or (tmp_path / "home" / ".vibecrafted")
    home.mkdir(parents=True, exist_ok=True)
    env["VIBECRAFTED_HOME"] = str(home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    # Prefer headless / no terminal transport in CI.
    env.pop("VIBECRAFTED_FORCE_TERMINAL", None)
    return env


def _run_vc_research(
    root: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    """Invoke public shell entry after loading repo helpers (zsh/bash function)."""
    quoted = " ".join(f'"{a}"' if " " in a else a for a in args)
    return subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; vc-research {quoted}',
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_deck_research(
    root: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["command", "vibecrafted", "research", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_receipt(stdout: str) -> dict[str, str]:
    """Extract fields from VIBECRAFTED LAUNCH RECEIPT or JSON --json body."""
    out = stdout.strip()
    # Prefer human receipt lines (always present on terminal launch).
    m = re.search(r"run_id:\s+(\S+)", out)
    if m:
        return {"run_id": m.group(1), "status": "launching", "raw": out}
    # JSON body may be first object line or the whole stdout.
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "run_id" in payload:
            return {
                "run_id": str(payload["run_id"]),
                "status": str(payload.get("status") or ""),
                "raw": out,
            }
        if payload.get("accepted") and "command" in payload:
            cmd = payload["command"]
            rid = ""
            for i, part in enumerate(cmd):
                if part == "--run-id" and i + 1 < len(cmd):
                    rid = str(cmd[i + 1])
                    break
            if rid:
                return {"run_id": rid, "status": "launching", "raw": out}
    # Fallback: rese-/rsch- token anywhere
    m2 = re.search(r"\b((?:rese|rsch)-[0-9a-zA-Z-]+)\b", out)
    assert m2 is not None, out
    return {"run_id": m2.group(1), "status": "launching", "raw": out}


def test_vc_research_help_is_pure_help() -> None:
    """Public vc-research --help must match the deck (not legacy shell help)."""
    result = subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-research --help'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    deck = subprocess.run(
        ["bash", "-lc", "command vibecrafted research --help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert deck.returncode == 0
    for token in (
        "--json",
        "--model",
        "--prompt-stdin",
        "--synthesizer-model",
        "vibecrafted research",
    ):
        assert token in result.stdout, f"missing canonical token {token!r}"
        assert token in deck.stdout, f"deck missing {token!r}"
    assert "Research swarm launched" not in result.stdout
    assert "command not found" not in result.stdout
    assert "command not found" not in result.stderr
    # Legacy shell-only help strings must not reappear (split-brain).
    assert "Configurable triple-agent research swarm launcher" not in result.stdout


def test_vc_research_shell_matches_deck_help_text() -> None:
    shell = subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-research --help'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    deck = subprocess.run(
        ["bash", "-lc", "command vibecrafted research --help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert shell.returncode == 0 and deck.returncode == 0
    # Same product surface — flags present on both (not byte-identical due to wrappers).
    for tok in (
        "--json",
        "--model",
        "--prompt-stdin",
        "--synthesizer-model",
        "--runtime",
    ):
        assert tok in shell.stdout
        assert tok in deck.stdout


def test_vc_research_launch_emits_control_plane_receipt(tmp_path: Path) -> None:
    """Sourced vc-research launches via core receipt (rese-*), not legacy rsch layout."""
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    env = _env(tmp_path, crafted_home=crafted_home)

    result = _run_vc_research(
        root,
        env,
        "codex",
        "--runtime",
        "headless",
        "--root",
        str(root),
        "--prompt",
        "Check auth providers",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    combined = result.stdout + result.stderr
    assert "LAUNCH RECEIPT" in combined or '"accepted": true' in combined
    receipt = _parse_receipt(combined if "run_id" in combined else result.stdout)
    run_id = receipt["run_id"]
    assert run_id.startswith(("rese-", "rsch-")), run_id
    # Durable launch artifacts under VIBECRAFTED_HOME (control JSON may lag;
    # prompt + launch log are written at accept time).
    runtime = crafted_home / "control_plane" / "runtime_runs" / run_id
    assert (runtime / "prompt.md").is_file(), f"missing prompt at {runtime}"
    launch_logs = list((crafted_home / "control_plane" / "launches").glob("*research*"))
    assert launch_logs, "expected a research launch log under control_plane/launches"
    assert "Research override (codex) prepared" not in result.stdout


def test_vc_research_and_deck_launch_same_skill(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    env = _env(tmp_path)

    shell = _run_vc_research(
        root,
        env,
        "--runtime",
        "headless",
        "--root",
        str(root),
        "--prompt",
        "parity probe",
        "--json",
    )
    # Second launch under same env should still accept.
    deck = _run_deck_research(
        root,
        env,
        "--runtime",
        "headless",
        "--root",
        str(root),
        "--prompt",
        "parity probe deck",
        "--json",
    )
    assert shell.returncode == 0, shell.stdout + shell.stderr
    assert deck.returncode == 0, deck.stdout + deck.stderr
    for out in (shell.stdout + shell.stderr, deck.stdout + deck.stderr):
        assert "rese-" in out or "accepted" in out


def test_vc_research_unsupported_agent_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    env = _env(tmp_path)

    result = _run_vc_research(
        root,
        env,
        "not-an-agent",
        "--runtime",
        "headless",
        "--root",
        str(root),
        "--prompt",
        "must not launch",
    )

    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "unsupported" in combined or "unknown" in combined or "error" in combined
    # No successful receipt for a bogus agent-only invocation without work flags.
    assert "status:     launching" not in result.stdout or "error" in combined


def test_vc_research_requires_prompt_or_file(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    env = _env(tmp_path)

    result = _run_vc_research(
        root,
        env,
        "codex",
        "--runtime",
        "headless",
        "--root",
        str(root),
    )
    # Deck refuses empty work (no -p/-f).
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert (
        "prompt" in combined.lower()
        or "file" in combined.lower()
        or "provide work" in combined.lower()
        or "error" in combined.lower()
    )


def test_vc_research_file_plan_launches(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    plan = tmp_path / "research-plan.md"
    plan.write_text(
        textwrap.dedent(
            """\
            # Research Plan: Prompt Hygiene

            ## Questions
            1. Which prompt content reaches the worker?
            """
        ),
        encoding="utf-8",
    )
    env = _env(tmp_path, crafted_home=crafted_home)

    result = _run_vc_research(
        root,
        env,
        "--runtime",
        "headless",
        "--root",
        str(root),
        "--file",
        str(plan),
        "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = _parse_receipt(result.stdout + result.stderr)
    assert receipt["run_id"]
    runtime = crafted_home / "control_plane" / "runtime_runs" / receipt["run_id"]
    assert (runtime / "prompt.md").is_file()


def test_legacy_shell_research_helper_still_exists_for_internal_use() -> None:
    """Internal _vetcoders_research may remain for non-public paths; public entry must not call it."""
    dispatch = (
        REPO_ROOT
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "runtime"
        / "shell"
        / "lib"
        / "dispatch.sh"
    )
    text = dispatch.read_text(encoding="utf-8")
    assert "vc-research() { _vetcoders_research" not in text
    assert "_vetcoders_vc_passthrough research" in text
    research_sh = (
        REPO_ROOT
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "runtime"
        / "vc-research"
        / "shell"
        / "research.sh"
    )
    # Legacy helper may still exist for internal/compat scripts.
    assert research_sh.is_file()
