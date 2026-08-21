"""Session-chain contract: loud empty, exact project, no implicit native resume."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from vibecrafted_core.aicx_session_chain import (
    MCP_RETRIEVAL_TOOLS,
    MCP_SESSION_CHAIN_TOOLS,
    CliSessionChain,
    SessionChain,
    SessionChainError,
    SessionListResult,
    SessionRecord,
    assemble_resume_continuity_pack,
    matches_exact_project,
    mcp_session_chain_contract,
    pack_contains_recover_instruction,
    project_filter_for_root,
)


class MemoryChain(SessionChain):
    def __init__(
        self,
        sessions: list[SessionRecord] | None = None,
        *,
        empty_kind: str = "none",
        scanned: int | None = None,
        continuity: str = "## NOW\npeer work\n## PEERS\n## DECISIONS\n## TASKS\n## SOURCES\n## INDEX HEALTH\nready",
        show: dict | None = None,
        extract: str = "user: hello\nassistant: world",
        show_error: SessionChainError | None = None,
        extract_error: SessionChainError | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self._sessions = list(sessions or [])
        self._empty_kind = empty_kind
        self._scanned = scanned if scanned is not None else len(self._sessions)
        self._continuity = continuity
        self._show = show or {}
        self._extract = extract
        self._show_error = show_error
        self._extract_error = extract_error
        self._warnings = list(warnings or [])
        self.list_calls: list[dict[str, object]] = []

    def list_sessions(self, **kwargs: object) -> SessionListResult:
        self.list_calls.append(kwargs)
        project = str(kwargs.get("project") or "")
        return SessionListResult(
            sessions=list(self._sessions),
            project_filter=project,
            empty_kind=self._empty_kind,  # type: ignore[arg-type]
            scanned=self._scanned,
            matched=len(self._sessions),
            warnings=list(self._warnings),
        )

    def show_session(self, session_id: str) -> dict:
        if self._show_error:
            raise self._show_error
        return {"session_id": session_id, **self._show}

    def extract_session(
        self, agent: str, session_id: str, *, conversation: bool = True
    ) -> str:
        if self._extract_error:
            raise self._extract_error
        return self._extract

    def continuity_pack(self, **kwargs: object) -> str:
        return self._continuity


def test_mcp_contract_names_the_missing_session_chain() -> None:
    contract = mcp_session_chain_contract()
    assert contract["mcp_tools"] == list(MCP_SESSION_CHAIN_TOOLS)
    assert "aicx_sessions" in contract["mcp_tools"]
    assert "aicx_extract" in contract["mcp_tools"]
    assert "aicx_continuity" in contract["mcp_tools"]
    assert contract["retrieval_tools_unchanged"] == list(MCP_RETRIEVAL_TOOLS)
    assert contract["native_resume"].startswith("only when operator")
    assert "recover previous session" in contract["pack_must_not"]


def test_exact_project_does_not_match_sibling_repo() -> None:
    root = Path("/tmp/codescribe")
    keep = SessionRecord(
        session_id="keep-1",
        agent="claude",
        project="vetcoders/codescribe",
        repo_path="/tmp/codescribe",
    )
    sibling = SessionRecord(
        session_id="leak-1",
        agent="claude",
        project="vetcoders/codescribe-rs",
        repo_path="/tmp/codescribe-rs",
    )
    foreign = SessionRecord(
        session_id="gpt-export",
        agent="chatgpt",
        project="exports/chatgpt",
        repo_path="/tmp/chatgpt-export",
    )
    assert matches_exact_project(keep, root=root, project_filter="/codescribe")
    assert not matches_exact_project(sibling, root=root, project_filter="/codescribe")
    assert not matches_exact_project(foreign, root=root, project_filter="/codescribe")


def test_list_without_project_is_missing_filter_not_silent_empty() -> None:
    chain = CliSessionChain("/usr/bin/false")
    result = chain.list_sessions(project=None)
    assert result.empty_kind == "missing_filter"
    assert result.matched == 0
    assert any("missing_filter" in warning for warning in result.warnings)


def test_list_empty_project_is_loud(tmp_path: Path) -> None:
    repo = tmp_path / "vibecrafted"
    repo.mkdir()
    calls: list[list[str]] = []

    def runner(
        cmd: list[str], timeout: float, cwd: Path | None
    ) -> tuple[int, str, str]:
        calls.append(list(cmd))
        if cmd[1:3] == ["sessions", "list"]:
            foreign = [
                {
                    "session_id": "chatgpt-export-1",
                    "agent": "chatgpt",
                    "project": "exports/chatgpt",
                    "repo_path": str(tmp_path / "chatgpt"),
                    "updated_at": "2026-08-16T00:00:00Z",
                    "title": "ChatGPT export",
                }
            ]
            return 0, json.dumps(foreign), ""
        return 1, "", "unused"

    chain = CliSessionChain("aicx", runner=runner)
    result = chain.list_sessions(project="/vibecrafted", root=repo)
    assert result.empty_kind == "empty_project"
    assert result.matched == 0
    assert result.scanned == 1
    assert any(
        warning.startswith("empty_project:/vibecrafted:") for warning in result.warnings
    )
    assert result.sessions == []


def test_show_and_extract_are_loud_on_ambiguous_id() -> None:
    def runner(
        cmd: list[str], timeout: float, cwd: Path | None
    ) -> tuple[int, str, str]:
        return 2, "", "ambiguous prefix matches 3 sessions"

    chain = CliSessionChain("aicx", runner=runner)
    with pytest.raises(SessionChainError) as show_err:
        chain.show_session("abc")
    assert show_err.value.kind == "ambiguous_id"
    with pytest.raises(SessionChainError) as extract_err:
        chain.extract_session("claude", "abc")
    assert extract_err.value.kind == "ambiguous_id"


def test_resume_pack_never_selects_native_even_with_same_agent(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    live = SessionRecord(
        session_id="live-bbbb-2222",
        agent="claude",
        project="repo",
        repo_path=str(repo),
        title="still resumable",
        updated_at="2026-08-16T12:00:00Z",
        live=True,
    )
    pack = assemble_resume_continuity_pack(
        agent="claude",
        root=repo,
        hours=48,
        context_file=tmp_path / "pack.md",
        meta_file=tmp_path / "pack.meta.json",
        chain=MemoryChain([live]),
        now=dt.datetime(2026, 8, 17, 12, 0, tzinfo=dt.timezone.utc),
    )
    assert pack.mode == "new_session"
    assert pack.session_id == ""
    assert pack.session_count == 1
    assert "live-bbbb-2222" in pack.body
    assert "prefer native resume" not in pack.body.lower()
    assert not pack_contains_recover_instruction(pack.body)
    assert "This pack is not that signal." in pack.body
    meta = json.loads(pack.meta_file.read_text(encoding="utf-8"))
    assert meta["mode"] == "new_session"
    assert meta["session_id"] == ""


def test_resume_pack_empty_project_is_loud_not_foreign_catalog(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "emptyproj"
    repo.mkdir()
    pack = assemble_resume_continuity_pack(
        agent="claude",
        root=repo,
        hours=48,
        context_file=tmp_path / "pack.md",
        meta_file=tmp_path / "pack.meta.json",
        chain=MemoryChain(
            [],
            empty_kind="empty_project",
            scanned=4,
            warnings=["empty_project:/emptyproj:scanned=4:matched=0"],
        ),
    )
    assert pack.empty_kind == "empty_project"
    assert "empty_project" in pack.body
    assert "chatgpt" not in pack.body.lower()
    assert "parser miss" in pack.body


def test_explicit_operator_session_is_background_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    pack = assemble_resume_continuity_pack(
        agent="claude",
        root=repo,
        hours=48,
        context_file=tmp_path / "pack.md",
        meta_file=tmp_path / "pack.meta.json",
        chain=MemoryChain([]),
        operator_session_id="explicit-id-999",
    )
    assert pack.mode == "native_resume"
    assert pack.session_id == "explicit-id-999"
    assert "operator_session: `explicit-id-999`" in pack.body
    assert not pack_contains_recover_instruction(pack.body)


def test_project_filter_for_root_is_slash_repo() -> None:
    assert (
        project_filter_for_root(Path("/Volumes/x/vetcoders/vibecrafted"))
        == "/vibecrafted"
    )
