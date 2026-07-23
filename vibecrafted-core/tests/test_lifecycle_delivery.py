"""Lifecycle stage seal bridge + resettle honesty tests."""

from __future__ import annotations

import json
from pathlib import Path

from vibecrafted_core.lifecycle_delivery import (
    claim_digest_for_text,
    resettle_retained_snapshots,
    try_grant_lifecycle_stage_seal,
)
from vibecrafted_core.settlement import settle_payload


def _valid_report(
    path: Path, *, status: str = "completed", claim_digest: str = ""
) -> None:
    lines = [
        "---",
        "run_id: stage-run-1",
        "agent: grok",
        "skill: implement",
        f"status: {status}",
        "claim_status: " + status,
    ]
    if claim_digest:
        lines.append(f"claim_digest: {claim_digest}")
    lines.extend(["---", "", "Done: stage work.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _event_sink(kind: str, run_id: str, message: str, payload: dict) -> dict:
    return {"kind": kind, "run_id": run_id, "message": message, "payload": payload}


def test_grant_seal_on_validated_report_with_claim_match(tmp_path: Path) -> None:
    mission = "ship settlement board truth"
    digest = claim_digest_for_text(mission)
    run_dir = tmp_path / "runtime_runs" / "stage-run-1"
    run_dir.mkdir(parents=True)
    report = run_dir / "report.md"
    _valid_report(report, claim_digest=digest)
    (run_dir / "transcript.log").write_text("ok\n", encoding="utf-8")
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": "stage-run-1",
                "state": "report_validated",
                "exit_code": 0,
                "agent": "grok",
                "skill": "implement",
            }
        ),
        encoding="utf-8",
    )

    result = try_grant_lifecycle_stage_seal(
        run_dir,
        run_id="stage-run-1",
        lifecycle_id="life-ship-1",
        stage_id="implement",
        report_path=report,
        mission_text=mission,
        mission_digest=digest,
        artifact_ok=True,
        exit_code=0,
        repo_root=tmp_path,
        event_sink=_event_sink,
    )
    assert result.granted is True
    assert result.proof_state == "passed"
    assert result.delivery_state == "sealed"
    assert (run_dir / "proof" / "result.json").is_file()
    assert (run_dir / "delivery-seal.json").is_file()
    assert (run_dir / "execution-envelope.json").is_file()
    assert (run_dir / "delivery-proof-contract.json").is_file()
    assert (run_dir / "delivery-record.json").is_file()
    proof = json.loads((run_dir / "proof" / "result.json").read_text())
    assert proof["subject_executed"] is True
    assert proof["assertion_consumed_subject_output"] is True
    assert proof["negative_control_results"][0]["detected_falsehood"] is True
    seal = json.loads((run_dir / "delivery-seal.json").read_text())
    assert seal["issuer"] == "vc-ship"
    assert seal["delivery_proof_contract_sha256"] != "sha256:" + "0" * 64

    # Settlement path: kernel axes + claim → finalized without operator action.
    payload = {
        "run_id": "stage-run-1",
        "state": "report_validated",
        "exit_code": 0,
        "liveness": "terminal",
        "proof_state": result.proof_state,
        "delivery_state": result.delivery_state,
        "claim_digest": result.claim_digest,
        "report": str(report),
        "latest_report": str(report),
    }
    settlement = settle_payload(payload, source="auto")
    assert settlement is not None
    assert settlement.verdict.value == "finalized"
    assert settlement.tui_key == "f"


def test_refuse_exit_zero_without_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "runtime_runs" / "no-report"
    run_dir.mkdir(parents=True)
    result = try_grant_lifecycle_stage_seal(
        run_dir,
        run_id="no-report",
        mission_text="mission",
        mission_digest=claim_digest_for_text("mission"),
        artifact_ok=False,
        exit_code=0,
    )
    assert result.granted is False
    assert result.reason == "artifact_not_ok"
    assert not (run_dir / "delivery-seal.json").exists()

    result2 = try_grant_lifecycle_stage_seal(
        run_dir,
        run_id="no-report",
        mission_text="mission",
        mission_digest=claim_digest_for_text("mission"),
        artifact_ok=True,  # validation said ok but report file absent
        exit_code=0,
        report_path=run_dir / "missing.md",
    )
    assert result2.granted is False
    assert result2.reason in {"exit_0_without_report", "report_missing"}
    assert not (run_dir / "delivery-seal.json").exists()

    payload = {
        "run_id": "no-report",
        "state": "completed",
        "exit_code": 0,
        "liveness": "terminal",
        "proof_state": "undeclared",
        "delivery_state": "unverified",
    }
    settlement = settle_payload(payload, source="auto")
    assert settlement is not None
    assert settlement.verdict.value == "needs_attention"
    assert settlement.tui_key == "n"


def test_refuse_report_without_claim_match(tmp_path: Path) -> None:
    mission = "expected mission text"
    digest = claim_digest_for_text(mission)
    run_dir = tmp_path / "runtime_runs" / "mismatch"
    run_dir.mkdir(parents=True)
    report = run_dir / "report.md"
    _valid_report(report, claim_digest="deadbeefdeadbeef")  # wrong digest

    result = try_grant_lifecycle_stage_seal(
        run_dir,
        run_id="mismatch",
        report_path=report,
        mission_text=mission,
        mission_digest=digest,
        artifact_ok=True,
        exit_code=0,
    )
    assert result.granted is False
    assert result.reason.startswith("claim_digest_mismatch")
    assert not (run_dir / "delivery-seal.json").exists()

    payload = {
        "run_id": "mismatch",
        "state": "report_validated",
        "exit_code": 0,
        "liveness": "terminal",
        "proof_state": "undeclared",
        "delivery_state": "unverified",
        "claim_digest": digest,
        "report": str(report),
    }
    settlement = settle_payload(payload, source="auto")
    assert settlement is not None
    assert settlement.verdict.value == "needs_attention"
    assert settlement.tui_key == "n"


def test_refuse_report_without_explicit_claim_digest(tmp_path: Path) -> None:
    mission = "expected mission text"
    digest = claim_digest_for_text(mission)
    run_dir = tmp_path / "runtime_runs" / "missing-digest"
    run_dir.mkdir(parents=True)
    report = run_dir / "report.md"
    _valid_report(report)

    result = try_grant_lifecycle_stage_seal(
        run_dir,
        run_id="missing-digest",
        report_path=report,
        mission_text=mission,
        mission_digest=digest,
        artifact_ok=True,
        exit_code=0,
        repo_root=tmp_path,
        event_sink=_event_sink,
    )

    assert result.granted is False
    assert result.reason == "report_claim_digest_missing"
    assert not (run_dir / "delivery-seal.json").exists()


def test_resettle_is_honest_and_idempotent(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    # Historical: undeclared axes, terminal → needs_attention (never fabricated f)
    (runs / "hist-n.json").write_text(
        json.dumps(
            {
                "run_id": "hist-n",
                "state": "report_validated",
                "exit_code": 0,
                "liveness": "terminal",
                "proof_state": "undeclared",
                "delivery_state": "unverified",
                "claim_digest": "abcd1234abcd1234",
            }
        ),
        encoding="utf-8",
    )
    # Already sealed → can finalize on resettle
    (runs / "hist-f.json").write_text(
        json.dumps(
            {
                "run_id": "hist-f",
                "state": "report_validated",
                "exit_code": 0,
                "liveness": "terminal",
                "proof_state": "passed",
                "delivery_state": "sealed",
                "claim_digest": "abcd1234abcd1234",
                "report": str(tmp_path / "r.md"),
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "r.md").write_text("# report\n", encoding="utf-8")
    (runs / "hist-invalid.json").write_text(
        json.dumps(
            {
                "run_id": "hist-invalid",
                "state": "report_invalid",
                "exit_code": 1,
                "liveness": "terminal",
                "proof_state": "invalid",
                "delivery_state": "unverified",
                "settlement_verdict": "invalid",
                "settlement_reason": "report_invalid",
                "settlement_tui": "x",
            }
        ),
        encoding="utf-8",
    )

    first = resettle_retained_snapshots(runs_dir=runs, force=True, dry_run=False)
    assert first["ok"] is True
    assert first["scanned"] == 3
    assert first["after"]["f"] == 1
    assert first["after"]["n"] >= 1
    assert first["after"]["f"] != 2  # never invent second f
    assert first["before"]["x"] == 1
    assert first["before"]["invalid"] == 1
    assert first["after"]["x"] == 1
    assert first["after"]["invalid"] == 1

    hist_n = json.loads((runs / "hist-n.json").read_text(encoding="utf-8"))
    assert hist_n.get("settlement_verdict") == "needs_attention"
    hist_f = json.loads((runs / "hist-f.json").read_text(encoding="utf-8"))
    assert hist_f.get("settlement_verdict") == "finalized"

    second = resettle_retained_snapshots(runs_dir=runs, force=True, dry_run=False)
    assert second["rewritten"] == 0  # idempotent
    assert second["after"]["f"] == first["after"]["f"]
    assert second["after"]["n"] == first["after"]["n"]
