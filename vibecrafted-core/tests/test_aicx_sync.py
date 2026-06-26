"""Tests for AICX cross-machine sync engine (Plan 08, META_22)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibecrafted_core import aicx_sync


# ---------------------------------------------------------------- helpers


def _write_json_chunk(
    root: Path,
    chunk_id: str,
    authority: str,
    content_hash: str,
    *,
    namespace: str = "VetCoders/vibecrafted",
    timestamp: str = "2026-05-12T10:00:00+00:00",
    relpath: str | None = None,
) -> Path:
    relpath = relpath or f"{chunk_id}.json"
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "chunk_id": chunk_id,
        "authority": authority,
        "content_hash": content_hash,
        "namespace": namespace,
        "timestamp": timestamp,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_md_chunk(
    root: Path,
    chunk_id: str,
    authority: str,
    content_hash: str,
    *,
    body: str = "body",
    relpath: str | None = None,
) -> Path:
    relpath = relpath or f"{chunk_id}.md"
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        f"chunk_id: {chunk_id}\n"
        f"authority: {authority}\n"
        f"content_hash: {content_hash}\n"
        f"namespace: VetCoders/vibecrafted\n"
        "timestamp: 2026-05-12T10:00:00+00:00\n"
        "---\n"
        f"{body}\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


def _make_chunk(
    chunk_id: str = "c1",
    authority: str = "aicx_agent",
    content_hash: str = "h1",
    path: Path | None = None,
) -> aicx_sync.AicxChunk:
    return aicx_sync.AicxChunk(
        chunk_id=chunk_id,
        authority=authority,
        content_hash=content_hash,
        path=path or Path("/dev/null"),
    )


# -------------------------------------------------------------- authority


def test_authority_canonical_names() -> None:
    assert aicx_sync.Authority.REPO_VERIFIED.value == "repo_verified"
    assert aicx_sync.Authority.AICX_OPERATOR.value == "aicx_operator"
    assert aicx_sync.Authority.STALE_OR_UNKNOWN.value == "stale_or_unknown"


def test_authority_from_str_canonical() -> None:
    assert (
        aicx_sync.Authority.from_str("repo_verified")
        is aicx_sync.Authority.REPO_VERIFIED
    )


def test_authority_from_str_camelcase_alias() -> None:
    # CamelCase aliases from the Plan 08 dispatch contract.
    assert (
        aicx_sync.Authority.from_str("RepoVerified")
        is aicx_sync.Authority.REPO_VERIFIED
    )
    assert (
        aicx_sync.Authority.from_str("AicxOperator")
        is aicx_sync.Authority.AICX_OPERATOR
    )
    assert (
        aicx_sync.Authority.from_str("MemexDerived")
        is aicx_sync.Authority.MEMEX_DERIVED
    )


def test_authority_from_str_unknown_raises() -> None:
    with pytest.raises(ValueError):
        aicx_sync.Authority.from_str("definitely-not-an-authority")


def test_normalize_authority_handles_empty_and_unknown() -> None:
    assert aicx_sync.normalize_authority(None) is None
    assert aicx_sync.normalize_authority("") is None
    assert aicx_sync.normalize_authority("   ") is None
    assert aicx_sync.normalize_authority("¯\\_(ツ)_/¯") is None


def test_authority_rank_ordering() -> None:
    # The complete tier table — top to bottom.
    rank = aicx_sync.authority_rank
    ordering = [
        "repo_verified",
        "aicx_operator",
        "loctree_derived",
        "aicx_agent",
        "aicx_failure",
        "semantic_guess",
        "memex_derived",
        "stale_or_unknown",
    ]
    ranks = [rank(label) for label in ordering]
    assert ranks == sorted(ranks, reverse=True), ranks
    # No accidental rank collisions in the canonical registry.
    assert len(set(ranks)) == len(ranks)


def test_authority_rank_unknown_returns_zero() -> None:
    assert aicx_sync.authority_rank("not-a-label") == 0
    assert aicx_sync.authority_rank(None) == 0


# -------------------------------------------------------------- AicxChunk


def test_aicx_chunk_canonical_authority_falls_back_for_unknown() -> None:
    chunk = _make_chunk(authority="not-a-label")
    assert chunk.authority_canonical == aicx_sync.Authority.STALE_OR_UNKNOWN.value


def test_aicx_chunk_rank_reflects_normalized_authority() -> None:
    chunk = _make_chunk(authority="RepoVerified")
    assert chunk.rank == aicx_sync.authority_rank("repo_verified")


# ------------------------------------------------------ discover_chunks


def test_discover_chunks_local_only(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    remote.mkdir()
    _write_json_chunk(local, "c1", "aicx_agent", "h1")
    _write_json_chunk(local, "c2", "aicx_operator", "h2")
    engine = aicx_sync.AicxSyncEngine(
        conflict_log=tmp_path / "log.jsonl", prompt_on_tie=False
    )
    plan = engine.discover_chunks(local, remote)
    assert plan.summary()["adds_local_to_remote"] == 2
    assert plan.summary()["adds_remote_to_local"] == 0
    assert plan.summary()["conflicts"] == 0


def test_discover_chunks_remote_only(tmp_path: Path) -> None:
    local = tmp_path / "local"
    local.mkdir()
    remote = tmp_path / "remote"
    _write_json_chunk(remote, "c1", "aicx_agent", "h1")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    assert plan.summary()["adds_remote_to_local"] == 1
    assert plan.summary()["adds_local_to_remote"] == 0


def test_discover_chunks_identical_content_skipped(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "c1", "aicx_agent", "same_hash")
    _write_json_chunk(remote, "c1", "aicx_agent", "same_hash")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    assert plan.is_empty


def test_discover_chunks_conflict_surfaced(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "c1", "aicx_agent", "hl")
    _write_json_chunk(remote, "c1", "repo_verified", "hr")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    assert plan.summary()["conflicts"] == 1


def test_discover_chunks_corrupted_reported(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    local.mkdir()
    remote.mkdir()
    bad = local / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    _write_json_chunk(local, "ok", "aicx_agent", "h1", relpath="ok.json")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    assert bad in plan.corrupted
    assert plan.summary()["adds_local_to_remote"] == 1
    # Engine must NOT crash on a corrupted chunk.


def test_discover_chunks_markdown_format(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    remote.mkdir()
    _write_md_chunk(local, "md1", "aicx_operator", "hmd")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    assert plan.summary()["adds_local_to_remote"] == 1
    assert plan.adds_local_to_remote[0].chunk_id == "md1"


def test_discover_chunks_rejects_remote_url_scheme(tmp_path: Path) -> None:
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    with pytest.raises(NotImplementedError):
        engine.discover_chunks(tmp_path, "ssh://user@host/path")
    with pytest.raises(NotImplementedError):
        engine.discover_chunks(tmp_path, "rsync://host/path")


def test_discover_chunks_accepts_file_url(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    remote.mkdir()
    _write_json_chunk(local, "c1", "aicx_agent", "h1")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, f"file://{remote}")
    assert plan.summary()["adds_local_to_remote"] == 1


# ------------------------------------------------------ resolve_conflict


def test_resolve_conflict_picks_higher_authority(tmp_path: Path) -> None:
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    local = _make_chunk(authority="aicx_agent")
    remote = _make_chunk(authority="repo_verified")
    winner = engine.resolve_conflict(local, remote)
    assert winner is remote


def test_resolve_conflict_local_higher_wins(tmp_path: Path) -> None:
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    local = _make_chunk(authority="aicx_operator")
    remote = _make_chunk(authority="memex_derived")
    winner = engine.resolve_conflict(local, remote)
    assert winner is local


def test_resolve_conflict_complete_tier_ladder(tmp_path: Path) -> None:
    """Sanity-check the full ladder beats every tier below it."""
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    ladder = [
        "repo_verified",
        "aicx_operator",
        "loctree_derived",
        "aicx_agent",
        "aicx_failure",
        "semantic_guess",
        "memex_derived",
        "stale_or_unknown",
    ]
    for i, high in enumerate(ladder):
        for low in ladder[i + 1 :]:
            local = _make_chunk(chunk_id=f"c-{high}-{low}", authority=high)
            remote = _make_chunk(chunk_id=f"c-{high}-{low}", authority=low)
            winner = engine.resolve_conflict(local, remote)
            assert winner is local, f"{high} should beat {low}"


def test_resolve_conflict_same_authority_returns_tie(tmp_path: Path) -> None:
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    local = _make_chunk(authority="aicx_agent", content_hash="hl")
    remote = _make_chunk(authority="aicx_agent", content_hash="hr")
    outcome = engine.resolve_conflict(local, remote)
    assert isinstance(outcome, aicx_sync.ConflictTie)
    assert outcome.local is local
    assert outcome.remote is remote


def test_resolve_conflict_honours_prior_local_decision(tmp_path: Path) -> None:
    log = tmp_path / "conflict-log.jsonl"
    log.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-11T00:00:00+00:00",
                "chunk_id": "tied",
                "local_authority": "aicx_agent",
                "remote_authority": "aicx_agent",
                "decision": "local",
                "decided_by": "operator",
                "reason": "prefer local for this chunk",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    engine = aicx_sync.AicxSyncEngine(conflict_log=log)
    local = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hl")
    remote = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hr")
    winner = engine.resolve_conflict(local, remote)
    assert winner is local


def test_resolve_conflict_honours_prior_remote_decision(tmp_path: Path) -> None:
    log = tmp_path / "conflict-log.jsonl"
    log.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-11T00:00:00+00:00",
                "chunk_id": "tied",
                "local_authority": "aicx_agent",
                "remote_authority": "aicx_agent",
                "decision": "remote",
                "decided_by": "operator",
                "reason": "remote was the post-incident retry",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    engine = aicx_sync.AicxSyncEngine(conflict_log=log)
    local = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hl")
    remote = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hr")
    winner = engine.resolve_conflict(local, remote)
    assert winner is remote


def test_resolve_conflict_log_last_write_wins(tmp_path: Path) -> None:
    """Multiple decisions for the same chunk_id → newest wins."""
    log = tmp_path / "conflict-log.jsonl"
    lines = [
        {
            "timestamp": "2026-05-10T00:00:00+00:00",
            "chunk_id": "tied",
            "decision": "local",
            "local_authority": "aicx_agent",
            "remote_authority": "aicx_agent",
        },
        {
            "timestamp": "2026-05-12T00:00:00+00:00",
            "chunk_id": "tied",
            "decision": "remote",
            "local_authority": "aicx_agent",
            "remote_authority": "aicx_agent",
        },
    ]
    log.write_text("\n".join(json.dumps(rec) for rec in lines) + "\n", encoding="utf-8")
    engine = aicx_sync.AicxSyncEngine(conflict_log=log)
    local = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hl")
    remote = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hr")
    winner = engine.resolve_conflict(local, remote)
    assert winner is remote  # newer decision overrides older.


def test_record_decision_appends_log(tmp_path: Path) -> None:
    log = tmp_path / "conflict-log.jsonl"
    engine = aicx_sync.AicxSyncEngine(conflict_log=log)
    local = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hl")
    remote = _make_chunk(chunk_id="tied", authority="aicx_agent", content_hash="hr")
    tie = engine.resolve_conflict(local, remote)
    assert isinstance(tie, aicx_sync.ConflictTie)
    engine.record_decision(tie, decision="local", reason="manual choice")
    assert log.exists()
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["chunk_id"] == "tied"
    assert rec["decision"] == "local"
    assert rec["decided_by"] == "operator"
    # And the engine now honours that decision on the next call.
    winner = engine.resolve_conflict(local, remote)
    assert winner is local


def test_record_decision_rejects_bad_decision(tmp_path: Path) -> None:
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    local = _make_chunk(chunk_id="t")
    remote = _make_chunk(chunk_id="t", content_hash="hr")
    tie = aicx_sync.ConflictTie(local=local, remote=remote, reason="t")
    with pytest.raises(ValueError):
        engine.record_decision(tie, decision="oops")


# --------------------------------------------------------- apply_plan


def test_apply_plan_dry_run_is_read_only(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "c1", "aicx_agent", "h1")
    _write_json_chunk(remote, "c2", "aicx_agent", "h2")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)

    # Capture pre-state.
    pre = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = engine.apply_plan(plan, dry_run=True)
    assert result.dry_run is True
    post = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert pre == post  # zero fs side effects.
    # But the result still describes the planned actions.
    assert len(result.applied) == 2


def test_apply_plan_records_adds_in_both_directions(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "only-local", "aicx_agent", "h1")
    _write_json_chunk(remote, "only-remote", "aicx_agent", "h2")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    result = engine.apply_plan(plan, dry_run=True)
    directions = sorted(a["direction"] for a in result.applied)
    assert directions == ["local_to_remote", "remote_to_local"]


def test_apply_plan_surfaces_ties(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "tied", "aicx_agent", "hl")
    _write_json_chunk(remote, "tied", "aicx_agent", "hr")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    result = engine.apply_plan(plan, dry_run=True)
    assert len(result.unresolved_ties) == 1
    assert not result.ok()


def test_apply_plan_resolves_authority_conflict(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "c1", "aicx_agent", "hl")
    _write_json_chunk(remote, "c1", "repo_verified", "hr")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    result = engine.apply_plan(plan, dry_run=True)
    assert result.ok()
    actions = [a for a in result.applied if a.get("action") == "resolve_conflict"]
    assert len(actions) == 1
    assert actions[0]["winner"] == "remote"
    assert actions[0]["winner_authority"] == "repo_verified"


def test_apply_plan_non_dry_run_no_crash(tmp_path: Path) -> None:
    """Non-dry-run path should not raise on a clean two-corpus fixture.

    The in-process engine treats the actual cross-machine copy as the
    bash wrapper's responsibility; what we verify here is that the engine
    completes the apply pass without raising on real corpora.
    """
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "c1", "aicx_agent", "h1")
    _write_json_chunk(remote, "c2", "aicx_agent", "h2")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    result = engine.apply_plan(plan, dry_run=False)
    assert result.dry_run is False
    assert not result.errors


def test_sync_result_to_jsonable_round_trip(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    _write_json_chunk(local, "c1", "aicx_agent", "h1")
    engine = aicx_sync.AicxSyncEngine(conflict_log=tmp_path / "log.jsonl")
    plan = engine.discover_chunks(local, remote)
    result = engine.apply_plan(plan, dry_run=True)
    blob = json.dumps(result.to_jsonable())
    parsed = json.loads(blob)
    assert parsed["dry_run"] is True
    assert isinstance(parsed["applied"], list)


# ------------------------------------------------------------------ cli


def test_cli_help_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = aicx_sync._cli(["--help"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "dry-run" in captured.out
    assert "apply" in captured.out


def test_cli_unknown_command_returns_two(capsys: pytest.CaptureFixture[str]) -> None:
    rc = aicx_sync._cli(["definitely-not-a-command"])
    assert rc == 2


def test_cli_dry_run_emits_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    remote.mkdir()
    _write_json_chunk(local, "c1", "aicx_agent", "h1")
    rc = aicx_sync._cli(["dry-run", str(local), str(remote)])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed["dry_run"] is True
    assert isinstance(parsed["applied"], list)


def test_cli_log_show_handles_missing_log(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(aicx_sync, "DEFAULT_CONFLICT_LOG", tmp_path / "missing.jsonl")
    rc = aicx_sync._cli(["log-show"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no decisions logged" in captured.out
