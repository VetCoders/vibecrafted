"""Mandatory report frontmatter + claim triangulation."""

from __future__ import annotations

from pathlib import Path

from vibecrafted_core.artifacts import validate_artifacts
from vibecrafted_core.report_contract import (
    ensure_frontmatter_on_text,
    materialize_launcher_report_template,
    parse_report_text,
    render_minimal_frontmatter,
    stamp_launcher_report_identity,
    validate_report_file,
)
from vibecrafted_core.run_triage import classify_run


def test_parse_and_validate_minimal_frontmatter(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text(
        render_minimal_frontmatter(
            run_id="run-1",
            agent="codex",
            skill="scaffold",
            status="completed",
            extra={"project": "vibecrafted"},
        )
        + "# Body\n\nok\n",
        encoding="utf-8",
    )
    fm = validate_report_file(report)
    assert fm.ok
    assert fm.claim_status == "completed"
    assert fm.fields["agent"] == "codex"
    assert fm.fields["finalized"] == "false"
    assert fm.finalized is False


def test_missing_frontmatter_fails_artifact_validation(tmp_path: Path) -> None:
    report = tmp_path / "bare.md"
    report.write_text("# no frontmatter\n\nbody\n", encoding="utf-8")
    meta = tmp_path / "meta.json"
    meta.write_text(
        '{{"report": {}, "transcript": {}}}'.format(
            repr(str(report)), repr(str(tmp_path / "t.log"))
        ),
        encoding="utf-8",
    )
    (tmp_path / "t.log").write_text("x\n", encoding="utf-8")
    result = validate_artifacts(meta_path=meta, report_path=report)
    assert not result.ok
    assert any(e.startswith("report_frontmatter_") for e in result.errors)
    assert result.report_valid is False


def test_ensure_frontmatter_prepends_block() -> None:
    text = ensure_frontmatter_on_text(
        "# Hello\n",
        run_id="r1",
        agent="claude",
        skill="workflow",
        status="completed",
    )
    fields, body, has_fm = parse_report_text(text)
    assert has_fm
    assert fields["run_id"] == "r1"
    assert fields["finalized"] == "false"
    assert "Hello" in body


def test_existing_positive_attestation_is_preserved() -> None:
    text = ensure_frontmatter_on_text(
        "---\nrun_id: r1\nagent: codex\nskill: workflow\nstatus: completed\n"
        "finalized: true\nclaim: lifecycle settled\n---\nbody\n",
    )
    fields, _, _ = parse_report_text(text)
    assert fields["finalized"] == "true"
    assert fields["claim"] == "lifecycle settled"


def test_launcher_claim_digest_overrides_worker_copy(tmp_path: Path) -> None:
    digest = "9e0d59e1dc48bc42"
    report = tmp_path / "report.md"

    assert materialize_launcher_report_template(
        report,
        run_id="bound-run",
        agent="codex",
        skill="polarize",
        claim_digest=digest,
    )
    assert f"claim_digest: {digest}" in report.read_text(encoding="utf-8")

    report.write_text(
        "---\nrun_id: copied\nsession_id: copied\nagent: codex\n"
        "skill: polarize\nstatus: completed\nfinalized: true\n"
        "claim: cut completed\nclaim_digest: deadbeefdeadbeef\n---\nbody\n",
        encoding="utf-8",
    )
    assert stamp_launcher_report_identity(
        report,
        run_id="bound-run",
        session_id="provider-session",
        agent="codex",
        skill="polarize",
        status="completed",
        claim_digest=digest,
    )
    fields, _, _ = parse_report_text(report.read_text(encoding="utf-8"))
    assert fields["run_id"] == "bound-run"
    assert fields["session_id"] == "provider-session"
    assert fields["claim_digest"] == digest


def test_classify_exit_0_claim_failed_is_attention() -> None:
    verdict = classify_run(
        0,
        "completed",
        True,
        500,
        1000,
        report_claim_status="failed",
        report_frontmatter_ok=True,
    )
    assert verdict.verdict == "needs_attention"
    assert "claim_failed" in verdict.reason


def test_classify_exit_0_missing_frontmatter_is_attention() -> None:
    verdict = classify_run(
        0,
        "completed",
        True,
        500,
        1000,
        report_claim_status="completed",
        report_frontmatter_ok=False,
    )
    assert verdict.verdict == "needs_attention"
    assert "frontmatter" in verdict.reason


def test_classify_exit_0_completed_claim_finalizes() -> None:
    verdict = classify_run(
        0,
        "completed",
        True,
        500,
        1000,
        report_claim_status="completed",
        report_frontmatter_ok=True,
    )
    assert verdict.verdict == "finalized"
