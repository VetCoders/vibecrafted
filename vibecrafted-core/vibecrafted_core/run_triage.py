"""Runtime caller for ``vc-frame triage-run``.

When a supervised run reaches a terminal state, the tab it lived in stops being
work-in-progress and starts being evidence. vc-frame owns the transfer primitive
(``vc-frame triage-run``, vc-frame ``71146085``); this module owns *calling* it —
the seam vc-frame deliberately left to the runtime, because vc-frame owns the
terminal and the runtime owns the run.

Two properties drive every decision here:

**Fail-open.** Triage is a convenience on top of a finished run. The report, the
meta, and the origin tab all already exist and are already correct by the time we
are called. So no failure in this module may propagate: a missing binary, a dead
session, a non-zero ``triage-run`` — each degrades to a recorded receipt, never an
exception and never a lost tab. vc-frame's engine guarantees no-close-before-confirm
on its side; this is the mirror of that caution on the caller side.

**Only ever our own tab.** The transfer closes the origin tab. That is safe only
when the tab belongs to this run alone. The runtime spawns run tabs named by run
id (``lib/vc_frame.sh``), but marbles runs share one tab across siblings — closing
that would take the siblings with it. :func:`plan_triage` refuses that case rather
than trusting the caller to know the difference.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

__all__ = [
    "BUCKET_FINALIZED",
    "BUCKET_NEEDS_ATTENTION",
    "TriagePlan",
    "TriageOutcome",
    "bucket_for_exit_code",
    "outcome_for_exit_code",
    "plan_triage",
    "triage_finished_run",
    "main",
]

# Bucket names are vc-frame's wire contract (BucketKind::session_name), not ours.
# They are mirrored here only so the receipt can name the destination without a
# round-trip; vc-frame remains the owner of the rail UI and these strings.
BUCKET_FINALIZED = "Finalized runs"
BUCKET_NEEDS_ATTENTION = "Needs attention"

# Receipt values written to meta.json under "triage".
OUTCOME_FINALIZED = "finalized"
OUTCOME_NEEDS_ATTENTION = "needs_attention"
OUTCOME_SKIPPED = "skipped"
OUTCOME_FAILED = "failed"

_TRUTHY_OFF = {"0", "false", "no", "off"}


def bucket_for_exit_code(exit_code: Any) -> str:
    """Map a run's exit code to its vc-frame bucket. The single source of truth.

    Mirrors vc-frame's ``BucketKind::for_exit_code``: exit 0 is the only success.
    Timeouts and kills arrive as their signal-derived codes (137, 143, ...) and
    are non-zero, so they land in "Needs attention" without a special case.

    An unparseable or missing exit code is treated as failure — a run whose
    outcome we cannot read is precisely a run that needs attention.
    """
    try:
        code = int(exit_code)
    except (TypeError, ValueError):
        return BUCKET_NEEDS_ATTENTION
    return BUCKET_FINALIZED if code == 0 else BUCKET_NEEDS_ATTENTION


def outcome_for_exit_code(exit_code: Any) -> str:
    """Receipt outcome corresponding to :func:`bucket_for_exit_code`."""
    return (
        OUTCOME_FINALIZED
        if bucket_for_exit_code(exit_code) == BUCKET_FINALIZED
        else OUTCOME_NEEDS_ATTENTION
    )


@dataclass(frozen=True)
class TriagePlan:
    """The decision, taken without side effects so it can be tested directly."""

    should_run: bool
    skip_reason: str = ""
    run_id: str = ""
    exit_code: int = 0
    bucket: str = ""
    origin_session: str = ""
    origin_tab: str = ""
    pane_id: str = ""
    cwd: str = ""
    command: tuple[str, ...] = ()

    def argv(self, binary: str) -> list[str]:
        """Render the ``vc-frame triage-run`` invocation for this plan."""
        argv = [
            binary,
            "triage-run",
            "--run",
            self.run_id,
            "--exit-code",
            str(self.exit_code),
        ]
        if self.origin_session:
            argv += ["--origin-session", self.origin_session]
        if self.origin_tab:
            argv += ["--origin-tab", self.origin_tab]
        if self.pane_id:
            argv += ["--pane-id", self.pane_id]
        if self.cwd:
            argv += ["--cwd", self.cwd]
        if self.command:
            # `command` is clap `last(true)`: everything after `--` is the
            # original command line, preserved for the rerun pane.
            argv += ["--", *self.command]
        return argv


@dataclass
class TriageOutcome:
    """What actually happened, as written into the run's receipt."""

    outcome: str
    reason: str = ""
    bucket: str = ""
    #: True only for the intent written before the transfer is attempted. A
    #: receipt left pending means the process did not survive its own transfer.
    pending: bool = False

    def receipt(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "triage": self.outcome,
            "triage_pending": self.pending,
        }
        # Always written, so a confirming receipt clears a stale intent.
        payload["triage_reason"] = self.reason
        payload["triage_bucket"] = self.bucket
        return payload


def plan_triage(
    meta: Mapping[str, Any],
    env: Mapping[str, str] | None = None,
) -> TriagePlan:
    """Decide whether this finished run may be transferred, and with what arguments.

    Pure: reads the meta payload and the environment, touches nothing.
    """
    env = os.environ if env is None else env

    def _env(*names: str) -> str:
        for name in names:
            value = str(env.get(name, "") or "").strip()
            if value:
                return value
        return ""

    if str(env.get("VIBECRAFTED_TRIAGE_RUN", "") or "").strip().lower() in _TRUTHY_OFF:
        return TriagePlan(should_run=False, skip_reason="disabled")

    run_id = str(meta.get("run_id", "") or "").strip() or _env(
        "SPAWN_RUN_ID", "VIBECRAFTED_RUN_ID"
    )
    if not run_id:
        return TriagePlan(should_run=False, skip_reason="no_run_id")

    # Headless / CI / detached (setsid) runs have no pane env at all. Not an
    # error — there is simply no terminal to triage.
    in_frame = bool(
        _env("VC_FRAME_PANE_ID", "ZELLIJ_PANE_ID")
        or "VC_FRAME" in env
        or "ZELLIJ" in env
    )
    origin_session = _env("VC_FRAME_SESSION_NAME", "ZELLIJ_SESSION_NAME")
    if not in_frame or not origin_session:
        return TriagePlan(should_run=False, skip_reason="no_session")

    # The run tab is named by run id (lib/vc_frame.sh). A marbles run instead
    # shares one tab with its siblings, so closing it would destroy their
    # scrollback along with ours. Refuse rather than guess.
    marbles_tab = _env("VIBECRAFTED_MARBLES_TAB_NAME")
    tab_name = _env("VC_FRAME_TAB_NAME") or run_id
    if marbles_tab and tab_name == marbles_tab and marbles_tab != run_id:
        return TriagePlan(should_run=False, skip_reason="shared_tab")

    exit_code_raw = meta.get("exit_code")
    try:
        exit_code = int(exit_code_raw)
    except (TypeError, ValueError):
        exit_code = 1

    # What the bucket tab's suspended pane will hold, one keypress from rerun.
    # meta.json has no "command" field today, but it has "launcher" — and the
    # generated launcher *is* the reproducible run, env and all. Re-running it is
    # a truer rerun than any reconstructed command line would be.
    command_raw = meta.get("command") or meta.get("launcher")
    if isinstance(command_raw, str):
        command: tuple[str, ...] = (command_raw,) if command_raw.strip() else ()
    elif isinstance(command_raw, Sequence):
        command = tuple(str(part) for part in command_raw if str(part).strip())
    else:
        command = ()

    return TriagePlan(
        should_run=True,
        run_id=run_id,
        exit_code=exit_code,
        bucket=bucket_for_exit_code(exit_code),
        origin_session=origin_session,
        origin_tab=tab_name,
        pane_id=_env("VC_FRAME_PANE_ID", "ZELLIJ_PANE_ID"),
        cwd=str(meta.get("root", "") or "") or _env("SPAWN_ROOT"),
        command=command,
    )


def _resolve_binary(env: Mapping[str, str]) -> str:
    from shutil import which

    explicit = str(env.get("VIBECRAFTED_VC_FRAME_BIN", "") or "").strip()
    if explicit:
        return explicit if Path(explicit).exists() else ""
    return which("vc-frame", path=env.get("PATH")) or ""


def _supports_triage_run(binary: str, runner: Callable[..., Any]) -> bool:
    """Probe for the subcommand.

    The installed binary may predate vc-frame ``71146085``; an older build parses
    ``triage-run`` as a stray argument and exits non-zero. Probing keeps a stale
    install a recorded skip rather than a spurious failure.
    """
    try:
        proc = runner([binary, "triage-run", "--help"])
    except Exception:
        return False
    return getattr(proc, "returncode", 1) == 0


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argv is built, never shell-interpolated.
        list(argv),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def triage_finished_run(
    meta_path: str | os.PathLike[str],
    env: Mapping[str, str] | None = None,
    runner: Callable[..., Any] | None = None,
) -> TriageOutcome:
    """Transfer a finished run's tab into its bucket, and record what happened.

    Never raises. Every failure path returns a :class:`TriageOutcome` and leaves
    the origin tab exactly where it was.
    """
    env = os.environ if env is None else env
    runner = _default_runner if runner is None else runner

    meta = Path(meta_path)
    try:
        payload = json.loads(meta.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("meta.json is not an object")
    except Exception as exc:
        # No meta means no receipt to write to either; report and stop.
        return TriageOutcome(OUTCOME_SKIPPED, reason=f"no_meta: {exc}")

    plan = plan_triage(payload, env)
    if not plan.should_run:
        outcome = TriageOutcome(OUTCOME_SKIPPED, reason=plan.skip_reason)
        _record_receipt(meta, payload, outcome)
        return outcome

    # A successful transfer closes the origin tab — the tab this process is
    # running in. Our own success is therefore likely to kill us before we can
    # write the receipt. So record the intent first, marked pending, and correct
    # it only if we live long enough to learn better. A run that vanishes mid-
    # transfer then still says where it was headed instead of saying nothing.
    intent = TriageOutcome(
        outcome_for_exit_code(plan.exit_code),
        bucket=plan.bucket,
        pending=True,
    )
    _record_receipt(meta, payload, intent)

    outcome = _run_triage(plan, env, runner)
    _record_receipt(meta, payload, outcome)
    return outcome


def _run_triage(
    plan: TriagePlan,
    env: Mapping[str, str],
    runner: Callable[..., Any],
) -> TriageOutcome:
    binary = _resolve_binary(env)
    if not binary:
        return TriageOutcome(OUTCOME_SKIPPED, reason="no_binary")
    if not _supports_triage_run(binary, runner):
        return TriageOutcome(OUTCOME_SKIPPED, reason="unsupported_binary")

    try:
        proc = runner(plan.argv(binary))
    except Exception as exc:
        return TriageOutcome(
            OUTCOME_FAILED,
            reason=f"invoke_error: {type(exc).__name__}: {exc}",
            bucket=plan.bucket,
        )

    returncode = getattr(proc, "returncode", 1)
    if returncode != 0:
        stderr = str(getattr(proc, "stderr", "") or "").strip()
        return TriageOutcome(
            OUTCOME_FAILED,
            reason=f"exit {returncode}: {stderr[:500]}"
            if stderr
            else f"exit {returncode}",
            bucket=plan.bucket,
        )

    return TriageOutcome(outcome_for_exit_code(plan.exit_code), bucket=plan.bucket)


def _record_receipt(
    meta: Path,
    payload: dict[str, Any],
    outcome: TriageOutcome,
) -> None:
    """Append the triage receipt to meta.json.

    Re-read first: this runs after the terminal write, and the control-plane sync
    or a concurrent writer may have touched the file since. Losing the receipt is
    acceptable; clobbering a run's terminal state to save it is not.
    """
    try:
        current = json.loads(meta.read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            current = payload
    except Exception:
        current = payload

    current.update(outcome.receipt())
    try:
        meta.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vibecrafted_core.run_triage",
        description="Transfer a finished run's tab into its vc-frame status bucket.",
    )
    parser.add_argument("meta", help="Path to the run's launcher meta.json")
    args = parser.parse_args(argv)

    outcome = triage_finished_run(args.meta)
    line = f"triage: {outcome.outcome}"
    if outcome.bucket and outcome.outcome in {
        OUTCOME_FINALIZED,
        OUTCOME_NEEDS_ATTENTION,
    }:
        line += f" → {outcome.bucket}"
    if outcome.reason:
        line += f" ({outcome.reason})"
    print(line)
    # Always 0: triage never fails a run.
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    raise SystemExit(main())
