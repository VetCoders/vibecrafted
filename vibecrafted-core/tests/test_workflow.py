from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibecrafted_core import workflow


def _source_dir(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    launcher = scripts / "vibecrafted"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
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
