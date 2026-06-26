from __future__ import annotations

from pathlib import Path

import pytest

from vibecrafted_core.dispatch_contract import (
    DispatchContractError,
    MATCHER_TYPES,
    doctor_dispatch_contract,
    parse_dispatch_contract,
)


def _valid_contract(**cut_overrides: str) -> str:
    cut_lines = {
        "id": '"w1-a"',
        "phase": '"Foundation"',
        "agent": '"codex"',
        "workflow": '"implement"',
        "prompt": '"implement the cut"',
    }
    cut_lines.update(cut_overrides)
    cut_body = "\n".join(f"{key} = {value}" for key, value in cut_lines.items())
    return f"""
schema = "vibecrafted.dispatch.v1"

[meta]
name = "dispatch-smoke"
repo = "/tmp/repo"
reports_dir = "/tmp/reports"

[policy]
concurrency = 1
on_timeout = "fail"

[[phases]]
title = "Foundation"
detail = "first cuts"

[[cuts]]
{cut_body}

  [[cuts.verify]]
  run = "echo ok"
  expect = {{ contains = "ok" }}
"""


def _error_text(text: str, *, base_dir: Path | None = None) -> str:
    with pytest.raises(DispatchContractError) as exc:
        parse_dispatch_contract(text, base_dir=base_dir)
    return "\n".join(exc.value.errors)


def test_minimal_valid_toml_parses_into_typed_contract_objects() -> None:
    contract = parse_dispatch_contract(_valid_contract())

    assert contract.schema == "vibecrafted.dispatch.v1"
    assert contract.meta.name == "dispatch-smoke"
    assert contract.policy.concurrency == 1
    assert contract.phases[0].title == "Foundation"
    assert contract.cuts[0].id == "w1-a"
    assert contract.cuts[0].resolved_workflow == "implement"
    assert contract.cuts[0].verify[0].matchers[0].kind == "contains"


def test_duplicate_cut_ids_are_rejected() -> None:
    text = (
        _valid_contract()
        + """

[[cuts]]
id = "w1-a"
phase = "Foundation"
agent = "claude"
workflow = "review"
prompt = "review"

  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
"""
    )

    assert "duplicate cut id 'w1-a'" in _error_text(text)


def test_unknown_schema_versions_are_rejected() -> None:
    text = _valid_contract().replace(
        'schema = "vibecrafted.dispatch.v1"',
        'schema = "vibecrafted.dispatch.v2"',
    )

    assert "unsupported schema 'vibecrafted.dispatch.v2'" in _error_text(text)


def test_unknown_workflow_names_are_rejected_unless_explicitly_mapped() -> None:
    text = _valid_contract(workflow='"moonshot"')

    assert "unsupported workflow 'moonshot'" in _error_text(text)

    mapped = text.replace(
        "[meta]",
        '[workflow_map]\nmoonshot = "review"\n\n[meta]',
    )
    contract = parse_dispatch_contract(mapped)

    assert contract.cuts[0].workflow == "moonshot"
    assert contract.cuts[0].resolved_workflow == "review"


def test_cuts_without_brief_or_prompt_are_rejected() -> None:
    text = _valid_contract(prompt='""')

    assert "prompt or brief is required" in _error_text(text)


def test_missing_brief_files_are_rejected(tmp_path: Path) -> None:
    text = _valid_contract(prompt='""', brief='"missing.md"')

    assert "brief: file is missing or unreadable" in _error_text(
        text,
        base_dir=tmp_path,
    )


def test_existing_brief_files_are_accepted(tmp_path: Path) -> None:
    brief = tmp_path / "brief.md"
    brief.write_text("do the thing\n", encoding="utf-8")

    contract = parse_dispatch_contract(
        _valid_contract(prompt='""', brief='"brief.md"'),
        base_dir=tmp_path,
    )

    assert contract.cuts[0].brief == "brief.md"


def test_cuts_without_verify_are_rejected_unless_observational_read_is_explicit() -> (
    None
):
    text = _valid_contract().replace(
        """
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
        "",
    )

    assert "verify: required unless observational READ is explicit" in _error_text(text)

    observational_read = text.replace(
        'prompt = "implement the cut"',
        'prompt = "inspect only"\nmode = "read"\nmutation = "forbid"\nobservational = true',
    )
    contract = parse_dispatch_contract(observational_read)

    assert contract.cuts[0].mode == "read"
    assert contract.cuts[0].observational is True
    assert contract.cuts[0].verify == ()


def test_concurrency_above_one_is_rejected_unless_enabled() -> None:
    text = _valid_contract().replace("concurrency = 1", "concurrency = 2")

    assert "values greater than 1 require allow_concurrency = true" in _error_text(text)

    enabled = text.replace(
        "concurrency = 2", "concurrency = 2\nallow_concurrency = true"
    )
    assert parse_dispatch_contract(enabled).policy.concurrency == 2


def test_read_cuts_require_mutation() -> None:
    text = _valid_contract().replace(
        'prompt = "implement the cut"',
        'prompt = "inspect only"\nmode = "read"',
    )

    assert "mutation: required for READ cuts" in _error_text(text)


def test_recovery_goto_must_resolve_to_known_cut_id_or_phase_title() -> None:
    text = _valid_contract().replace(
        'prompt = "implement the cut"',
        'prompt = "implement the cut"\nrecovery = { on = "[!]", goto = "missing" }',
    )

    assert "recovery.goto: unknown target 'missing'" in _error_text(text)

    by_phase = text.replace('goto = "missing"', 'goto = "Foundation"')
    assert parse_dispatch_contract(by_phase).cuts[0].recovery is not None


def test_matcher_types_include_required_minimum_set() -> None:
    text = _valid_contract().replace(
        'expect = { contains = "ok" }',
        'expect = { contains = "ok", equals = "ok", matches = "o[k]", not_contains = "fail", exit_code = 0 }',
    )

    contract = parse_dispatch_contract(text)

    assert {
        matcher.kind for matcher in contract.cuts[0].verify[0].matchers
    } == MATCHER_TYPES


def test_unsupported_matcher_shapes_are_rejected() -> None:
    text = _valid_contract().replace(
        'expect = { contains = "ok" }',
        'expect = { starts_with = "ok" }',
    )

    assert "expect.starts_with: unsupported matcher" in _error_text(text)


def test_doctor_result_returns_errors_without_throwing() -> None:
    result = doctor_dispatch_contract("schema = 'wrong'")

    assert result.ok is False
    assert result.contract is None
    assert any("unsupported schema" in error for error in result.errors)
