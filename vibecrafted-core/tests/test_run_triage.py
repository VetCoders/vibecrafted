"""Tests for the runtime caller of ``vc-frame triage-run``.

The transfer primitive itself lives in vc-frame and is tested there. What is at
stake here is the caller's judgement: which runs may be transferred at all, where
each exit code lands, and — above all — that nothing in this path can damage a run
that has already finished.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pytest

from vibecrafted_core.run_triage import (
    BUCKET_FINALIZED,
    BUCKET_NEEDS_ATTENTION,
    OUTCOME_FAILED,
    OUTCOME_FINALIZED,
    OUTCOME_NEEDS_ATTENTION,
    OUTCOME_SKIPPED,
    bucket_for_exit_code,
    plan_triage,
    triage_finished_run,
)


class FakeProc:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


class Runner:
    """Records invocations; answers the `--help` probe as a modern binary would."""

    def __init__(self, result: Any = None, supports: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.result = result if result is not None else FakeProc(0)
        self.supports = supports

    def __call__(self, argv: Sequence[str]) -> Any:
        argv = list(argv)
        self.calls.append(argv)
        if argv[1:] == ["triage-run", "--help"]:
            return FakeProc(0 if self.supports else 2)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    @property
    def transfer_calls(self) -> list[list[str]]:
        return [c for c in self.calls if c[1:2] == ["triage-run"] and "--help" not in c]


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


def write_meta(tmp_path: Path, **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "status": "completed",
        "run_id": "run-0007",
        "exit_code": 0,
        "root": "/repo",
        "launcher": "/tmp/launch-run-0007.sh",
        "liveness": "terminal",
    }
    payload.update(overrides)
    meta = tmp_path / "agent.meta.json"
    meta.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return meta


# --------------------------------------------------------------------------
# Exit code → bucket. One place, and it must hold for the whole integer range.
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

    assert outcome.outcome == OUTCOME_FAILED
    assert "bucket session vanished" in outcome.reason


def test_exploding_runner_is_contained(tmp_path: Path) -> None:
    """Even an OSError from the subprocess layer must not escape."""
    meta = write_meta(tmp_path)
    runner = Runner(result=OSError("no fork for you"))

    outcome = triage_finished_run(meta, live_env(tmp_path), runner)

    assert outcome.outcome == OUTCOME_FAILED
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


def test_failed_run_receipt_says_needs_attention(tmp_path: Path) -> None:
    meta = write_meta(tmp_path, exit_code=137, status="failed")

    outcome = triage_finished_run(meta, live_env(tmp_path), Runner())

    assert outcome.outcome == OUTCOME_NEEDS_ATTENTION
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["triage_bucket"] == BUCKET_NEEDS_ATTENTION


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
