from __future__ import annotations

import json
from pathlib import Path

import pytest
from vibecrafted_core.dispatch.model import (
    STATE_FAILED,
    STATE_UNKNOWN,
    STATE_VERIFIED,
    Cut,
    Matcher,
    Verify,
)
from vibecrafted_core.dispatch.verify import (
    MATCHER_FAIL,
    MATCHER_PASS,
    MATCHER_TIMEOUT,
    run_verifies,
    sanitize_env,
)


def make_cut(*verifies: Verify) -> Cut:
    return Cut(
        id="c1",
        phase="Foundation",
        agent="claude",
        workflow="implement",
        resolved_workflow="implement",
        verify=tuple(verifies),
    )


def verify(run: str, **expect: str | int) -> Verify:
    matchers = tuple(
        Matcher(kind=kind, expected=expected) for kind, expected in expect.items()
    )
    return Verify(run=run, matchers=matchers)


def test_all_green_matchers_verify_cut(tmp_path: Path) -> None:
    cut = make_cut(verify("echo hello", contains="hello", exit_code=0))

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_VERIFIED
    assert verdict.failures == ()
    evidence = verdict.verifiers[0]
    assert evidence.ok is True
    assert evidence.matcher_result == MATCHER_PASS
    assert evidence.exit_code == 0
    assert evidence.command == "echo hello"
    assert "hello" in evidence.evidence
    assert evidence.elapsed_ms is not None and evidence.elapsed_ms >= 0
    assert evidence.timestamp


def test_one_failure_per_red_matcher_with_evidence(tmp_path: Path) -> None:
    cut = make_cut(
        verify("echo hello", contains="absent", equals="nope", not_contains="hello")
    )

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_FAILED
    assert len(verdict.failures) == 3
    assert all("hello" in failure for failure in verdict.failures)
    assert verdict.verifiers[0].matcher_result == MATCHER_FAIL
    assert verdict.verifiers[0].ok is False


def test_verdict_is_and_of_all_verifiers(tmp_path: Path) -> None:
    cut = make_cut(
        verify("echo green", contains="green"),
        verify("echo red", contains="missing"),
    )

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_FAILED
    assert len(verdict.failures) == 1
    assert verdict.verifiers[0].matcher_result == MATCHER_PASS
    assert verdict.verifiers[1].matcher_result == MATCHER_FAIL


def test_exit_code_matcher_on_failing_command(tmp_path: Path) -> None:
    cut = make_cut(verify("exit 3", exit_code=3))

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_VERIFIED
    assert verdict.verifiers[0].exit_code == 3


def test_matchers_see_stderr(tmp_path: Path) -> None:
    cut = make_cut(verify("echo oops 1>&2", contains="oops"))

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_VERIFIED
    assert "oops" in verdict.verifiers[0].evidence


def test_timeout_marks_cut_unknown(tmp_path: Path) -> None:
    cut = make_cut(verify("sleep 5", contains="never"))

    verdict = run_verifies(cut, repo=str(tmp_path), timeout_s=0.2)

    assert verdict.state == STATE_UNKNOWN
    evidence = verdict.verifiers[0]
    assert evidence.matcher_result == MATCHER_TIMEOUT
    assert evidence.ok is False
    assert evidence.exit_code is None
    assert len(verdict.failures) == 1
    assert "timeout" in verdict.failures[0]


def test_red_matcher_beats_timeout(tmp_path: Path) -> None:
    cut = make_cut(
        verify("echo red", contains="missing"),
        verify("sleep 5", contains="never"),
    )

    verdict = run_verifies(cut, repo=str(tmp_path), timeout_s=0.2)

    assert verdict.state == STATE_FAILED
    assert len(verdict.failures) == 2


def test_commands_run_in_repo_cwd(tmp_path: Path) -> None:
    cut = make_cut(verify("pwd", equals=str(tmp_path.resolve())))

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_VERIFIED, verdict.failures


def test_env_is_sanitized_for_verifier_shells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VC_DISPATCH_SECRET", "leak")
    cut = make_cut(verify('echo "${VC_DISPATCH_SECRET:-absent}"', equals="absent"))

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_VERIFIED, verdict.failures


def test_sanitize_env_keeps_path_and_drops_noise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VC_DISPATCH_SECRET", "leak")

    env = sanitize_env()

    assert "VC_DISPATCH_SECRET" not in env
    assert env.get("PATH")
    assert sanitize_env(extra={"VC_EXTRA": "1"})["VC_EXTRA"] == "1"


def test_evidence_serializes_to_journal_json(tmp_path: Path) -> None:
    cut = make_cut(verify("echo hello", contains="hello"))

    verdict = run_verifies(cut, repo=str(tmp_path))
    payload = json.loads(json.dumps(verdict.to_dict()))

    record = payload["verifiers"][0]
    assert set(record) == {
        "command",
        "ok",
        "exit_code",
        "evidence",
        "elapsed_ms",
        "timestamp",
        "matcher_result",
    }


def test_excerpt_keeps_head_and_tail(tmp_path: Path) -> None:
    cut = make_cut(
        verify("for i in {1..100}; do echo line-$i; done", contains="line-100")
    )

    verdict = run_verifies(cut, repo=str(tmp_path))

    excerpt = verdict.verifiers[0].evidence
    assert verdict.state == STATE_VERIFIED
    assert "line-1\n" in excerpt
    assert "line-100" in excerpt
    assert "lines omitted" in excerpt


def test_cut_without_verifiers_stays_unknown(tmp_path: Path) -> None:
    cut = make_cut()

    verdict = run_verifies(cut, repo=str(tmp_path))

    assert verdict.state == STATE_UNKNOWN
    assert verdict.verifiers == ()
    assert verdict.failures == ()


def test_bare_verify_list_with_expect_reports_ok(tmp_path: Path) -> None:
    verdict = run_verifies(
        [
            Verify(run="echo hello", expect={"contains": "hello"}),
            Verify(run="false", expect={"exit_code": "1"}),
        ],
        repo=str(tmp_path),
        env={},
    )

    assert verdict.ok is True
    assert verdict.state == STATE_VERIFIED
    assert verdict.cut_id == "adhoc"


def test_verdict_ok_is_false_on_red_matcher(tmp_path: Path) -> None:
    verdict = run_verifies(
        [Verify(run="echo hello", expect={"contains": "absent"})],
        repo=str(tmp_path),
    )

    assert verdict.ok is False
    assert verdict.state == STATE_FAILED


def test_expect_exit_code_coerces_string_to_int() -> None:
    matcher = Verify(run="false", expect={"exit_code": "1"}).matchers[0]

    assert matcher.expected == 1
    assert matcher.check("", exit_code=1) is True


def test_expect_rejects_unknown_matcher_kind() -> None:
    with pytest.raises(ValueError, match="unsupported matcher kind"):
        Verify(run="true", expect={"exitcode": "0"})


def test_repo_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    verdict = run_verifies(
        [Verify(run="pwd", expect={"equals": str(tmp_path.resolve())})]
    )

    assert verdict.ok is True, verdict.failures
