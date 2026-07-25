from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from vibecrafted_core import cli, trust
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


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Trust Fixture")
    _git(repo, "config", "user.email", "trust@example.test")
    (repo / "proof.txt").write_text("proof\n", encoding="utf-8")
    _git(repo, "add", "proof.txt")
    _git(repo, "commit", "-m", "prove trust fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_registry_exposes_trust_as_read_only() -> None:
    definition = registry.workflow_definition("trust")

    assert definition is not None
    assert definition.cadence == "read"
    assert definition.can_modify_code is False
    assert definition.tooling[-1] == "vc-trust"
    assert registry.workflow_definition("guard") is None
    assert {
        verdict: trust.tui_key_for(terminal)
        for verdict, terminal in trust.VERDICT_TO_SETTLEMENT.items()
    } == {
        "pass": "f",
        "pass-with-gaps": "n",
        "block": "x",
    }


def test_core_command_deck_exposes_trust_launcher(capsys) -> None:
    assert cli.main(["trust", "--help"]) == 0
    output = capsys.readouterr().out
    assert "vibecrafted trust <claude|codex|agy|junie|grok>" in output
    assert "version 1.0.0 · READ" in output


def test_note_appends_claim_evidence_and_projects_settlement(
    tmp_path: Path, monkeypatch
) -> None:
    repo, sha = _repo(tmp_path)
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
    assert board_fxn_counts([projected]) == {"f": 0, "x": 0, "n": 1}


def test_enumerate_skips_commits_already_in_append_only_journal(
    tmp_path: Path,
) -> None:
    repo, sha = _repo(tmp_path)
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
