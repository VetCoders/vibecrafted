from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vibecrafted_core.workflow import WorkflowLaunchSpec, launch_workflow

from .model import (
    STATE_FAILED,
    STATE_PENDING,
    STATE_UNKNOWN,
    STATE_VERIFIED,
    STATE_WORKER_DONE,
    Baton,
    Cut,
    Dispatch,
    Verdict,
)
from .schema import render_cell_prompt, render_cut_verifies
from .verify import run_verifies

DEFAULT_POLL_S = 90.0
DEFAULT_TIMEOUT_MIN = 90.0
SUBSTRATE_FAILURE_MARKER = "SUBSTRATE_FAILURE"
RESULT_SCHEMA = "vibecrafted.dispatch-result.v1"

# Recovery report search tolerates clock skew between the supervisor wall
# clock and the worker's filesystem writes.
_MTIME_TOLERANCE_S = 1.0


class CellContractError(RuntimeError):
    """The external runtime ended without a trustworthy delivery envelope."""


@dataclass
class CellRun:
    """Process handle for one launched work cell.

    `proc` is set by in-process launchers (tests, future embedded runners)
    and awaited via Popen.poll(); production `launch_workflow` cells only
    expose `pid`, awaited via waitpid/kill(0) probing.
    """

    cut_id: str
    kind: str
    accepted: bool
    run_id: str = ""
    pid: int | None = None
    report_path: str = ""
    meta_path: str = ""
    exit_code: int | None = None
    error: str = ""
    proc: subprocess.Popen[Any] | None = None


CellLauncher = Callable[[Cut, str, str], CellRun]


@dataclass(frozen=True)
class AwaitOutcome:
    finished: bool
    timed_out: bool
    elapsed_s: float
    report_path: str = ""
    report_text: str = ""
    recovered_by_mtime: bool = False


@dataclass(frozen=True)
class DispatchResult:
    line_broken: bool
    baton: Baton
    states: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    # Ordered per-cut entries (dispatch order, skipped cuts included) so
    # machine consumers can read result["cuts"][i]["state"] positionally.
    cuts: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESULT_SCHEMA,
            "line_broken": self.line_broken,
            "states": dict(self.states),
            "cuts": [dict(entry) for entry in self.cuts],
            "baton": self.baton.to_dict(),
            "artifacts": dict(self.artifacts),
        }


def workflow_cell_launcher(
    dispatch: Dispatch, *, source_dir: str | Path | None = None
) -> CellLauncher:
    """Production launcher: every cell goes through the existing
    `launch_workflow` runtime — the dispatch layer never spawns its own
    agent convention."""

    base_dir = Path(source_dir) if source_dir is not None else Path(dispatch.meta.repo)

    def launch(cut: Cut, prompt: str, kind: str) -> CellRun:
        spec = WorkflowLaunchSpec(
            agent=cut.agent,
            mode=cut.resolved_workflow,
            skill=cut.resolved_workflow,
            prompt=prompt,
            file="",
            runtime="headless",
            root=dispatch.meta.repo,
        )
        result = launch_workflow(spec, base_dir)
        return CellRun(
            cut_id=cut.id,
            kind=kind,
            accepted=bool(result.get("accepted")),
            run_id=str(result.get("run_id") or ""),
            pid=result.get("pid"),
            report_path=str(result.get("report") or ""),
            meta_path=str(result.get("meta") or ""),
            error=str(result.get("error") or result.get("message") or ""),
        )

    return launch


class DispatchSupervisor:
    """Deterministic control plane for one dispatch: render -> launch ->
    await -> substrate check -> verify -> repair -> state -> baton.

    The supervisor is the ONLY writer of tracker states. A cut flips from
    `[~]` to `[x]` exclusively after this class executed the declared
    verifiers and every matcher passed (measure-core invariant).
    """

    def __init__(
        self,
        dispatch: Dispatch,
        *,
        launcher: CellLauncher | None = None,
        artifacts_dir: str | Path | None = None,
        source_dir: str | Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.dispatch = dispatch
        self.policy = dispatch.policy
        self.repo = dispatch.meta.repo
        self.launcher = launcher or workflow_cell_launcher(
            dispatch, source_dir=source_dir
        )
        self._sleep = sleep

        base = artifacts_dir
        if base is None and dispatch.meta.tracker:
            base = Path(dispatch.meta.tracker).expanduser().parent
        if base is None and dispatch.meta.reports_dir:
            base = Path(dispatch.meta.reports_dir).expanduser()
        if base is None:
            base = Path.cwd()
        self.artifacts_dir = Path(base)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        tracker = dispatch.meta.tracker
        self.tracker_path = (
            Path(tracker).expanduser() if tracker else self.artifacts_dir / "tracker.md"
        )
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.artifacts_dir / "journal.md"
        self.handoff_path = self.artifacts_dir / "handoff.md"
        self.result_path = self.artifacts_dir / "dispatch-result.json"
        self.prompts_dir = self.artifacts_dir / "prompts"

        self._states: dict[str, tuple[str, str]] = {
            cut.id: (STATE_PENDING, "pending") for cut in dispatch.cuts
        }

    # ------------------------------------------------------------------ run

    def run(self) -> DispatchResult:
        baton = self.dispatch.empty_baton()
        line_broken = False
        active_cut: Cut | None = None
        result: DispatchResult | None = None
        poll_s, timeout_s = self._await_config()
        try:
            self._journal(
                f"dispatch start: {self.dispatch.meta.name!r} repo={self.repo}"
                f" cuts={len(self.dispatch.cuts)} repair_rounds={self.policy.repair_rounds}"
                f" on_critical_fail={self.policy.on_critical_fail}"
                f" on_timeout={self.policy.on_timeout}"
                f" await=poll {poll_s:g}s/timeout {timeout_s:g}s"
            )
            self._write_tracker()

            for cut in self.dispatch.cuts:
                active_cut = cut
                if line_broken:
                    self._set_state(
                        cut.id, STATE_PENDING, "skipped: line broken upstream"
                    )
                    continue
                verdict = self._run_cut(cut, baton)
                baton = baton.append(verdict)
                self._set_state(cut.id, verdict.state, self._verdict_note(verdict))
                if (
                    cut.critical
                    and not verdict.ok
                    and self.policy.on_critical_fail == "break"
                ):
                    line_broken = True
                    self._journal(
                        f"[{cut.id}] critical cut not verified ({verdict.state}):"
                        " breaking the dispatch line"
                    )

            result = self._build_result(baton, line_broken)
            return result
        except Exception as exc:
            label = (
                "dispatch substrate failure"
                if isinstance(exc, CellContractError)
                else "supervisor exception"
            )
            message = f"{label}: {type(exc).__name__}: {exc}"
            self._journal(message)
            if active_cut is not None:
                self._set_state(active_cut.id, STATE_FAILED, message)
                baton = baton.append(
                    Verdict(
                        cut_id=active_cut.id,
                        phase=active_cut.phase,
                        state=STATE_FAILED,
                        failures=(f"{active_cut.id}: {message}",),
                    )
                )
                line_broken = True
                self._mark_downstream_skipped(active_cut.id)
            result = self._build_result(baton, line_broken)
            return result
        finally:
            final_result = result or self._build_result(baton, line_broken)
            self._write_final_artifacts(final_result)

    # -------------------------------------------------------------- per cut

    def _run_cut(self, cut: Cut, baton: Baton) -> Verdict:
        prompt = render_cell_prompt(self.dispatch, cut, baton=baton)
        self._materialize_prompt(cut, "initial", prompt)
        git_before = self._git_state()
        if cut.mode != "read" and self.policy.require_commit and git_before[1]:
            raise CellContractError(
                f"[{cut.id}] WRITE cut started from a dirty worktree: {git_before[1]}"
            )
        repair_attempts = 0

        outcome, launch_failure = self._execute_cell(cut, prompt, "initial")
        if launch_failure is not None:
            raise CellContractError(
                "; ".join(launch_failure.failures) or f"[{cut.id}] launch failed"
            )
        assert outcome is not None

        if outcome.timed_out:
            timeout_note = (
                f"timeout after {outcome.elapsed_s:.0f}s;"
                f" policy on_timeout={self.policy.on_timeout}"
            )
            self._set_state(cut.id, STATE_UNKNOWN, timeout_note)
            if self.policy.on_timeout == "fail":
                return Verdict(
                    cut_id=cut.id,
                    phase=cut.phase,
                    state=STATE_FAILED,
                    failures=(f"{cut.id}: {timeout_note}",),
                )
            if self.policy.on_timeout == "continue":
                return Verdict(
                    cut_id=cut.id,
                    phase=cut.phase,
                    state=STATE_UNKNOWN,
                    failures=(f"{cut.id}: {timeout_note}",),
                )
            # on_timeout == "repair"
            if self.policy.repair_rounds < 1:
                return Verdict(
                    cut_id=cut.id,
                    phase=cut.phase,
                    state=STATE_UNKNOWN,
                    failures=(f"{cut.id}: {timeout_note}; no repair rounds available",),
                )
            repair_attempts += 1
            repair_prompt = self._repair_prompt(
                prompt, (f"previous attempt timed out after {outcome.elapsed_s:.0f}s",)
            )
            self._materialize_prompt(cut, f"repair{repair_attempts}", repair_prompt)
            outcome, launch_failure = self._execute_cell(
                cut, repair_prompt, f"repair{repair_attempts}"
            )
            if launch_failure is not None:
                raise CellContractError(
                    "; ".join(launch_failure.failures)
                    or f"[{cut.id}] repair launch failed"
                )
            assert outcome is not None
            if outcome.timed_out:
                raise CellContractError(
                    f"[{cut.id}] repair round {repair_attempts} also timed out"
                )

        self._set_state(
            cut.id,
            STATE_WORKER_DONE,
            "worker finished; supervisor verification pending",
        )

        substrate = self._substrate_failure(cut, outcome)
        if substrate is not None:
            raise CellContractError("; ".join(substrate.failures))

        if cut.mode == "read":
            violation = self._read_violation(cut, git_before)
            if violation:
                self._journal(f"[{cut.id}] {violation}")
                return Verdict(
                    cut_id=cut.id,
                    phase=cut.phase,
                    state=STATE_FAILED,
                    report=outcome.report_path,
                    failures=(violation,),
                    repair_attempts=repair_attempts,
                )

        verdict = self._verify(cut)
        while (
            verdict.state == STATE_FAILED
            and repair_attempts < self.policy.repair_rounds
        ):
            repair_attempts += 1
            self._journal(
                f"[{cut.id}] verify failed; launching repair round"
                f" {repair_attempts}/{self.policy.repair_rounds}:"
                f" {'; '.join(verdict.failures) or 'no failure detail'}"
            )
            repair_prompt = self._repair_prompt(prompt, verdict.failures)
            self._materialize_prompt(cut, f"repair{repair_attempts}", repair_prompt)
            outcome2, launch_failure = self._execute_cell(
                cut, repair_prompt, f"repair{repair_attempts}"
            )
            if launch_failure is not None:
                raise CellContractError(
                    "; ".join(launch_failure.failures)
                    or f"[{cut.id}] repair launch failed"
                )
            assert outcome2 is not None
            if outcome2.timed_out:
                raise CellContractError(
                    f"[{cut.id}] repair round {repair_attempts} timed out"
                )
            substrate = self._substrate_failure(cut, outcome2)
            if substrate is not None:
                raise CellContractError("; ".join(substrate.failures))
            if cut.mode == "read":
                violation = self._read_violation(cut, git_before)
                if violation:
                    self._journal(f"[{cut.id}] {violation}")
                    return Verdict(
                        cut_id=cut.id,
                        phase=cut.phase,
                        state=STATE_FAILED,
                        report=outcome2.report_path,
                        failures=(violation,),
                        repair_attempts=repair_attempts,
                    )
            outcome = outcome2
            verdict = self._verify(cut)

        delivery_commit = self._git_head()
        if cut.mode != "read" and self.policy.require_commit:
            head_before = git_before[0]
            head_after, status_after = self._git_state()
            if status_after:
                raise CellContractError(
                    f"[{cut.id}] WRITE cut left uncommitted changes after verification:"
                    f" {status_after}"
                )
            if verdict.ok and (
                not head_before or not head_after or head_after == head_before
            ):
                existing = self._existing_delivery_commit(cut, outcome.report_text)
                if not existing:
                    raise CellContractError(
                        f"[{cut.id}] WRITE cut produced no new commit and supplied"
                        " no valid idempotent existing-commit proof:"
                        f" HEAD remained {head_after[:8] or '<unknown>'}"
                    )
                delivery_commit = existing
                self._journal(
                    f"[{cut.id}] accepted idempotent existing commit {existing[:8]}"
                )
            elif verdict.ok and not self._commit_matches_cut(cut, head_after):
                raise CellContractError(
                    f"[{cut.id}] new HEAD {head_after[:8]} does not identify"
                    " the delivered cut"
                )

        return replace(
            verdict,
            commit=delivery_commit,
            report=outcome.report_path,
            repair_attempts=repair_attempts,
        )

    # ------------------------------------------------------- cell execution

    def _execute_cell(
        self, cut: Cut, prompt: str, kind: str
    ) -> tuple[AwaitOutcome | None, Verdict | None]:
        try:
            cell = self.launcher(cut, prompt, kind)
        except Exception as exc:
            message = f"{kind} launch crashed: {type(exc).__name__}: {exc}"
            self._journal(f"[{cut.id}] {message}")
            return None, Verdict(
                cut_id=cut.id,
                phase=cut.phase,
                state=STATE_FAILED,
                failures=(f"{cut.id}: {message}",),
            )
        if not cell.accepted:
            message = f"{kind} launch refused: {cell.error or 'unknown error'}"
            self._journal(f"[{cut.id}] {message}")
            return None, Verdict(
                cut_id=cut.id,
                phase=cut.phase,
                state=STATE_FAILED,
                failures=(f"{cut.id}: {message}",),
            )
        self._journal(
            f"[{cut.id}] {kind} cell launched:"
            f" run_id={cell.run_id or '?'} pid={cell.pid or '?'}"
            f" report={cell.report_path or '?'}"
        )
        outcome = self._await(cell)
        if outcome.timed_out:
            self._terminate(cell)
            self._journal(
                f"[{cut.id}] {kind} cell timed out after {outcome.elapsed_s:.0f}s;"
                " process terminated"
            )
        else:
            recovered = " (recovered by mtime)" if outcome.recovered_by_mtime else ""
            self._journal(
                f"[{cut.id}] {kind} cell finished in {outcome.elapsed_s:.1f}s;"
                f" report={outcome.report_path or 'MISSING'}{recovered}"
            )
            failure = self._cell_contract_failure(cell, outcome)
            if failure:
                self._journal(f"[{cut.id}] {failure}")
                raise CellContractError(f"[{cut.id}] {failure}")
        return outcome, None

    def _cell_contract_failure(self, cell: CellRun, outcome: AwaitOutcome) -> str:
        if cell.exit_code not in (None, 0):
            return f"runtime process failed: exit_code={cell.exit_code}"

        meta: dict[str, Any] = {}
        if cell.meta_path:
            try:
                payload = json.loads(
                    Path(cell.meta_path).expanduser().read_text(encoding="utf-8")
                )
                if isinstance(payload, dict):
                    meta = payload
            except (OSError, json.JSONDecodeError) as exc:
                return (
                    "runtime contract failed: meta missing or unreadable"
                    f" ({type(exc).__name__}: {exc})"
                )

        if cell.meta_path:
            status = str(meta.get("status") or "").strip().lower()
            exit_code = meta.get("exit_code")
            if status != "completed" or exit_code not in (0, "0"):
                detail = str(meta.get("error") or meta.get("last_error") or "").strip()
                suffix = f"; {detail}" if detail else ""
                return (
                    "runtime contract failed:"
                    f" status={status or '<unknown>'}"
                    f" exit_code={exit_code!r}{suffix}"
                )
        elif cell.proc is None and cell.exit_code is None:
            return "runtime contract failed: exit status unavailable"

        if not outcome.report_path:
            return (
                "runtime contract failed: report missing"
                f" for run_id={cell.run_id or '<unknown>'}"
            )
        if not outcome.report_text.strip():
            return (
                "runtime contract failed: report empty"
                f" for run_id={cell.run_id or '<unknown>'}"
            )
        return ""

    def _existing_delivery_commit(self, cut: Cut, report_text: str) -> str:
        if not self.policy.allow_idempotent_existing:
            return ""
        match = re.search(
            r"(?mi)^(?:commit|commit_sha|sha|head_sha):"
            r"\s*['\"]?([0-9a-f]{7,40})['\"]?\s*$",
            report_text,
        )
        if match is None:
            return ""
        resolved = self._git(["rev-parse", "--verify", f"{match.group(1)}^{{commit}}"])
        if not resolved or not self._git_ok(
            ["merge-base", "--is-ancestor", resolved, "HEAD"]
        ):
            return ""
        if not self._commit_matches_cut(cut, resolved):
            return ""
        return resolved

    def _commit_matches_cut(self, cut: Cut, commit: str) -> bool:
        message = self._git(["show", "-s", "--format=%B", commit])
        slot = cut.id.split("_", 1)[0]
        return cut.id in message or f"[{slot}]" in message

    def _await(self, cell: CellRun) -> AwaitOutcome:
        """Await the cell through its process handle, never through meta.json
        state — the launcher-truth prerequisite says terminal metadata may
        lie, the process cannot."""
        poll_s, timeout_s = self._await_config()
        started = time.monotonic()
        wall_started = time.time()
        while not self._cell_finished(cell):
            elapsed = time.monotonic() - started
            if elapsed >= timeout_s:
                return AwaitOutcome(finished=False, timed_out=True, elapsed_s=elapsed)
            self._sleep(poll_s)
        elapsed = time.monotonic() - started
        report_path, report_text, recovered = self._resolve_report(cell, wall_started)
        return AwaitOutcome(
            finished=True,
            timed_out=False,
            elapsed_s=elapsed,
            report_path=report_path,
            report_text=report_text,
            recovered_by_mtime=recovered,
        )

    def _cell_finished(self, cell: CellRun) -> bool:
        if cell.proc is not None:
            exit_code = cell.proc.poll()
            if exit_code is None:
                return False
            cell.exit_code = exit_code
            return True
        if not cell.pid:
            return True
        try:
            done, status = os.waitpid(cell.pid, os.WNOHANG)
        except ChildProcessError:
            pass  # not our child: fall through to the liveness probe
        except OSError:
            pass
        else:
            if done == cell.pid:
                cell.exit_code = os.waitstatus_to_exitcode(status)
                return True
            return False
        try:
            os.kill(cell.pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        return False

    def _terminate(self, cell: CellRun) -> None:
        try:
            if cell.proc is not None:
                cell.proc.terminate()
            elif cell.pid:
                # launch_workflow spawns with start_new_session, so the pid
                # doubles as the process-group id.
                os.killpg(cell.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def _resolve_report(
        self, cell: CellRun, wall_started: float
    ) -> tuple[str, str, bool]:
        announced = Path(cell.report_path).expanduser() if cell.report_path else None
        if announced is not None and announced.is_file():
            try:
                return str(announced), announced.read_text(encoding="utf-8"), False
            except OSError:
                pass
        # Recovery ONLY: the announced path is broken, search reports_dir
        # for the freshest report written since launch.
        reports_dir = (
            Path(self.dispatch.meta.reports_dir).expanduser()
            if self.dispatch.meta.reports_dir
            else None
        )
        if reports_dir is not None and reports_dir.is_dir():
            candidates = [
                path
                for path in reports_dir.glob("*.md")
                if path.is_file()
                and path.stat().st_mtime >= wall_started - _MTIME_TOLERANCE_S
            ]
            if candidates:
                newest = max(candidates, key=lambda path: path.stat().st_mtime)
                self._journal(
                    f"[{cell.cut_id}] announced report path broken"
                    f" ({cell.report_path or 'none'}); recovered by mtime:"
                    f" {newest}"
                )
                try:
                    return str(newest), newest.read_text(encoding="utf-8"), True
                except OSError:
                    pass
        return "", "", False

    # ------------------------------------------------------------- checks

    def _substrate_failure(self, cut: Cut, outcome: AwaitOutcome) -> Verdict | None:
        if SUBSTRATE_FAILURE_MARKER not in outcome.report_text:
            return None
        line = next(
            (
                stripped
                for stripped in outcome.report_text.splitlines()
                if SUBSTRATE_FAILURE_MARKER in stripped
            ),
            SUBSTRATE_FAILURE_MARKER,
        ).strip()
        self._journal(f"[{cut.id}] substrate failure reported by worker: {line}")
        return Verdict(
            cut_id=cut.id,
            phase=cut.phase,
            state=STATE_FAILED,
            report=outcome.report_path,
            failures=(f"{cut.id}: {line}",),
        )

    def _read_violation(self, cut: Cut, before: tuple[str, str]) -> str:
        # "allow-report-only" permits artifact writes outside the repo;
        # any in-repo git drift still violates it, same as "forbid".
        if cut.mutation == "allow":
            return ""
        after = self._git_state()
        if before == after:
            return ""
        policy = cut.mutation or "forbid"
        head_before = before[0][:8] or "<none>"
        head_after = after[0][:8] or "<none>"
        drift = after[1] if after[1] != before[1] else ""
        return (
            f"READ cut mutated the repository (mutation policy {policy!r}):"
            f" HEAD {head_before} -> {head_after};"
            f" status drift: {drift.strip() or '<head moved>'}"
        )

    def _verify(self, cut: Cut) -> Verdict:
        if self.policy.verify_executor != "supervisor":
            self._journal(
                f"[{cut.id}] verify_executor={self.policy.verify_executor!r}"
                " is not supported yet; falling back to supervisor execution"
            )
        verdict = run_verifies(render_cut_verifies(self.dispatch, cut), repo=self.repo)
        for evidence in verdict.verifiers:
            self._journal(
                f"[{cut.id}] verifier {evidence.matcher_result}:"
                f" {evidence.command!r} exit={evidence.exit_code}"
                f" ({evidence.elapsed_ms}ms)"
            )
        for failure in verdict.failures:
            self._journal(f"[{cut.id}] verifier failure: {failure}")
        return verdict

    def _repair_prompt(self, prompt: str, failures: tuple[str, ...]) -> str:
        details = "\n".join(f"- {failure}" for failure in failures)
        return (
            f"{prompt}\n\nREPAIR ROUND — the supervisor refuted the previous"
            f" attempt with this evidence:\n{details or '- no failure detail'}\n"
            "Fix the refuted surface, re-run the gates, and commit the repair."
        )

    # ------------------------------------------------------------- git

    def _git_state(self) -> tuple[str, str]:
        return self._git_head(), self._git(["status", "--porcelain"])

    def _git_head(self) -> str:
        return self._git(["rev-parse", "HEAD"])

    def _git(self, args: list[str]) -> str:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=self.repo,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return proc.stdout.strip() if proc.returncode == 0 else ""

    def _git_ok(self, args: list[str]) -> bool:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=self.repo,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return proc.returncode == 0

    # --------------------------------------------------------- artifacts

    def _await_config(self) -> tuple[float, float]:
        config = self.policy.await_config or {}
        poll_s = float(config.get("poll_s", DEFAULT_POLL_S))
        timeout_s = float(config.get("timeout_min", DEFAULT_TIMEOUT_MIN)) * 60.0
        return max(poll_s, 0.01), max(timeout_s, 0.01)

    def _materialize_prompt(self, cut: Cut, kind: str, prompt: str) -> None:
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        path = self.prompts_dir / f"{cut.id}_{kind}.md"
        path.write_text(prompt, encoding="utf-8")

    def _set_state(self, cut_id: str, state: str, note: str) -> None:
        self._states[cut_id] = (state, note)
        self._journal(f"[{cut_id}] state {state}: {note}")
        self._write_tracker()

    def _verdict_note(self, verdict: Verdict) -> str:
        parts: list[str] = []
        if verdict.commit:
            parts.append(f"commit {verdict.commit[:8]}")
        if verdict.verifiers:
            green = sum(1 for evidence in verdict.verifiers if evidence.ok)
            parts.append(f"verifiers {green}/{len(verdict.verifiers)} green")
        if verdict.repair_attempts:
            parts.append(f"repair rounds {verdict.repair_attempts}")
        if verdict.failures:
            parts.append(verdict.failures[0])
        return "; ".join(parts) or "no evidence recorded"

    def _journal(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {timestamp} {message}\n")

    def _write_tracker(self) -> None:
        meta = self.dispatch.meta
        lines = [
            f"# dispatch tracker — {meta.name or 'unnamed'}",
            "",
            f"- repo: {meta.repo}",
            f"- baseline_branch: {meta.baseline.get('branch', '')}",
            f"- baseline_head: {meta.baseline.get('head', '')}",
            f"- validated_copy: {self.artifacts_dir / 'validated-dispatch.toml'}",
            f"- updated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            "- writer: dispatch supervisor (single writer; verified state"
            " flips only after green supervisor verify)",
            "",
            "| Cut | Phase | Agent | State | Supervisor evidence |",
            "|---|---|---|---:|---|",
        ]
        for cut in self.dispatch.cuts:
            state, note = self._states[cut.id]
            lines.append(f"| {cut.id} | {cut.phase} | {cut.agent} | {state} | {note} |")
        self.tracker_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _mark_downstream_skipped(self, cut_id: str) -> None:
        past_failed_cut = False
        for cut in self.dispatch.cuts:
            if cut.id == cut_id:
                past_failed_cut = True
                continue
            if past_failed_cut and self._states[cut.id][0] == STATE_PENDING:
                self._set_state(cut.id, STATE_PENDING, "skipped: line broken upstream")

    def _build_result(self, baton: Baton, line_broken: bool) -> DispatchResult:
        verdicts = {state.cut_id: state for state in baton.states}
        return DispatchResult(
            line_broken=line_broken,
            baton=baton,
            states={cut_id: state for cut_id, (state, _) in self._states.items()},
            cuts=tuple(
                {
                    "id": cut.id,
                    "phase": cut.phase,
                    "agent": cut.agent,
                    "state": self._states[cut.id][0],
                    "note": self._states[cut.id][1],
                    "commit": verdicts[cut.id].commit if cut.id in verdicts else "",
                    "report": verdicts[cut.id].report if cut.id in verdicts else "",
                }
                for cut in self.dispatch.cuts
            ),
            artifacts={
                "tracker": str(self.tracker_path),
                "journal": str(self.journal_path),
                "handoff": str(self.handoff_path),
                "result": str(self.result_path),
            },
        )

    def _write_final_artifacts(self, result: DispatchResult) -> None:
        self.result_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._write_handoff(result)
        self._journal(
            f"dispatch end: dou_index {result.baton.verified}/{result.baton.total}"
            f" line_broken={result.line_broken}"
        )

    def _write_handoff(self, result: DispatchResult) -> None:
        baton = result.baton
        meta = self.dispatch.meta
        lines = [
            f"# dispatch handoff — {meta.name or 'unnamed'}",
            "",
            f"- repo: {meta.repo}",
            f"- dou_index: {baton.verified}/{baton.total}"
            f" ({baton.ratio:.0%} supervisor-verified)",
            f"- line_broken: {result.line_broken}",
            f"- tracker: {self.tracker_path}",
            f"- journal: {self.journal_path}",
            "",
            "## Cut states",
            "",
            "| Cut | Phase | State | Commit | Report |",
            "|---|---|---:|---|---|",
        ]
        verdicts = {state.cut_id: state for state in baton.states}
        for cut in self.dispatch.cuts:
            state, _ = self._states[cut.id]
            recorded = verdicts.get(cut.id)
            commit = recorded.commit[:8] if recorded and recorded.commit else ""
            report = recorded.report if recorded else ""
            lines.append(f"| {cut.id} | {cut.phase} | {state} | {commit} | {report} |")
        lines += ["", "## Evidence", ""]
        last = baton.last
        seen_verdicts = []
        # Baton states carry summaries; full verifier evidence is journaled
        # per transition. Surface the final verdict's evidence here too.
        if last is not None:
            seen_verdicts.append(last)
        for verdict in seen_verdicts:
            for evidence in verdict.verifiers:
                status = "PASS" if evidence.ok else evidence.matcher_result.upper()
                lines.append(
                    f"- [{verdict.cut_id}] {status}: `{evidence.command}`"
                    f" exit={evidence.exit_code}"
                )
            for failure in verdict.failures:
                lines.append(f"- [{verdict.cut_id}] FAILURE: {failure}")
        lines += ["", "## Next suggested action", ""]
        lines.append(self._next_action(result))
        self.handoff_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _next_action(self, result: DispatchResult) -> str:
        if result.line_broken:
            broken = [
                cut_id
                for cut_id, (state, _) in self._states.items()
                if state == STATE_FAILED
            ]
            return (
                f"Critical cut failed ({', '.join(broken) or 'unknown'});"
                " operator decision required before re-dispatch."
            )
        unverified = [
            cut_id
            for cut_id, (state, _) in self._states.items()
            if state != STATE_VERIFIED
        ]
        if not unverified:
            return (
                "All cuts supervisor-verified. STOP at the operator button:"
                " push/release stays a human action."
            )
        return f"Re-dispatch or inspect unverified cuts: {', '.join(unverified)}."


def run_dispatch(
    dispatch: Dispatch,
    *,
    launcher: CellLauncher | None = None,
    artifacts_dir: str | Path | None = None,
    source_dir: str | Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> DispatchResult:
    supervisor = DispatchSupervisor(
        dispatch,
        launcher=launcher,
        artifacts_dir=artifacts_dir,
        source_dir=source_dir,
        sleep=sleep,
    )
    return supervisor.run()
