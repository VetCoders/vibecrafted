from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SH = REPO_ROOT / "runtime" / "scripts" / "common.sh"

_ENV_SANITIZE = """
unset ZELLIJ ZELLIJ_PANE_ID ZELLIJ_SESSION_NAME ZELLIJ_TAB_NAME ZELLIJ_CONFIG_DIR
unset VIBECRAFTED_OPERATOR_SESSION VIBECRAFTED_RUN_ID VIBECRAFTED_RUN_LOCK
unset VIBECRAFTED_SKILL_CODE VIBECRAFTED_SKILL_NAME VIBECRAFTED_LOOP_NR
unset VIBECRAFTED_PARENT_MODEL CLAUDE_MODEL CODEX_MODEL GEMINI_MODEL GROK_MODEL
unset SPAWN_LOOP_NR SPAWN_META SPAWN_TRANSCRIPT SPAWN_REPORT SPAWN_ROOT
unset SPAWN_RUN_ID SPAWN_RUN_LOCK SPAWN_AGENT SPAWN_SKILL_CODE SPAWN_SKILL_NAME
unset SPAWN_MODEL SPAWN_PROMPT_ID
"""


def _bash(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", _ENV_SANITIZE + script],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _write_meta(meta: Path, status: str) -> None:
    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_RUN_ID=lcyc-test-001
        spawn_write_meta "{meta}" "{status}" claude implement / plan.md report.md t.log l.sh
        '''
    )


def _load(meta: Path) -> dict:
    return json.loads(meta.read_text(encoding="utf-8"))


def test_mark_meta_running_flips_launching_to_running(tmp_path: Path) -> None:
    meta = tmp_path / "run.meta.json"
    _write_meta(meta, "launching")
    before = _load(meta)

    _bash(f'source "{COMMON_SH}"; spawn_mark_meta_running "{meta}"')

    after = _load(meta)
    assert after["status"] == "running"
    assert after["run_id"] == before["run_id"]
    assert after["created_at"] == before["created_at"]
    assert after["report"] == before["report"]


def test_mark_meta_running_never_resurrects_terminal_states(tmp_path: Path) -> None:
    meta = tmp_path / "run.meta.json"
    _write_meta(meta, "launching")
    _bash(f'source "{COMMON_SH}"; spawn_finish_meta "{meta}" completed 0')

    _bash(f'source "{COMMON_SH}"; spawn_mark_meta_running "{meta}"')

    assert _load(meta)["status"] == "completed"


def test_finish_meta_delegates_to_python_terminal_writer(tmp_path: Path) -> None:
    meta = tmp_path / "run.meta.json"
    transcript = tmp_path / "transcript.log"
    _write_meta(meta, "running")
    transcript.write_text("[12:10:00] session: shell-finish-001\n", encoding="utf-8")
    payload = _load(meta)
    payload["transcript"] = str(transcript)
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    _bash(f'source "{COMMON_SH}"; spawn_finish_meta "{meta}" failed 9')

    final = _load(meta)
    assert final["status"] == "failed"
    assert final["exit_code"] == 9
    assert final["liveness"] == "terminal"
    assert final["session_id"] == "shell-finish-001"
    assert isinstance(final["duration_s"], (int, float))


def test_finalize_artifacts_persists_model_and_duration(tmp_path: Path) -> None:
    meta = tmp_path / "run.meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "transcript.log"
    report.write_text("# Report\n\nDone.\n", encoding="utf-8")
    transcript.write_text(
        "[12:40:43] session: telemetry-session-001\n", encoding="utf-8"
    )

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_RUN_ID=lcyc-test-001
        export CODEX_MODEL=gpt-5.3-codex
        spawn_write_meta "{meta}" launching codex implement "{tmp_path}" plan.md "{report}" "{transcript}" l.sh
        spawn_finish_meta "{meta}" completed 0
        python3 - "{meta}" <<'PY'
import json
import sys
path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)
payload["model"] = "unknown"
payload["duration_s"] = None
payload["created_at"] = "2026-06-10T08:00:00+00:00"
payload["completed_at"] = "2026-06-10T08:00:05+00:00"
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\\n")
PY
        spawn_finalize_artifacts "{meta}" "{report}" "{transcript}"
        '''
    )

    final = _load(meta)
    assert final["model"] == "gpt-5.3-codex"
    assert final["duration_s"] == 5.0
    assert final["run_id"] == "lcyc-test-001"
    assert final["status"] == "completed"
    assert final["session_id"] == "telemetry-session-001"


def test_generated_launcher_walks_full_lifecycle(tmp_path: Path) -> None:
    # Plan verifier (VC-vbcr-stabilize-031): a trivial run must pass through
    # "running" while the agent command executes and land on a terminal state.
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "run.meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "transcript.log"

    _write_meta(meta, "launching")
    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_AGENT=claude
        export SPAWN_RUN_ID=lcyc-test-001
        spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "sleep 2"
        chmod +x "{launcher}"
        '''
    )

    proc = subprocess.Popen(
        ["bash", str(launcher)],
        cwd=REPO_ROOT,
        env={
            "PATH": "/usr/bin:/bin",
            "VIBECRAFTED_INLINE_STARTUP_WATCH": "0",
            "HOME": str(tmp_path),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        seen_running = False
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status = _load(meta).get("status")
            if status == "running":
                seen_running = True
                break
            if status in {"completed", "failed"}:
                break
            time.sleep(0.1)
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()

    assert seen_running, "meta.json never reported status=running mid-run"
    final = _load(meta)
    assert final["status"] == "completed"
    assert final["exit_code"] == 0
    assert final["liveness"] == "terminal"
    assert final["model"] == "claude-cli-default"
    assert isinstance(final["duration_s"], (int, float))
