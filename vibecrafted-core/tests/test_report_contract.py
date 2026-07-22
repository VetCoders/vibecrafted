"""Mandatory report frontmatter + claim triangulation."""

from __future__ import annotations

from pathlib import Path

from vibecrafted_core.artifacts import validate_artifacts
from vibecrafted_core.report_contract import (
    ensure_frontmatter_on_text,
    parse_report_text,
    render_minimal_frontmatter,
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


def test_missing_frontmatter_fails_artifact_validation(tmp_path: Path) -> None:
    report = tmp_path / "bare.md"
    report.write_text("# no frontmatter\n\nbody\n", encoding="utf-8")
    meta = tmp_path / "meta.json"
    meta.write_text(
        '{"report": %s, "transcript": %s}'
        % (repr(str(report)), repr(str(tmp_path / "t.log"))),
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
    assert "Hello" in body


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
