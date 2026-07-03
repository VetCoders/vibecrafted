from __future__ import annotations

import asyncio
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .control_plane import control_plane_home, normalize_run_root, run_liveness
from .workflow import (
    SUPPORTED_AGENTS,
    WorkflowLaunchSpec,
    await_launch_truth,
    launch_workflow,
    report_dou_index,
)
from .workflows.registry import workflow_manifest, workflow_manifest_payload
from .workflows.model import WorkflowManifest, WorkflowStage

LaunchWorkflow = Callable[[WorkflowLaunchSpec, str | Path], dict[str, Any]]
AwaitWorkflow = Callable[[dict[str, Any]], dict[str, Any]]
LIFECYCLE_SCHEMA_ID = "vibecrafted.lifecycle.v1"


@dataclass(frozen=True)
class LifecycleRunSpec:
    workflow_id: str
    agent: str
    prompt: str = ""
    file: str = ""
    root: str = ""
    runtime: str = "headless"
    await_stages: bool = False
    start_stage: str = ""
    count: int | None = None
    depth: int | None = None
    parent_run_id: str = ""
    # Baton cargo: stage reports accumulated by earlier runs in the relay.
    # Continuation runs (approve / force-audit) seed these so the next stage
    # prompt keeps consuming what the previous Read/Write stages produced.
    previous_reports: tuple[str, ...] = ()


def _lifecycle_run_id(workflow_id: str) -> str:
    stamp = time.strftime("%y%m%d-%H%M%S")
    code = workflow_id.removeprefix("vc-")[:4].ljust(4, "x")
    entropy = int(time.time_ns() % 100000)
    return f"life-{code}-{stamp}-{entropy:05d}"


def _git_head(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _git_status(root: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return sorted(line for line in proc.stdout.splitlines() if line.strip())


def _status_paths(lines: list[str]) -> set[str]:
    paths: set[str] = set()
    for line in lines:
        raw = line[3:] if len(line) > 3 else line
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        if raw:
            paths.add(raw)
    return paths


def _file_fingerprint(root: Path, relative_path: str) -> str:
    path = root / relative_path
    try:
        if path.is_dir():
            return "dir"
        if not path.is_file():
            return "missing"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        return f"error:{type(exc).__name__}"


def _git_worktree_snapshot(root: Path, status_lines: list[str]) -> dict[str, str]:
    return {path: _file_fingerprint(root, path) for path in _status_paths(status_lines)}


def _changed_paths_between(
    before_status: list[str],
    after_status: list[str],
    before_snapshot: dict[str, str],
    after_snapshot: dict[str, str],
) -> list[str]:
    paths = _status_paths(after_status) - _status_paths(before_status)
    for path in set(before_snapshot) | set(after_snapshot):
        if before_snapshot.get(path) != after_snapshot.get(path):
            paths.add(path)
    return sorted(paths)


def _commits_between(root: Path, before: str, after: str) -> list[str]:
    if not before or not after or before == after:
        return []
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--reverse", f"{before}..{after}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return [after]
    commits = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return commits if proc.returncode == 0 else [after]


def _committed_paths_between(root: Path, before: str, after: str) -> list[str]:
    if not before or not after or before == after:
        return []
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", f"{before}..{after}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return sorted(line.strip() for line in proc.stdout.splitlines() if line.strip())


def _read_file(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return f"Read the requested prompt file yourself: {path}"


def load_context_atlas(root: Path, *, task: str) -> dict[str, Any]:
    command = ["loct", "context", "--task", task]
    try:
        proc = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "ok": False,
            "command": command,
            "error": f"{type(exc).__name__}: {exc}",
            "stdout": "",
            "stderr": "",
        }
    return {
        "ok": proc.returncode == 0,
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-4000:],
    }


def _context_excerpt(context: dict[str, Any]) -> str:
    stdout = str(context.get("stdout") or "").strip()
    stderr = str(context.get("stderr") or "").strip()
    if stdout:
        return stdout[-6000:]
    if stderr:
        return f"Context Atlas stderr:\n{stderr[-2000:]}"
    if context.get("ok"):
        return "Context Atlas loaded; no text output captured."
    error = str(context.get("error") or "").strip()
    return f"Context Atlas unavailable: {error or 'unknown error'}"


def _env_float(name: str, default: float | None) -> float | None:
    raw = str(os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _lifecycle_await_idle_seconds() -> float:
    """Idle (zero-movement) window before a stage is treated as genuinely stalled.

    This is NOT a wall-clock budget — :func:`await_run` resets it on every burst
    of real activity. A single marble can legitimately run ~13 min; the default
    here is the *silence* a run may show before we call it stalled, far below the
    work time but well above normal token cadence. Override with
    ``VIBECRAFTED_AWAIT_IDLE_S``.
    """
    return _env_float("VIBECRAFTED_AWAIT_IDLE_S", 600.0) or 600.0


def _lifecycle_await_hard_cap_seconds() -> float | None:
    """Absolute ceiling for a live-but-wedged stage, far above realistic work.

    Liveness governs by default; this cap only fires when a worker stays alive
    yet never finishes. Default 6h is far above any single-marble run. Override
    with ``VIBECRAFTED_AWAIT_HARD_CAP_S`` (set to 0 to disable the cap entirely).
    """
    raw = str(os.environ.get("VIBECRAFTED_AWAIT_HARD_CAP_S") or "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            return 21600.0
        return value if value > 0 else None
    return 21600.0


def _surfaced_dou_index(payload: dict[str, Any]) -> int | None:
    """Validated worker-reported DoU index from an await/launch payload.

    ``bool`` is an ``int`` subclass in Python — reject it explicitly so a
    stray ``dou_index: true`` never reads as 1.
    """
    value = payload.get("dou_index")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _state_dou_value(state: dict[str, Any]) -> int | None:
    dou = state.get("dou_index")
    if not isinstance(dou, dict):
        return None
    value = dou.get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _stage_worker_liveness(
    state: dict[str, Any],
    stage_launch: dict[str, Any],
    liveness_reader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconciled liveness of the current stage's worker run.

    Closes the report-on-death gap at the lifecycle surface: in no-await mode
    a worker that dies at startup leaves the lifecycle run in ``launching``
    forever, and only OS-level liveness tells a corpse apart from slow work.
    ``worker_dead_without_report`` is the actionable signal — the stage will
    never deliver on its own; recover with interrupt/fallback/approve.
    """
    stage_run_id = str(stage_launch.get("run_id") or "").strip()
    if not stage_run_id or state.get("status") != "launching":
        return {}
    reader = liveness_reader or run_liveness
    liveness = reader(stage_run_id)
    report_path = str(stage_launch.get("report") or "").strip()
    report_written = bool(report_path) and Path(report_path).is_file()
    liveness["report_written"] = report_written
    liveness["worker_dead_without_report"] = (
        bool(liveness.get("found"))
        and not liveness.get("worker_alive")
        and not report_written
    )
    return liveness


def _lifecycle_max_stage_launches(manifest: WorkflowManifest) -> int:
    """Ceiling on stage launches per lifecycle run.

    Fallback edges (audit -> marbles) and worker-requested steering
    (``next_stage`` in the report frontmatter) make the stage graph cyclic by
    design — the umbrella may walk backwards. This cap turns a steering loop
    that never converges into an explicit failure instead of an unbounded
    dispatch spree. Override with ``VIBECRAFTED_LIFECYCLE_MAX_STAGES``.
    """
    raw = str(os.environ.get("VIBECRAFTED_LIFECYCLE_MAX_STAGES") or "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
    return max(6, 3 * len(manifest.stages))


class LifecycleRunner:
    def __init__(
        self,
        *,
        launcher: LaunchWorkflow = launch_workflow,
        awaiter: AwaitWorkflow | None = None,
    ) -> None:
        self.launcher = launcher
        self.awaiter = awaiter or (
            lambda payload: await_launch_truth(
                payload,
                timeout_seconds=_lifecycle_await_idle_seconds(),
                interval_seconds=5,
                hard_cap_seconds=_lifecycle_await_hard_cap_seconds(),
            )
        )

    async def run(self, spec: LifecycleRunSpec) -> dict[str, Any]:
        manifest = workflow_manifest(spec.workflow_id)
        if manifest is None:
            raise ValueError(f"Unsupported lifecycle workflow: {spec.workflow_id}")

        root = Path(normalize_run_root(spec.root, Path.cwd()))
        source_prompt = spec.prompt or _read_file(spec.file)
        run_id = _lifecycle_run_id(manifest.id)
        run_dir = control_plane_home() / "lifecycle_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        state_path = run_dir / "state.json"
        report_path = run_dir / "report.md"
        transcript_path = run_dir / "transcript.log"
        current_stage = spec.start_stage or manifest.first_stage.id

        context = load_context_atlas(
            root,
            task=f"{manifest.id}: {source_prompt[:160] or spec.file or 'lifecycle run'}",
        )
        previous_reports: list[str] = [
            str(path).strip() for path in spec.previous_reports if str(path).strip()
        ]
        state: dict[str, Any] = {
            "schema": LIFECYCLE_SCHEMA_ID,
            "run_id": run_id,
            "workflow": manifest.id,
            "agent": spec.agent,
            "root": str(root),
            "status": "launching",
            "await_stages": spec.await_stages,
            "parent_run_id": spec.parent_run_id,
            "operator_actions": [],
            "spec": {
                "workflow_id": manifest.id,
                "agent": spec.agent,
                "prompt": source_prompt,
                "file": spec.file,
                "root": str(root),
                "runtime": spec.runtime,
                "await_stages": spec.await_stages,
                "start_stage": current_stage,
                "count": spec.count,
                "depth": spec.depth,
                "previous_reports": list(previous_reports),
            },
            "supervisor": "vibecrafted_core.lifecycle_runner.LifecycleSupervisor",
            "human_controls": list(manifest.human_controls),
            "state_path": str(state_path),
            "report_path": str(report_path),
            "transcript_path": str(transcript_path),
            "context_atlas": {
                "ok": bool(context.get("ok")),
                "command": context.get("command", []),
                "returncode": context.get("returncode"),
                "error": context.get("error", ""),
                "excerpt": _context_excerpt(context),
            },
            "manifest": workflow_manifest_payload(manifest.id),
            "baton": {
                "from_stage": "",
                "next_stage": current_stage,
                "next_agent": spec.agent,
                "reason": "initial",
                "previous_reports": list(previous_reports),
                "dou_index": None,
            },
            "stages": [],
            "accepted_dou_findings": [],
        }
        self._write_state(state_path, state)

        max_stage_launches = _lifecycle_max_stage_launches(manifest)
        current = current_stage
        current_agent = spec.agent
        while current:
            if len(state["stages"]) >= max_stage_launches:
                state["status"] = "failed"
                state["error"] = (
                    f"lifecycle stage cap reached ({max_stage_launches} launches); "
                    f"steering loop suspected before stage: {current}"
                )
                break
            stage = manifest.stage(current)
            if stage is None:
                state["status"] = "failed"
                state["error"] = f"unknown lifecycle stage: {current}"
                break
            record = await self._start_stage(
                manifest=manifest,
                stage=stage,
                spec=spec,
                agent=stage.agent or current_agent,
                source_prompt=source_prompt,
                root=root,
                previous_reports=previous_reports,
                context=context,
                state_path=state_path,
            )
            state["stages"].append(record)
            self._write_state(state_path, state)
            with transcript_path.open(
                "a", encoding="utf-8", errors="replace"
            ) as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not spec.await_stages:
                # The worker writes this report while the operator decides;
                # the baton must carry it into the approved continuation.
                launched_report = str(record["launch"].get("report") or "").strip()
                if launched_report:
                    previous_reports.append(launched_report)
                state["status"] = "launching"
                state["next_stage"] = stage.next_stage
                state["baton"] = self._baton(
                    stage=stage,
                    next_stage=stage.next_stage,
                    next_agent=current_agent,
                    previous_reports=previous_reports,
                    dou_index=_state_dou_value(state),
                    reason="stage_launched_without_await",
                )
                break

            state["status"] = "running"
            self._write_state(state_path, state)
            await_result = await asyncio.to_thread(self.awaiter, record["launch"])
            record["await"] = await_result
            record["status"] = (
                "completed" if await_result.get("artifact_ok") else "failed"
            )
            reported_dou = _surfaced_dou_index(await_result)
            if reported_dou is not None:
                record["dou_index"] = reported_dou
                state["dou_index"] = {
                    "value": reported_dou,
                    "stage": stage.id,
                    "report": str(record["launch"].get("report") or ""),
                }
            record["commit_after"] = _git_head(root)
            record["git_after"] = _git_status(root)
            record["git_snapshot_after"] = _git_worktree_snapshot(
                root, list(record.get("git_after") or [])
            )
            status_changed_files = _changed_paths_between(
                list(record.get("git_before") or []),
                list(record.get("git_after") or []),
                dict(record.get("git_snapshot_before") or {}),
                dict(record.get("git_snapshot_after") or {}),
            )
            committed_changed_files = _committed_paths_between(
                root,
                str(record.get("commit_before") or ""),
                str(record.get("commit_after") or ""),
            )
            record["changed_files"] = sorted(
                set(status_changed_files) | set(committed_changed_files)
            )
            record["new_commits"] = _commits_between(
                root,
                str(record.get("commit_before") or ""),
                str(record.get("commit_after") or ""),
            )
            if record["phase"] == "read" and record["changed_files"]:
                record["read_phase_violation"] = True
                state["status"] = "failed"
                state["error"] = f"READ stage {stage.id} changed files: " + ", ".join(
                    record["changed_files"]
                )
                break
            if record["launch"].get("report"):
                previous_reports.append(str(record["launch"]["report"]))
            self._write_state(state_path, state)

            next_stage = self._next_stage(manifest, stage, await_result)
            current_agent = self._next_agent(current_agent, await_result)
            record["transition"] = {
                "next_stage": next_stage,
                "requested_next_stage": str(await_result.get("next_stage") or ""),
                "next_agent": current_agent,
                "requested_next_agent": str(await_result.get("next_agent") or ""),
                "conditions": list(stage.transition_conditions),
                "fallback_stage": stage.fallback_stage,
                "audit_after": stage.audit_after,
            }
            state["baton"] = self._baton(
                stage=stage,
                next_stage=next_stage,
                next_agent=current_agent,
                previous_reports=previous_reports,
                dou_index=_state_dou_value(state),
                reason="awaited_stage_completed",
            )
            if not next_stage:
                state["status"] = "completed"
                break
            current = next_stage
        else:
            state["status"] = "completed"

        self._write_state(state_path, state)
        self._write_report(report_path, state)
        return state

    async def _start_stage(
        self,
        *,
        manifest: WorkflowManifest,
        stage: WorkflowStage,
        spec: LifecycleRunSpec,
        agent: str,
        source_prompt: str,
        root: Path,
        previous_reports: list[str],
        context: dict[str, Any],
        state_path: Path | None = None,
    ) -> dict[str, Any]:
        prompt = self._stage_prompt(
            manifest=manifest,
            stage=stage,
            source_prompt=source_prompt,
            previous_reports=previous_reports,
            context=context,
        )
        launch_spec = WorkflowLaunchSpec(
            agent=agent,
            mode=stage.workflow,
            skill=stage.workflow,
            prompt=prompt,
            file="",
            runtime=spec.runtime,
            root=str(root),
            count=spec.count if stage.workflow == "marbles" else None,
            depth=spec.depth if stage.workflow == "marbles" else None,
            lifecycle_state_path=str(state_path or ""),
        )
        commit_before = _git_head(root)
        git_before = _git_status(root)
        git_snapshot_before = _git_worktree_snapshot(root, git_before)
        launch = await asyncio.to_thread(self.launcher, launch_spec, root)
        return {
            "id": stage.id,
            "name": stage.name,
            "workflow": stage.workflow,
            "agent": agent,
            "phase": stage.phase,
            "can_modify_code": stage.can_modify_code,
            "tooling": list(stage.tooling),
            "transition_conditions": list(stage.transition_conditions),
            "allowed_artifacts": list(stage.allowed_artifacts),
            "next_stage": stage.next_stage,
            "fallback_stage": stage.fallback_stage,
            "audit_after": stage.audit_after,
            "commit_before": commit_before,
            "git_before": git_before,
            "git_snapshot_before": git_snapshot_before,
            "launch": launch,
            "status": "launching",
        }

    def _stage_prompt(
        self,
        *,
        manifest: WorkflowManifest,
        stage: WorkflowStage,
        source_prompt: str,
        previous_reports: list[str],
        context: dict[str, Any],
    ) -> str:
        previous = "\n".join(f"- {path}" for path in previous_reports) or "- none"
        mutation = "may modify code" if stage.can_modify_code else "must stay read-only"
        atlas = _context_excerpt(context)
        transition_conditions = (
            ", ".join(stage.transition_conditions) or "launch_accepted"
        )
        allowed_artifacts = ", ".join(stage.allowed_artifacts) or "none"
        human_controls = ", ".join(manifest.human_controls) or "none"
        known_agents = ", ".join(sorted(SUPPORTED_AGENTS))
        dou_contract = ""
        if stage.workflow == "dou":
            dou_contract = (
                "\n- dou_index: <int> — REQUIRED for DoU stages: the count of open"
                "\n  Definition-of-Undone findings you measured (gaps the operator has"
                "\n  consciously accepted via accept-dou do not count as open);"
                "\n  0 = ZERO DoU index, the launch-ready target."
            )
        return f"""Vibecrafted Lifecycle Runtime

Workflow: {manifest.id} ({manifest.name})
Stage: {stage.order}. {stage.name}
Runtime workflow: vc-{stage.workflow}
Phase: {stage.phase.upper()} ({mutation})
Required tooling: {", ".join(stage.tooling) or "none"}
Transition conditions: {transition_conditions}
Allowed artifacts: {allowed_artifacts}
Human controls: {human_controls}
Next stage: {stage.next_stage or "complete"}
Fallback/audit stage: {stage.fallback_stage or stage.audit_after or "none"}

READ phase rule:
- Do not modify code during READ phases.
- Reports, cache, and run artifacts are allowed.

WRITE phase rule:
- Code changes are allowed, but changed files must be reported.

Lifecycle steering (optional, via your report YAML frontmatter):
- next_stage: <stage-id> — steer the lifecycle forward or backward; unknown
  stage ids are ignored (manifest-validated). No key = manifest order.
- next_agent: <agent-id> — hand the baton to that agent for the following
  stages ({known_agents}); unknown agents are ignored.{dou_contract}

Previous stage reports:
{previous}

Context Atlas:
{atlas}

Operator prompt:
{source_prompt}
"""

    def _next_stage(
        self,
        manifest: WorkflowManifest,
        stage: WorkflowStage,
        await_result: dict[str, Any],
    ) -> str:
        requested = str(await_result.get("next_stage") or "").strip()
        if requested and manifest.stage(requested) is not None:
            return requested
        if not await_result.get("artifact_ok") and stage.fallback_stage:
            return stage.fallback_stage
        if stage.audit_after and manifest.stage(stage.audit_after) is not None:
            return stage.audit_after
        return stage.next_stage

    def _next_agent(self, current_agent: str, await_result: dict[str, Any]) -> str:
        """Sticky baton handoff: a valid worker-requested ``next_agent`` becomes
        the holder for the following stages until re-steered; unknown agents
        are ignored (mirrors unknown ``next_stage`` handling)."""
        requested = str(await_result.get("next_agent") or "").strip()
        if requested and requested in SUPPORTED_AGENTS:
            return requested
        return current_agent

    def _baton(
        self,
        *,
        stage: WorkflowStage,
        next_stage: str,
        next_agent: str,
        previous_reports: list[str],
        dou_index: int | None,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "from_stage": stage.id,
            "from_phase": stage.phase,
            "next_stage": next_stage,
            "next_agent": next_agent,
            "fallback_stage": stage.fallback_stage,
            "audit_after": stage.audit_after,
            "reason": reason,
            "previous_reports": list(previous_reports),
            "dou_index": dou_index,
        }

    def _write_state(self, path: Path, state: dict[str, Any]) -> None:
        write_lifecycle_state(path, state)

    def _write_report(self, path: Path, state: dict[str, Any]) -> None:
        write_lifecycle_report(path, state)


def write_lifecycle_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def record_stage_worker_exit(
    state_path: str | Path,
    stage_run_id: str,
    exit_payload: dict[str, Any],
) -> bool:
    """Push-side report-on-death: write the worker's terminal truth into the
    lifecycle state itself (docs/runtime/AGENT_OPS.md, Class 2).

    Called by the dispatcher when a lifecycle stage worker exits in failure,
    so purely passive readers of ``state.json`` (the Rust server, dashboards)
    see the death without anyone running a status verb. Additive within
    lifecycle.schema.v1: annotates the matching stage with ``worker_exit`` and
    mirrors it top-level as ``stage_worker_exit`` while the run still waits in
    ``launching``. Never raises — a corrupt or missing state file returns
    ``False``; poisoning the dispatch exit path would trade one blind spot for
    another.
    """
    target = str(stage_run_id or "").strip()
    path = Path(state_path).expanduser()
    if not target:
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(state, dict):
        return False
    stages = state.get("stages")
    if not isinstance(stages, list) or not stages:
        return False
    matched_index: int | None = None
    for index in range(len(stages) - 1, -1, -1):
        stage = stages[index]
        if not isinstance(stage, dict):
            continue
        launch = stage.get("launch") or {}
        if str(launch.get("run_id") or "") == target:
            matched_index = index
            break
    if matched_index is None:
        return False
    payload = dict(exit_payload)
    payload.setdefault("recorded_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    stages[matched_index]["worker_exit"] = payload
    # Top-level mirror only for the CURRENT stage of a still-waiting run: a
    # stage that was already superseded (fallback/approve relaunch) is
    # history, not an alarm.
    if matched_index == len(stages) - 1 and state.get("status") == "launching":
        state["stage_worker_exit"] = {
            **payload,
            "stage": str(stages[matched_index].get("id") or ""),
            "run_id": target,
        }
    try:
        write_lifecycle_state(path, state)
    except OSError:
        return False
    return True


def write_lifecycle_report(path: Path, state: dict[str, Any]) -> None:
    stages = state.get("stages") or []
    lines = [
        f"# Lifecycle run {state.get('run_id')}",
        "",
        f"- workflow: {state.get('workflow')}",
        f"- status: {state.get('status')}",
        f"- agent: {state.get('agent')}",
        f"- root: {state.get('root')}",
        f"- context_atlas_ok: {state.get('context_atlas', {}).get('ok')}",
        f"- supervisor: {state.get('supervisor')}",
        "- human_controls: " + ", ".join(state.get("human_controls") or []),
    ]
    if state.get("parent_run_id"):
        lines.append(f"- parent_run_id: {state.get('parent_run_id')}")
    dou = state.get("dou_index")
    if isinstance(dou, dict) and dou.get("value") is not None:
        lines.append(f"- dou_index: {dou.get('value')} (stage: {dou.get('stage', '')})")
    accepted_dou = state.get("accepted_dou_findings") or []
    if accepted_dou:
        lines.append(f"- accepted_dou_findings: {len(accepted_dou)}")
    lines.extend(["", "## Stages"])
    for stage in stages:
        lines.extend(
            [
                "",
                f"- {stage.get('id')} ({stage.get('phase')}): {stage.get('status')}",
                f"  - agent: {stage.get('agent', '')}",
                f"  - run_id: {stage.get('launch', {}).get('run_id', '')}",
                f"  - report: {stage.get('launch', {}).get('report', '')}",
                f"  - commit_before: {stage.get('commit_before', '')}",
                f"  - commit_after: {stage.get('commit_after', '')}",
                f"  - exit_code: {stage.get('await', {}).get('exit_code', '')}",
                f"  - artifact_ok: {stage.get('await', {}).get('artifact_ok', '')}",
                "  - transition_conditions: "
                + ", ".join(stage.get("transition_conditions") or []),
                "  - allowed_artifacts: "
                + ", ".join(stage.get("allowed_artifacts") or []),
                "  - new_commits: " + ", ".join(stage.get("new_commits") or []),
                "  - changed_files: " + ", ".join(stage.get("changed_files") or []),
            ]
        )
    baton = state.get("baton") or {}
    lines.extend(
        [
            "",
            "## Baton",
            f"- from_stage: {baton.get('from_stage', '')}",
            f"- next_stage: {baton.get('next_stage', '')}",
            f"- next_agent: {baton.get('next_agent', '')}",
            f"- reason: {baton.get('reason', '')}",
        ]
    )
    operator_actions = state.get("operator_actions") or []
    if operator_actions:
        lines.extend(["", "## Operator actions"])
        for action in operator_actions:
            details = action.get("details") or {}
            summary = ", ".join(f"{key}={details[key]}" for key in sorted(details))
            lines.append(
                f"- {action.get('at', '')} {action.get('action', '')}"
                + (f" ({summary})" if summary else "")
            )
    if state.get("error"):
        lines.extend(["", "## Error", str(state["error"])])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


class LifecycleSupervisor:
    """Small async facade for lifecycle supervision and future server wiring."""

    def __init__(self, runner: LifecycleRunner | None = None) -> None:
        self.runner = runner or LifecycleRunner()

    async def start(self, spec: LifecycleRunSpec) -> dict[str, Any]:
        return await self.runner.run(spec)

    def read_state(self, state_path: str | Path) -> dict[str, Any]:
        path = Path(state_path).expanduser()
        return json.loads(path.read_text(encoding="utf-8"))

    def status(self, state: dict[str, Any]) -> dict[str, Any]:
        stages = list(state.get("stages") or [])
        last_stage = stages[-1] if stages else {}
        stage_launch = dict(last_stage.get("launch") or {})
        dou_value = _state_dou_value(state)
        if dou_value is None:
            # Primary no-await mode: the runner exits before the worker writes
            # its report, so the DoU index only exists in the live frontmatter.
            dou_value = report_dou_index(str(stage_launch.get("report") or ""))
        return {
            "schema": state.get("schema"),
            "run_id": state.get("run_id"),
            "workflow": state.get("workflow"),
            "status": state.get("status"),
            "current_stage": last_stage.get("id", ""),
            "next_stage": (state.get("baton") or {}).get("next_stage", ""),
            "next_agent": (state.get("baton") or {}).get("next_agent", ""),
            "exit_code": (last_stage.get("await") or {}).get("exit_code", ""),
            "dou_index": dou_value,
            "accepted_dou": len(state.get("accepted_dou_findings") or []),
            "state_path": state.get("state_path"),
            "report_path": state.get("report_path"),
            "stage_worker": _stage_worker_liveness(state, stage_launch),
        }


def run_lifecycle(spec: LifecycleRunSpec) -> dict[str, Any]:
    return asyncio.run(LifecycleSupervisor().start(spec))


def _print_lifecycle_receipt(state: dict[str, Any]) -> None:
    workflow = str(state.get("workflow") or "lifecycle")
    title = f"{workflow.upper()} LIFECYCLE RECEIPT"
    print(f"==================== {title} ====================")
    print(f"run_id:     {state.get('run_id')}")
    print(f"workflow:   {state.get('workflow')}")
    print(f"status:     {state.get('status')}")
    print(f"state:      {state.get('state_path')}")
    print(f"report:     {state.get('report_path')}")
    print("=" * (24 + len(title)))


def _control_verbs() -> frozenset[str]:
    from .lifecycle_control import CONTROL_VERBS

    return CONTROL_VERBS


def lifecycle_main(workflow_id: str, argv: Sequence[str] | None = None) -> int:
    manifest = workflow_manifest(workflow_id)
    if manifest is None:
        raise ValueError(f"Unsupported lifecycle workflow: {workflow_id}")
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] in _control_verbs():
        from .lifecycle_control import lifecycle_control_main

        return lifecycle_control_main(args_list, workflow_id=manifest.id)
    supports_loop_options = any(
        stage.workflow == "marbles" for stage in manifest.stages
    )

    parser = argparse.ArgumentParser(prog=workflow_id)
    parser.add_argument(
        "agent", nargs="?", default="codex", choices=sorted(SUPPORTED_AGENTS)
    )
    parser.add_argument("-p", "--prompt", default="")
    parser.add_argument("-f", "--file", default="")
    parser.add_argument("--runtime", default="headless")
    parser.add_argument("--root", default="")
    parser.add_argument("--start-stage", default="")
    parser.add_argument("--checkpoint", dest="start_stage", default="")
    parser.add_argument("--await-stages", action="store_true")
    if supports_loop_options:
        parser.add_argument("--count", type=int)
        parser.add_argument("--depth", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(args_list)

    state = run_lifecycle(
        LifecycleRunSpec(
            workflow_id=manifest.id,
            agent=args.agent,
            prompt=args.prompt,
            file=args.file,
            root=args.root or str(Path.cwd()),
            runtime=args.runtime or "headless",
            await_stages=args.await_stages,
            start_stage=args.start_stage,
            count=getattr(args, "count", None),
            depth=getattr(args, "depth", None),
        )
    )
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_lifecycle_receipt(state)
    return 0 if state.get("status") in {"launching", "completed"} else 1
