from __future__ import annotations

from pathlib import Path

import pytest
from vibecrafted_core.dispatch.doctor import diagnose_file, main

FIXTURES = Path(__file__).parent / "fixtures"
INVALID = FIXTURES / "invalid"


@pytest.mark.parametrize(
    ("fixture", "path", "message"),
    [
        ("unknown-schema.dispatch.toml", "schema", "unsupported schema"),
        ("missing-meta-repo.dispatch.toml", "meta.repo", "required"),
        ("unreadable-brief.dispatch.toml", "cuts[0].brief", "missing or unreadable"),
        ("missing-prompt-and-brief.dispatch.toml", "cuts[0]", "prompt or brief"),
        ("missing-verify.dispatch.toml", "cuts[0].verify", "required unless"),
        ("unknown-workflow.dispatch.toml", "cuts[0].workflow", "unsupported workflow"),
        ("unknown-phase.dispatch.toml", "cuts[0].phase", "unknown phase"),
        ("duplicate-id.dispatch.toml", "cuts[1].id", "duplicate cut id"),
        (
            "concurrency-without-policy.dispatch.toml",
            "policy.concurrency",
            "require allow_concurrency",
        ),
        (
            "unknown-matcher.dispatch.toml",
            "cuts[0].verify[0].expect.stderr",
            "unsupported matcher",
        ),
        ("hard-stop-push.dispatch.toml", "cuts[0].verify[0].run", "git push"),
        ("hard-stop-release.dispatch.toml", "cuts[0].verify[0].run", "release"),
        ("hard-stop-no-verify.dispatch.toml", "cuts[0].verify[0].run", "--no-verify"),
        (
            "read-without-mutation.dispatch.toml",
            "cuts[0].mutation",
            "required for READ",
        ),
    ],
)
def test_dispatch_doctor_rejects_design_refusal_fixtures(
    fixture: str, path: str, message: str
) -> None:
    report = diagnose_file(INVALID / fixture)

    assert report.ok is False
    assert any(
        error.path == path and message in error.message for error in report.errors
    ), report.errors


def test_dispatch_doctor_allows_observational_read_with_mutation_policy() -> None:
    report = diagnose_file(FIXTURES / "observational-read.dispatch.toml")

    assert report.ok is True
    assert report.errors == ()


def test_dispatch_doctor_rejects_legacy_stage0_review_no_edit_read() -> None:
    report = diagnose_file(FIXTURES / "legacy-stage0-read-no-edit.dispatch.toml")

    assert report.ok is False
    assert any(
        error.path == "cuts[0].mutation" and "required for READ" in error.message
        for error in report.errors
    ), report.errors


def test_dispatch_doctor_cli_returns_nonzero_for_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([str(INVALID / "unknown-schema.dispatch.toml")])

    captured = capsys.readouterr()
    assert code == 1
    assert "schema: unsupported schema" in captured.out


def test_dispatch_doctor_cli_returns_zero_for_valid_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([str(FIXTURES / "minimal.dispatch.toml")])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "dispatch-doctor: ok"
