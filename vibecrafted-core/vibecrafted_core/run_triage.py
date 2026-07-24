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

**Single signals lie.** The drawer a run lands in is decided by
:func:`classify_run`. When a delivery-kernel receipt is present, the three
orthogonal axes (``execution_state`` / ``proof_state`` / ``delivery_state``)
own the verdict; otherwise a conjunction over exit code, run state, report
delivery and transcript volume decides — never the exit code alone. The AICX
record from 2026-05-14 holds runs reporting top-level ``completed``/exit 0
whose own reports said ``failed``, and ``timed_out``/``report_missing`` states
sitting next to complete artifacts. Every such contradiction is routed to
human review rather than to a confident drawer, and so is every signal the
classifier cannot read.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "BUCKET_FAILED",
    "BUCKET_FINALIZED",
    "BUCKET_NEEDS_ATTENTION",
    "MINIMAL_REPORT_BYTES",
    "MINIMAL_TRANSCRIPT_BYTES",
    "VERDICT_FAILED",
    "VERDICT_FINALIZED",
    "VERDICT_NEEDS_ATTENTION",
    "KernelAxes",
    "RunClassification",
    "RunSignals",
    "TriageOutcome",
    "TriagePlan",
    "bucket_for_exit_code",
    "classify_run",
    "main",
    "outcome_for_exit_code",
    "plan_triage",
    "read_kernel_axes",
    "read_run_signals",
    "triage_finished_run",
]

# Bucket names are vc-frame's wire contract (BucketKind::session_name), not ours.
# They are mirrored here only so the receipt can name the destination without a
# round-trip; vc-frame remains the owner of the rail UI and these strings.
BUCKET_FINALIZED = "Finalized runs"
BUCKET_FAILED = "Failed runs"
BUCKET_NEEDS_ATTENTION = "Needs attention"

# The three verdicts. Also the receipt values written to meta.json under
# "triage" — the headline of a receipt is where the run went.
VERDICT_FINALIZED = "finalized"
VERDICT_FAILED = "failed"
VERDICT_NEEDS_ATTENTION = "needs_attention"

OUTCOME_FINALIZED = VERDICT_FINALIZED
OUTCOME_FAILED = VERDICT_FAILED
OUTCOME_NEEDS_ATTENTION = VERDICT_NEEDS_ATTENTION
#: No transfer was attempted — nothing to triage, or nothing able to triage it.
OUTCOME_SKIPPED = "skipped"
#: The transfer itself broke. A different axis from the verdict: it says nothing
#: about the run, only about our call into vc-frame.
OUTCOME_ERROR = "error"

_TRUTHY_OFF = {"0", "false", "no", "off"}

# --------------------------------------------------------------------------
# Signal thresholds. Measured, not guessed (sample: every run transcript under
# ~/.vibecrafted/artifacts newer than 2026-06-15, read through their compat
# symlinks, on 2026-07-21).
# --------------------------------------------------------------------------

#: A transcript below this carries only the launcher's frontmatter banner
#: (~380 B) — no tool call, no output, no work. The smallest transcript in the
#: sample that came from a run which actually produced a report was 885 B, so
#: 512 sits in the empty gap between "died at startup" and "did something".
MINIMAL_TRANSCRIPT_BYTES = 512

#: A report file that exists but holds nothing is what control_plane calls
#: `report_invalid` — a contradiction, never a delivery.
MINIMAL_REPORT_BYTES = 1

# Run states, in control_plane's vocabulary (`FINAL_STATES`). Split by what each
# one *asserts*, because the verdict is a conjunction: a state that disagrees
# with the exit code is itself the contradiction.

#: States asserting the artifact contract held.
_STATES_DELIVERED = frozenset({"report_validated", "completed", "closed", "converged"})
#: States asserting the run stopped without delivering. Consistent with a death.
_STATES_DIED = frozenset({"failed", "stopped", "report_missing"})
#: States that *are* the contradiction, or that name human review outright.
#: These never reach a confident drawer regardless of the other signals.
_STATES_CONTRADICTORY = frozenset(
    {
        "report_invalid",
        "contract_failed",
        "recovery_required",
        "blocked",
        "stalled",
        "timed_out",
        "ghost",
        "gc",
    }
)

_BUCKET_FOR_VERDICT = {
    VERDICT_FINALIZED: BUCKET_FINALIZED,
    VERDICT_FAILED: BUCKET_FAILED,
    VERDICT_NEEDS_ATTENTION: BUCKET_NEEDS_ATTENTION,
}
# vc-frame's `triage-run --bucket` takes the kebab spelling (W2-B-4a).
_BUCKET_FLAG_FOR_VERDICT = {
    VERDICT_FINALIZED: "finalized",
    VERDICT_FAILED: "failed",
    VERDICT_NEEDS_ATTENTION: "needs-attention",
}


@dataclass(frozen=True)
class RunClassification:
    """Where a finished run belongs, and the evidence that put it there."""

    verdict: str
    reason: str

    @property
    def bucket(self) -> str:
        """The vc-frame session name for this verdict."""
        return _BUCKET_FOR_VERDICT[self.verdict]

    @property
    def bucket_flag(self) -> str:
        """The value for ``triage-run --bucket``."""
        return _BUCKET_FLAG_FOR_VERDICT[self.verdict]


def _attention(reason: str) -> RunClassification:
    return RunClassification(VERDICT_NEEDS_ATTENTION, reason)


# Axis field names written by lifecycle/ship receipts and nested under
# ``delivery_axes``. Presence of any of these (or a nested receipt body) is
# the switch that hands the drawer to the kernel path.
_KERNEL_AXIS_KEYS = ("execution_state", "proof_state", "delivery_state")


@dataclass(frozen=True)
class KernelAxes:
    """Delivery-kernel axes when a kernel receipt is present for the run.

    Constructed only when a receipt exists. Individual fields may be ``None``
    (unreadable). ``corrupt=True`` means the receipt body itself could not be
    parsed — that is not the same as "no receipt", and fails closed.
    """

    execution_state: str | None = None
    proof_state: str | None = None
    delivery_state: str | None = None
    corrupt: bool = False


def _normalize_axis_value(raw: Any) -> str | None:
    """Coerce one axis field. ``None`` / blank → unreadable (fail closed)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip().lower()
        return text or None
    # Enums and other value-bearing objects: take their value/str form.
    enum_value = getattr(raw, "value", None)
    if isinstance(enum_value, str):
        text = enum_value.strip().lower()
        return text or None
    text = str(raw).strip().lower()
    return text or None


def _kernel_axes_from_mapping(source: Mapping[str, Any]) -> KernelAxes:
    execution = _normalize_axis_value(source.get("execution_state"))
    if (
        execution in ("launched", "running")
        and str(source.get("status") or "") == "failed"
    ):
        execution = "failed"
    return KernelAxes(
        execution_state=execution,
        proof_state=_normalize_axis_value(source.get("proof_state")),
        delivery_state=_normalize_axis_value(source.get("delivery_state")),
        corrupt=False,
    )


def _load_axes_blob(raw: Any) -> KernelAxes | None:
    """Parse a nested ``delivery_axes`` value into axes or a corrupt marker.

    Returns ``None`` only when ``raw`` is a missing/empty marker (caller should
    fall through to top-level keys). A present-but-broken body is corrupt.
    """
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        return _kernel_axes_from_mapping(raw)
    if not isinstance(raw, str):
        return KernelAxes(corrupt=True)
    text = raw.strip()
    if not text:
        return None
    # Inline JSON object.
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return KernelAxes(corrupt=True)
        if not isinstance(payload, Mapping):
            return KernelAxes(corrupt=True)
        return _kernel_axes_from_mapping(payload)
    # Path to a receipt file on disk.
    path = Path(text)
    try:
        if not path.is_file():
            return KernelAxes(corrupt=True)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return KernelAxes(corrupt=True)
    if not isinstance(payload, Mapping):
        return KernelAxes(corrupt=True)
    return _kernel_axes_from_mapping(payload)


def read_kernel_axes(meta: Mapping[str, Any]) -> KernelAxes | None:
    """Extract kernel axes from a run receipt, or ``None`` if no receipt exists.

    Presence rules (any one is enough):

    * nested ``delivery_axes`` mapping / JSON / path
    * any of ``execution_state`` / ``proof_state`` / ``delivery_state`` on meta

    A present-but-unreadable body returns :class:`KernelAxes` with
    ``corrupt=True`` — never raises, never pretends the receipt was absent.
    """
    if "delivery_axes" in meta:
        loaded = _load_axes_blob(meta.get("delivery_axes"))
        if loaded is not None:
            return loaded
        # Explicit null/empty delivery_axes still counts as a receipt attempt
        # only when other axis keys are also absent; fall through.
    if any(key in meta for key in _KERNEL_AXIS_KEYS):
        return _kernel_axes_from_mapping(meta)
    return None


def _classify_from_kernel_axes(axes: KernelAxes) -> RunClassification:
    """Drawer from the three delivery-kernel axes. Fail closed on uncertainty.

    * ``delivery=sealed`` → finalized (seal is authority; legacy signals ignored)
    * ``execution=failed`` or ``proof∈{failed,invalid}`` → failed
    * every other combination, partial axes, or corrupt receipt → needs_attention
    """
    if axes.corrupt:
        return _attention("kernel_axes_unreadable")

    delivery = axes.delivery_state
    execution = axes.execution_state
    proof = axes.proof_state

    if delivery == "sealed":
        return RunClassification(VERDICT_FINALIZED, "delivery_sealed")

    if execution == "failed":
        return RunClassification(VERDICT_FAILED, "execution_failed")
    if proof == "failed":
        return RunClassification(VERDICT_FAILED, "proof_failed")
    if proof == "invalid":
        return RunClassification(VERDICT_FAILED, "proof_invalid")

    # Partial, in-progress, or honest-but-unsealed terminals.
    parts = [
        f"e={execution or 'none'}",
        f"p={proof or 'none'}",
        f"d={delivery or 'none'}",
    ]
    return _attention("axes_" + "_".join(parts))


def classify_run(
    exit_code: Any,
    run_state: Any,
    report_exists: bool | None,
    report_bytes: int | None,
    transcript_bytes: int | None,
    *,
    kernel_axes: KernelAxes | None = None,
    report_claim_status: str = "",
    report_frontmatter_ok: bool | None = None,
) -> RunClassification:
    """Decide a finished run's drawer from its signals.

    Pure. Three outcomes, and only two of them are confident.

    When ``kernel_axes`` is provided (a delivery-kernel receipt was present),
    the three orthogonal axes decide:

    * **finalized** — ``delivery_state=sealed``
    * **failed** — ``execution_state=failed`` or ``proof_state∈{failed,invalid}``
    * **needs_attention** — every other axis combination, and any unreadable
      receipt body

    When no kernel receipt is present (``kernel_axes is None``), the legacy
    five-signal conjunction applies:

    * **finalized** — exit 0, a state asserting delivery, a non-empty report
      with valid frontmatter claim, and claim not contradicting death. Agent
      claim alone never finalizes.
    * **failed** — exit non-zero, a state asserting death, no report, and a
      transcript too small to contain work. A run that died before doing any.
    * **needs_attention** — everything else. Every contradiction between signals
      (exit 0 with no report, non-zero exit *with* a report, a state that
      disagrees with the exit code, ``report_invalid``/``contract_failed``/
      ``ghost``/``timed_out``), missing/invalid report frontmatter, claim
      vs evidence conflicts, and every signal we could not read.

    The last clause is the point: an unreadable signal fails closed, to a human,
    never to a confident drawer. ``report_exists=None`` and
    ``transcript_bytes=None`` mean "could not stat", not "absent".
    """
    if kernel_axes is not None:
        return _classify_from_kernel_axes(kernel_axes)

    state = str(run_state or "").strip().lower()
    if not state:
        return _attention("state_unreadable")
    if state in _STATES_CONTRADICTORY:
        return _attention(f"state_{state}")
    if state not in _STATES_DELIVERED and state not in _STATES_DIED:
        return _attention(f"state_unrecognized:{state}")

    try:
        code = int(exit_code)
    except (TypeError, ValueError):
        return _attention("exit_code_unreadable")

    if report_exists is None:
        return _attention("report_unreadable")

    delivered = bool(report_exists)
    if delivered:
        if report_bytes is None:
            return _attention("report_size_unreadable")
        if report_bytes < MINIMAL_REPORT_BYTES:
            return _attention("report_empty")
        # Mandatory frontmatter when checked (False). None = not evaluated (unit tests).
        if report_frontmatter_ok is False:
            return _attention("report_frontmatter_invalid")

    claim = str(report_claim_status or "").strip().lower()
    from .report_contract import (
        CLAIM_BLOCKED,
        CLAIM_COMPLETED,
        CLAIM_FAILED,
        CLAIM_PARTIAL,
    )

    if code == 0:
        if not delivered:
            # The 2026-05-14 specimen: top-level success, nothing delivered.
            return _attention("exit_0_without_report")
        if state not in _STATES_DELIVERED:
            return _attention(f"exit_0_but_state_{state}")
        if claim in CLAIM_FAILED:
            return _attention("exit_0_but_claim_failed")
        if claim in CLAIM_BLOCKED or claim in CLAIM_PARTIAL:
            return _attention(f"exit_0_claim_{claim or 'partial'}")
        # claim completed / empty: empty allowed only if frontmatter_ok is True
        # (required keys present including status). Missing claim after ok FM
        # should not happen; treat unrecognized as attention.
        if claim and claim not in CLAIM_COMPLETED:
            return _attention(f"exit_0_claim_unrecognized:{claim}")
        return RunClassification(VERDICT_FINALIZED, "exit_0_report_delivered")

    # Non-zero exit from here down.
    if delivered:
        # Claim can admit failure while still leaving a report for the board.
        if claim in CLAIM_FAILED:
            return RunClassification(
                VERDICT_FAILED, f"exit_{code}_claim_failed_with_report"
            )
        # The mirror specimen: the run says it died, the artifacts say otherwise.
        return _attention(f"exit_{code}_with_report")
    if state not in _STATES_DIED:
        return _attention(f"exit_{code}_but_state_{state}")
    if transcript_bytes is None:
        return _attention("transcript_unreadable")
    if transcript_bytes >= MINIMAL_TRANSCRIPT_BYTES:
        # It died, but not before working. Whatever it managed is worth a look.
        return _attention(f"exit_{code}_no_report_after_{transcript_bytes}b")
    return RunClassification(
        VERDICT_FAILED,
        f"exit_{code}_no_report_transcript_{transcript_bytes}b",
    )


@dataclass(frozen=True)
class RunSignals:
    """The classifier's inputs, read off a run's meta payload and its artifacts.

    ``None`` always means "could not read", never "absent" — the distinction the
    classifier needs to fail closed. ``kernel_axes`` is ``None`` when no delivery
    kernel receipt is present (legacy path); a :class:`KernelAxes` instance when
    one is, including the corrupt case.
    """

    exit_code: Any
    run_state: str
    report_exists: bool | None
    report_bytes: int | None
    transcript_bytes: int | None
    kernel_axes: KernelAxes | None = None
    # Agent claim from report frontmatter (claim_status/status). Empty = absent.
    report_claim_status: str = ""
    report_frontmatter_ok: bool | None = None

    def classify(self) -> RunClassification:
        return classify_run(
            self.exit_code,
            self.run_state,
            self.report_exists,
            self.report_bytes,
            self.transcript_bytes,
            kernel_axes=self.kernel_axes,
            report_claim_status=self.report_claim_status,
            report_frontmatter_ok=self.report_frontmatter_ok,
        )


def _stat_artifact(raw: Any) -> tuple[bool | None, int | None]:
    """``(exists, bytes)`` for an artifact path.

    Three distinguishable answers, because the classifier needs them apart:
    an undeclared path is unknown (``None`` bytes — we do not know where to
    look), a declared path that is not there is a known zero, and an ``OSError``
    is unreadable in both fields.
    """
    path = str(raw or "").strip()
    if not path:
        return False, None
    try:
        target = Path(path)
        if not target.exists():
            return False, 0
        return True, target.stat().st_size
    except OSError:
        return None, None


def read_run_signals(meta: Mapping[str, Any]) -> RunSignals:
    """Gather the classifier's inputs from a run's meta payload.

    The only impure step in the chain — it stats the report and the transcript.
    ``Path.stat`` follows symlinks, which matters: ``spawn.finalize_artifacts``
    leaves a compat symlink at the announced path, so the announced transcript is
    routinely a link to the real one.
    """
    report_exists, report_bytes = _stat_artifact(meta.get("report"))
    _, transcript_bytes = _stat_artifact(meta.get("transcript"))
    # `state` is the control-plane spelling, `status` the launcher meta's. Either
    # is the run's own account of how it ended.
    run_state = str(meta.get("state") or meta.get("status") or "").strip()

    claim_status = str(meta.get("report_claim_status") or "").strip()
    frontmatter_ok: bool | None = None
    report_path = str(meta.get("report") or "").strip()
    if report_exists and report_path:
        from .report_contract import validate_report_file

        fm = validate_report_file(report_path, require_frontmatter=True)
        frontmatter_ok = fm.ok
        if not claim_status:
            claim_status = fm.claim_status
    elif report_exists is False:
        frontmatter_ok = None

    return RunSignals(
        exit_code=meta.get("exit_code"),
        run_state=run_state,
        report_exists=report_exists,
        report_bytes=report_bytes,
        transcript_bytes=transcript_bytes,
        kernel_axes=read_kernel_axes(meta),
        report_claim_status=claim_status,
        report_frontmatter_ok=frontmatter_ok,
    )


def bucket_for_exit_code(exit_code: Any) -> str:
    """Map a run's exit code to its vc-frame bucket — the degraded path only.

    :func:`classify_run` is the verdict. This survives for one case: a vc-frame
    predating ``triage-run --bucket``, which buckets by exit code on its own. We
    mirror its arithmetic so the receipt can name the destination it will pick.

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
    verdict: str = ""
    verdict_reason: str = ""
    origin_session: str = ""
    origin_tab: str = ""
    pane_id: str = ""
    cwd: str = ""
    command: tuple[str, ...] = ()

    def argv(self, binary: str, with_bucket: bool = True) -> list[str]:
        """Render the ``vc-frame triage-run`` invocation for this plan.

        ``with_bucket=False`` omits ``--bucket`` for a binary predating W2-B-4a,
        leaving vc-frame to bucket by exit code on its own — the degraded path.
        """
        argv = [
            binary,
            "triage-run",
            "--run",
            self.run_id,
            "--exit-code",
            str(self.exit_code),
        ]
        if with_bucket and self.verdict:
            argv += ["--bucket", _BUCKET_FLAG_FOR_VERDICT[self.verdict]]
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
    #: The classifier's verdict and its evidence, preserved independently of the
    #: outcome so the operator can audit *why* a run went where — including when
    #: the transfer later broke, or when the destination was degraded.
    verdict: str = ""
    verdict_reason: str = ""
    #: Non-empty when the destination was not the classifier's to choose:
    #: ``exit_code_only`` for a vc-frame predating ``--bucket``.
    verdict_degraded: str = ""

    def receipt(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "triage": self.outcome,
            "triage_pending": self.pending,
        }
        # Always written, so a confirming receipt clears a stale intent.
        payload["triage_reason"] = self.reason
        payload["triage_bucket"] = self.bucket
        payload["triage_verdict"] = self.verdict
        payload["triage_verdict_reason"] = self.verdict_reason
        payload["triage_verdict_degraded"] = self.verdict_degraded
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

    def _meta_str(*names: str) -> str:
        for name in names:
            value = str(meta.get(name, "") or "").strip()
            if value:
                return value
        return ""

    # Origin identity: prefer durable meta fields (dispatcher path stamps them
    # at finish; shell launchers may already have them). Fall back to live pane
    # env for the classic in-tab finish path.
    origin_session = _meta_str(
        "origin_session",
        "vc_frame_session",
        "operator_session",
        "worker_session",
    ) or _env(
        "VIBECRAFTED_WORKER_SESSION",
        "VIBECRAFTED_OPERATOR_SESSION",
        "VC_FRAME_SESSION_NAME",
        "ZELLIJ_SESSION_NAME",
    )
    tab_name = (
        _meta_str("origin_tab", "vc_frame_tab", "tab_name")
        or _env("VC_FRAME_TAB_NAME")
        or run_id
    )
    pane_id = _meta_str("origin_pane_id", "vc_frame_pane_id", "pane_id") or _env(
        "VC_FRAME_PANE_ID", "ZELLIJ_PANE_ID"
    )

    # Headless / CI / detached (setsid) runs have no pane env and no stamped
    # host session. Not an error — there is simply no terminal to triage.
    # Meta-stamped origin_session is enough for the Python dispatcher path:
    # triage-run targets that session by name without needing ambient pane env.
    in_frame = bool(
        pane_id
        or origin_session
        or _env("VC_FRAME_PANE_ID", "ZELLIJ_PANE_ID")
        or "VC_FRAME" in env
        or "ZELLIJ" in env
    )
    if not in_frame or not origin_session:
        return TriagePlan(should_run=False, skip_reason="no_session")

    # The run tab is named by run id (lib/vc_frame.sh). A marbles run instead
    # shares one tab with its siblings, so closing it would destroy their
    # scrollback along with ours. Refuse rather than guess.
    marbles_tab = _meta_str("marbles_tab_name") or _env("VIBECRAFTED_MARBLES_TAB_NAME")
    if marbles_tab and tab_name == marbles_tab and marbles_tab != run_id:
        return TriagePlan(should_run=False, skip_reason="shared_tab")

    exit_code_raw: Any = meta.get("exit_code")
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

    classification = read_run_signals(meta).classify()

    return TriagePlan(
        should_run=True,
        run_id=run_id,
        exit_code=exit_code,
        bucket=classification.bucket,
        verdict=classification.verdict,
        verdict_reason=classification.reason,
        origin_session=origin_session,
        origin_tab=tab_name,
        pane_id=pane_id,
        cwd=str(meta.get("root", "") or "") or _env("SPAWN_ROOT"),
        command=command,
    )


def _resolve_binary(env: Mapping[str, str]) -> str:
    from shutil import which

    explicit = str(env.get("VIBECRAFTED_VC_FRAME_BIN", "") or "").strip()
    if explicit:
        return explicit if Path(explicit).exists() else ""
    return which("vc-frame", path=env.get("PATH")) or ""


@dataclass(frozen=True)
class _Probe:
    """What the installed vc-frame can actually be asked to do."""

    supported: bool
    bucket: bool = False


def _probe_triage_run(binary: str, runner: Callable[..., Any]) -> _Probe:
    """Probe for the subcommand, and for ``--bucket`` within it.

    The installed binary may predate vc-frame ``71146085``; an older build parses
    ``triage-run`` as a stray argument and exits non-zero. Probing keeps a stale
    install a recorded skip rather than a spurious failure. A binary that has
    ``triage-run`` but predates W2-B-4a has no ``--bucket``, so its help text is
    read too: we degrade to exit-code bucketing rather than passing a flag that
    would make the whole call fail.
    """
    try:
        proc = runner([binary, "triage-run", "--help"])
    except Exception:  # noqa: BLE001
        return _Probe(supported=False)
    if getattr(proc, "returncode", 1) != 0:
        return _Probe(supported=False)
    help_text = (
        f"{getattr(proc, 'stdout', '') or ''}{getattr(proc, 'stderr', '') or ''}"
    )
    return _Probe(supported=True, bucket="--bucket" in help_text)


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
            raise TypeError("meta.json is not an object")
    except Exception as exc:  # noqa: BLE001
        # No meta means no receipt to write to either; report and stop.
        return TriageOutcome(OUTCOME_SKIPPED, reason=f"no_meta: {exc}")

    plan = plan_triage(payload, env)
    if not plan.should_run:
        outcome = TriageOutcome(OUTCOME_SKIPPED, reason=plan.skip_reason)
        _record_receipt(meta, payload, outcome)
        return outcome

    # Resolve the binary before writing anything: a stale or absent vc-frame
    # means no transfer will be attempted at all, and a pending intent for a
    # transfer that never starts would be a receipt describing fiction.
    binary = _resolve_binary(env)
    if not binary:
        outcome = TriageOutcome(OUTCOME_SKIPPED, reason="no_binary")
        _record_receipt(meta, payload, outcome)
        return outcome
    probe = _probe_triage_run(binary, runner)
    if not probe.supported:
        outcome = TriageOutcome(OUTCOME_SKIPPED, reason="unsupported_binary")
        _record_receipt(meta, payload, outcome)
        return outcome

    # Where the run will actually land. With `--bucket` that is the classifier's
    # verdict; without it vc-frame decides by exit code alone, so the receipt
    # must say the exit-code answer — and say that it was degraded to it.
    if probe.bucket:
        destination, bucket = plan.verdict, plan.bucket
        degraded = ""
    else:
        destination = outcome_for_exit_code(plan.exit_code)
        bucket = bucket_for_exit_code(plan.exit_code)
        degraded = "exit_code_only"

    # A successful transfer closes the origin tab — the tab this process is
    # running in. Our own success is therefore likely to kill us before we can
    # write the receipt. So record the intent first, marked pending, and correct
    # it only if we live long enough to learn better. A run that vanishes mid-
    # transfer then still says where it was headed instead of saying nothing.
    intent = TriageOutcome(
        destination,
        reason=plan.verdict_reason,
        bucket=bucket,
        pending=True,
        verdict=plan.verdict,
        verdict_reason=plan.verdict_reason,
        verdict_degraded=degraded,
    )
    _record_receipt(meta, payload, intent)

    outcome = _run_triage(plan, binary, probe, runner, destination, bucket, degraded)
    _record_receipt(meta, payload, outcome)
    return outcome


def _run_triage(
    plan: TriagePlan,
    binary: str,
    probe: _Probe,
    runner: Callable[..., Any],
    destination: str,
    bucket: str,
    degraded: str,
) -> TriageOutcome:
    def _error(reason: str) -> TriageOutcome:
        return TriageOutcome(
            OUTCOME_ERROR,
            reason=reason,
            bucket=bucket,
            verdict=plan.verdict,
            verdict_reason=plan.verdict_reason,
            verdict_degraded=degraded,
        )

    try:
        proc = runner(plan.argv(binary, with_bucket=probe.bucket))
    except Exception as exc:  # noqa: BLE001
        return _error(f"invoke_error: {type(exc).__name__}: {exc}")

    returncode = getattr(proc, "returncode", 1)
    if returncode != 0:
        stderr = str(getattr(proc, "stderr", "") or "").strip()
        return _error(
            f"exit {returncode}: {stderr[:500]}" if stderr else f"exit {returncode}"
        )

    return TriageOutcome(
        destination,
        reason=plan.verdict_reason,
        bucket=bucket,
        verdict=plan.verdict,
        verdict_reason=plan.verdict_reason,
        verdict_degraded=degraded,
    )


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
    except Exception:  # noqa: BLE001
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
    if outcome.bucket and outcome.outcome in _BUCKET_FOR_VERDICT:
        line += f" → {outcome.bucket}"
    if outcome.reason:
        line += f" ({outcome.reason})"
    if outcome.verdict_degraded:
        line += f" [degraded: {outcome.verdict_degraded}]"
    print(line)
    # Always 0: triage never fails a run.
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    raise SystemExit(main())
