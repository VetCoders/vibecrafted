"""Tests for vibecrafted-mcp v0.1.

Synthesis stubs and helpers are tested directly; the FastMCP server
roundtrip is exercised via the in-memory client when ``fastmcp`` is
installed in the test environment, and skipped otherwise.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from vibecrafted_mcp import server, synthesis


# ---------------------------------------------------------------------------
# Synthesis stubs (pure logic — no fastmcp dependency required)
# ---------------------------------------------------------------------------


def test_live_failure_score_clean_repo_is_low() -> None:
    state: dict[str, Any] = {
        "status": {"staged": 0, "unstaged": 0, "untracked": 0},
        "behind": 0,
        "ahead": 0,
        "stashes": 0,
    }
    doctor = {"ok": 5, "warnings": 0, "failures": 0, "healthy": True}
    payload = synthesis.live_failure_score(state, doctor)
    assert payload["score"] == 0
    assert payload["band"] == "low"
    assert payload["reasons"] == []


def test_live_failure_score_dirty_tree_with_failures_is_high() -> None:
    state = {
        "status": {"staged": 4, "unstaged": 6, "untracked": 3},
        "behind": 5,
        "ahead": 12,
        "stashes": 2,
    }
    doctor = {"ok": 0, "warnings": 4, "failures": 2}
    payload = synthesis.live_failure_score(state, doctor)
    assert payload["score"] >= 60
    assert payload["band"] == "high"
    assert any("doctor" in reason for reason in payload["reasons"])
    assert any(
        "upstream" in reason or "ahead" in reason for reason in payload["reasons"]
    )


def test_live_failure_score_is_bounded() -> None:
    state = {
        "status": {"staged": 50, "unstaged": 50, "untracked": 50},
        "behind": 100,
        "ahead": 100,
        "stashes": 100,
    }
    doctor = {"failures": 50, "warnings": 50}
    payload = synthesis.live_failure_score(state, doctor)
    assert 0 <= payload["score"] <= 100


def test_unmade_decisions_flags_staged_changes() -> None:
    state = {
        "status": {"staged": 2, "unstaged": 0},
        "ahead": 0,
        "behind": 0,
        "stashes": 0,
    }
    pending = synthesis.unmade_decisions(state)
    assert any("commit" in note for note in pending)


def test_unmade_decisions_flags_behind_upstream() -> None:
    state = {
        "status": {"staged": 0, "unstaged": 0},
        "ahead": 0,
        "behind": 3,
        "stashes": 0,
    }
    pending = synthesis.unmade_decisions(state)
    assert any("upstream" in note for note in pending)


def test_unverified_claims_lists_required_senses() -> None:
    claims = synthesis.unverified_claims()
    assert any("loctree" in claim for claim in claims)
    assert any("aicx" in claim for claim in claims)


# ---------------------------------------------------------------------------
# Helpers (env override + event filtering)
# ---------------------------------------------------------------------------


def test_override_vibecrafted_home_restores_previous(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", "/sentinel")
    with server._override_vibecrafted_home(str(tmp_path)):
        assert os.environ["VIBECRAFTED_HOME"] == str(tmp_path)
    assert os.environ["VIBECRAFTED_HOME"] == "/sentinel"


def test_override_vibecrafted_home_clears_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VIBECRAFTED_HOME", raising=False)
    with server._override_vibecrafted_home(str(tmp_path)):
        assert os.environ["VIBECRAFTED_HOME"] == str(tmp_path)
    assert "VIBECRAFTED_HOME" not in os.environ


def test_filter_events_by_run_respects_limit() -> None:
    events = [
        {"run_id": "a", "ts": "1"},
        {"run_id": "b", "ts": "2"},
        {"run_id": "a", "ts": "3"},
        {"run_id": "a", "ts": "4"},
    ]
    filtered = server._filter_events_by_run(events, "a", limit=2)
    assert [event["ts"] for event in filtered] == ["1", "3"]


def test_read_run_event_tail_returns_empty_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path))
    assert server._read_run_event_tail("nope", home=str(tmp_path)) == []


def test_read_run_event_tail_filters_stream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path))
    stream = tmp_path / "control_plane" / "events.jsonl"
    stream.parent.mkdir(parents=True, exist_ok=True)
    stream.write_text(
        "\n".join(
            json.dumps(item)
            for item in [
                {"run_id": "alpha", "ts": "1", "kind": "state"},
                {"run_id": "beta", "ts": "2", "kind": "state"},
                {"run_id": "alpha", "ts": "3", "kind": "state"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    events = server._read_run_event_tail("alpha", home=str(tmp_path))
    assert [event["ts"] for event in events] == ["3", "1"]


def test_doctor_payload_unavailable_when_installer_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise ModuleNotFoundError("vetcoders_install")

    monkeypatch.setattr(server._doctor, "doctor_run", _boom)
    payload = server._doctor_payload(slim=True)
    assert payload["unavailable"] is True
    assert payload["healthy"] is True
    assert payload["findings"] == []


# ---------------------------------------------------------------------------
# FastMCP roundtrip (skipped when fastmcp is not installed)
# ---------------------------------------------------------------------------


fastmcp = pytest.importorskip("fastmcp")


def _run(coro: Any) -> Any:
    return (
        asyncio.get_event_loop().run_until_complete(coro)
        if False
        else asyncio.run(coro)
    )


def test_build_server_registers_tools_and_resources() -> None:
    mcp = server.build_server()

    async def _inspect() -> tuple[set[str], set[str]]:
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        templates = await mcp.list_resource_templates()
        tool_names = {tool.name for tool in tools}
        resource_uris = {str(item.uri) for item in resources}
        resource_uris |= {
            str(getattr(item, "uri_template", getattr(item, "uriTemplate", "")))
            for item in templates
        }
        return tool_names, resource_uris

    tool_names, resource_uris = _run(_inspect())
    assert {"vc_repo_full", "vc_doctor", "vc_board_status", "vc_init"} <= tool_names
    assert any("vibecrafted://board/runs" in uri for uri in resource_uris)
    assert any("vibecrafted://control-plane/events" in uri for uri in resource_uris)


def test_vc_repo_full_returns_ground_truth(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"], check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)

    from fastmcp import Client

    mcp = server.build_server()

    async def _call() -> Any:
        async with Client(mcp) as client:
            return await client.call_tool("vc_repo_full", {"project": str(repo)})

    result = _run(_call())
    payload = result.data
    assert payload["branch"] == "main"
    assert payload["repo"] == "repo"
    assert payload["recent_commits"]


def test_vc_init_slim_stays_within_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"], check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)

    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))

    from fastmcp import Client

    mcp = server.build_server()

    async def _call() -> Any:
        async with Client(mcp) as client:
            return await client.call_tool(
                "vc_init", {"project": str(repo), "slim": True}
            )

    result = _run(_call())
    payload = result.data
    assert "ground_truth" in payload
    assert "doctor" in payload
    assert "synthesis" in payload
    slim_meta = payload.get("_slim") or {}
    assert slim_meta.get("within_budget") is True
    assert slim_meta.get("bytes", 0) <= server.SLIM_BUDGET_BYTES


def test_board_runs_resource_returns_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))

    from fastmcp import Client

    mcp = server.build_server()

    async def _call() -> Any:
        async with Client(mcp) as client:
            return await client.read_resource("vibecrafted://board/runs")

    result = _run(_call())
    assert result
    payload = json.loads(result[0].text)
    assert "active_runs" in payload
    assert "recent_runs" in payload
