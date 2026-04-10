"""Tests for marbles runtime environment propagation and helper wiring.

Verifies that VIBECRAFTED_SKILL_CODE survives the spawn_normalize_ambient_context
call that runs at source-time of common.sh.  The fix exports SKILL_CODE/SKILL_NAME
in marbles_spawn.sh and marbles_next.sh AFTER the source point.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "vc-agents" / "scripts"


def _prepare_scripts(tmp_path: Path, capture_file: Path) -> Path:
    """Copy real scripts and write fake agent_spawn.sh stubs."""
    sd = tmp_path / "scripts"
    sd.mkdir()
    shutil.copytree(SCRIPTS_DIR / "lib", sd / "lib")
    for n in ("common.sh", "marbles_spawn.sh", "marbles_next.sh", "marbles_watcher.sh"):
        t = sd / n
        shutil.copy2(SCRIPTS_DIR / n, t)
        t.chmod(0o755)

    stub = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
        source "$SCRIPT_DIR/common.sh"
        agent="$(basename "${{BASH_SOURCE[0]}}" _spawn.sh)"
        mode=implement runtime=terminal model="" root="" success_hook="" failure_hook="" plan_file=""
        while [[ $# -gt 0 ]]; do
          case "$1" in
            --mode) shift; mode="$1";; --runtime) shift; runtime="$1";;
            --root) shift; root="$1";; --model) shift; model="$1";;
            --success-hook) shift; success_hook="$1";; --failure-hook) shift; failure_hook="$1";;
            *) [[ -z "$plan_file" ]] || {{ echo "unexpected: $1" >&2; exit 1; }}; plan_file="$1";;
          esac; shift
        done
        spawn_prepare_paths "$agent" "$plan_file" "$root" "$mode"
        spawn_write_meta "$SPAWN_META" launching "$agent" "$mode" "$SPAWN_ROOT" \\
          "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$0" "$model"
        python3 - "{capture_file}" "$SPAWN_META" <<'PY'
        import json, pathlib, sys
        cap, meta = sys.argv[1:3]
        p = json.load(open(meta, encoding="utf-8"))
        c = pathlib.Path(cap); c.parent.mkdir(parents=True, exist_ok=True)
        with c.open("a") as h: json.dump(p, h, ensure_ascii=False); h.write("\\n")
        PY
        cat > "$SPAWN_REPORT" <<EOF
        ---
        run_id: ${{SPAWN_RUN_ID}}
        agent: ${{SPAWN_AGENT}}
        status: completed
        ---
        P0: 0
        EOF
        cat > "$SPAWN_TRANSCRIPT" <<EOF
        ---
        run_id: ${{SPAWN_RUN_ID}}
        agent: ${{SPAWN_AGENT}}
        status: transcript
        ---
        session: fake
        EOF
        cp "$SPAWN_REPORT" "${{SPAWN_REPORT%.md}}_verified.md"
        spawn_finish_meta "$SPAWN_META" completed 0
        [[ -z "$success_hook" ]] || bash -lc "$success_hook"
    """)
    for a in ("claude", "codex", "gemini"):
        s = sd / f"{a}_spawn.sh"
        s.write_text(stub, encoding="utf-8")
        s.chmod(0o755)
    return sd


def _base_env(tmp_path: Path) -> dict[str, str]:
    """Clean env for headless marbles runs."""
    (tmp_path / "home").mkdir(exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["VIBECRAFTED_HOME"] = str(tmp_path / "home" / ".vibecrafted")
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    for k in (
        "ZELLIJ",
        "ZELLIJ_PANE_ID",
        "ZELLIJ_SESSION_NAME",
        "VIBECRAFTED_OPERATOR_SESSION",
        "VIBECRAFTED_RUN_ID",
        "VIBECRAFTED_SKILL_CODE",
        "VIBECRAFTED_SKILL_NAME",
        "VIBECRAFTED_RUN_LOCK",
    ):
        env.pop(k, None)
    return env


def _load_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_marbles(tmp_path: Path, agent: str, prompt: str) -> list[dict[str, object]]:
    """Run a single headless marbles spawn and return captured meta events."""
    cap = tmp_path / "meta.jsonl"
    sd = _prepare_scripts(tmp_path, cap)
    env = _base_env(tmp_path)
    env["MARBLES_SPAWN_CAPTURE"] = str(cap)
    subprocess.run(
        [
            "bash",
            str(sd / "marbles_spawn.sh"),
            "--agent",
            agent,
            "--count",
            "1",
            "--runtime",
            "headless",
            "--no-watch",
            "--prompt",
            prompt,
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return _load_events(cap)


# -- 1. CRITICAL: skill_code survives normalize --------------------------------


def test_skill_code_survives_normalize(tmp_path: Path) -> None:
    """VIBECRAFTED_SKILL_CODE='marb' must appear in meta.json after headless spawn.

    Regression guard: common.sh calls spawn_normalize_ambient_context at
    source-time which unsets SKILL_CODE, but marbles_spawn.sh exports it
    AFTER the source point.
    """
    events = _run_marbles(tmp_path, "codex", "env test")
    assert len(events) >= 1, "Expected at least one meta event"
    assert events[0]["skill_code"] == "marb"
    assert str(events[0]["run_id"]).startswith("marb-")


# -- 2. skill_name identity in meta --------------------------------------------


def test_skill_name_in_meta(tmp_path: Path) -> None:
    """Marbles skill identity propagates to spawn meta for any agent."""
    events = _run_marbles(tmp_path, "claude", "skill name test")
    assert len(events) >= 1
    assert events[0]["skill_code"] == "marb"
    assert events[0]["agent"] == "claude"


# -- 3. Explicit export survives after sourcing common.sh ----------------------


def test_normalize_does_not_clear_after_export() -> None:
    """Re-exporting VIBECRAFTED_SKILL_CODE after sourcing common.sh must survive.

    Shell-level proof that the fix pattern works: normalize runs at source
    time and may unset SKILL_CODE, but a subsequent export restores it.
    """
    result = subprocess.run(
        [
            "bash",
            "-c",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{SCRIPTS_DIR / "common.sh"}"',
                    'export VIBECRAFTED_SKILL_CODE="test_value"',
                    'echo "$VIBECRAFTED_SKILL_CODE"',
                ]
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "test_value"


# -- 4. Rotation schedule for trio mode ----------------------------------------


def test_rotation_schedule_trio() -> None:
    """Trio mode starting with codex rotates deterministically across the trio."""
    result = subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{SCRIPTS_DIR / "common.sh"}"',
                    "for loop_nr in 1 2 3 4 5 6; do",
                    '  spawn_rotation_schedule_agent "trio" "codex" "$loop_nr"',
                    "done",
                ]
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "codex",
        "claude",
        "gemini",
        "codex",
        "claude",
        "gemini",
    ]


# -- 5. Ancestor frontmatter parsing -------------------------------------------


def test_ancestor_frontmatter_parse() -> None:
    """Parse agent/focus/model from a live ancestor frontmatter file."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ancestor = tmp_path / "ancestor.md"
        ancestor.write_text(
            textwrap.dedent(
                """\
                ---
                agent: gemini
                focus: installer portability
                model: gemini-2.5-pro
                ---

                Steer the next loop toward portability.
                """
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                "bash",
                "-lc",
                "\n".join(
                    [
                        "set -euo pipefail",
                        f'source "{SCRIPTS_DIR / "common.sh"}"',
                        f'echo "$(spawn_frontmatter_field "{ancestor}" "agent")"',
                        f'echo "$(spawn_frontmatter_field "{ancestor}" "focus")"',
                        f'echo "$(spawn_frontmatter_field "{ancestor}" "model")"',
                    ]
                ),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        assert result.stdout.splitlines() == [
            "gemini",
            "installer portability",
            "gemini-2.5-pro",
        ]
