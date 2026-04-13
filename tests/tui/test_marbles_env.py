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


def _run_prepare_paths_probe(
    tmp_path: Path,
    *,
    requested_root: Path,
    ambient_spawn_root: Path | None = None,
    store_dir: Path | None = None,
    store_root: Path | None = None,
) -> dict[str, str]:
    requested_root.mkdir(parents=True, exist_ok=True)
    plan = requested_root / "plan.md"
    plan.write_text("# Probe plan\n", encoding="utf-8")

    env = _base_env(tmp_path)
    if ambient_spawn_root is not None:
        env["SPAWN_ROOT"] = str(ambient_spawn_root)
    if store_dir is not None:
        env["VIBECRAFTED_STORE_DIR"] = str(store_dir)
    if store_root is not None:
        env["VIBECRAFTED_STORE_ROOT"] = str(store_root)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{SCRIPTS_DIR / "common.sh"}"',
                    f'spawn_prepare_paths codex "{plan}" "{requested_root}" implement',
                    'printf "SPAWN_ROOT=%s\\n" "$SPAWN_ROOT"',
                    'printf "SPAWN_REPORT_DIR=%s\\n" "$SPAWN_REPORT_DIR"',
                    'printf "SPAWN_REPORT=%s\\n" "$SPAWN_REPORT"',
                ]
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    payload: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key] = value
    return payload


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


def test_normalize_clears_loop_nr_with_stale_run_context(tmp_path: Path) -> None:
    home = tmp_path / "home"
    lock_dir = home / ".vibecrafted" / "locks" / "wrong-repo"
    lock_dir.mkdir(parents=True)
    stale_lock = lock_dir / "marb-123456-001.lock"
    stale_lock.write_text("run_id=marb-123456-001\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_RUN_ID"] = "marb-123456-001"
    env["VIBECRAFTED_RUN_LOCK"] = str(stale_lock)
    env["VIBECRAFTED_SKILL_CODE"] = "marb"
    env["VIBECRAFTED_SKILL_NAME"] = "marbles"
    env["VIBECRAFTED_LOOP_NR"] = "7"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{SCRIPTS_DIR / "common.sh"}"',
                    "spawn_normalize_ambient_context",
                    'printf "RUN_ID=%s\\n" "${VIBECRAFTED_RUN_ID:-}"',
                    'printf "LOOP_NR=%s\\n" "${VIBECRAFTED_LOOP_NR:-}"',
                ]
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "RUN_ID=" in result.stdout
    assert "LOOP_NR=" in result.stdout
    assert "RUN_ID=marb-123456-001" not in result.stdout
    assert "LOOP_NR=7" not in result.stdout


# -- 4. Store isolation across nested spawns -----------------------------------


def test_prepare_paths_ignores_inherited_store_dir_from_other_root(
    tmp_path: Path,
) -> None:
    ambient_root = tmp_path / "ambient-root"
    requested_root = tmp_path / "target-root"
    leaked_store = ambient_root / ".vibecrafted" / "marbles"
    leaked_store.mkdir(parents=True, exist_ok=True)

    payload = _run_prepare_paths_probe(
        tmp_path,
        requested_root=requested_root,
        ambient_spawn_root=ambient_root,
        store_dir=leaked_store,
    )

    assert payload["SPAWN_ROOT"] == str(requested_root)
    assert payload["SPAWN_REPORT_DIR"] == str(
        requested_root / ".vibecrafted" / "reports"
    )
    assert payload["SPAWN_REPORT"].startswith(
        str(requested_root / ".vibecrafted" / "reports")
    )
    assert str(leaked_store) not in payload["SPAWN_REPORT_DIR"]


def test_prepare_paths_honors_store_dir_when_store_root_matches_requested_root(
    tmp_path: Path,
) -> None:
    ambient_root = tmp_path / "ambient-root"
    requested_root = tmp_path / "target-root"
    marbles_store = requested_root / ".vibecrafted" / "marbles"

    payload = _run_prepare_paths_probe(
        tmp_path,
        requested_root=requested_root,
        ambient_spawn_root=ambient_root,
        store_dir=marbles_store,
        store_root=requested_root,
    )

    assert payload["SPAWN_ROOT"] == str(requested_root)
    assert payload["SPAWN_REPORT_DIR"] == str(marbles_store / "reports")
    assert payload["SPAWN_REPORT"].startswith(str(marbles_store / "reports"))


def test_prepare_paths_ignores_bare_store_dir_without_matching_root(
    tmp_path: Path,
) -> None:
    requested_root = tmp_path / "target-root"
    leaked_store = tmp_path / "ambient-root" / ".vibecrafted" / "marbles"
    leaked_store.mkdir(parents=True, exist_ok=True)

    payload = _run_prepare_paths_probe(
        tmp_path,
        requested_root=requested_root,
        store_dir=leaked_store,
    )

    assert payload["SPAWN_ROOT"] == str(requested_root)
    assert payload["SPAWN_REPORT_DIR"] == str(
        requested_root / ".vibecrafted" / "reports"
    )
    assert payload["SPAWN_REPORT"].startswith(
        str(requested_root / ".vibecrafted" / "reports")
    )
    assert str(leaked_store) not in payload["SPAWN_REPORT_DIR"]


# -- 5. Rotation schedule for trio mode ----------------------------------------


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


def test_rotation_schedule_trio_respects_seed_agent() -> None:
    """Trio mode keeps the requested seed agent at the front of the cycle."""
    result = subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{SCRIPTS_DIR / "common.sh"}"',
                    "for loop_nr in 1 2 3 4; do",
                    '  spawn_rotation_schedule_agent "trio" "gemini" "$loop_nr"',
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
