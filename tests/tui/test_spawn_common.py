from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SH = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "common.sh"
CLAUDE_SPAWN_SH = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "claude_spawn.sh"
CODEX_SPAWN_SH = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "codex_spawn.sh"
CODEX_STREAM_BRIDGE = (
    REPO_ROOT / "skills" / "vc-agents" / "scripts" / "codex_stream_bridge.py"
)
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


def _read_json_or_none(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return None
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _wait_for_meta_payload(
    artifacts_root: Path, pattern: str, timeout: float = 5.0
) -> tuple[Path | None, dict | None]:
    deadline = time.time() + timeout
    latest_meta: Path | None = None
    while time.time() < deadline:
        meta_files = sorted(artifacts_root.rglob(pattern))
        if meta_files:
            latest_meta = meta_files[0]
            payload = _read_json_or_none(latest_meta)
            if payload and payload.get("status") in {"completed", "failed"}:
                return latest_meta, payload
        time.sleep(0.1)
    if latest_meta is None:
        return None, None
    return latest_meta, _read_json_or_none(latest_meta)


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


def test_runtime_prompt_includes_vc_agents_worker_charter(tmp_path: Path) -> None:
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
        spawn_build_runtime_prompt "{source_file}" "{runtime_file}" "{report_path}" codex
        '''
    )

    payload = runtime_file.read_text(encoding="utf-8")
    assert "## VC Agents Worker Charter" in payload
    assert "Do NOT invoke vc-agents" in payload
    assert "do not reinterpret it" in payload
    assert "record the boundary clearly in your report" in payload
    assert "**COMMIT**: mandatory. One commit when done." in payload


def test_research_runtime_prompt_forbids_commits_and_source_mutation(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "source.md"
    runtime_file = tmp_path / "runtime.md"
    report_path = tmp_path / "report.md"
    source_file.write_text("# Research prompt\n", encoding="utf-8")

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_RUN_ID="rsch-123"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_SKILL_NAME="research"
        export SPAWN_SKILL_CODE="rsch"
        spawn_build_runtime_prompt "{source_file}" "{runtime_file}" "{report_path}" codex
        '''
    )

    payload = runtime_file.read_text(encoding="utf-8")
    assert "## Research Safety Contract" in payload
    assert "**COMMIT**: forbidden" in payload
    assert "git write operation" in payload
    assert "Do not edit repo source files" in payload
    assert "**COMMIT**: mandatory. One commit when done." not in payload


def test_codex_research_prompt_uses_clean_research_payload(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "source.md"
    runtime_file = tmp_path / "runtime.md"
    report_path = tmp_path / "report.md"
    source_file.write_text(
        "\n".join(
            [
                "---",
                "run_id: rsch-123",
                "skill: vc-research",
                "status: in-progress",
                "---",
                "",
                "# Research Prompt",
                "",
                "Question: How should clean worker prompts behave?",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_RUN_ID="rsch-123"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_SKILL_NAME="research"
        spawn_build_runtime_prompt "{source_file}" "{runtime_file}" "{report_path}" codex
        '''
    )

    payload = runtime_file.read_text(encoding="utf-8")
    assert "# Research Prompt" in payload
    assert "Question: How should clean worker prompts behave?" in payload
    assert "## Codex Report Write Contract" in payload
    assert "`codex exec --output-last-message`" in payload
    assert "write the COMPLETE markdown report to the exact `Report path`" in payload
    assert "using a shell command such as a heredoc" in payload
    assert "must not be the only place where the report exists" in payload
    assert "skill: vc-research" not in payload
    assert "Perform the vc-research skill" not in payload
    assert "## VC Agents Worker Charter" not in payload
    assert "Do NOT invoke vc-agents" not in payload
    assert "Codex Research Report Capture Contract" not in payload
    assert "triple-agent research swarm" not in payload.lower()
    assert "delegate" not in payload.lower()


def test_codex_implement_prompt_does_not_get_research_capture_contract(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "source.md"
    runtime_file = tmp_path / "runtime.md"
    report_path = tmp_path / "report.md"
    source_file.write_text("# Implement Prompt\n", encoding="utf-8")

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_RUN_ID="impl-123"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_SKILL_NAME="implement"
        spawn_build_runtime_prompt "{source_file}" "{runtime_file}" "{report_path}" codex
        '''
    )

    payload = runtime_file.read_text(encoding="utf-8")
    assert "## Codex Research Report Capture Contract" not in payload
    assert (
        "final assistant message MUST be the complete markdown report verbatim"
        not in payload
    )


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


def test_generated_launcher_fails_fast_on_invalid_hook_syntax(tmp_path: Path) -> None:
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
            export SPAWN_RUN_ID="run-123"
            export SPAWN_LOOP_NR="1"
            export SPAWN_SKILL_CODE="marb"
            cmd='printf "ok\\n" > "{report}"'
            bad_hook="echo '"
            spawn_write_meta "{meta}" "launching" "claude" "marbles" "{tmp_path}" "{launcher}" "{report}" "{transcript}" "{launcher}"
            spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd" "" "$bad_hook"
            ''',
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Generated launcher has invalid shell syntax" in result.stderr
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 1


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


def test_spawn_watch_startup_reports_failure_without_dashboard_hint(
    tmp_path: Path,
) -> None:
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
    assert "vibecrafted dashboard" not in result.stdout


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


def test_spawn_watch_startup_can_probe_without_echoing_transcript(
    tmp_path: Path,
) -> None:
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
        export VIBECRAFTED_STARTUP_WATCH_ECHO=0
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
    assert "session: 54865595-899c-4402-b957-911433e46199" not in result.stdout
    assert "Working..." not in result.stdout


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


def test_codex_stream_bridge_tolerates_turn_abort_and_malformed_json(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "trace.log"
    raw = tmp_path / "trace.raw.jsonl"
    payload = "\n".join(
        [
            '{"type":"thread.started","thread_id":"fake-session-001"}',
            '{"type":"turn.aborted","message":"refresh token already used"}',
            '{"type":"item.completed"',
        ]
    )

    subprocess.run(
        [
            "python3",
            str(CODEX_STREAM_BRIDGE),
            "--transcript",
            str(transcript),
            "--raw",
            str(raw),
        ],
        check=True,
        cwd=REPO_ROOT,
        input=payload,
        capture_output=True,
        text=True,
    )

    transcript_text = transcript.read_text(encoding="utf-8")
    raw_text = raw.read_text(encoding="utf-8")
    assert "session: fake-session-001" in transcript_text
    assert "refresh token already used" in transcript_text
    assert '{"type":"item.completed"' in transcript_text
    assert payload in raw_text


def test_codex_spawn_marks_meta_failed_when_codex_emits_non_json_auth_error(
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
                'printf "Your access token could not be refreshed because your refresh token was already used.\\n" >&2',
                "exit 17",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

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

    assert "Agent launched." in result.stdout
    assert "Await:" in result.stdout

    artifacts_root = crafted_home / "artifacts"
    meta_file, meta_payload = _wait_for_meta_payload(
        artifacts_root, "*_plan_codex.meta.json"
    )

    assert meta_file is not None, "codex spawn did not write meta.json"
    assert meta_payload is not None, "codex spawn did not finish writing meta.json"
    assert meta_payload["status"] == "failed"
    assert meta_payload["exit_code"] == 17

    report_file = Path(meta_payload["report"])
    deadline = time.time() + 5
    while time.time() < deadline:
        if report_file.exists():
            break
        time.sleep(0.1)

    assert report_file.exists()
    assert (
        "Codex failed before writing a standalone report file."
        in report_file.read_text(encoding="utf-8")
    )
    transcript_file = meta_file.with_name(
        meta_file.name.replace(".meta.json", ".transcript.log")
    )
    assert "refresh token was already used" in transcript_file.read_text(
        encoding="utf-8"
    )


def test_codex_spawn_preserves_standalone_report_when_last_message_is_handoff(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    fake_bin = tmp_path / "bin"
    plan = tmp_path / "research-plan.md"

    home.mkdir()
    fake_bin.mkdir()
    plan.write_text("# Research Plan\n", encoding="utf-8")

    fake_codex = fake_bin / "codex"
    fake_codex.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'last_message=""',
                "while [[ $# -gt 0 ]]; do",
                '  case "$1" in',
                '    --output-last-message) shift; last_message="${1:-}" ;;',
                "  esac",
                "  shift || true",
                "done",
                'prompt="$(cat)"',
                'report_path="$(printf "%s\\n" "$prompt" | sed -n \'s/^Report path: //p\' | tail -n 1)"',
                '[[ -n "$report_path" ]] || exit 22',
                'mkdir -p "$(dirname "$report_path")"',
                'cat > "$report_path" <<EOF_REPORT',
                "---",
                "agent: codex",
                "status: completed",
                "---",
                "",
                "# Full Research Report",
                "",
                "This is the durable report body.",
                "EOF_REPORT",
                'if [[ -n "$last_message" ]]; then',
                '  mkdir -p "$(dirname "$last_message")"',
                '  cat > "$last_message" <<EOF_LAST',
                "Done. Report saved at: $report_path",
                "EOF_LAST",
                "fi",
                'printf \'{"type":"thread.started","thread_id":"fake-session-standalone"}\\n\'',
                'printf \'{"type":"item.completed","item":{"type":"agent_message","text":"structured report was streamed earlier"}}\\n\'',
                'printf \'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\\n\'',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home),
        "VIBECRAFTED_HOME": str(crafted_home),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "VIBECRAFTED_INLINE_STARTUP_WATCH": "0",
        "VIBECRAFTED_SKILL_CODE": "rsch",
        "VIBECRAFTED_SKILL_NAME": "research",
    }

    result = subprocess.run(
        [
            "bash",
            str(CODEX_SPAWN_SH),
            "--mode",
            "research",
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

    assert "Agent launched." in result.stdout

    artifacts_root = crafted_home / "artifacts"
    meta_file, meta_payload = _wait_for_meta_payload(
        artifacts_root, "*_research-plan_codex.meta.json"
    )

    assert meta_file is not None, "codex spawn did not write research meta.json"
    assert meta_payload is not None, "codex spawn did not finish writing meta.json"
    assert meta_payload["status"] == "completed"

    report_file = Path(meta_payload["report"])
    report_text = report_file.read_text(encoding="utf-8")
    assert "# Full Research Report" in report_text
    assert "This is the durable report body." in report_text
    assert "Done. Report saved at" not in report_text

    last_message_file = Path(meta_payload["transcript"]).with_suffix(".last-message.md")
    assert last_message_file.exists()
    assert "Done. Report saved at" in last_message_file.read_text(encoding="utf-8")


def test_codex_research_does_not_copy_pointer_last_message_as_report(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    fake_bin = tmp_path / "bin"
    plan = tmp_path / "research-plan.md"

    home.mkdir()
    fake_bin.mkdir()
    plan.write_text("# Research Plan\n", encoding="utf-8")

    fake_codex = fake_bin / "codex"
    fake_codex.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'last_message=""',
                "while [[ $# -gt 0 ]]; do",
                '  case "$1" in',
                '    --output-last-message) shift; last_message="${1:-}" ;;',
                "  esac",
                "  shift || true",
                "done",
                "cat >/dev/null",
                'if [[ -n "$last_message" ]]; then',
                '  mkdir -p "$(dirname "$last_message")"',
                '  cat > "$last_message" <<EOF_LAST',
                "Done. Report saved at: /tmp/research/codex.md",
                "EOF_LAST",
                "fi",
                'printf \'{"type":"thread.started","thread_id":"fake-session-pointer"}\\n\'',
                'printf \'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\\n\'',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home),
        "VIBECRAFTED_HOME": str(crafted_home),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "VIBECRAFTED_INLINE_STARTUP_WATCH": "0",
        "VIBECRAFTED_SKILL_CODE": "rsch",
        "VIBECRAFTED_SKILL_NAME": "research",
    }

    result = subprocess.run(
        [
            "bash",
            str(CODEX_SPAWN_SH),
            "--mode",
            "research",
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

    assert "Agent launched." in result.stdout

    artifacts_root = crafted_home / "artifacts"
    meta_file, meta_payload = _wait_for_meta_payload(
        artifacts_root, "*_research-plan_codex.meta.json"
    )

    assert meta_file is not None, "codex spawn did not write research meta.json"
    assert meta_payload is not None, "codex spawn did not finish writing meta.json"
    assert meta_payload["status"] == "failed"
    assert meta_payload["exit_code"] == 65

    report_file = Path(meta_payload["report"])
    deadline = time.time() + 5
    report_text = ""
    while time.time() < deadline:
        if report_file.exists():
            report_text = report_file.read_text(encoding="utf-8")
            if "Codex failed before writing a standalone report file." in report_text:
                break
        time.sleep(0.1)
    assert report_file.exists()
    assert "Codex failed before writing a standalone report file." in report_text
    assert "Done. Report saved at" not in report_text

    last_message_file = Path(meta_payload["transcript"]).with_suffix(".last-message.md")
    assert last_message_file.exists()
    assert "Done. Report saved at" in last_message_file.read_text(encoding="utf-8")


def test_claude_spawn_marks_meta_failed_when_stream_has_no_json(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    fake_bin = tmp_path / "bin"
    plan = tmp_path / "plan.md"

    home.mkdir()
    fake_bin.mkdir()
    plan.write_text("# Plan\n", encoding="utf-8")

    fake_claude = fake_bin / "claude"
    fake_claude.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "cat >/dev/null || true",
                'printf "Not logged in · Please run /login\\n" >&2',
                "exit 19",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)

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
            str(CLAUDE_SPAWN_SH),
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

    assert "Agent launched." in result.stdout
    assert "Await:" in result.stdout

    artifacts_root = crafted_home / "artifacts"
    meta_file, meta_payload = _wait_for_meta_payload(
        artifacts_root, "*_plan_claude.meta.json"
    )

    assert meta_file is not None, "claude spawn did not write meta.json"
    assert meta_payload is not None, "claude spawn did not finish writing meta.json"
    assert meta_payload["status"] == "failed"
    assert meta_payload["exit_code"] != 0


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
    assert (
        'VIBECRAFTED_STARTUP_WATCH_ECHO=0 spawn_watch_startup "$meta" "$transcript" "$report" &'
        in body
    )
    assert 'wait "$startup_watch_pid"' in body


def test_research_launcher_blocks_git_write_operations(tmp_path: Path) -> None:
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
            export SPAWN_AGENT="codex"
            export SPAWN_PROMPT_ID="prompt-123"
            export SPAWN_RUN_ID="rsch-014520-002"
            export SPAWN_LOOP_NR="0"
            export SPAWN_SKILL_CODE="rsch"
            export SPAWN_SKILL_NAME="research"
            export VIBECRAFTED_INLINE_STARTUP_WATCH=0
            cmd='git commit --allow-empty -m blocked'
            spawn_write_meta "{meta}" "launching" "codex" "research" "{tmp_path}" "{launcher}" "{report}" "{transcript}" "{launcher}"
            spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd"
            chmod +x "{launcher}"
            bash "{launcher}"
            ''',
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 126
    assert "vibecrafted research mode blocks git write operation: git commit" in (
        result.stderr + result.stdout
    )
    assert json.loads(meta.read_text(encoding="utf-8"))["status"] == "failed"


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


def test_generated_launcher_marks_meta_failed_before_failure_hook(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.txt"
    transcript = tmp_path / "trace.log"
    failure_seen = tmp_path / "failure-meta.json"

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
            cmd='printf "boom\\n" >&2; exit 23'
            failure_hook='python3 - <<'"'"'PY'"'"'
import json
from pathlib import Path
Path("{failure_seen}").write_text(Path("{meta}").read_text(encoding="utf-8"), encoding="utf-8")
PY'
            spawn_write_meta "{meta}" "launching" "claude" "marbles" "{tmp_path}" "{launcher}" "{report}" "{transcript}" "{launcher}"
            spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd" "" "" "$failure_hook"
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
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 23
    failure_payload = json.loads(failure_seen.read_text(encoding="utf-8"))
    assert failure_payload["status"] == "failed"
    assert failure_payload["exit_code"] == 23


def test_gc_marks_dead_launcher_pid_as_ghost(tmp_path: Path) -> None:
    meta = tmp_path / "dead.meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "trace.log"

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_AGENT="codex"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="impl-010203-999"
        export SPAWN_SKILL_CODE="impl"
        spawn_write_meta "{meta}" "running" "codex" "implement" "{tmp_path}" "{tmp_path / "plan.md"}" "{report}" "{transcript}" "{tmp_path / "launcher.sh"}"
        python3 - <<'PY'
import json
from pathlib import Path
path = Path("{meta}")
payload = json.loads(path.read_text(encoding="utf-8"))
payload["launcher_pid"] = 999999999
payload["liveness"] = "pid_alive"
path.write_text(json.dumps(payload), encoding="utf-8")
PY
        spawn_gc_dead_runs "{tmp_path}"
        '''
    )

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["status"] == "ghost"
    assert payload["liveness"] == "pid_dead"
    assert payload["ghost_reason"] == "launcher_pid dead at reap"


def test_gc_marks_live_meta_without_pid_as_unknown_legacy(tmp_path: Path) -> None:
    meta = tmp_path / "legacy.meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "trace.log"

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_AGENT="claude"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="impl-010203-998"
        export SPAWN_SKILL_CODE="impl"
        spawn_write_meta "{meta}" "running" "claude" "implement" "{tmp_path}" "{tmp_path / "plan.md"}" "{report}" "{transcript}" "{tmp_path / "launcher.sh"}"
        spawn_gc_dead_runs "{tmp_path}"
        '''
    )

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["status"] == "running"
    assert payload["liveness"] == "unknown_legacy"
    assert payload["liveness_reason"] == "live status without launcher_pid"


def test_operator_intervention_is_run_scoped_auditable_jsonl(
    tmp_path: Path,
) -> None:
    meta = tmp_path / "agent.meta.json"
    report = tmp_path / "report.md"
    transcript = tmp_path / "trace.log"

    result = _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_AGENT="codex"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="impl-010203-997"
        export SPAWN_SKILL_CODE="impl"
        spawn_write_meta "{meta}" "running" "codex" "implement" "{tmp_path}" "{tmp_path / "plan.md"}" "{report}" "{transcript}" "{tmp_path / "launcher.sh"}"
        spawn_append_operator_intervention "{meta}" "Please narrow the next pass to liveness tests." "operator"
        '''
    )

    intervention_path = Path(result.stdout.strip().splitlines()[-1])
    payload = json.loads(meta.read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in intervention_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert payload["intervention_path"] == str(intervention_path)
    assert payload["intervention_count"] == 1
    assert events[0]["schema"] == "vibecrafted.operator_intervention.v1"
    assert events[0]["run_id"] == "impl-010203-997"
    assert events[0]["consumer_contract"] == "compatible-watchers-and-bridges-only"
    transcript_text = transcript.read_text(encoding="utf-8")
    assert "operator intervention" in transcript_text
    assert "run_id=impl-010203-997" in transcript_text


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
    assert re.fullmatch(r"fwup-\d{6}-\d+", payload["RUN_ID"])
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


def test_spawn_in_operator_session_suppresses_zellij_tab_number_output(
    tmp_path: Path,
) -> None:
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
                'printf "7\\n"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zellij.chmod(0o755)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'''
            set -euo pipefail
            export PATH="{fake_bin}:$PATH"
            export CAPTURE_FILE="{capture_file}"
            export VIBECRAFTED_RUN_ID="{run_id}"
            export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
            export SPAWN_ROOT="{tmp_path}"
            source "{COMMON_SH}"
            spawn_in_operator_session "{launcher}" "workflow"
            ''',
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""


def test_spawn_in_zellij_pane_marbles_tab_suppresses_tab_number_output(
    tmp_path: Path,
) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

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
                'if [[ "${1:-}" == "action" && "${2:-}" == "list-tabs" ]]; then',
                '  printf \'[{"name":"operator-tab","tab_id":2},{"name":"marbles","tab_id":7}]\\n\'',
                "  exit 0",
                "fi",
                'if [[ "${1:-}" == "action" && "${2:-}" == "new-pane" ]]; then',
                '  printf "terminal_13\\n"',
                "  exit 0",
                "fi",
                'printf "12\\n"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zellij.chmod(0o755)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'''
            set -euo pipefail
            export PATH="{fake_bin}:$PATH"
            export CAPTURE_FILE="{capture_file}"
            export ZELLIJ=1
            export ZELLIJ_PANE_ID=terminal_1
            export ZELLIJ_SESSION_NAME="{operator_session}"
            export ZELLIJ_TAB_NAME="operator-tab"
            export VIBECRAFTED_RUN_ID="{run_id}"
            export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
            export VIBECRAFTED_MARBLES_TAB_NAME="marbles"
            export SPAWN_ROOT="{tmp_path}"
            export SPAWN_LOOP_NR=1
            source "{COMMON_SH}"
            spawn_in_zellij_pane "{launcher}" "workflow"
            ''',
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
    calls = _split_zellij_calls(capture_file.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert calls[0][:3] == ["action", "list-tabs", "--json"]
    assert calls[1][:2] == ["action", "new-pane"]
    assert "--tab-id" in calls[1]
    assert "7" in calls[1]
    assert "--stacked" in calls[1]
    assert "--close-on-exit" not in calls[1]
    assert not any("go-to-tab-name" in call for call in calls)


def test_spawn_in_zellij_pane_marbles_tab_can_close_agent_panes(
    tmp_path: Path,
) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

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
                'if [[ "${1:-}" == "action" && "${2:-}" == "list-tabs" ]]; then',
                '  printf \'[{"name":"marbles","tab_id":7}]\\n\'',
                "  exit 0",
                "fi",
                'if [[ "${1:-}" == "action" && "${2:-}" == "new-pane" ]]; then',
                '  printf "terminal_13\\n"',
                "  exit 0",
                "fi",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zellij.chmod(0o755)

    subprocess.run(
        [
            "bash",
            "-lc",
            f'''
            set -euo pipefail
            export PATH="{fake_bin}:$PATH"
            export CAPTURE_FILE="{capture_file}"
            export ZELLIJ=1
            export ZELLIJ_PANE_ID=terminal_1
            export ZELLIJ_SESSION_NAME="{operator_session}"
            export VIBECRAFTED_RUN_ID="{run_id}"
            export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
            export VIBECRAFTED_MARBLES_TAB_NAME="marbles"
            export VIBECRAFTED_ZELLIJ_CLOSE_AGENT_PANES=1
            export SPAWN_ROOT="{tmp_path}"
            export SPAWN_LOOP_NR=1
            source "{COMMON_SH}"
            spawn_in_zellij_pane "{launcher}" "workflow"
            ''',
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    calls = _split_zellij_calls(capture_file.read_text(encoding="utf-8"))
    assert calls[1][:2] == ["action", "new-pane"]
    assert "--stacked" in calls[1]
    assert "--close-on-exit" in calls[1]


def test_spawn_probe_uses_active_tab_and_restores_focus(tmp_path: Path) -> None:
    transcript = tmp_path / "trace.log"
    transcript.write_text("hello\n", encoding="utf-8")

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
                'if [[ "${1:-}" == "action" && "${2:-}" == "current-tab-info" ]]; then',
                '  printf \'{"name":"operator-tab","tab_id":9}\\n\'',
                "  exit 0",
                "fi",
                'if [[ "${1:-}" == "action" && "${2:-}" == "list-panes" ]]; then',
                '  printf \'[{"pane_id":"terminal_42","is_focused":true}]\\n\'',
                "  exit 0",
                "fi",
                'if [[ "${1:-}" == "action" && "${2:-}" == "new-pane" ]]; then',
                '  printf "terminal_99\\n"',
                "  exit 0",
                "fi",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zellij.chmod(0o755)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'''
            set -euo pipefail
            export PATH="{fake_bin}:$PATH"
            export CAPTURE_FILE="{capture_file}"
            export ZELLIJ=1
            export ZELLIJ_PANE_ID=terminal_1
            export ZELLIJ_SESSION_NAME="operator-session"
            export ZELLIJ_TAB_NAME="operator-tab"
            export SPAWN_AGENT="gemini"
            export VIBECRAFTED_SPAWN_PROBE_SECONDS=1
            export VIBECRAFTED_SPAWN_PROBE_DELAY_SECONDS=0
            source "{COMMON_SH}"
            spawn_probe "{transcript}"
            sleep 0.2
            ''',
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
    calls = _split_zellij_calls(capture_file.read_text(encoding="utf-8"))
    assert any(call[:3] == ["action", "current-tab-info", "--json"] for call in calls)
    assert any(
        call[:4] == ["action", "list-panes", "--json", "--state"] for call in calls
    )
    probe_calls = [call for call in calls if call[:2] == ["action", "new-pane"]]
    assert len(probe_calls) == 1
    probe_call = probe_calls[0]
    assert "--floating" in probe_call
    assert "--tab-id" in probe_call
    assert "9" in probe_call
    assert "--name" in probe_call
    assert "probe-gemini" in probe_call
    assert any(call[:3] == ["action", "focus-pane-id", "terminal_42"] for call in calls)


def test_spawn_in_operator_session_new_tab_opens_monitor_and_disables_inline_watch(
    tmp_path: Path,
) -> None:
    run_id = "rsch-014520"
    operator_session = _expected_operator_session(run_id)
    expected_tmp_root = tmp_path / ".vibecrafted" / "tmp"
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
    assert monitor_script.parent == expected_tmp_root
    monitor_body = monitor_script.read_text(encoding="utf-8")
    assert "trap 'rm -f \"$0\"' EXIT" not in monitor_body
    assert (
        "Your vibecrafted session %s invoked the %s run that landed in %s %s."
        in monitor_body
    )
    assert "spawn_watch_startup" in monitor_body

    workflow_script = Path(workflow_call[workflow_call.index("--") + 1])
    assert workflow_script.parent == expected_tmp_root
    workflow_cmd = workflow_script.read_text(encoding="utf-8")
    assert "VIBECRAFTED_INLINE_STARTUP_WATCH=0" in workflow_cmd
    assert str(launcher) in workflow_cmd
