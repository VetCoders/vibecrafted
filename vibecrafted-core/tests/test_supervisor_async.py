from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from vibecrafted_core import control_plane, dispatcher
from vibecrafted_core import supervisor_async as supervisor_async_module
from vibecrafted_core.artifacts import validate_artifacts
from vibecrafted_core.control_plane import read_event_tail
from vibecrafted_core.lifecycle import RunState, transition_allowed
from vibecrafted_core.lifecycle_delivery import claim_digest_for_text
from vibecrafted_core.lifecycle_runner import (
    LifecycleRunner,
    LifecycleRunSpec,
    record_stage_worker_completion,
)
from vibecrafted_core.report_contract import CLAIM_DIGEST_ENV
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
        f"Path({str(report)!r}).write_text('---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n')\n"
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


def test_async_supervisor_heartbeats_while_worker_stdout_is_silent(
    tmp_path: Path, monkeypatch
) -> None:
    """A tool call can be quiet for minutes while its worker is healthy.

    Heartbeats must be driven by the live process clock, not by stdout lines:
    the latter disappear exactly while a long build/test/install is running.
    """
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(supervisor_async_module, "_HEARTBEAT_INTERVAL_SECONDS", 0.05)
    report = tmp_path / "quiet-report.md"
    transcript = tmp_path / "quiet-transcript.log"
    script = tmp_path / "quiet-worker.py"
    script.write_text(
        "import time\n"
        "from pathlib import Path\n"
        "time.sleep(0.18)\n"
        f"Path({str(report)!r}).write_text('---\\nrun_id: asup-quiet\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n')\n"
        "print('quiet tool finished')\n",
        encoding="utf-8",
    )
    run_id = "asup-quiet-1"

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

    heartbeats = [
        event
        for event in read_event_tail(limit=100)
        if event.get("run_id") == run_id and event.get("message") == "worker heartbeat"
    ]
    assert len(heartbeats) >= 2
    assert all(event.get("payload", {}).get("heartbeat_at") for event in heartbeats)
    # No output arrived during these pulses, so the lifecycle did not fabricate
    # FIRST_OUTPUT_SEEN or mutate the handle's state history.
    assert heartbeats[0]["payload"]["state"] == "process_spawned"
    assert handle.states.count(RunState.FIRST_OUTPUT_SEEN) == 1
    assert handle.exit_code == 0


def test_dispatcher_cli_runs_full_lifecycle(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    script = tmp_path / "worker.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(report)!r}).write_text('---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n')\n"
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


def test_dispatcher_normalizes_bare_codex_report_before_validation(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VIBECRAFTED_SKILL_NAME", "implement")
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    codex = tmp_path / "codex"
    codex.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'# Worker handoff\\n\\nSubstantive body.\\n', encoding='utf-8')\n"
        "print('done')\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)

    rc = dispatcher.main(
        [
            "run",
            "--run-id",
            "disp-bare-codex",
            "--root",
            str(tmp_path),
            "--report",
            str(report),
            "--transcript",
            str(transcript),
            "--json",
            "--",
            str(codex),
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["artifact_ok"] is True
    assert payload["state"] == "report_validated"
    report_text = report.read_text(encoding="utf-8")
    assert "run_id: disp-bare-codex" in report_text
    assert "agent: codex" in report_text
    assert "skill: implement" in report_text
    assert "status: completed" in report_text
    assert "# Worker handoff\n\nSubstantive body.\n" in report_text


def test_async_supervisor_preseeds_and_stamps_launcher_owned_identity(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VIBECRAFTED_SKILL", "implement")
    digest = "9e0d59e1dc48bc42"
    monkeypatch.setenv(CLAIM_DIGEST_ENV, digest)
    report = tmp_path / "identity.md"
    meta = tmp_path / "meta.json"
    worker = tmp_path / "codex"
    worker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "report = Path(os.environ['VIBECRAFTED_REPORT_PATH'])\n"
        "template = report.read_text(encoding='utf-8')\n"
        "assert 'run_id: identity-run' in template\n"
        "assert 'session_id: pending-unset' in template\n"
        "assert 'finalized: false' in template\n"
        "assert 'launcher_template: true' in template\n"
        f"assert 'claim_digest: {digest}' in template\n"
        "report.write_text("
        "'---\\nrun_id: copied-wrong\\nsession_id: copied-wrong\\nagent: codex\\n"
        "skill: implement\\nstatus: completed\\nfinalized: true\\n"
        "claim: identity was launcher-stamped\\n"
        "claim_digest: deadbeefdeadbeef\\n---\\n# Evidence\\n', "
        "encoding='utf-8')\n"
        "print(json.dumps({'type': 'thread.started', 'thread_id': 'codex-child'}))\n",
        encoding="utf-8",
    )
    worker.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="identity-run",
            command=[str(worker)],
            root=tmp_path,
            meta_path=meta,
            report_path=report,
        )
    )

    assert handle.artifact_validation is not None
    assert handle.artifact_validation.ok
    assert handle.agent_session_id == "codex-child"
    report_text = report.read_text(encoding="utf-8")
    assert "run_id: identity-run" in report_text
    assert "session_id: codex-child" in report_text
    assert "copied-wrong" not in report_text
    assert "launcher_template:" not in report_text
    assert "finalized: true" in report_text
    assert "claim: identity was launcher-stamped" in report_text
    assert f"claim_digest: {digest}" in report_text
    assert "deadbeefdeadbeef" not in report_text
    meta_payload = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_payload["agent_session_id"] == "codex-child"
    assert meta_payload["claim_digest"] == digest


def test_async_supervisor_preserves_explicit_resume_identity_without_new_event(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    report = tmp_path / "resume-report.md"
    transcript = tmp_path / "resume.log"
    meta = tmp_path / "resume.meta.json"
    worker = tmp_path / "codex"
    worker.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'# resumed handoff\\n', encoding='utf-8')\n"
        "print('resumed without identity banner')\n",
        encoding="utf-8",
    )
    worker.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="resume-child",
            command=[str(worker)],
            root=tmp_path,
            env={
                "VIBECRAFTED_AGENT": "codex",
                "VIBECRAFTED_AGENT_SESSION_ID": "codex-native-parent",
                "VIBECRAFTED_SESSION_ID": "runtime-child",
            },
            meta_path=meta,
            report_path=report,
            transcript_path=transcript,
        )
    )

    assert handle.agent_session_id == "codex-native-parent"
    assert handle.session_id == "runtime-child"
    meta_payload = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_payload["agent_session_id"] == "codex-native-parent"
    assert meta_payload["runtime_session_id"] == "runtime-child"


def test_async_supervisor_preserves_blocked_claim_while_filling_identity(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VIBECRAFTED_SKILL_NAME", "implement")
    report = tmp_path / "blocked.md"
    worker = tmp_path / "codex"
    worker.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'---\\nstatus: blocked\\nclaim_status: blocked\\n---\\n# Body\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    worker.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="blocked-claim",
            command=[str(worker)],
            root=tmp_path,
            report_path=report,
        )
    )

    assert handle.artifact_validation is not None
    assert handle.artifact_validation.ok
    report_text = report.read_text(encoding="utf-8")
    assert "status: blocked" in report_text
    assert "claim_status: blocked" in report_text
    assert "run_id: blocked-claim" in report_text
    assert "# Body\n" in report_text


def test_async_supervisor_normalizes_existing_report_after_nonzero_exit(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VIBECRAFTED_SKILL_NAME", "implement")
    report = tmp_path / "failed.md"
    worker = tmp_path / "codex"
    worker.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text('# Failure evidence\\n', encoding='utf-8')\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    worker.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="failed-with-report",
            command=[str(worker)],
            root=tmp_path,
            report_path=report,
        )
    )

    assert handle.exit_code == 7
    assert handle.artifact_validation is not None
    assert handle.artifact_validation.ok
    report_text = report.read_text(encoding="utf-8")
    assert "status: failed" in report_text
    assert "# Failure evidence\n" in report_text


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
        "report = (\n"
        "  '---\\n'\n"
        "  'run_id: disp-test-prompt-file\\n'\n"
        "  'agent: python\\n'\n"
        "  'skill: test\\n'\n"
        "  'status: completed\\n'\n"
        "  'claim_status: completed\\n'\n"
        "  '---\\n'\n"
        "  + body\n"
        ")\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text(report, encoding='utf-8')\n"
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
    report_text = report.read_text(encoding="utf-8")
    assert report_text.startswith("---\n")
    assert "line one\nline two\n" in report_text
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
        f"Path({str(report)!r}).write_text('---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n')\n"
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
        f"Path({str(report)!r}).write_text('---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n')\n",
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
    monkeypatch.delenv("VIBECRAFTED_AGENT", raising=False)
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    meta = tmp_path / "dispatch.meta.json"
    claude = tmp_path / "claude"
    claude.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n', encoding='utf-8'"
        ")\n"
        "print(json.dumps({'type': 'system', 'session_id': 'sess-123', "
        "'model': 'claude-opus-4-8'}))\n"
        "print(json.dumps({'type': 'assistant', 'message': {'content': ["
        "{'type': 'text', 'text': 'visible text from claude'}"
        "]}}))\n"
        "print(json.dumps({'type': 'result', 'result': 'done', 'usage': {"
        "'input_tokens': 10, 'cache_read_input_tokens': 3, "
        "'cache_creation_input_tokens': 2, 'output_tokens': 5}, "
        "'total_cost_usd': 0.02}))\n",
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
    assert "tokens_cache_write: 2" in out
    # input 10 + output 5; cached 3 is subset of input (not double-counted)
    assert "tokens_total: 15" in out
    assert '"type": "assistant"' not in out
    transcript_text = transcript.read_text(encoding="utf-8")
    assert '"type": "assistant"' in transcript_text
    assert handle.agent_session_id == "sess-123"
    assert handle.agent_model == "claude-opus-4-8"
    assert handle.resume_command.endswith("claude --resume sess-123")
    meta_payload = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_payload["agent_session_id"] == "sess-123"
    assert meta_payload["agent_model"] == "claude-opus-4-8"
    assert meta_payload["tokens_cached_input"] == 3
    assert meta_payload["tokens_cache_write"] == 2
    assert meta_payload["tokens_total"] == 15
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
        "'---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n', encoding='utf-8'"
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


def test_async_supervisor_records_requested_model_next_to_reported_model(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VIBECRAFTED_AGENT", "gemini")
    monkeypatch.setenv("VIBECRAFTED_MODEL_REQUESTED", "gemini-pro")
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    meta = tmp_path / "dispatch.meta.json"
    worker = tmp_path / "gemini"
    worker.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
        "'---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n', encoding='utf-8'"
        ")\n"
        "print('model: gemini-real')\n",
        encoding="utf-8",
    )
    worker.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="asup-gemini-model-requested",
            command=[str(worker)],
            root=tmp_path,
            meta_path=meta,
            report_path=report,
            transcript_path=transcript,
            tee_output=True,
        )
    )

    assert handle.exit_code == 0
    assert handle.agent_model == "gemini-real"
    assert handle.model_requested == "gemini-pro"
    assert handle.model_override_skipped is True
    out = capsys.readouterr().out
    assert "model: gemini-real" in out
    assert "model_requested: gemini-pro" in out
    meta_payload = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_payload["agent_model"] == "gemini-real"
    assert meta_payload["model_requested"] == "gemini-pro"
    assert meta_payload["model_override_supported"] is False
    assert meta_payload["model_override_skipped"] is True
    assert meta_payload["model_override_skip_reason"] == "unsupported_agent_model_flag"


def test_async_supervisor_salvages_grok_report_from_streaming_json(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("VIBECRAFTED_AGENT", raising=False)
    report = tmp_path / "dispatch-report.md"
    transcript = tmp_path / "dispatch.log"
    meta = tmp_path / "dispatch.meta.json"
    grok = tmp_path / "grok"
    grok.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print('ERROR worker quit with fatal: Transport channel closed, when Auth(AuthorizationRequired)')\n"
        "print(json.dumps({'type': 'thought', 'data': 'thinking'}))\n"
        "print(json.dumps({'type': 'text', 'data': 'Ok'}))\n"
        "print(json.dumps({'type': 'text', 'data': '.'}))\n"
        "print(json.dumps({'type': 'end', 'sessionId': 'grok-session'}))\n",
        encoding="utf-8",
    )
    grok.chmod(0o755)

    handle = asyncio.run(
        AsyncSupervisor().run(
            run_id="asup-grok-visible",
            command=[str(grok), "--output-format", "streaming-json", "--single"],
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
    assert "---\nrunner: vibecrafted" in out
    assert "status: launching" in out
    assert "status: report_validated" in out
    assert "thinking" in out
    assert "Ok." in out
    assert "Transport channel" not in out
    assert "None" not in out
    assert "session_id: grok-session" in out
    assert "tokens_input: 0" in out
    assert "tokens_output: 0" in out
    assert "cost_usd: unknown" in out
    report_text = report.read_text(encoding="utf-8")
    assert "fallback_report: true" in report_text
    assert "tokens_input: 0" in report_text
    assert "tokens_output: 0" in report_text
    assert "cost_usd: unknown" in report_text
    assert "Ok." in report_text
    assert "thinking" not in report_text
    assert "Transport channel" not in report_text
    meta_payload = json.loads(meta.read_text(encoding="utf-8"))
    assert meta_payload["agent_session_id"] == "grok-session"
    assert meta_payload["exit_code"] == 0
    assert meta_payload["status"] == "completed"


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
        "'---\\nrun_id: asup-test\\nagent: python\\nskill: test\\nstatus: completed\\nclaim_status: completed\\n---\\nbody\\n', encoding='utf-8'"
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
    template = (tmp_path / "missing.md").read_text(encoding="utf-8")
    assert "run_id: disp-test-2" in template
    assert "session_id: pending-unset" in template
    assert "finalized: false" in template
    assert "launcher_template: true" in template


def test_dispatcher_cli_records_lifecycle_worker_death(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "status": "launching",
                "stages": [{"id": "implement", "launch": {"run_id": "disp-death-1"}}],
            }
        ),
        encoding="utf-8",
    )
    script = tmp_path / "worker.py"
    script.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")

    rc = dispatcher.main(
        [
            "run",
            "--run-id",
            "disp-death-1",
            "--root",
            str(tmp_path),
            "--report",
            str(tmp_path / "never-written.md"),
            "--transcript",
            str(tmp_path / "dispatch.log"),
            "--lifecycle-state",
            str(state_path),
            "--json",
            "--",
            sys.executable,
            str(script),
        ]
    )

    assert rc == 3
    # Push-side report-on-death: the death landed in the lifecycle state
    # itself, readable by purely passive consumers with no status verb.
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    worker_exit = reloaded["stages"][0]["worker_exit"]
    assert worker_exit["exit_code"] == 3
    assert worker_exit["artifact_ok"] is False
    assert reloaded["stage_worker_exit"]["stage"] == "implement"
    assert reloaded["stage_worker_exit"]["run_id"] == "disp-death-1"
    capsys.readouterr()


def test_default_no_await_dispatcher_reconciles_finalized_and_refusals(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The real default path, not the opt-in synchronous runner, owns f/n."""
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {"ok": True, "command": ["loct", "context"]},
    )
    # The dispatcher's finish hook triages with ambient os.environ. Under a
    # live vc-frame session env that fires real dump-screen/bucket-session
    # actions at the operator's terminal. Scrub the blast surface.
    monkeypatch.setenv("VIBECRAFTED_TRIAGE_RUN", "0")
    for hazard in (
        "ZELLIJ_SESSION_NAME",
        "ZELLIJ_PANE_ID",
        "VC_FRAME_SESSION_NAME",
        "VC_FRAME_PANE_ID",
        "VC_FRAME_TAB_NAME",
    ):
        monkeypatch.delenv(hazard, raising=False)

    mission = "default lifecycle dispatch must settle from validated proof"
    mission_digest = claim_digest_for_text(mission)
    cases = (
        ("matching", mission_digest, 0, "finalized", "f"),
        ("mismatch", "deadbeefdeadbeef", 0, "needs_attention", "n"),
        ("missing", None, 2, "needs_attention", "n"),
    )

    for name, report_digest, expected_rc, expected_verdict, expected_tui in cases:
        case_dir = tmp_path / name
        repo = case_dir / "repo"
        home = case_dir / "home"
        repo.mkdir(parents=True)
        monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=VC Test",
                "-c",
                "user.email=vc@example.test",
                "commit",
                "-m",
                "initial",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        stage_run_id = f"default-dispatch-{name}"
        runtime_dir = home / "control_plane" / "runtime_runs" / stage_run_id
        artifact_dir = home / "artifacts" / "tests" / stage_run_id
        report = artifact_dir / "report.md"
        transcript = artifact_dir / "transcript.log"
        meta = runtime_dir / "meta.json"
        seen_state_paths: list[str] = []

        def fake_launcher(
            spec,
            _source_dir,
            *,
            _runtime_dir=runtime_dir,
            _artifact_dir=artifact_dir,
            _seen_state_paths=seen_state_paths,
            _meta=meta,
            _stage_run_id=stage_run_id,
            _report=report,
            _transcript=transcript,
        ):
            # Default-arg capture avoids B023 loop-variable binding in the body.
            _runtime_dir.mkdir(parents=True)
            _artifact_dir.mkdir(parents=True)
            _seen_state_paths.append(spec.lifecycle_state_path)
            _meta.write_text(
                json.dumps(
                    {
                        "run_id": _stage_run_id,
                        "claim_digest": spec.claim_digest,
                    }
                ),
                encoding="utf-8",
            )
            return {
                "accepted": True,
                "run_id": _stage_run_id,
                "report": str(_report),
                "transcript": str(_transcript),
                "meta": str(_meta),
            }

        state = asyncio.run(
            LifecycleRunner(launcher=fake_launcher).run(
                LifecycleRunSpec(
                    workflow_id="vc-implement",
                    agent="codex",
                    prompt=mission,
                    root=str(repo),
                )
            )
        )
        state_path = Path(str(state["state_path"]))
        assert state["await_stages"] is False
        assert seen_state_paths == [str(state_path)]

        worker = case_dir / "worker.py"
        if report_digest is None:
            worker.write_text("print('exit zero without report')\n", encoding="utf-8")
        else:
            report_text = "\n".join(
                [
                    "---",
                    f"run_id: {stage_run_id}",
                    "agent: codex",
                    "skill: implement",
                    "status: completed",
                    "claim_status: completed",
                    "finalized: true",
                    "claim: default lifecycle stage completed",
                    f"claim_digest: {report_digest}",
                    "---",
                    "",
                    "Validated default-mode stage output.",
                    "",
                ]
            )
            worker.write_text(
                "from pathlib import Path\n"
                "import os\n"
                f"Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text({report_text!r}, encoding='utf-8')\n"
                "print('default lifecycle worker complete')\n",
                encoding="utf-8",
            )

        rc = dispatcher.main(
            [
                "run",
                "--run-id",
                stage_run_id,
                "--root",
                str(repo),
                "--meta",
                str(meta),
                "--report",
                str(report),
                "--transcript",
                str(transcript),
                "--lifecycle-state",
                str(state_path),
                "--json",
                "--",
                sys.executable,
                str(worker),
            ]
        )
        assert rc == expected_rc
        summary = json.loads(capsys.readouterr().out)
        reloaded = json.loads(state_path.read_text(encoding="utf-8"))
        snapshot = json.loads(
            (control_plane.run_snapshot_dir() / f"{stage_run_id}.json").read_text(
                encoding="utf-8"
            )
        )
        assert snapshot["settlement_verdict"] == expected_verdict
        assert snapshot["settlement_tui"] == expected_tui

        if name == "matching":
            assert summary["lifecycle_reconciled"] is True
            assert reloaded["proof_state"] == "passed"
            assert reloaded["delivery_state"] == "sealed"
            assert reloaded["stages"][0]["worker_completion"]["processed"] is True
            assert reloaded["stages"][0]["lifecycle_seal"]["granted"] is True
            seal_path = runtime_dir / "delivery-seal.json"
            first_seal = seal_path.read_bytes()
            assert record_stage_worker_completion(state_path, stage_run_id, summary)
            assert seal_path.read_bytes() == first_seal
        elif name == "mismatch":
            assert summary["lifecycle_reconciled"] is True
            assert reloaded["proof_state"] == "undeclared"
            assert reloaded["delivery_state"] == "unverified"
            refusal = reloaded["stages"][0]["lifecycle_seal"]
            assert refusal["granted"] is False
            assert refusal["reason"].startswith("claim_digest_mismatch")
            assert not (runtime_dir / "delivery-seal.json").exists()
        else:
            assert summary["lifecycle_reconciled"] is True
            assert reloaded["stages"][0]["worker_exit"]["artifact_ok"] is False
            assert not (runtime_dir / "delivery-seal.json").exists()


def test_origin_pane_is_stamped_only_from_the_runs_own_tab() -> None:
    """2026-07-25: dispatched runs stamped the dispatcher's pane ("1") as
    origin_pane_id; triage aimed dump-screen at it and captured nothing. The
    pane env is the run's own only when the env also claims the run's tab."""
    fields = supervisor_async_module._origin_fields_from_env(
        {
            "ZELLIJ_SESSION_NAME": "vc-workspace",
            "ZELLIJ_PANE_ID": "1",
            "VIBECRAFTED_RUN_ID": "work-260725-020101-07000",
        }
    )
    assert fields["origin_session"] == "vc-workspace"
    assert fields["origin_tab"] == "work-260725-020101-07000"
    assert "origin_pane_id" not in fields


def test_origin_pane_survives_when_env_sits_in_the_run_tab() -> None:
    fields = supervisor_async_module._origin_fields_from_env(
        {
            "VC_FRAME_SESSION_NAME": "vc-workspace",
            "VC_FRAME_TAB_NAME": "work-1",
            "VC_FRAME_PANE_ID": "terminal_7",
            "VIBECRAFTED_RUN_ID": "work-1",
        }
    )
    assert fields["origin_tab"] == "work-1"
    assert fields["origin_pane_id"] == "terminal_7"


def test_operator_tab_env_never_reaches_the_stamp() -> None:
    """A leaked operator VC_FRAME_TAB_NAME must not become the run's origin_tab
    — a meta-stamped tab bypasses plan_triage's foreign-tab refusal, so triage
    would capture and close the operator's own tab."""
    fields = supervisor_async_module._origin_fields_from_env(
        {
            "VC_FRAME_SESSION_NAME": "vc-workspace",
            "VC_FRAME_TAB_NAME": "operator-tab",
            "VC_FRAME_PANE_ID": "terminal_1",
            "VIBECRAFTED_RUN_ID": "work-2",
        }
    )
    assert fields["origin_tab"] == "work-2"
    assert "origin_pane_id" not in fields
