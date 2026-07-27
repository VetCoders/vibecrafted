from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from vibecrafted_core import cli, settlement_ledger
from vibecrafted_core.settlements_query import (
    SettlementsQueryError,
    inspect_settlement,
    list_settlements,
    settlements_summary,
)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "crafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    (home / "control_plane" / "runs" / "archive").mkdir(parents=True)
    (home / "control_plane" / "runtime_runs").mkdir(parents=True)
    return home


def _write_snapshot(
    path: Path,
    *,
    run_id: str,
    tui: str,
    revision: int = 1,
    agent: str = "codex",
    skill: str = "workflow",
    reason: str = "axes_e=exited_p=undeclared_d=unverified",
    root: str = "",
    state: str = "completed",
    exit_code: int | None = 0,
    launcher_pid: int | None = 1234,
    last_error: str = "",
    report_path: str = "",
    transcript_path: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    verdict = {
        "f": "finalized",
        "x": "failed",
        "n": "needs_attention",
    }[tui]
    payload: dict[str, Any] = {
        "run_id": run_id,
        "agent": agent,
        "skill": skill,
        "root": root,
        "state": state,
        "exit_code": exit_code,
        "launcher_pid": launcher_pid,
        "last_error": last_error,
        "latest_report": report_path,
        "latest_transcript": transcript_path,
        "settlement_tui": tui,
        "settlement_verdict": verdict,
        "settlement_reason": reason,
        "settlement_revision": revision,
        "settlement_source": "auto",
        "settlement": {
            "verdict": verdict,
            "reason": reason,
            "tui": tui,
            "revision": revision,
            "source": "auto",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_revalidatable_n(home: Path, run_id: str = "run-n-reval") -> Path:
    root = home / "control_plane"
    report = home / "artifacts" / f"{run_id}_report.md"
    transcript = home / "control_plane" / "runtime_runs" / run_id / "transcript.log"
    report.parent.mkdir(parents=True, exist_ok=True)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# report\n", encoding="utf-8")
    transcript.write_text("transcript\n", encoding="utf-8")
    checkout = home / "src" / "demo-repo"
    checkout.mkdir(parents=True)
    _write_snapshot(
        root / "runs" / "archive" / f"{run_id}.json",
        run_id=run_id,
        tui="n",
        agent="claude",
        skill="implement",
        reason="axes_e=exited_p=undeclared_d=unverified",
        root=str(checkout),
        state="completed",
        exit_code=0,
        report_path=str(report),
        transcript_path=str(transcript),
    )
    return checkout


def _seed_failed_x(home: Path, run_id: str = "run-x-fail") -> None:
    root = home / "control_plane"
    _write_snapshot(
        root / "runs" / f"{run_id}.json",
        run_id=run_id,
        tui="x",
        agent="codex",
        skill="marbles",
        reason="execution_failed",
        state="failed",
        exit_code=1,
        launcher_pid=None,
        last_error="launcher_pid is missing; settlement parks as failed",
    )


def test_summary_list_inspect_revalidatable_and_group(isolated_home: Path) -> None:
    checkout = _seed_revalidatable_n(isolated_home)
    _seed_failed_x(isolated_home)
    settlement_ledger.initialize_settlement_ledger()

    summary = settlements_summary()
    assert summary["schema"] == "vibecrafted.settlements-query.v1"
    assert summary["read_only"] is True
    assert summary["counts"]["latest_by_run"]["n"] == 1
    assert summary["counts"]["latest_by_run"]["x"] == 1
    assert summary["revalidatable_n"] == 1
    assert summary["n_inventory"]["exit_0"] == 1
    assert summary["n_inventory"]["completed_state"] == 1
    assert summary["n_inventory"]["checkout_exists"] == 1
    assert summary["x_inventory"]["skill_marbles"] == 1
    assert summary["x_inventory"]["launcher_pid_missing"] == 1
    assert "Guardian" in summary["guardian_auto_resume_note"]

    reval = list_settlements(bucket="n", revalidatable=True)
    assert reval["matched"] == 1
    assert reval["runs"][0]["run_id"] == "run-n-reval"
    assert reval["runs"][0]["revalidatable"] is True
    assert reval["runs"][0]["checkout_exists"] is True
    assert reval["runs"][0]["root"] == str(checkout)

    grouped = list_settlements(bucket="x", group="agent,skill,reason")
    assert grouped["matched"] == 1
    assert grouped["groups"][0]["count"] == 1
    assert grouped["groups"][0]["key"] == {
        "agent": "codex",
        "skill": "marbles",
        "reason": "execution_failed",
    }

    detail = inspect_settlement("run-n-reval")
    assert detail["run_id"] == "run-n-reval"
    assert detail["ledger"]["settlement_tui"] == "n"
    assert detail["enriched"]["revalidatable"] is True
    assert detail["snapshot_source"] == "archive"


def test_list_rejects_unknown_bucket_and_group() -> None:
    with pytest.raises(SettlementsQueryError, match="invalid bucket"):
        list_settlements(bucket="q")
    with pytest.raises(SettlementsQueryError, match="unknown group field"):
        list_settlements(group="agent,bogus")


def test_inspect_missing_run_fails() -> None:
    settlement_ledger.initialize_settlement_ledger()
    with pytest.raises(SettlementsQueryError, match="not present"):
        inspect_settlement("no-such-run")


def test_cli_settlements_surface(
    isolated_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_revalidatable_n(isolated_home)
    _seed_failed_x(isolated_home)
    settlement_ledger.initialize_settlement_ledger()

    assert cli.main(["settlements", "summary", "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["revalidatable_n"] == 1

    assert (
        cli.main(["settlements", "list", "--bucket", "n", "--revalidatable", "--json"])
        == 0
    )
    listing = json.loads(capsys.readouterr().out)
    assert listing["matched"] == 1
    assert listing["runs"][0]["run_id"] == "run-n-reval"

    assert (
        cli.main(
            [
                "settlements",
                "list",
                "--bucket",
                "x",
                "--group",
                "agent,skill,reason,root",
                "--json",
            ]
        )
        == 0
    )
    grouped = json.loads(capsys.readouterr().out)
    assert grouped["groups"][0]["key"]["skill"] == "marbles"

    assert cli.main(["settlements", "inspect", "run-x-fail", "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["enriched"]["reason"] == "execution_failed"

    assert cli.main(["settlements"]) == 2
    err = capsys.readouterr().err
    assert "settlements summary" in err


def test_root_help_mentions_settlements(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "settlements" in out
