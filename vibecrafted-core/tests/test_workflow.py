from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from vibecrafted_core import workflow


def _source_dir(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    root.mkdir(parents=True)
    return root


def test_normalize_launch_spec_requires_prompt_or_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Launch requires"):
        workflow.normalize_launch_spec({"skill": "workflow"}, tmp_path)


def test_launch_workflow_returns_pid_and_logs_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    source = _source_dir(tmp_path)
    spec = workflow.normalize_launch_spec(
        {"skill": "workflow", "agent": "claude", "prompt": "go"},
        source,
    )

    monkeypatch.setattr(
        workflow,
        "_default_command",
        lambda _agent, _prompt: [
            sys.executable,
            "-c",
            "from pathlib import Path; import os; Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text('ok\\n')",
        ],
    )
    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert isinstance(payload["pid"], int)
    log_lines = Path(payload["launch_log"]).read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line).get("event") == "spawned" for line in log_lines)


def test_launch_workflow_keeps_dispatcher_launch_even_if_worker_command_is_bad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    spec = workflow.WorkflowLaunchSpec(
        agent="claude",
        mode="workflow",
        skill="workflow",
        prompt="go",
        file="",
        runtime="headless",
        root=str(tmp_path),
    )

    def _missing_command(*_args: Any, **_kwargs: Any) -> list[str]:
        return ["definitely-missing-vibecrafted-binary"]

    monkeypatch.setattr(workflow, "build_launch_command", _missing_command)
    payload = workflow.launch_workflow(spec, tmp_path)

    assert payload["accepted"] is True
    assert payload["run_id"]
    assert payload["worker_command"] == ["definitely-missing-vibecrafted-binary"]


def test_runtime_prompt_keeps_metadata_runtime_owned(tmp_path: Path) -> None:
    spec = workflow.WorkflowLaunchSpec(
        agent="codex",
        mode="workflow",
        skill="workflow",
        prompt="ship it",
        file="",
        runtime="headless",
        root=str(tmp_path),
    )

    prompt = workflow._runtime_prompt(spec)

    assert "Write your final report to the path in VIBECRAFTED_REPORT_PATH" in prompt
    assert "runtime owns VIBECRAFTED_META_PATH" in prompt
    assert "If you create or update run metadata" not in prompt


def test_launch_workflow_artifact_paths_are_terminal_truth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    source = _source_dir(tmp_path)
    spec = workflow.normalize_launch_spec(
        {"skill": "workflow", "agent": "claude", "prompt": "go"},
        source,
    )

    monkeypatch.setattr(
        workflow,
        "_default_command",
        lambda _agent, _prompt: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import os; "
                "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
                "'---\\nstatus: completed\\n---\\nbody\\n', encoding='utf-8'"
                "); "
                "print('launcher truth worker complete')"
            ),
        ],
    )

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert payload["run_id"]
    assert payload["report"]
    assert payload["transcript"]
    assert payload["meta"]
    assert payload["control_plane_identity"] == {
        "run_id": payload["run_id"],
        "session_id": payload["session_id"],
        "operator_session": payload["operator_session"],
    }

    truth = workflow.await_launch_truth(
        payload,
        timeout_seconds=10,
        interval_seconds=0.05,
        require_transcript_output=True,
    )

    assert truth["completed"] is True
    assert truth["terminal"] is True
    assert truth["artifact_ok"] is True
    assert truth["paths_exist"] == {
        "report": True,
        "transcript": True,
        "meta": True,
    }
    assert truth["run"]["state"] == "report_validated"
    assert truth["run"]["liveness"] == "terminal"
    assert truth["meta_payload"]["run_id"] == payload["run_id"]
    assert truth["meta_payload"]["terminal"] is True
    assert truth["meta_payload"]["state"] == "report_validated"
    assert truth["meta_payload"]["report"] == payload["report"]


def test_stop_run_signals_worker_pgid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "active",
            "worker_pgid": 4321,
            "liveness": "pid_alive",
            "exit_code": None,
        },
    )
    calls: dict[str, Any] = {}
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: calls.setdefault("events", []).append(kwargs),
    )
    monkeypatch.setattr(workflow.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        workflow.os,
        "killpg",
        lambda pgid, sig: calls.setdefault("killpg", []).append((pgid, sig)),
    )

    payload = workflow.stop_run("wflw-010101-0001", reason="manual")

    assert payload["accepted"] is True
    assert payload["target"] == "worker_pgid"
    assert calls["killpg"][0][0] == 4321


def test_block_run_marks_active_run_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter(["active", "blocked"])
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": next(states),
            "exit_code": None,
        },
    )
    calls: dict[str, Any] = {}
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: calls.setdefault("events", []).append(kwargs),
    )

    payload = workflow.block_run(
        "wflw-010101-0001", reason="needs creds", note="api key"
    )

    assert payload["accepted"] is True
    assert payload["run"]["state"] == "blocked"
    event = calls["events"][0]
    assert event["kind"] == "audit:block"
    assert event["payload"]["state"] == "blocked"
    assert event["payload"]["note"] == "api key"


def test_block_run_rejects_terminal_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {"run_id": run_id, "state": "completed", "exit_code": 0},
    )
    calls: dict[str, Any] = {}
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: calls.setdefault("events", []).append(kwargs),
    )

    payload = workflow.block_run("wflw-010101-0001")

    assert payload["accepted"] is False
    assert payload["reason"] == "run_terminal"
    assert calls["events"][0]["payload"]["accepted"] is False


def test_retry_run_relaunches_terminal_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "failed",
            "agent": "claude",
            "skill": "workflow",
            "mode": "workflow",
            "runtime": "headless",
            "prompt": "go",
            "file": "",
            "root": str(tmp_path),
            "exit_code": 1,
        },
    )
    captured: dict[str, Any] = {}

    def _launch(
        spec: workflow.WorkflowLaunchSpec,
        source_dir: str | Path,
        *,
        env: dict[str, str] | None = None,
        retry_of: str = "",
    ) -> dict[str, Any]:
        captured["spec"] = spec
        captured["source_dir"] = str(source_dir)
        captured["retry_of"] = retry_of
        return {"accepted": True, "run_id": "wflw-020202-0002"}

    monkeypatch.setattr(workflow, "launch_workflow", _launch)
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: captured.setdefault("events", []).append(kwargs),
    )

    payload = workflow.retry_run("wflw-010101-0001", source_dir=tmp_path)

    assert payload["accepted"] is True
    assert payload["retry_run_id"] == "wflw-020202-0002"
    assert captured["retry_of"] == "wflw-010101-0001"


def test_build_launch_command_uses_core_agent_command_not_legacy_deck(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, str] = {}

    def _fake_default(agent: str, prompt: str) -> list[str]:
        captured["agent"] = agent
        captured["prompt"] = prompt
        return ["agent-bin", prompt]

    monkeypatch.setattr(workflow, "_default_command", _fake_default)
    spec = workflow.WorkflowLaunchSpec(
        agent="claude",
        mode="implement",
        skill="implement",
        prompt="ship it",
        file="",
        runtime="headless",
        root=str(tmp_path),
    )

    command = workflow.build_launch_command(spec, tmp_path / "source")

    assert command[0] == "agent-bin"
    assert command[0:2] != [
        "bash",
        str(tmp_path / "source" / "scripts" / "vibecrafted"),
    ]
    assert "Skill: vc-implement" in captured["prompt"]
    assert "Do not call legacy Vibecrafted skill launchers" in captured["prompt"]
    assert "ship it" in captured["prompt"]


def test_research_swarm_uses_core_codex_coordinator(
    tmp_path: Path,
) -> None:
    spec = workflow.normalize_launch_spec(
        {"skill": "research", "prompt": "map the surface", "root": str(tmp_path)},
        tmp_path,
    )

    command = workflow.build_launch_command(spec, tmp_path)

    assert spec.agent == "swarm"
    assert command[:3] == [sys.executable, "-m", "vibecrafted_core.workflow_runtime"]
    assert command[3] == "research"
    assert "map the surface" in command


def test_marbles_uses_supervised_core_runtime(tmp_path: Path) -> None:
    spec = workflow.normalize_launch_spec(
        {
            "skill": "marbles",
            "agent": "codex",
            "prompt": "converge",
            "root": str(tmp_path),
            "count": 2,
            "depth": 4,
        },
        tmp_path,
    )

    command = workflow.build_launch_command(spec, tmp_path)

    assert command[:3] == [sys.executable, "-m", "vibecrafted_core.workflow_runtime"]
    assert command[3] == "marbles"
    assert command[command.index("--count") + 1] == "2"
    assert command[command.index("--depth") + 1] == "4"
