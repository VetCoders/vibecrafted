"""Tests for the runtime caller of ``vc-frame triage-run``.

The transfer primitive itself lives in vc-frame and is tested there. What is at
stake here is the caller's judgement: which runs may be transferred at all, which
drawer the conjunction of a run's signals earns it, and — above all — that nothing
in this path can damage a run that has already finished.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pytest

from vibecrafted_core.run_triage import (
    BUCKET_FAILED,
    BUCKET_FINALIZED,
    BUCKET_NEEDS_ATTENTION,
    KernelAxes,
    MINIMAL_TRANSCRIPT_BYTES,
    OUTCOME_ERROR,
    OUTCOME_FAILED,
    OUTCOME_FINALIZED,
    OUTCOME_NEEDS_ATTENTION,
    OUTCOME_SKIPPED,
    VERDICT_FAILED,
    VERDICT_FINALIZED,
    VERDICT_NEEDS_ATTENTION,
    bucket_for_exit_code,
    classify_run,
    plan_triage,
    read_kernel_axes,
    read_run_signals,
    triage_finished_run,
)

MODERN_HELP = "Usage: vc-frame triage-run [OPTIONS]\n  --bucket <BUCKET>\n"


class FakeProc:
    def __init__(self, returncode: int = 0, stderr: str = "", stdout: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


class Runner:
    """Records invocations; answers the `--help` probe as a modern binary would."""

    def __init__(
        self,
        result: Any = None,
        supports: bool = True,
        supports_bucket: bool = True,
    ) -> None:
        self.calls: list[list[str]] = []
        self.result = result if result is not None else FakeProc(0)
        self.supports = supports
        self.supports_bucket = supports_bucket

    def __call__(self, argv: Sequence[str]) -> Any:
        argv = list(argv)
        self.calls.append(argv)
        if argv[1:] == ["triage-run", "--help"]:
            if not self.supports:
                return FakeProc(2)
            return FakeProc(0, stdout=MODERN_HELP if self.supports_bucket else "")
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    @property
    def transfer_calls(self) -> list[list[str]]:
        return [c for c in self.calls if c[1:2] == ["triage-run"] and "--help" not in c]

    def bucket_flag(self) -> str | None:
        call = self.transfer_calls[0]
        return call[call.index("--bucket") + 1] if "--bucket" in call else None


LIVE_ENV = {
    "VC_FRAME_SESSION_NAME": "vibecrafted-dev",
    "VC_FRAME_PANE_ID": "terminal_3",
    "PATH": "/usr/bin",
    "VIBECRAFTED_VC_FRAME_BIN": "",
}


def make_env(**overrides: str) -> dict[str, str]:
    env = dict(LIVE_ENV)
    env.update(overrides)
    return env


def fake_bin(tmp_path: Path) -> str:
    """An on-disk vc-frame stand-in — `_resolve_binary` requires the path to exist."""
    binary = tmp_path / "vc-frame"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return str(binary)


def live_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    return make_env(VIBECRAFTED_VC_FRAME_BIN=fake_bin(tmp_path), **overrides)


def _tiny_transcript(tmp_path: Path) -> Path:
    """A transcript holding nothing but the launcher banner — the W0-A shape."""
    path = tmp_path / "banner-only.transcript.log"
    path.write_text("x" * (MINIMAL_TRANSCRIPT_BYTES - 1), encoding="utf-8")
    return path


def write_meta(tmp_path: Path, **overrides: Any) -> Path:
    """A clean finalized run: exit 0, `completed`, report on disk, real transcript.

    Every deviation a test wants is an override, so each test names exactly the
    one signal it is bending.
    """
    report = tmp_path / "agent.md"
    report.write_text("# report\n", encoding="utf-8")
    transcript = tmp_path / "agent.transcript.log"
    transcript.write_text("x" * (MINIMAL_TRANSCRIPT_BYTES * 4), encoding="utf-8")

    payload: dict[str, Any] = {
        "status": "completed",
        "run_id": "run-0007",
        "exit_code": 0,
        "root": "/repo",
        "launcher": "/tmp/launch-run-0007.sh",
        "liveness": "terminal",
        "report": str(report),
        "transcript": str(transcript),
    }
    payload.update(overrides)
    meta = tmp_path / "agent.meta.json"
    meta.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return meta


# --------------------------------------------------------------------------
# The classifier. Single signals lie, so the verdict is a conjunction — and the
# whole point of this matrix is that only two rows are allowed to be confident.
# --------------------------------------------------------------------------

BIG = MINIMAL_TRANSCRIPT_BYTES * 10
TINY = MINIMAL_TRANSCRIPT_BYTES - 1


def verdict(
    exit_code: Any = 0,
    state: Any = "completed",
    report_exists: bool | None = True,
    report_bytes: int | None = 512,
    transcript_bytes: int | None = BIG,
) -> str:
    return classify_run(
        exit_code, state, report_exists, report_bytes, transcript_bytes
    ).verdict


# --- The two confident verdicts ------------------------------------------


@pytest.mark.parametrize(
    "state", ["completed", "report_validated", "closed", "converged"]
)
def test_finalized_needs_all_three_signals(state: str) -> None:
    """Exit 0 AND a delivery state AND a report actually on disk."""
    assert verdict(exit_code=0, state=state) == VERDICT_FINALIZED


@pytest.mark.parametrize("state", ["failed", "stopped", "report_missing"])
@pytest.mark.parametrize("code", [1, 2, 137, 143])
def test_failed_is_a_run_that_died_before_working(state: str, code: int) -> None:
    """Non-zero exit AND death state AND no report AND nothing in the transcript."""
    assert (
        verdict(
            exit_code=code,
            state=state,
            report_exists=False,
            report_bytes=0,
            transcript_bytes=TINY,
        )
        == VERDICT_FAILED
    )


def test_w0a_specimen_is_failed() -> None:
    """Today's live specimen: worker killed by the session limit.

    Exit non-zero, control-plane state `report_missing`, no report, and a
    transcript holding nothing but the launcher banner. This is the shape the
    third bucket exists for — it must not land in "Needs attention" and drown
    the contradictions that actually need a human.
    """
    signals = classify_run(
        exit_code=1,
        run_state="report_missing",
        report_exists=False,
        report_bytes=0,
        transcript_bytes=180,
    )
    assert signals.verdict == VERDICT_FAILED
    assert signals.bucket == BUCKET_FAILED
    assert signals.bucket_flag == "failed"
    assert "180b" in signals.reason


# --- Every contradiction routes to a human -------------------------------


def test_exit_zero_without_report_is_a_contradiction() -> None:
    """The 2026-05-14 record: top-level `completed`/exit 0, nothing delivered."""
    assert (
        verdict(exit_code=0, report_exists=False, report_bytes=0)
        == VERDICT_NEEDS_ATTENTION
    )


def test_nonzero_exit_with_a_report_is_a_contradiction() -> None:
    """The mirror: the run says it died, the artifacts say it delivered."""
    assert verdict(exit_code=1, state="failed") == VERDICT_NEEDS_ATTENTION


def test_exit_zero_with_a_death_state_is_a_contradiction() -> None:
    assert verdict(exit_code=0, state="failed") == VERDICT_NEEDS_ATTENTION


def test_nonzero_exit_with_a_delivery_state_is_a_contradiction() -> None:
    assert (
        verdict(exit_code=1, state="completed", report_exists=False, report_bytes=0)
        == VERDICT_NEEDS_ATTENTION
    )


def test_empty_report_is_never_a_delivery() -> None:
    """A zero-byte report is control_plane's `report_invalid`, not a report."""
    assert verdict(exit_code=0, report_bytes=0) == VERDICT_NEEDS_ATTENTION


def test_death_after_real_work_is_not_a_clean_failure() -> None:
    """It died — but it did something first, and that something is worth a look."""
    assert (
        verdict(
            exit_code=1,
            state="failed",
            report_exists=False,
            report_bytes=0,
            transcript_bytes=BIG,
        )
        == VERDICT_NEEDS_ATTENTION
    )


@pytest.mark.parametrize(
    "state",
    [
        "report_invalid",
        "contract_failed",
        "ghost",
        "timed_out",
        "recovery_required",
        "blocked",
        "stalled",
        "gc",
    ],
)
@pytest.mark.parametrize("code", [0, 1])
def test_ambiguous_states_never_reach_a_confident_drawer(state: str, code: int) -> None:
    """These states *are* the contradiction — no other signal can rescue them."""
    assert verdict(exit_code=code, state=state) == VERDICT_NEEDS_ATTENTION


# --- Unreadable signals fail closed, never to a drawer -------------------


@pytest.mark.parametrize("code", [None, "", "abc", [], {}])
def test_unreadable_exit_code_fails_closed(code: Any) -> None:
    assert verdict(exit_code=code) == VERDICT_NEEDS_ATTENTION


@pytest.mark.parametrize("state", [None, "", "   ", "some_state_from_the_future"])
def test_unreadable_or_unknown_state_fails_closed(state: Any) -> None:
    """An unrecognised state is a signal we cannot read, not a benign one."""
    assert verdict(state=state) == VERDICT_NEEDS_ATTENTION


def test_unstattable_report_fails_closed() -> None:
    assert verdict(report_exists=None, report_bytes=None) == VERDICT_NEEDS_ATTENTION


def test_report_of_unknown_size_fails_closed() -> None:
    assert verdict(report_exists=True, report_bytes=None) == VERDICT_NEEDS_ATTENTION


def test_unreadable_transcript_fails_closed() -> None:
    """Without the transcript we cannot tell a death from a death-after-work."""
    assert (
        verdict(
            exit_code=1,
            state="failed",
            report_exists=False,
            report_bytes=0,
            transcript_bytes=None,
        )
        == VERDICT_NEEDS_ATTENTION
    )


def test_state_matching_is_case_and_whitespace_tolerant() -> None:
    assert verdict(state="  Completed  ") == VERDICT_FINALIZED


def test_every_verdict_carries_a_reason() -> None:
    """The receipt has to be able to say *why*, for all three verdicts."""
    for classification in (
        classify_run(0, "completed", True, 10, BIG),
        classify_run(1, "failed", False, 0, TINY),
        classify_run(0, "ghost", True, 10, BIG),
    ):
        assert classification.reason
        assert classification.bucket
        assert classification.bucket_flag


# --------------------------------------------------------------------------
# Reading the signals off a run's artifacts
# --------------------------------------------------------------------------


def test_signals_are_read_from_the_artifacts_on_disk(tmp_path: Path) -> None:
    report = tmp_path / "r.md"
    report.write_text("body", encoding="utf-8")
    transcript = tmp_path / "t.log"
    transcript.write_text("xyz", encoding="utf-8")

    signals = read_run_signals(
        {
            "exit_code": 0,
            "status": "completed",
            "report": str(report),
            "transcript": str(transcript),
        }
    )

    assert signals.report_exists is True
    assert signals.report_bytes == 4
    assert signals.transcript_bytes == 3
    assert signals.classify().verdict == VERDICT_FINALIZED


def test_declared_but_absent_report_is_absent_not_unreadable(tmp_path: Path) -> None:
    signals = read_run_signals(
        {"exit_code": 1, "status": "failed", "report": str(tmp_path / "gone.md")}
    )
    assert signals.report_exists is False
    assert signals.report_bytes == 0


def test_undeclared_transcript_is_unknown(tmp_path: Path) -> None:
    """No transcript path means we do not know where to look — not zero work."""
    signals = read_run_signals({"exit_code": 1, "status": "failed"})
    assert signals.transcript_bytes is None
    assert signals.classify().verdict == VERDICT_NEEDS_ATTENTION


def test_symlinked_transcript_is_measured_through_the_link(tmp_path: Path) -> None:
    """`spawn.finalize_artifacts` leaves a compat symlink at the announced path,
    so the announced transcript is routinely a link to the real one. Measuring
    the link instead of its target reads ~60 bytes and calls a full run dead."""
    real = tmp_path / "real.log"
    real.write_text("x" * BIG, encoding="utf-8")
    link = tmp_path / "announced.log"
    link.symlink_to(real)

    signals = read_run_signals(
        {"exit_code": 1, "status": "failed", "transcript": str(link)}
    )

    assert signals.transcript_bytes == BIG


def test_control_plane_state_key_wins_over_launcher_status() -> None:
    """`state` is the control-plane spelling; when present it is the fresher truth."""
    signals = read_run_signals(
        {"exit_code": 0, "status": "completed", "state": "contract_failed"}
    )
    assert signals.run_state == "contract_failed"
    assert signals.classify().verdict == VERDICT_NEEDS_ATTENTION


# --------------------------------------------------------------------------
# Exit code → bucket. The degraded path only; it must hold for the whole range.
# --------------------------------------------------------------------------


def test_only_exit_zero_is_success() -> None:
    assert bucket_for_exit_code(0) == BUCKET_FINALIZED
    for code in (1, 2, 7, 127, 255):
        assert bucket_for_exit_code(code) == BUCKET_NEEDS_ATTENTION


def test_timeouts_and_kills_need_attention() -> None:
    # SIGKILL / SIGTERM as the shell reports them. The spec calls these out
    # explicitly; they are non-zero, so they need no special case — this test
    # exists to keep it that way.
    assert bucket_for_exit_code(137) == BUCKET_NEEDS_ATTENTION  # 128 + SIGKILL
    assert bucket_for_exit_code(143) == BUCKET_NEEDS_ATTENTION  # 128 + SIGTERM
    assert bucket_for_exit_code(124) == BUCKET_NEEDS_ATTENTION  # coreutils timeout


@pytest.mark.parametrize("code", [None, "", "abc", [], {}])
def test_unreadable_exit_code_needs_attention(code: Any) -> None:
    """A run whose outcome we cannot read is exactly a run needing attention."""
    assert bucket_for_exit_code(code) == BUCKET_NEEDS_ATTENTION


def test_string_exit_codes_parse() -> None:
    assert bucket_for_exit_code("0") == BUCKET_FINALIZED
    assert bucket_for_exit_code("1") == BUCKET_NEEDS_ATTENTION


# --------------------------------------------------------------------------
# Which runs may be transferred at all
# --------------------------------------------------------------------------


def test_headless_run_is_skipped_not_failed() -> None:
    """CI / detached runs have no pane env. Nothing to triage is not an error."""
    plan = plan_triage({"run_id": "r1", "exit_code": 0}, {"PATH": "/usr/bin"})
    assert plan.should_run is False
    assert plan.skip_reason == "no_session"


def test_pane_env_without_session_name_is_skipped() -> None:
    plan = plan_triage(
        {"run_id": "r1", "exit_code": 0},
        {"VC_FRAME_PANE_ID": "terminal_1"},
    )
    assert plan.should_run is False
    assert plan.skip_reason == "no_session"


def test_legacy_zellij_env_still_identifies_a_session() -> None:
    """vc-frame dual-emits ZELLIJ_* during the rename transition."""
    plan = plan_triage(
        {"run_id": "r1", "exit_code": 0},
        {"ZELLIJ_PANE_ID": "terminal_1", "ZELLIJ_SESSION_NAME": "sess"},
    )
    assert plan.should_run is True
    assert plan.origin_session == "sess"


def test_marbles_shared_tab_is_never_closed() -> None:
    """Closing a shared tab would destroy the sibling marbles' scrollback."""
    plan = plan_triage(
        {"run_id": "r1", "exit_code": 0},
        make_env(
            VIBECRAFTED_MARBLES_TAB_NAME="marbles-wave-3",
            VC_FRAME_TAB_NAME="marbles-wave-3",
        ),
    )
    assert plan.should_run is False
    assert plan.skip_reason == "shared_tab"


def test_run_owning_its_tab_is_transferred_even_under_marbles() -> None:
    """A marbles run in its OWN tab is safe — only the shared tab is refused."""
    plan = plan_triage(
        {"run_id": "r1", "exit_code": 0},
        make_env(
            VIBECRAFTED_MARBLES_TAB_NAME="marbles-wave-3",
            VC_FRAME_TAB_NAME="r1",
        ),
    )
    assert plan.should_run is True
    assert plan.origin_tab == "r1"


def test_missing_run_id_is_skipped() -> None:
    plan = plan_triage({"exit_code": 0}, make_env())
    assert plan.should_run is False
    assert plan.skip_reason == "no_run_id"


def test_run_id_falls_back_to_spawn_env() -> None:
    plan = plan_triage({"exit_code": 0}, make_env(SPAWN_RUN_ID="run-from-env"))
    assert plan.should_run is True
    assert plan.run_id == "run-from-env"


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "OFF"])
def test_operator_can_switch_triage_off(value: str) -> None:
    plan = plan_triage(
        {"run_id": "r1", "exit_code": 0},
        make_env(VIBECRAFTED_TRIAGE_RUN=value),
    )
    assert plan.should_run is False
    assert plan.skip_reason == "disabled"


def test_tab_defaults_to_run_id() -> None:
    """The runtime names run tabs by run id (lib/vc_frame.sh)."""
    plan = plan_triage({"run_id": "run-0007", "exit_code": 0}, make_env())
    assert plan.origin_tab == "run-0007"


# --------------------------------------------------------------------------
# The rendered invocation
# --------------------------------------------------------------------------


def test_argv_carries_the_full_identity() -> None:
    plan = plan_triage(
        {
            "run_id": "run-0007",
            "exit_code": 3,
            "root": "/repo",
            "launcher": "/tmp/l.sh",
        },
        make_env(),
    )
    argv = plan.argv("/usr/bin/vc-frame")

    assert argv[:2] == ["/usr/bin/vc-frame", "triage-run"]
    assert argv[argv.index("--run") + 1] == "run-0007"
    assert argv[argv.index("--exit-code") + 1] == "3"
    assert argv[argv.index("--origin-session") + 1] == "vibecrafted-dev"
    assert argv[argv.index("--origin-tab") + 1] == "run-0007"
    assert argv[argv.index("--pane-id") + 1] == "terminal_3"
    assert argv[argv.index("--cwd") + 1] == "/repo"
    # The rerun pane gets the launcher — the run, reproducible.
    assert argv[-2:] == ["--", "/tmp/l.sh"]


def test_argv_carries_the_verdict_as_a_bucket_flag(tmp_path: Path) -> None:
    """W2-B-4a's contract: the drawer is ours to choose, in kebab spelling."""
    meta = write_meta(tmp_path, exit_code=0)
    runner = Runner()

    triage_finished_run(meta, live_env(tmp_path), runner)

    assert runner.bucket_flag() == "finalized"


def test_command_is_passed_after_the_separator() -> None:
    """clap `last(true)`: everything after `--` is the preserved command line."""
    plan = plan_triage(
        {"run_id": "r", "exit_code": 0, "command": ["claude", "-p", "do it"]},
        make_env(),
    )
    argv = plan.argv("vc-frame")
    assert argv[argv.index("--") + 1 :] == ["claude", "-p", "do it"]


# --------------------------------------------------------------------------
# Fail-open. Nothing here may ever damage an already-finished run.
# --------------------------------------------------------------------------


def test_stale_binary_without_the_subcommand_is_a_skip(tmp_path: Path) -> None:
    """An install predating vc-frame 71146085 must not read as a failure."""
    meta = write_meta(tmp_path)
    runner = Runner(supports=False)

    outcome = triage_finished_run(meta, live_env(tmp_path), runner)

    assert outcome.outcome == OUTCOME_SKIPPED
    assert outcome.reason == "unsupported_binary"
    # Crucially: we never attempted the transfer against a binary that can't do it.
    assert runner.transfer_calls == []


def test_binary_predating_the_bucket_flag_degrades_gracefully(tmp_path: Path) -> None:
    """A vc-frame with `triage-run` but no `--bucket` must still work.

    Passing a flag it cannot parse would fail the whole call, so we omit it and
    let vc-frame bucket by exit code — and the receipt says so, both in where the
    run actually went and in the fact that the verdict did not choose it.
    """
    meta = write_meta(
        tmp_path,
        exit_code=137,
        status="report_missing",
        report=str(tmp_path / "never-written.md"),
        transcript=str(_tiny_transcript(tmp_path)),
    )
    runner = Runner(supports_bucket=False)

    outcome = triage_finished_run(meta, live_env(tmp_path), runner)

    assert runner.bucket_flag() is None
    assert outcome.verdict_degraded == "exit_code_only"
    # The verdict was `failed`, but a stale vc-frame has no such drawer, so the
    # receipt must name the drawer the run really lands in.
    assert outcome.verdict == VERDICT_FAILED
    assert outcome.outcome == OUTCOME_NEEDS_ATTENTION
    assert outcome.bucket == BUCKET_NEEDS_ATTENTION

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["triage_verdict"] == VERDICT_FAILED
    assert payload["triage_bucket"] == BUCKET_NEEDS_ATTENTION
    assert payload["triage_verdict_degraded"] == "exit_code_only"


def test_missing_binary_is_a_skip(tmp_path: Path) -> None:
    meta = write_meta(tmp_path)
    runner = Runner()

    outcome = triage_finished_run(
        meta, make_env(PATH="/nonexistent", VIBECRAFTED_VC_FRAME_BIN=""), runner
    )

    assert outcome.outcome == OUTCOME_SKIPPED
    assert outcome.reason == "no_binary"


def test_nonzero_triage_exit_is_recorded_not_raised(tmp_path: Path) -> None:
    meta = write_meta(tmp_path)
    runner = Runner(result=FakeProc(2, stderr="bucket session vanished"))

    outcome = triage_finished_run(meta, live_env(tmp_path), runner)

    # `error` and not `failed`: a broken transfer says nothing about the run.
    assert outcome.outcome == OUTCOME_ERROR
    assert "bucket session vanished" in outcome.reason
    # The verdict survives the broken transfer, so the operator still sees it.
    assert outcome.verdict == VERDICT_FINALIZED


def test_exploding_runner_is_contained(tmp_path: Path) -> None:
    """Even an OSError from the subprocess layer must not escape."""
    meta = write_meta(tmp_path)
    runner = Runner(result=OSError("no fork for you"))

    outcome = triage_finished_run(meta, live_env(tmp_path), runner)

    assert outcome.outcome == OUTCOME_ERROR
    assert "no fork for you" in outcome.reason


def test_unreadable_meta_does_not_raise(tmp_path: Path) -> None:
    meta = tmp_path / "broken.meta.json"
    meta.write_text("{not json", encoding="utf-8")

    outcome = triage_finished_run(meta, make_env(), Runner())

    assert outcome.outcome == OUTCOME_SKIPPED
    assert outcome.reason.startswith("no_meta")


def test_absent_meta_does_not_raise(tmp_path: Path) -> None:
    outcome = triage_finished_run(tmp_path / "gone.json", make_env(), Runner())
    assert outcome.outcome == OUTCOME_SKIPPED


# --------------------------------------------------------------------------
# Receipts
# --------------------------------------------------------------------------


def test_success_receipt_names_the_bucket(tmp_path: Path) -> None:
    meta = write_meta(tmp_path, exit_code=0)

    outcome = triage_finished_run(meta, live_env(tmp_path), Runner())

    assert outcome.outcome == OUTCOME_FINALIZED
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["triage"] == OUTCOME_FINALIZED
    assert payload["triage_bucket"] == BUCKET_FINALIZED
    assert payload["triage_pending"] is False


def test_receipt_records_the_verdict_and_its_evidence(tmp_path: Path) -> None:
    """The operator must be able to audit *why* a run went where it went."""
    meta = write_meta(tmp_path, exit_code=0)

    triage_finished_run(meta, live_env(tmp_path), Runner())

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["triage_verdict"] == VERDICT_FINALIZED
    assert payload["triage_verdict_reason"] == "exit_0_report_delivered"
    assert payload["triage_verdict_degraded"] == ""


def test_killed_run_receipt_says_failed(tmp_path: Path) -> None:
    """Exit 137, no report, banner-only transcript — the W0-A shape, end to end."""
    meta = write_meta(
        tmp_path,
        exit_code=137,
        status="report_missing",
        report=str(tmp_path / "never-written.md"),
        transcript=str(_tiny_transcript(tmp_path)),
    )

    outcome = triage_finished_run(meta, live_env(tmp_path), Runner())

    assert outcome.outcome == OUTCOME_FAILED
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["triage_bucket"] == BUCKET_FAILED
    assert payload["triage_verdict"] == VERDICT_FAILED


def test_contradicting_run_receipt_says_needs_attention(tmp_path: Path) -> None:
    """Exit 137 with a full report on disk — the signals disagree, so: a human."""
    meta = write_meta(tmp_path, exit_code=137, status="failed")

    outcome = triage_finished_run(meta, live_env(tmp_path), Runner())

    assert outcome.outcome == OUTCOME_NEEDS_ATTENTION
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["triage_bucket"] == BUCKET_NEEDS_ATTENTION
    assert payload["triage_verdict_reason"] == "exit_137_with_report"


def test_skip_receipt_is_written_for_headless_runs(tmp_path: Path) -> None:
    """The spec's `triage_skipped: no_session` — a note, not an error."""
    meta = write_meta(tmp_path)

    triage_finished_run(meta, {"PATH": "/usr/bin"}, Runner())

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["triage"] == OUTCOME_SKIPPED
    assert payload["triage_reason"] == "no_session"


def test_intent_is_recorded_before_the_transfer(tmp_path: Path) -> None:
    """Our own success closes this tab and can kill us mid-flight.

    So the receipt must be on disk *before* the transfer runs, marked pending.
    Asserted by reading meta.json from inside the runner.
    """
    meta = write_meta(tmp_path, exit_code=0)
    seen: dict[str, Any] = {}

    class PeekingRunner(Runner):
        def __call__(self, argv: Sequence[str]) -> Any:
            if list(argv)[1:2] == ["triage-run"] and "--help" not in argv:
                seen.update(json.loads(meta.read_text(encoding="utf-8")))
            return super().__call__(argv)

    triage_finished_run(meta, live_env(tmp_path), PeekingRunner())

    assert seen["triage"] == OUTCOME_FINALIZED
    assert seen["triage_pending"] is True
    assert seen["triage_bucket"] == BUCKET_FINALIZED


def test_receipt_never_disturbs_terminal_state(tmp_path: Path) -> None:
    """The run's own truth is not ours to edit."""
    meta = write_meta(tmp_path, exit_code=7, status="failed", duration_s=12.5)

    triage_finished_run(meta, live_env(tmp_path), Runner())

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 7
    assert payload["duration_s"] == 12.5
    assert payload["liveness"] == "terminal"


def test_concurrent_writer_is_not_clobbered(tmp_path: Path) -> None:
    """meta.json is re-read before the receipt lands, so a control-plane sync
    (or any other writer) that touched it mid-transfer keeps its change."""
    meta = write_meta(tmp_path, exit_code=0)

    class ConcurrentRunner(Runner):
        def __call__(self, argv: Sequence[str]) -> Any:
            if list(argv)[1:2] == ["triage-run"] and "--help" not in argv:
                payload = json.loads(meta.read_text(encoding="utf-8"))
                payload["session_id"] = "written-by-someone-else"
                meta.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            return super().__call__(argv)

    triage_finished_run(meta, live_env(tmp_path), ConcurrentRunner())

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["session_id"] == "written-by-someone-else"
    assert payload["triage"] == OUTCOME_FINALIZED


# --------------------------------------------------------------------------
# G4 — Delivery-kernel three-axis branch
#
# When a kernel receipt is present, the drawer follows the orthogonal axes
# (execution / proof / delivery). Without a receipt the legacy 5-signal
# conjunction above is the whole story — those tests must stay green.
# --------------------------------------------------------------------------


def _axes(
    *,
    execution: str = "exited",
    proof: str = "passed",
    delivery: str = "unverified",
    corrupt: bool = False,
) -> KernelAxes:
    return KernelAxes(
        execution_state=execution,
        proof_state=proof,
        delivery_state=delivery,
        corrupt=corrupt,
    )


def test_kernel_sealed_is_finalized_even_with_tiny_transcript() -> None:
    """delivery=sealed is authority; legacy transcript size is irrelevant."""
    classification = classify_run(
        exit_code=1,
        run_state="failed",
        report_exists=False,
        report_bytes=0,
        transcript_bytes=TINY,
        kernel_axes=_axes(delivery="sealed", execution="exited", proof="passed"),
    )
    assert classification.verdict == VERDICT_FINALIZED
    assert classification.bucket_flag == "finalized"
    assert "sealed" in classification.reason


def test_kernel_proof_invalid_is_failed() -> None:
    classification = classify_run(
        0,
        "completed",
        True,
        512,
        BIG,
        kernel_axes=_axes(proof="invalid", delivery="unverified"),
    )
    assert classification.verdict == VERDICT_FAILED
    assert classification.bucket_flag == "failed"
    assert (
        "proof_invalid" in classification.reason or "invalid" in classification.reason
    )


def test_kernel_execution_failed_is_failed() -> None:
    classification = classify_run(
        0,
        "completed",
        True,
        512,
        BIG,
        kernel_axes=_axes(
            execution="failed", proof="undeclared", delivery="unverified"
        ),
    )
    assert classification.verdict == VERDICT_FAILED
    assert classification.bucket_flag == "failed"
    assert (
        "execution_failed" in classification.reason or "failed" in classification.reason
    )


def test_kernel_partial_axes_need_attention() -> None:
    """exited + passed + unverified is honest incompleteness, not a drawer lie."""
    classification = classify_run(
        0,
        "completed",
        True,
        512,
        BIG,
        kernel_axes=_axes(execution="exited", proof="passed", delivery="unverified"),
    )
    assert classification.verdict == VERDICT_NEEDS_ATTENTION
    assert classification.bucket_flag == "needs-attention"


def test_kernel_proof_failed_is_failed() -> None:
    classification = classify_run(
        0,
        "completed",
        True,
        512,
        BIG,
        kernel_axes=_axes(proof="failed", delivery="unverified"),
    )
    assert classification.verdict == VERDICT_FAILED


def test_no_kernel_receipt_keeps_legacy_conjunction() -> None:
    """Absence of axes is the pre-G4 path — sealed-or-not never enters."""
    # Same inputs as the legacy finalized matrix row.
    assert (
        classify_run(0, "completed", True, 512, BIG, kernel_axes=None).verdict
        == VERDICT_FINALIZED
    )
    # And the W0-A death still fails without axes.
    assert (
        classify_run(1, "report_missing", False, 0, TINY, kernel_axes=None).verdict
        == VERDICT_FAILED
    )


def test_corrupt_kernel_receipt_fails_closed_never_raises(tmp_path: Path) -> None:
    """Unreadable receipt body is not 'no receipt' — it is unreadable axes."""
    bad = tmp_path / "axes.json"
    bad.write_text("{not-json", encoding="utf-8")

    # Path to a broken JSON file.
    axes = read_kernel_axes({"delivery_axes": str(bad)})
    assert axes is not None
    assert axes.corrupt is True
    assert (
        classify_run(0, "completed", True, 512, BIG, kernel_axes=axes).verdict
        == VERDICT_NEEDS_ATTENTION
    )

    # Inline garbage is the same fail-closed shape.
    axes2 = read_kernel_axes({"delivery_axes": "{still-not-json"})
    assert axes2 is not None and axes2.corrupt is True
    assert (
        classify_run(0, "completed", True, 512, BIG, kernel_axes=axes2).verdict
        == VERDICT_NEEDS_ATTENTION
    )


def test_read_run_signals_picks_up_meta_axes(tmp_path: Path) -> None:
    """Lifecycle/ship write the three axis keys onto the run receipt."""
    report = tmp_path / "r.md"
    report.write_text("body", encoding="utf-8")
    # Tiny transcript would block legacy finalized; axes must win.
    transcript = tmp_path / "t.log"
    transcript.write_text("x" * TINY, encoding="utf-8")

    signals = read_run_signals(
        {
            "exit_code": 0,
            "status": "completed",
            "report": str(report),
            "transcript": str(transcript),
            "execution_state": "exited",
            "proof_state": "passed",
            "delivery_state": "sealed",
        }
    )
    assert signals.kernel_axes is not None
    assert signals.kernel_axes.delivery_state == "sealed"
    assert signals.classify().verdict == VERDICT_FINALIZED


def test_read_kernel_axes_absent_when_no_receipt() -> None:
    assert read_kernel_axes({"exit_code": 0, "status": "completed"}) is None


def test_nested_delivery_axes_dict_is_a_receipt() -> None:
    axes = read_kernel_axes(
        {
            "delivery_axes": {
                "execution_state": "exited",
                "proof_state": "passed",
                "delivery_state": "sealed",
            }
        }
    )
    assert axes is not None
    assert axes.delivery_state == "sealed"


def test_modern_caller_always_passes_explicit_bucket_for_every_verdict(
    tmp_path: Path,
) -> None:
    """vc-frame BucketKind::for_exit_code never yields Failed — only --bucket does.

    The modern path must therefore always ship an explicit --bucket flag for
    every confident verdict, including failed.
    """
    cases = [
        # sealed axes → finalized
        {
            "exit_code": 0,
            "status": "completed",
            "execution_state": "exited",
            "proof_state": "passed",
            "delivery_state": "sealed",
            "expected_bucket": "finalized",
        },
        # execution failed axes → failed
        {
            "exit_code": 1,
            "status": "failed",
            "report": str(tmp_path / "gone.md"),
            "transcript": str(_tiny_transcript(tmp_path)),
            "execution_state": "failed",
            "proof_state": "undeclared",
            "delivery_state": "unverified",
            "expected_bucket": "failed",
        },
        # partial axes → needs-attention
        {
            "exit_code": 0,
            "status": "completed",
            "execution_state": "exited",
            "proof_state": "passed",
            "delivery_state": "unverified",
            "expected_bucket": "needs-attention",
        },
    ]
    for case in cases:
        expected = case.pop("expected_bucket")
        meta = write_meta(tmp_path, **case)
        runner = Runner()
        triage_finished_run(meta, live_env(tmp_path), runner)
        assert runner.bucket_flag() == expected, case
        # And the flag is present on the argv, not merely in the receipt.
        transfer = runner.transfer_calls[0]
        assert "--bucket" in transfer
        assert transfer[transfer.index("--bucket") + 1] == expected
        # Reset meta file for next case (write_meta overwrites).
        meta.unlink(missing_ok=True)


def test_plan_argv_includes_bucket_for_failed_verdict(tmp_path: Path) -> None:
    """Direct plan.argv contract: failed is only reachable via explicit flag."""
    meta_payload = {
        "run_id": "run-fail",
        "exit_code": 1,
        "status": "failed",
        "report": str(tmp_path / "gone.md"),
        "transcript": str(_tiny_transcript(tmp_path)),
        "execution_state": "failed",
        "proof_state": "undeclared",
        "delivery_state": "unverified",
    }
    plan = plan_triage(meta_payload, make_env())
    assert plan.verdict == VERDICT_FAILED
    argv = plan.argv("/usr/bin/vc-frame", with_bucket=True)
    assert "--bucket" in argv
    assert argv[argv.index("--bucket") + 1] == "failed"
