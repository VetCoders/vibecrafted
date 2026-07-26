from __future__ import annotations

import argparse
import json
import subprocess
import textwrap
from pathlib import Path

from vibecrafted_core import cli, guard, trust, workflow
from vibecrafted_core.settlement import board_fxn_counts
from vibecrafted_core.workflows import registry


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Trust Fixture")
    _git(repo, "config", "user.email", "agents@vetcoders.io")
    return repo


def _commit(repo: Path, message: str, files: dict[str, str]) -> str:
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        _git(repo, "add", rel)
    # GIT_EDITOR workaround for multi-line via -m multiple times
    parts = message.strip().split("\n\n", 1)
    subject = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""
    cmd = ["commit", "-m", subject]
    if body:
        cmd.extend(["-m", body])
    _git(repo, *cmd)
    return _git(repo, "rev-parse", "HEAD")


def _fair_message(agent: str = "codex") -> str:
    return textwrap.dedent(
        f"""\
        [{agent}/workflow] feat(trust): prove honest envelope

        Implements the focused path with pytest coverage on the real helper.

        Authored-By: {agent} <agents@vetcoders.io>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        time: 2026-07-25T12:00:00+02:00
        runtime: terminal
        """
    )


def _unfair_message() -> str:
    return textwrap.dedent(
        """\
        [claude/workflow] feat(trust): all done production ready

        Authored-By: codex <agents@vetcoders.io>
        Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        time: 2026-07-25T12:00:00+02:00
        runtime: terminal
        """
    )


def test_registry_exposes_trust_as_read_only_and_guard_as_enforcer() -> None:
    definition = registry.workflow_definition("trust")

    assert definition is not None
    assert definition.cadence == "read"
    assert definition.can_modify_code is False
    assert definition.tooling[-1] == "vc-trust"

    guard_def = registry.workflow_definition("guard")
    assert guard_def is not None
    assert guard_def.cadence == "read"
    assert guard_def.can_modify_code is False
    assert "vc-guard" in guard_def.tooling

    assert {
        verdict: trust.tui_key_for(terminal)
        for verdict, terminal in trust.VERDICT_TO_SETTLEMENT.items()
    } == {
        "pass": "f",
        "pass-with-gaps": "n",
        "block": "x",
    }


def test_core_command_deck_exposes_trust_and_guard_launchers(capsys) -> None:
    assert cli.main(["trust", "--help"]) == 0
    trust_out = capsys.readouterr().out
    assert "vibecrafted trust <claude|codex|agy|junie|grok>" in trust_out
    assert "version 1.0.0 · READ" in trust_out

    assert cli.main(["guard", "--help"]) == 0
    guard_out = capsys.readouterr().out
    assert "vibecrafted guard" in guard_out
    assert "READ" in guard_out


def test_note_appends_claim_evidence_and_projects_settlement(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, _fair_message(), {"proof.txt": "proof\n"})
    crafted_home = tmp_path / "crafted"
    run_dir = crafted_home / "control_plane" / "runtime_runs" / "run-trust"
    run_dir.mkdir(parents=True)
    meta = run_dir / "meta.json"
    meta.write_text(
        json.dumps(
            {
                "run_id": "run-trust",
                "state": "completed",
                "exit_code": 0,
                "agent": "codex",
                "skill": "workflow",
            }
        ),
        encoding="utf-8",
    )
    snapshot = crafted_home / "control_plane" / "runs" / "run-trust.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(
        json.dumps(
            {
                "run_id": "run-trust",
                "state": "completed",
                "exit_code": 0,
            }
        ),
        encoding="utf-8",
    )
    journal = tmp_path / "journal.jsonl"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))

    entry = trust.note_verdict(
        repo=repo,
        journal=journal,
        sha=sha,
        verdict="pass-with-gaps",
        run_id="run-trust",
        claims=[
            {
                "claim": "the focused test proves the path",
                "grade": "strong",
                "evidence": "negative fixture failed, then passed",
            }
        ],
    )

    assert entry["verdict"] == "pass-with-gaps"
    assert entry["settlement_tui"] == "n"
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    assert records == [entry]
    settled = json.loads(meta.read_text())
    assert settled["settlement_verdict"] == "needs_attention"
    assert settled["settlement_source"] == "trust"
    assert settled["settlement_tui"] == "n"
    assert board_fxn_counts([settled]) == {"f": 0, "x": 0, "n": 1}
    projected = json.loads(snapshot.read_text())
    assert projected["settlement_source"] == "trust"
    assert projected["settlement_revision"] == 1
    assert board_fxn_counts([projected]) == {"f": 0, "x": 0, "n": 1}
    settlement_events = [
        json.loads(line)
        for line in (crafted_home / "control_plane" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if json.loads(line).get("kind") == "settlement.changed"
    ]
    assert len(settlement_events) == 1
    assert settlement_events[0]["payload"] == {
        "schema": "vibecrafted.settlement-event.v1",
        "run_id": "run-trust",
        "previous": None,
        "current": {"verdict": "needs_attention", "tui": "n"},
        "reason": f"trust_pass_with_gaps:{sha}",
        "source": "trust",
        "settled_at": entry["recorded_at"],
        "claim_digest": projected["settlement_claim_digest"],
        "waived": False,
        "revision": 1,
    }

    # The explicit trust snapshot write follows sync_state; it must not publish
    # a second event for the same revision.
    trust.control_plane.sync_state(only_run_id="run-trust")
    replayed = [
        json.loads(line)
        for line in (crafted_home / "control_plane" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if json.loads(line).get("kind") == "settlement.changed"
    ]
    assert len(replayed) == 1


def test_enumerate_skips_commits_already_in_append_only_journal(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, _fair_message(), {"proof.txt": "proof\n"})
    journal = tmp_path / "journal.jsonl"
    trust.note_verdict(
        repo=repo,
        journal=journal,
        sha=sha,
        verdict="pass",
        claims=[{"claim": "fixture", "grade": "strong", "evidence": "direct"}],
    )

    assert trust.enumerate_commits(repo=repo, journal=journal) == []
    assert (
        trust.enumerate_commits(repo=repo, journal=journal, include_noted=True)[0][
            "sha"
        ]
        == sha
    )


def test_triage_uses_latest_verdict_per_repo_and_commit() -> None:
    records = [
        {"repo_root": "/repo", "sha": "a", "settlement_tui": "x"},
        {"repo_root": "/repo", "sha": "a", "settlement_tui": "f"},
        {"repo_root": "/repo", "sha": "b", "settlement_tui": "n"},
        {"repo_root": "/other", "sha": "a", "settlement_tui": "x"},
    ]

    result = trust.triage_records(records)

    assert result["counts"] == {"f": 1, "x": 1, "n": 1}
    assert result["commits"] == 3


def test_claim_grade_and_evidence_are_one_to_one() -> None:
    args = argparse.Namespace(
        claim=["one", "two"],
        grade=["strong"],
        evidence=["proof"],
    )

    try:
        trust._claims_from_args(args)
    except ValueError as exc:
        assert "each --claim" in str(exc)
    else:
        raise AssertionError("mismatched claim evidence must fail closed")


def test_inspect_flags_agent_fairness_breach_and_never_auto_passes(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path)
    # Root commit: must list real files (diff-tree --root) and must not invent
    # an empty-envelope gap when the commit actually added paths.
    fair_sha = _commit(repo, _fair_message("codex"), {"proof.txt": "proof\n"})
    unfair_sha = _commit(repo, _unfair_message(), {"bad.txt": "bad\n"})

    fair = trust.extract_fairness_and_completeness_claims(repo=repo, sha=fair_sha)
    unfair = trust.extract_fairness_and_completeness_claims(repo=repo, sha=unfair_sha)

    assert fair["subject_agent"] == "codex"
    assert fair["authored_by_agent"] == "codex"
    assert fair["recommended_verdict"] in {"pass-with-gaps", "pass"}
    # Format alone must not become pass without runtime evidence.
    assert fair["recommended_verdict"] == "pass-with-gaps"
    assert fair["failures"] == []
    assert fair["files"] == ["proof.txt"]
    assert not any("empty envelope" in g for g in fair["gaps"])
    assert not any(
        "zero paths" in str(c.get("evidence", ""))
        for c in fair["claims"]
        if isinstance(c, dict)
    )

    assert unfair["recommended_verdict"] == "block"
    assert any("fairness" in f for f in unfair["failures"])
    assert any("vendor" in f for f in unfair["failures"])
    assert any(
        "fairness" in c["claim"] for c in unfair["claims"] if isinstance(c, dict)
    )
    # Non-root unfair commit also lists its real file.
    assert unfair["files"] == ["bad.txt"]


def test_inspect_root_commit_lists_files_via_diff_tree_root(tmp_path: Path) -> None:
    """Regression: root commits must not look like empty envelopes."""
    repo = _init_repo(tmp_path)
    sha = _commit(
        repo,
        _fair_message("grok"),
        {"proof.txt": "root-proof\n", "nested/a.py": "print(1)\n"},
    )
    files = trust._commit_files(repo, sha)
    assert "proof.txt" in files
    assert "nested/a.py" in files

    inspect = trust.extract_fairness_and_completeness_claims(repo=repo, sha=sha)
    assert set(inspect["files"]) == {"proof.txt", "nested/a.py"}
    assert not any("empty envelope" in g for g in inspect["gaps"])
    assert inspect["recommended_verdict"] == "pass-with-gaps"
    assert inspect["failures"] == []


def test_inspect_flags_foreign_unclaimed_envelope_files(tmp_path: Path) -> None:
    """Message claims a scoped path set while the envelope smuggles foreign files."""
    repo = _init_repo(tmp_path)
    # Baseline root so the unfair commit is a non-root multi-file envelope.
    _commit(repo, _fair_message("codex"), {"README.md": "base\n"})

    foreign_message = textwrap.dedent(
        """\
        [codex/workflow] feat(trust): touch only core/owned.py

        Updates `core/owned.py` with the focused helper path and pytest coverage.

        Authored-By: codex <agents@vetcoders.io>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        time: 2026-07-25T12:00:00+02:00
        runtime: terminal
        """
    )
    sha = _commit(
        repo,
        foreign_message,
        {
            "core/owned.py": "owned = True\n",
            "secrets/other_agent.env": "FOREIGN=1\n",
            "unrelated/smuggled.txt": "nope\n",
        },
    )

    inspect = trust.extract_fairness_and_completeness_claims(repo=repo, sha=sha)

    assert "core/owned.py" in inspect["files"]
    assert "secrets/other_agent.env" in inspect["files"]
    assert "unrelated/smuggled.txt" in inspect["files"]
    assert inspect["recommended_verdict"] in {"pass-with-gaps", "block"}
    assert any("foreign unclaimed" in g for g in inspect["gaps"])
    assert any(
        "foreign unclaimed" in c["claim"]
        for c in inspect["claims"]
        if isinstance(c, dict)
    )
    # Named evidence must list the smuggled paths.
    foreign_claim = next(
        c
        for c in inspect["claims"]
        if isinstance(c, dict) and "foreign unclaimed" in c["claim"]
    )
    assert "secrets/other_agent.env" in foreign_claim["evidence"]
    assert "unrelated/smuggled.txt" in foreign_claim["evidence"]


def test_inspect_flags_claimed_paths_absent_from_envelope(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    message = textwrap.dedent(
        """\
        [grok/workflow] fix(runtime): repair never_exists.py

        Fixes `never_exists.py` and documents the gate in docs/missing.md.

        Authored-By: grok <agents@vetcoders.io>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        time: 2026-07-25T12:00:00+02:00
        runtime: terminal
        """
    )
    sha = _commit(repo, message, {"actually_touched.txt": "x\n"})
    inspect = trust.extract_fairness_and_completeness_claims(repo=repo, sha=sha)

    assert inspect["files"] == ["actually_touched.txt"]
    assert inspect["recommended_verdict"] == "block"
    assert any("absent from the commit envelope" in f for f in inspect["failures"])
    assert any(
        "message-claimed paths are present" in c["claim"]
        for c in inspect["claims"]
        if isinstance(c, dict)
    )


def test_inspect_cli_drives_real_entry_point(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, _unfair_message(), {"x.txt": "x\n"})
    rc = trust.main(["--repo", str(repo), "inspect", sha])
    assert rc == 0


def test_git_log_range_never_feeds_failed_rev_to_since(tmp_path: Path) -> None:
    """Unresolvable since (root^) must fail open — never become --since=<rev>."""
    repo = _init_repo(tmp_path)
    root = _commit(repo, _fair_message("codex"), {"root.txt": "r\n"})
    child = _commit(repo, _fair_message("codex"), {"child.txt": "c\n"})

    # Valid parent → exclusive range args.
    assert trust._git_log_range(repo, root) == [f"{root}..HEAD"]

    # Root has no parent: root^ fails rev-parse → no lower bound (not --since).
    bad = trust._git_log_range(repo, root + "^")
    assert bad == []
    assert not any(a.startswith("--since=") for a in bad)

    # ISO run-meta dates still use the date filter (await-primary boundary).
    assert trust._git_log_range(repo, "2026-07-25T00:00:00+00:00") == [
        "--since=2026-07-25T00:00:00+00:00"
    ]

    # Empty since → no bound; enumerate must still see both commits.
    empty = trust.enumerate_commits(
        repo=repo, journal=tmp_path / "empty.jsonl", since=""
    )
    shas = {c["sha"] for c in empty}
    assert root in shas and child in shas

    # Unresolvable rev fails open: still lists existing commits.
    open_range = trust.enumerate_commits(
        repo=repo, journal=tmp_path / "empty2.jsonl", since=root + "^"
    )
    open_shas = {c["sha"] for c in open_range}
    assert root in open_shas and child in open_shas


def test_await_primary_lists_candidates_and_does_not_auto_note(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _init_repo(tmp_path)
    # Two commits so since can be a real parent baseline (deterministic).
    parent = _commit(repo, _fair_message("codex"), {"parent.txt": "p\n"})
    sha = _commit(repo, _fair_message("codex"), {"a.txt": "a\n"})
    journal = tmp_path / "journal.jsonl"
    crafted_home = tmp_path / "crafted"
    run_dir = crafted_home / "control_plane" / "runtime_runs" / "run-await"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": "run-await",
                "state": "completed",
                "exit_code": 0,
                "started_at": "2026-07-25T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))

    def _fake_await(run_id: str, **_kwargs):
        return {
            "completed": True,
            "reason": "completed",
            "await_rc": 0,
            "await_outcome": "completed",
        }

    monkeypatch.setattr(trust.control_plane, "await_run", _fake_await)

    # Parent..HEAD range: child is a candidate; parent is the lower bound.
    result = trust.await_primary(
        run_id="run-await",
        repo=repo,
        journal=journal,
        since=parent,
        interval=0.1,
        timeout=2.0,
    )

    assert result["schema"] == "vibecrafted.trust-await-primary.v1"
    assert result["await"]["completed"] is True
    candidate_shas = [c["sha"] for c in result["candidate_commits"]]
    assert sha in candidate_shas
    assert parent not in candidate_shas
    # No auto-note: journal must still be empty
    assert not journal.is_file() or journal.read_text().strip() == ""

    # Root-only fail-open path: unresolvable since=HEAD^ must still list HEAD.
    solo_base = tmp_path / "solo"
    solo_base.mkdir()
    solo = _init_repo(solo_base)
    solo_sha = _commit(solo, _fair_message("grok"), {"solo.txt": "s\n"})
    solo_journal = tmp_path / "solo-journal.jsonl"
    solo_run = crafted_home / "control_plane" / "runtime_runs" / "run-await-solo"
    solo_run.mkdir(parents=True)
    (solo_run / "meta.json").write_text(
        json.dumps(
            {
                "run_id": "run-await-solo",
                "state": "completed",
                "exit_code": 0,
                "started_at": "2026-07-25T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    solo_result = trust.await_primary(
        run_id="run-await-solo",
        repo=solo,
        journal=solo_journal,
        since=solo_sha + "^",
        interval=0.1,
        timeout=2.0,
    )
    assert any(c["sha"] == solo_sha for c in solo_result["candidate_commits"])
    assert not solo_journal.is_file() or solo_journal.read_text().strip() == ""


def test_guard_inventory_and_block_enforcement(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, _unfair_message(), {"z.txt": "z\n"})
    journal = tmp_path / "journal.jsonl"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "crafted"))

    inv = guard.inventory()
    assert inv["schema"] == "vibecrafted.guard-inventory.v1"
    assert any(g["id"] == "trust-block-dispatch" for g in inv["gates"])
    assert inv["doctrine"]["settlement_authority"].startswith("vc-trust")

    open_decision = guard.enforce_continuation(repo=repo, journal=journal)
    assert open_decision.allowed is True

    inspect = trust.extract_fairness_and_completeness_claims(repo=repo, sha=sha)
    trust.note_verdict(
        repo=repo,
        journal=journal,
        sha=sha,
        verdict="block",
        claims=inspect["claims"][:2]
        or [
            {
                "claim": "agent fairness",
                "grade": "strong",
                "evidence": "subject != Authored-By",
            }
        ],
    )

    blocked = guard.enforce_continuation(repo=repo, journal=journal, sha=sha)
    assert blocked.allowed is False
    assert blocked.blocking_verdict == "block"
    assert "Remedium" in blocked.remedium
    assert blocked.blocking_sha.startswith(sha[:8]) or blocked.blocking_sha == sha

    # pass after block: append newer verdict for same sha (latest wins)
    trust.note_verdict(
        repo=repo,
        journal=journal,
        sha=sha,
        verdict="pass",
        claims=[
            {
                "claim": "runtime proof",
                "grade": "strong",
                "evidence": "negative fixture then green",
            }
        ],
    )
    allowed = guard.enforce_continuation(repo=repo, journal=journal, sha=sha)
    assert allowed.allowed is True

    # CLI exit codes
    assert guard.main(["inventory"]) == 0
    # After pass, check allows
    assert (
        guard.main(
            ["--repo", str(repo), "--journal", str(journal), "check", "--sha", sha]
        )
        == 0
    )


def test_launch_workflow_refuses_on_trust_block(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, _unfair_message(), {"w.txt": "w\n"})
    journal = tmp_path / "journal.jsonl"
    crafted = tmp_path / "crafted"
    crafted.mkdir()
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted))
    monkeypatch.setenv("VIBECRAFTED_GUARD", "1")
    monkeypatch.setattr(trust, "default_journal_path", lambda: journal)

    trust.note_verdict(
        repo=repo,
        journal=journal,
        sha=sha,
        verdict="block",
        claims=[
            {
                "claim": "agent fairness",
                "grade": "strong",
                "evidence": "subject != Authored-By",
            }
        ],
    )

    # Patch guard to use our journal when launch_workflow imports it
    real_enforce = guard.enforce_continuation

    def _enforce(**kwargs):
        kwargs = {**kwargs, "journal": journal, "repo": repo}
        return real_enforce(**kwargs)

    monkeypatch.setattr(guard, "enforce_continuation", _enforce)

    from vibecrafted_core.workflow import WorkflowLaunchSpec

    spec = WorkflowLaunchSpec(
        skill="implement",
        agent="codex",
        mode="prompt",
        file="",
        runtime="headless",
        root=str(repo),
        prompt="should be refused",
    )
    try:
        workflow.launch_workflow(spec, source_dir=repo)
    except ValueError as exc:
        assert "vc-guard" in str(exc) or "Remedium" in str(exc) or "block" in str(exc)
    else:
        raise AssertionError("launch_workflow must refuse on trust block")


def test_settlement_mapping_closed_pass_f_gaps_n_block_x(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, _fair_message(), {"m.txt": "m\n"})
    journal = tmp_path / "j.jsonl"
    for verdict, letter in (
        ("pass", "f"),
        ("pass-with-gaps", "n"),
        ("block", "x"),
    ):
        entry = trust.note_verdict(
            repo=repo,
            journal=journal,
            sha=sha,
            verdict=verdict,
            claims=[
                {
                    "claim": f"map {verdict}",
                    "grade": "strong",
                    "evidence": "unit",
                }
            ],
        )
        assert entry["settlement_tui"] == letter
    triage = trust.triage_records(
        [json.loads(line) for line in journal.read_text().splitlines()]
    )
    # latest wins for same sha — last was block → x only for that sha
    assert triage["counts"]["x"] == 1
    assert triage["commits"] == 1
