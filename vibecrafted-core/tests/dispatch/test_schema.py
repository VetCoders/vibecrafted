from __future__ import annotations

from pathlib import Path

import pytest

from vibecrafted_core.dispatch.model import (
    Baton,
    CutState,
    Matcher,
    STATE_VERIFIED,
    Verdict,
    VerifierEvidence,
)
from vibecrafted_core.dispatch.schema import (
    DispatchSchemaError,
    doctor_dispatch,
    load_dispatch,
    parse_dispatch,
    render_cell_prompt,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_minimal_fixture_parses_into_typed_model() -> None:
    dispatch = load_dispatch(FIXTURES / "minimal.dispatch.toml")

    assert dispatch.schema == "vibecrafted.dispatch.v1"
    assert dispatch.meta.name == "dispatch-minimal"
    assert dispatch.policy.concurrency == 1
    assert dispatch.phases[0].title == "Foundation"
    assert dispatch.cuts[0].id == "d1-schema-parser"
    assert dispatch.cuts[0].verify[0].matchers[0].kind == "contains"


def test_stage0_maximum_fixture_is_accepted() -> None:
    dispatch = load_dispatch(FIXTURES / "stage0.dispatch.toml")

    assert dispatch.meta.name == "d1-schema-parser"
    assert dispatch.policy.await_config == {"poll_s": 90, "timeout_min": 90}
    assert dispatch.workflow_map["audit"] == "review"
    assert dispatch.cuts[0].brief.endswith("stage0-brief.md")
    assert dispatch.cuts[1].resolved_workflow == "review"
    assert dispatch.cuts[1].mutation == ""
    assert dispatch.cuts[1].observational is True


def test_prompt_rendering_substitutes_common_body_extra_and_empty_baton() -> None:
    dispatch = load_dispatch(FIXTURES / "minimal.dispatch.toml")
    prompt = render_cell_prompt(dispatch, dispatch.cuts[0])

    assert "Repo: /tmp/vibecrafted-dispatch-fixture" in prompt
    assert "Implement parser cut d1-schema-parser" in prompt
    assert "Use workflow implement" in prompt
    assert '"last": null' in prompt
    assert '"states": []' in prompt
    assert '"verified": 0' in prompt
    assert '"total": 1' in prompt
    assert '"ratio": 0.0' in prompt


def test_prompt_rendering_substitutes_previous_verdict_baton() -> None:
    dispatch = load_dispatch(FIXTURES / "stage0.dispatch.toml")
    verdict = Verdict(
        cut_id="d1-schema-parser",
        phase="Foundation",
        state=STATE_VERIFIED,
        commit="abc1234",
        report="/tmp/d1.md",
        verifiers=(
            VerifierEvidence(
                command="make dispatch-test",
                ok=True,
                exit_code=0,
                evidence="1 passed",
                elapsed_ms=123,
                timestamp="2026-06-10T20:30:00-07:00",
            ),
        ),
    )
    baton = Baton(
        last=verdict,
        states=(CutState.from_verdict(verdict),),
        total=len(dispatch.cuts),
    )

    prompt = render_cell_prompt(dispatch, dispatch.cuts[1], baton=baton)

    assert '"cut_id": "d1-schema-parser"' in prompt
    assert '"commit": "abc1234"' in prompt
    assert '"verified": 1' in prompt
    assert '"total": 2' in prompt
    assert '"ratio": 0.5' in prompt


def test_matchers_cover_required_set() -> None:
    output = "test result: ok. 3 passed"

    assert Matcher("contains", "3 passed").check(output, exit_code=0)
    assert Matcher("equals", output).check(output, exit_code=0)
    assert Matcher("matches", r"\d+ passed").check(output, exit_code=0)
    assert Matcher("not_contains", "FAILED").check(output, exit_code=0)
    assert Matcher("exit_code", 0).check(output, exit_code=0)
    assert not Matcher("exit_code", 1).check(output, exit_code=0)


def test_doctor_reports_schema_errors_without_throwing() -> None:
    result = doctor_dispatch("schema = 'wrong'")

    assert result.ok is False
    assert result.dispatch is None
    assert any("unsupported schema" in error for error in result.errors)


def test_parser_accepts_read_cut_without_mutation_for_doctor_policy() -> None:
    text = (FIXTURES / "stage0.dispatch.toml").read_text(encoding="utf-8")

    dispatch = parse_dispatch(text, base_dir=FIXTURES)
    result = doctor_dispatch(text, base_dir=FIXTURES)

    assert dispatch.cuts[1].mode == "read"
    assert dispatch.cuts[1].mutation == ""
    assert result.ok is False
    assert result.dispatch is not None
    assert "cuts[1].mutation: required for READ cuts" in result.errors


def test_rejects_unsupported_read_mutation_at_parse_time() -> None:
    text = (FIXTURES / "stage0.dispatch.toml").read_text(encoding="utf-8")
    text = text.replace(
        'mode = "read"\nobservational = true',
        'mode = "read"\nmutation = "teleport"\nobservational = true',
    )

    with pytest.raises(DispatchSchemaError) as exc:
        parse_dispatch(text, base_dir=FIXTURES)

    assert "cuts[1].mutation: unsupported value 'teleport'" in exc.value.errors


def test_rejects_duplicate_cut_ids_and_missing_verify() -> None:
    text = (FIXTURES / "minimal.dispatch.toml").read_text(encoding="utf-8")
    text += """

[[cuts]]
id = "d1-schema-parser"
phase = "Foundation"
agent = "codex"
workflow = "implement"
prompt = "duplicate"
"""

    with pytest.raises(DispatchSchemaError) as exc:
        parse_dispatch(text, base_dir=FIXTURES)

    errors = "\n".join(exc.value.errors)
    assert "duplicate cut id 'd1-schema-parser'" in errors
    assert "verify: required unless observational READ is explicit" in errors
