from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SH = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "common.sh"
CODEX_SPAWN_SH = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "codex_spawn.sh"
CODEX_STREAM_FILTER = (
    REPO_ROOT / "skills" / "vc-agents" / "scripts" / "codex_stream_filter.jq"
)


def _bash(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", script],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def _split_zellij_calls(payload: str) -> list[list[str]]:
    calls: list[list[str]] = []
    current: list[str] = []
    for line in payload.splitlines():
        if line == "--CALL--":
            if current:
                calls.append(current)
                current = []
            continue
        current.append(line)
    if current:
        calls.append(current)
    return calls


def test_runtime_prompt_guards_report_path_from_bare_slash(tmp_path: Path) -> None:
    source_file = tmp_path / "source.md"
    runtime_file = tmp_path / "runtime.md"
    report_path = tmp_path / "report.md"
    source_file.write_text("# Prompt\n", encoding="utf-8")

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_PROMPT_ID="prompt-123"
        spawn_build_runtime_prompt "{source_file}" "{runtime_file}" "{report_path}" claude
        '''
    )

    payload = runtime_file.read_text(encoding="utf-8")
    assert f"Report path: {report_path}" in payload
    assert f"\n{report_path}\n" not in payload


def test_generated_launcher_runs_from_spawn_root(tmp_path: Path) -> None:
    root_dir = tmp_path / "project"
    root_dir.mkdir()
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.txt"
    transcript = tmp_path / "trace.log"

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{root_dir}"
        export SPAWN_AGENT="claude"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_LOOP_NR="2"
        export SPAWN_SKILL_CODE="marb"
        cmd='pwd > "{report}"'
        spawn_write_meta "{meta}" "launching" "claude" "marbles" "{root_dir}" "{launcher}" "{report}" "{transcript}" "{launcher}"
        spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd"
        chmod +x "{launcher}"
        bash "{launcher}"
        '''
    )

    assert report.read_text(encoding="utf-8").strip() == str(root_dir)


def test_spawn_watch_startup_reports_pass_and_dashboard_hint(tmp_path: Path) -> None:
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "trace.log"

    result = _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_AGENT="codex"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_SKILL_CODE="impl"
        spawn_write_meta "{meta}" "launching" "codex" "implement" "{tmp_path}" "{tmp_path / "plan.md"}" "{report}" "{transcript}" "{tmp_path / "launcher.sh"}"
        spawn_write_frontmatter "{transcript}" "codex" "unknown" "transcript"
        (
          sleep 0.2
          printf '[12:40:43] session: 54865595-899c-4402-b957-911433e46199\\nWorking...\\n' >> "{transcript}"
        ) &
        spawn_watch_startup "{meta}" "{transcript}" "{report}" 1
        '''
    )

    assert "Startup check: passed in the first 1s." in result.stdout
    assert "vibecrafted dashboard" in result.stdout


def test_spawn_watch_startup_reports_failure_and_dashboard_hint(tmp_path: Path) -> None:
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "trace.log"

    result = _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_AGENT="claude"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_SKILL_CODE="impl"
        spawn_write_meta "{meta}" "launching" "claude" "implement" "{tmp_path}" "{tmp_path / "plan.md"}" "{report}" "{transcript}" "{tmp_path / "launcher.sh"}"
        spawn_write_frontmatter "{transcript}" "claude" "unknown" "transcript"
        (
          sleep 0.2
          printf 'Not logged in · Please run /login\\n' >> "{transcript}"
          spawn_finish_meta "{meta}" "failed" "1"
        ) &
        spawn_watch_startup "{meta}" "{transcript}" "{report}" 1
        '''
    )

    assert "Startup check: failed in the first 1s." in result.stdout
    assert "vibecrafted dashboard" in result.stdout


def test_spawn_watch_startup_reports_still_launching_when_quiet(
    tmp_path: Path,
) -> None:
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "trace.log"

    result = _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_AGENT="gemini"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_SKILL_CODE="impl"
        spawn_write_meta "{meta}" "launching" "gemini" "implement" "{tmp_path}" "{tmp_path / "plan.md"}" "{report}" "{transcript}" "{tmp_path / "launcher.sh"}"
        spawn_write_frontmatter "{transcript}" "gemini" "unknown" "transcript"
        spawn_watch_startup "{meta}" "{transcript}" "{report}" 1
        '''
    )

    assert "Startup check: still launching after 1s." in result.stdout
    assert "vibecrafted dashboard" in result.stdout


def test_codex_stream_filter_handles_structured_turn_failed_payload() -> None:
    payload = (
        '{"type":"turn.failed","error":{"message":"stream exploded","code":"EPIPE"}}\n'
    )

    result = subprocess.run(
        ["jq", "-rj", "-f", str(CODEX_STREAM_FILTER)],
        check=True,
        cwd=REPO_ROOT,
        input=payload,
        capture_output=True,
        text=True,
    )

    assert "stream exploded" in result.stdout
    assert "cannot be added" not in result.stderr


def test_codex_spawn_marks_meta_failed_when_stream_filter_crashes(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    fake_bin = tmp_path / "bin"
    plan = tmp_path / "plan.md"

    home.mkdir()
    fake_bin.mkdir()
    plan.write_text("# Plan\n", encoding="utf-8")

    fake_codex = fake_bin / "codex"
    fake_codex.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'report=""',
                "while [[ $# -gt 0 ]]; do",
                '  case "$1" in',
                '    --output-last-message) shift; report="$1" ;;',
                "  esac",
                "  shift || true",
                "done",
                "cat >/dev/null || true",
                'printf \'{"type":"thread.started","thread_id":"fake-session-001"}\\n\'',
                'if [[ -n "$report" ]]; then',
                '  : > "$report"',
                "fi",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    fake_jq = fake_bin / "jq"
    fake_jq.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "cat >/dev/null || true",
                "echo 'jq: error (at <stdin>:1): string and object cannot be added' >&2",
                "exit 5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_jq.chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home),
        "VIBECRAFTED_HOME": str(crafted_home),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "VIBECRAFTED_INLINE_STARTUP_WATCH": "0",
    }

    result = subprocess.run(
        [
            "bash",
            str(CODEX_SPAWN_SH),
            "--runtime",
            "headless",
            "--root",
            str(REPO_ROOT),
            str(plan),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "Agent launched. Report will land at:" in result.stdout

    meta_files: list[Path] = []
    deadline = time.time() + 5
    artifacts_root = crafted_home / "artifacts"
    while time.time() < deadline:
        meta_files = list(artifacts_root.rglob("*_plan_codex.meta.json"))
        if meta_files:
            payload = json.loads(meta_files[0].read_text(encoding="utf-8"))
            if payload.get("status") in {"completed", "failed"}:
                break
        time.sleep(0.1)

    assert meta_files, "codex spawn did not write meta.json"
    meta_payload = json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert meta_payload["status"] == "failed"
    assert meta_payload["exit_code"] == 5

    report_file = meta_files[0].with_name(
        meta_files[0].name.replace(".meta.json", ".md")
    )
    assert report_file.exists()
    assert (
        "Codex failed before writing a standalone report file."
        in report_file.read_text(encoding="utf-8")
    )


def test_generated_launcher_includes_startup_watch(tmp_path: Path) -> None:
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.txt"
    transcript = tmp_path / "trace.log"

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_AGENT="claude"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_LOOP_NR="2"
        export SPAWN_SKILL_CODE="impl"
        cmd='printf "ok\\n" > "{report}"'
        spawn_write_meta "{meta}" "launching" "claude" "implement" "{tmp_path}" "{launcher}" "{report}" "{transcript}" "{launcher}"
        spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd"
        '''
    )

    body = launcher.read_text(encoding="utf-8")
    assert 'spawn_watch_startup "$meta" "$transcript" "$report" &' in body
    assert 'wait "$startup_watch_pid"' in body


def test_spawn_in_zellij_pane_honors_requested_direction(tmp_path: Path) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture_file = tmp_path / "zellij-args.txt"
    zellij = fake_bin / "zellij"
    zellij.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zellij.chmod(0o755)

    _bash(
        f'''
        set -euo pipefail
        export PATH="{fake_bin}:$PATH"
        export CAPTURE_FILE="{capture_file}"
        export ZELLIJ=1
        export ZELLIJ_PANE_ID=terminal_1
        export VIBECRAFTED_RUN_ID="{run_id}"
        export ZELLIJ_SESSION_NAME="{operator_session}"
        export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
        export VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=down
        source "{COMMON_SH}"
        spawn_in_zellij_pane "{launcher}" "workflow"
        '''
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--name" in payload
    assert "workflow" in payload
    assert "--direction" in payload
    assert "down" in payload


def test_generated_launcher_preserves_operator_session_contract(tmp_path: Path) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.txt"
    transcript = tmp_path / "trace.log"

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_AGENT="claude"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_LOOP_NR="2"
        export SPAWN_SKILL_CODE="marb"
        export VIBECRAFTED_RUN_ID="{run_id}"
        export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
        export VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION="right"
        cmd='printf "%s\\n%s\\n" "$VIBECRAFTED_OPERATOR_SESSION" "$VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION" > "{report}"'
        spawn_write_meta "{meta}" "launching" "claude" "marbles" "{tmp_path}" "{launcher}" "{report}" "{transcript}" "{launcher}"
        spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd"
        chmod +x "{launcher}"
        bash "{launcher}"
        '''
    )

    payload = report.read_text(encoding="utf-8").splitlines()
    assert payload == [operator_session, "right"]


def test_generated_launcher_completes_meta_before_success_hook_failure(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.txt"
    transcript = tmp_path / "trace.log"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'''
            set -euo pipefail
            source "{COMMON_SH}"
            export SPAWN_ROOT="{tmp_path}"
            export SPAWN_AGENT="claude"
            export SPAWN_PROMPT_ID="prompt-123"
            export SPAWN_RUN_ID="marb-014520-002"
            export SPAWN_LOOP_NR="2"
            export SPAWN_SKILL_CODE="marb"
            cmd='printf "ok\\n" > "{report}"'
            spawn_write_meta "{meta}" "launching" "claude" "marbles" "{tmp_path}" "{launcher}" "{report}" "{transcript}" "{launcher}"
            spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd" "" "exit 23"
            chmod +x "{launcher}"
            bash "{launcher}"
            ''',
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 23
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["exit_code"] == 0


def test_spawn_prepare_paths_generates_real_run_context_when_missing(
    tmp_path: Path,
) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("# Prompt\n", encoding="utf-8")

    result = _bash(
        f'''
        set -euo pipefail
        export HOME="{tmp_path / "home"}"
        export VIBECRAFTED_ROOT="{REPO_ROOT}"
            mkdir -p "$VIBECRAFTED_ROOT/"
        source "{COMMON_SH}"
        unset VIBECRAFTED_RUN_ID
        unset VIBECRAFTED_RUN_LOCK
        unset VIBECRAFTED_SKILL_CODE
        export VIBECRAFTED_LOOP_NR="0"
        spawn_prepare_paths claude "{prompt_file}" "{tmp_path}" "followup"
        printf 'RUN_ID=%s\\n' "$SPAWN_RUN_ID"
        printf 'SKILL_CODE=%s\\n' "$SPAWN_SKILL_CODE"
        printf 'RUN_LOCK=%s\\n' "$SPAWN_RUN_LOCK"
        '''
    )

    payload = dict(
        line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line
    )
    assert re.fullmatch(r"fwup-\d{6}", payload["RUN_ID"])
    assert payload["SKILL_CODE"] == "fwup"
    lock_path = Path(payload["RUN_LOCK"])
    expected_lock = (
        tmp_path
        / "home"
        / ".vibecrafted"
        / "locks"
        / tmp_path.name
        / f"{payload['RUN_ID']}.lock"
    )
    assert lock_path == expected_lock
    assert "skill=followup" in lock_path.read_text(encoding="utf-8")
    assert result.stderr == ""


def test_spawn_in_operator_session_targets_named_session(tmp_path: Path) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture_file = tmp_path / "zellij-args.txt"
    zellij = fake_bin / "zellij"
    zellij.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zellij.chmod(0o755)

    _bash(
        f'''
        set -euo pipefail
        export PATH="{fake_bin}:$PATH"
        export CAPTURE_FILE="{capture_file}"
        export VIBECRAFTED_RUN_ID="{run_id}"
        export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
        export SPAWN_ROOT="{tmp_path}"
        source "{COMMON_SH}"
        spawn_in_operator_session "{launcher}" "workflow"
        '''
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert operator_session in payload
    assert "action" in payload
    # When spawning from outside a zellij context (no ZELLIJ/ZELLIJ_PANE_ID),
    # the routing guard forces a new-tab to avoid landing in a stale operator tab.
    assert "new-tab" in payload
    assert "--name" in payload
    assert "workflow" in payload


def test_spawn_in_operator_session_new_tab_opens_monitor_and_disables_inline_watch(
    tmp_path: Path,
) -> None:
    run_id = "rsch-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

    meta = tmp_path / "meta.json"
    transcript = tmp_path / "trace.log"
    report = tmp_path / "report.md"
    meta.write_text("{}", encoding="utf-8")
    transcript.write_text("", encoding="utf-8")
    report.write_text("", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture_file = tmp_path / "zellij-calls.txt"
    zellij = fake_bin / "zellij"
    zellij.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf -- "--CALL--\\n"',
                '  printf "%s\\n" "$@"',
                '} >> "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zellij.chmod(0o755)

    _bash(
        f'''
        set -euo pipefail
        export PATH="{fake_bin}:$PATH"
        export CAPTURE_FILE="{capture_file}"
        export VIBECRAFTED_RUN_ID="{run_id}"
        export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_META="{meta}"
        export SPAWN_TRANSCRIPT="{transcript}"
        export SPAWN_REPORT="{report}"
        export SPAWN_SKILL_NAME="research"
        source "{COMMON_SH}"
        spawn_in_operator_session "{launcher}" "workflow"
        '''
    )

    calls = _split_zellij_calls(capture_file.read_text(encoding="utf-8"))
    assert len(calls) == 2

    monitor_call, workflow_call = calls
    assert monitor_call[:4] == ["--session", operator_session, "action", "new-pane"]
    assert "--name" in monitor_call
    assert "startup-monitor" in monitor_call
    assert "--direction" in monitor_call
    assert "down" in monitor_call

    assert workflow_call[:4] == ["--session", operator_session, "action", "new-tab"]
    assert "--name" in workflow_call
    assert "workflow" in workflow_call

    monitor_cmd = Path(monitor_call[monitor_call.index("--") + 1]).read_text(
        encoding="utf-8"
    )
    assert "; exit" in monitor_cmd
    monitor_script_match = re.search(
        r"(/[^'\"\s]*vc-startup-monitor\.[^'\"\s]*)", monitor_cmd
    )
    assert monitor_script_match is not None
    monitor_script = Path(monitor_script_match.group(1))
    monitor_body = monitor_script.read_text(encoding="utf-8")
    assert "trap 'rm -f \"$0\"' EXIT" in monitor_body
    assert (
        "Your vibecrafted session %s invoked the %s run that landed in %s %s."
        in monitor_body
    )
    assert "spawn_watch_startup" in monitor_body

    workflow_cmd = Path(workflow_call[workflow_call.index("--") + 1]).read_text(
        encoding="utf-8"
    )
    assert "VIBECRAFTED_INLINE_STARTUP_WATCH=0" in workflow_cmd
    assert str(launcher) in workflow_cmd
