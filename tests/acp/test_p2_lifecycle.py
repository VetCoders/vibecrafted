from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from vibecrafted_acp.bridge import RuntimeBridge
from vibecrafted_acp.server import ACPServer
from vibecrafted_core import control_plane
from vibecrafted_core.workflows.registry import WORKFLOW_DEFINITIONS


def _messages(output: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in output.getvalue().splitlines() if line]


def _request(
    server: ACPServer,
    *,
    request_id: int,
    method: str,
    params: dict[str, object],
) -> None:
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
    )


def _response(output: io.StringIO, request_id: int) -> dict[str, Any]:
    message = next(item for item in _messages(output) if item.get("id") == request_id)
    result = message.get("result")
    assert isinstance(result, dict)
    return result


def _run_two_stage_fixture(
    tmp_path: Path,
) -> tuple[str, RuntimeBridge, ACPServer, io.StringIO]:
    output = io.StringIO()
    bridge = RuntimeBridge(dry_run=True)
    server = ACPServer(bridge=bridge, output=output)
    _request(server, request_id=0, method="initialize", params={})
    _request(
        server,
        request_id=1,
        method="session/new",
        params={
            "cwd": str(tmp_path),
            "mcpServers": [],
            "_meta": {
                "vibecrafted": {
                    "agent": "codex",
                    "skill": "ship",
                    "runtime": "terminal",
                    "dryStages": 2,
                }
            },
        },
    )
    session_id = str(_response(output, 1)["sessionId"])
    _request(
        server,
        request_id=2,
        method="session/prompt",
        params={
            "sessionId": session_id,
            "prompt": [{"type": "text", "text": "/ship prove the fixture"}],
        },
    )
    server.wait()
    return session_id, bridge, server, output


def test_parent_lifecycle_receipt_plan_and_slash_catalog(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    session_id, bridge, server, output = _run_two_stage_fixture(tmp_path)
    session = server.sessions[session_id]

    assert session.stage == "implement"
    assert len(session.child_run_ids) == 2
    assert set(session.child_run_ids) == set(bridge._dry_runs)
    assert session_id not in bridge._dry_runs

    prompt_result = _response(output, 2)
    assert prompt_result["stopReason"] == "end_turn"
    meta = prompt_result["_meta"]["vibecrafted"]
    assert meta == {
        "parent_run_id": session_id,
        "child_run_ids": session.child_run_ids,
        "stage": "implement",
    }

    messages = _messages(output)
    plans = [
        item["params"]["update"]
        for item in messages
        if item.get("method") == "session/update"
        and item["params"]["update"]["sessionUpdate"] == "plan"
    ]
    assert len(plans) == 4
    assert [entry["status"] for entry in plans[-1]["entries"][:3]] == [
        "completed",
        "completed",
        "pending",
    ]

    catalog = next(
        item["params"]["update"]
        for item in messages
        if item.get("method") == "session/update"
        and item["params"]["update"]["sessionUpdate"] == "available_commands_update"
    )
    commands = {command["name"]: command for command in catalog["availableCommands"]}
    assert set(commands) == {"ship", *WORKFLOW_DEFINITIONS}
    assert commands["implement"]["_meta"]["vibecrafted"]["argv"] == [
        "vibecrafted",
        "implement",
    ]

    run_dir = control_plane.control_plane_home() / "lifecycle_runs" / session_id
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["run_id"] == session_id
    assert state["manifest"]["id"] == "vc-ship"
    assert state["baton"]["previous_reports"] == []
    assert state["baton"]["dou_index"] is None
    assert [
        stage["launch"]["run_id"] for stage in state["stages"]
    ] == session.child_run_ids
    transcript = (run_dir / "transcript.log").read_text(encoding="utf-8")
    assert f"child_run_id={session.child_run_ids[0]}" in transcript
    assert f"child_run_id={session.child_run_ids[1]}" in transcript
    assert (run_dir / "report.md").is_file()


def test_load_rehydrates_killed_parent_and_continues_with_child(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    session_id, _bridge, _server, _output = _run_two_stage_fixture(tmp_path)

    resumed_output = io.StringIO()
    resumed_bridge = RuntimeBridge(dry_run=True)
    resumed_server = ACPServer(bridge=resumed_bridge, output=resumed_output)
    _request(resumed_server, request_id=10, method="initialize", params={})
    _request(
        resumed_server,
        request_id=11,
        method="session/load",
        params={
            "sessionId": session_id,
            "cwd": str(tmp_path),
            "mcpServers": [],
        },
    )
    loaded = _response(resumed_output, 11)
    assert loaded["_meta"]["vibecrafted"]["restored_from"] == [
        "report",
        "transcript",
    ]
    assert len(resumed_server.sessions[session_id].child_run_ids) == 2
    assert any(
        item.get("method") == "session/update"
        and item["params"]["update"]["sessionUpdate"] == "agent_message_chunk"
        and "child_run_id=" in item["params"]["update"]["content"]["text"]
        for item in _messages(resumed_output)
    )

    resume_output = io.StringIO()
    resume_bridge = RuntimeBridge(dry_run=True)
    resume_server = ACPServer(bridge=resume_bridge, output=resume_output)
    _request(resume_server, request_id=20, method="initialize", params={})
    _request(
        resume_server,
        request_id=21,
        method="session/resume",
        params={"sessionId": session_id, "cwd": str(tmp_path)},
    )
    resumed = _response(resume_output, 21)
    assert resumed["_meta"]["vibecrafted"]["restored_from"] == [
        "report",
        "transcript",
    ]
    assert not any(
        item.get("method") == "session/update"
        and item["params"]["update"]["sessionUpdate"] == "agent_message_chunk"
        for item in _messages(resume_output)
    )

    _request(
        resume_server,
        request_id=22,
        method="session/prompt",
        params={
            "sessionId": session_id,
            "prompt": [{"type": "text", "text": "/implement continue after restart"}],
        },
    )
    resume_server.wait()
    continued = _response(resume_output, 22)
    assert continued["stopReason"] == "end_turn"
    child_run_ids = continued["_meta"]["vibecrafted"]["child_run_ids"]
    assert len(child_run_ids) == 3
    assert child_run_ids[-1] in resume_bridge._dry_runs
    assert continued["_meta"]["vibecrafted"]["stage"] == "implement"


def test_resume_fails_closed_when_transcript_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    session_id, _bridge, _server, _output = _run_two_stage_fixture(tmp_path)
    run_dir = control_plane.control_plane_home() / "lifecycle_runs" / session_id
    (run_dir / "transcript.log").unlink()

    output = io.StringIO()
    server = ACPServer(bridge=RuntimeBridge(dry_run=True), output=output)
    _request(server, request_id=20, method="initialize", params={})
    _request(
        server,
        request_id=21,
        method="session/resume",
        params={"sessionId": session_id, "cwd": str(tmp_path)},
    )

    error = next(item["error"] for item in _messages(output) if item.get("id") == 21)
    assert error["code"] == -32004
    assert "missing non-empty artifacts: transcript" in error["message"]
