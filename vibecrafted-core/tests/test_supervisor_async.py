from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from vibecrafted_core import dispatcher
from vibecrafted_core.artifacts import validate_artifacts
from vibecrafted_core.control_plane import read_event_tail
from vibecrafted_core.lifecycle import RunState, transition_allowed
from vibecrafted_core.supervisor_async import AsyncSupervisor


def test_lifecycle_transition_table_rejects_backwards_transition() -> None:
    assert transition_allowed(RunState.CREATED, RunState.PROCESS_SPAWNED)
    assert not transition_allowed(RunState.REPORT_VALIDATED, RunState.ACTIVE)


def test_artifact_validator_reports_missing_report(tmp_path: Path) -> None:
    meta = tmp_path / "run.meta.json"
    meta.write_text(json.dumps({"transcript": str(tmp_path / "run.log")}))

    result = validate_artifacts(meta_path=meta)

    assert not result.ok
    assert result.errors == ("report_missing",)
    assert result.meta_exists is True


def test_async_supervisor_emits_lifecycle_and_validates_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "report.md"
    transcript = tmp_path / "transcript.log"
    script = tmp_path / "worker.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(report)!r}).write_text('---\\nstatus: completed\\n---\\nbody\\n')\n"
        "print('hello from async supervisor')\n"
    )
    run_id = "asup-test-1"

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id=run_id,
            command=[sys.executable, str(script)],
            root=tmp_path,
            report_path=report,
            transcript_path=transcript,
            require_transcript_output=True,
        )
    )

    assert handle.exit_code == 0
    assert handle.artifact_validation is not None
    assert handle.artifact_validation.ok
    assert RunState.PROCESS_SPAWNED in handle.states
    assert RunState.FIRST_OUTPUT_SEEN in handle.states
    assert RunState.REPORT_VALIDATED in handle.states
    assert "hello from async supervisor" in transcript.read_text()

    states = [
        event.get("payload", {}).get("state")
        for event in read_event_tail(limit=20)
        if event.get("run_id") == run_id
    ]
    assert "created" in states
    assert "process_spawned" in states
    assert "report_validated" in states


def test_dispatcher_cli_runs_full_lifecycle(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    script = tmp_path / "worker.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(report)!r}).write_text('---\\nstatus: completed\\n---\\nbody\\n')\n"
        "print('dispatcher lifecycle hello')\n",
        encoding="utf-8",
    )

    rc = dispatcher.main(
        [
            "run",
            "--run-id",
            "disp-test-1",
            "--root",
            str(tmp_path),
            "--report",
            str(report),
            "--transcript",
            str(transcript),
            "--require-transcript-output",
            "--json",
            "--",
            sys.executable,
            str(script),
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "disp-test-1"
    assert payload["artifact_ok"] is True
    assert payload["state"] == "report_validated"
    assert "process_spawned" in payload["states"]
    assert "first_output_seen" in payload["states"]
    assert "report_validated" in payload["states"]
    assert "dispatcher lifecycle hello" in transcript.read_text(encoding="utf-8")


def test_dispatcher_cli_delivers_prompt_file_on_stdin(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("line one\nline two\n", encoding="utf-8")
    script = tmp_path / "worker.py"
    script.write_text(
        "from pathlib import Path\n"
        "import os, sys\n"
        "body = sys.stdin.read()\n"
        "assert body == Path(os.environ['VIBECRAFTED_PROMPT_PATH']).read_text()\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text(body, encoding='utf-8')\n"
        "print('stdin prompt ok')\n",
        encoding="utf-8",
    )

    rc = dispatcher.main(
        [
            "run",
            "--run-id",
            "disp-test-prompt-file",
            "--root",
            str(tmp_path),
            "--report",
            str(report),
            "--transcript",
            str(transcript),
            "--prompt-file",
            str(prompt),
            "--require-transcript-output",
            "--json",
            "--",
            sys.executable,
            str(script),
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["artifact_ok"] is True
    assert report.read_text(encoding="utf-8") == "line one\nline two\n"
    assert "stdin prompt ok" in transcript.read_text(encoding="utf-8")


def test_dispatcher_cli_tees_visible_worker_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    script = tmp_path / "worker.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(report)!r}).write_text('---\\nstatus: completed\\n---\\nbody\\n')\n"
        "print('visible worker line')\n",
        encoding="utf-8",
    )

    rc = dispatcher.main(
        [
            "run",
            "--run-id",
            "disp-test-visible",
            "--root",
            str(tmp_path),
            "--report",
            str(report),
            "--transcript",
            str(transcript),
            "--require-transcript-output",
            "--tee-output",
            "--json",
            "--",
            sys.executable,
            str(script),
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "visible worker line" in out
    assert '"run_id": "disp-test-visible"' in out
    assert "visible worker line" in transcript.read_text(encoding="utf-8")


def test_dispatcher_cli_quiet_suppresses_final_summary(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    script = tmp_path / "worker.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(report)!r}).write_text('---\\nstatus: completed\\n---\\nbody\\n')\n",
        encoding="utf-8",
    )

    rc = dispatcher.main(
        [
            "run",
            "--run-id",
            "disp-test-quiet",
            "--root",
            str(tmp_path),
            "--report",
            str(report),
            "--transcript",
            str(transcript),
            "--quiet",
            "--",
            sys.executable,
            str(script),
        ]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_async_supervisor_renders_claude_stream_json_for_visible_terminal(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    meta = tmp_path / "dispatch.meta.json"
    claude = tmp_path / "claude"
    claude.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'---\\nstatus: completed\\n---\\nbody\\n', encoding='utf-8'"
        ")\n"
        "print(json.dumps({'type': 'system', 'session_id': 'sess-123', "
        "'model': 'claude-opus-4-8'}))\n"
        "print(json.dumps({'type': 'assistant', 'message': {'content': ["
        "{'type': 'text', 'text': 'visible text from claude'}"
        "]}}))\n",
        encoding="utf-8",
    )
    claude.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="asup-claude-visible",
            command=[
                str(claude),
                "-p",
                "--output-format",
                "stream-json",
                "--verbose",
            ],
            root=tmp_path,
            meta_path=meta,
            report_path=report,
            transcript_path=transcript,
            tee_output=True,
        )
    )

    assert handle.exit_code == 0
    out = capsys.readouterr().out
    assert "session: sess-123" in out
    assert "model: claude-opus-4-8" in out
    assert "visible text from claude" in out
    assert '"type": "assistant"' not in out
    transcript_text = transcript.read_text(encoding="utf-8")
    assert '"type": "assistant"' in transcript_text
    assert handle.agent_session_id == "sess-123"
    assert handle.agent_model == "claude-opus-4-8"
    assert handle.resume_command.endswith("claude --resume sess-123")
    meta_payload = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_payload["agent_session_id"] == "sess-123"
    assert meta_payload["agent_model"] == "claude-opus-4-8"
    assert meta_payload["resume_command"].endswith("claude --resume sess-123")


def test_async_supervisor_uses_env_model_for_codex_thread_banner(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEX_MODEL", "gpt-5.3-codex")
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    meta = tmp_path / "dispatch.meta.json"
    codex = tmp_path / "codex"
    codex.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'---\\nstatus: completed\\n---\\nbody\\n', encoding='utf-8'"
        ")\n"
        "print(json.dumps({'type': 'thread.started', 'thread_id': 'codex-thread'}))\n"
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'codex text'}}))\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="asup-codex-visible",
            command=[str(codex), "exec", "--json", "-"],
            root=tmp_path,
            meta_path=meta,
            report_path=report,
            transcript_path=transcript,
            tee_output=True,
        )
    )

    assert handle.exit_code == 0
    out = capsys.readouterr().out
    assert "session: codex-thread model: gpt-5.3-codex" in out
    assert "codex text" in out
    assert handle.agent_model == "gpt-5.3-codex"
    meta_payload = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_payload["agent_model"] == "gpt-5.3-codex"


def test_async_supervisor_survives_large_single_json_line_from_mcp(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    meta = tmp_path / "dispatch.meta.json"
    worker = tmp_path / "codex"
    worker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'---\\nstatus: completed\\n---\\nbody\\n', encoding='utf-8'"
        ")\n"
        "print(json.dumps({'type': 'thread.started', 'thread_id': 'codex-thread'}))\n"
        "huge = 'x' * 120000\n"
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'result': {'content': [{'text': huge}]}}}))\n",
        encoding="utf-8",
    )
    worker.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="asup-large-json-line",
            command=[str(worker), "exec", "--json", "-"],
            root=tmp_path,
            meta_path=meta,
            report_path=report,
            transcript_path=transcript,
            tee_output=True,
        )
    )

    assert handle.exit_code == 0
    assert handle.artifact_validation is not None
    assert handle.artifact_validation.ok
    out = capsys.readouterr().out
    assert "Separator is not found" not in out
    assert "... (120000 chars)" in out
    assert len(out) < 6000
    assert transcript.stat().st_size > 120000


def test_dispatcher_cli_fails_missing_report_contract(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    transcript = tmp_path / "dispatch.log"
    script = tmp_path / "worker.py"
    script.write_text("print('no report here')\n", encoding="utf-8")

    rc = dispatcher.main(
        [
            "run",
            "--run-id",
            "disp-test-2",
            "--root",
            str(tmp_path),
            "--report",
            str(tmp_path / "missing.md"),
            "--transcript",
            str(transcript),
            "--json",
            "--",
            sys.executable,
            str(script),
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["artifact_ok"] is False
    assert payload["artifact_errors"] == ["report_missing"]
    assert payload["state"] == "report_missing"
