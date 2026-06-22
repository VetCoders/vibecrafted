from __future__ import annotations

import asyncio
import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .control_plane import control_plane_home, normalize_run_root
from .workflow import (
    SUPPORTED_AGENTS,
    WorkflowLaunchSpec,
    await_launch_truth,
    launch_workflow,
)
from .workflows.registry import workflow_manifest, workflow_manifest_payload
from .workflows.model import WorkflowManifest, WorkflowStage

LaunchWorkflow = Callable[[WorkflowLaunchSpec, str | Path], dict[str, Any]]
AwaitWorkflow = Callable[[dict[str, Any]], dict[str, Any]]


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
                timeout_seconds=300,
                interval_seconds=5,
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
        state: dict[str, Any] = {
            "run_id": run_id,
            "workflow": manifest.id,
            "agent": spec.agent,
            "root": str(root),
            "status": "launching",
            "await_stages": spec.await_stages,
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
                "reason": "initial",
                "previous_reports": [],
            },
            "stages": [],
        }
        self._write_state(state_path, state)

        previous_reports: list[str] = []
        current = current_stage
        while current:
            stage = manifest.stage(current)
            if stage is None:
                state["status"] = "failed"
                state["error"] = f"unknown lifecycle stage: {current}"
                break
            record = await self._start_stage(
                manifest=manifest,
                stage=stage,
                spec=spec,
                source_prompt=source_prompt,
                root=root,
                previous_reports=previous_reports,
                context=context,
            )
            state["stages"].append(record)
            self._write_state(state_path, state)
            with transcript_path.open(
                "a", encoding="utf-8", errors="replace"
            ) as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not spec.await_stages:
                state["status"] = "launching"
                state["next_stage"] = stage.next_stage
                state["baton"] = self._baton(
                    stage=stage,
                    next_stage=stage.next_stage,
                    previous_reports=previous_reports,
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
            record["transition"] = {
                "next_stage": next_stage,
                "requested_next_stage": str(await_result.get("next_stage") or ""),
                "conditions": list(stage.transition_conditions),
                "fallback_stage": stage.fallback_stage,
                "audit_after": stage.audit_after,
            }
            state["baton"] = self._baton(
                stage=stage,
                next_stage=next_stage,
                previous_reports=previous_reports,
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
        source_prompt: str,
        root: Path,
        previous_reports: list[str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = self._stage_prompt(
            manifest=manifest,
            stage=stage,
            source_prompt=source_prompt,
            previous_reports=previous_reports,
            context=context,
        )
        launch_spec = WorkflowLaunchSpec(
            agent=spec.agent,
            mode=stage.workflow,
            skill=stage.workflow,
            prompt=prompt,
            file="",
            runtime=spec.runtime,
            root=str(root),
            count=spec.count if stage.workflow == "marbles" else None,
            depth=spec.depth if stage.workflow == "marbles" else None,
        )
        commit_before = _git_head(root)
        git_before = _git_status(root)
        git_snapshot_before = _git_worktree_snapshot(root, git_before)
        launch = await asyncio.to_thread(self.launcher, launch_spec, root)
        return {
            "id": stage.id,
            "name": stage.name,
            "workflow": stage.workflow,
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

    def _baton(
        self,
        *,
        stage: WorkflowStage,
        next_stage: str,
        previous_reports: list[str],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "from_stage": stage.id,
            "from_phase": stage.phase,
            "next_stage": next_stage,
            "fallback_stage": stage.fallback_stage,
            "audit_after": stage.audit_after,
            "reason": reason,
            "previous_reports": list(previous_reports),
        }

    def _write_state(self, path: Path, state: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_report(self, path: Path, state: dict[str, Any]) -> None:
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
            "",
            "## Stages",
        ]
        for stage in stages:
            lines.extend(
                [
                    "",
                    f"- {stage.get('id')} ({stage.get('phase')}): {stage.get('status')}",
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
                f"- reason: {baton.get('reason', '')}",
            ]
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
        return {
            "run_id": state.get("run_id"),
            "workflow": state.get("workflow"),
            "status": state.get("status"),
            "current_stage": last_stage.get("id", ""),
            "next_stage": (state.get("baton") or {}).get("next_stage", ""),
            "exit_code": (last_stage.get("await") or {}).get("exit_code", ""),
            "state_path": state.get("state_path"),
            "report_path": state.get("report_path"),
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


def lifecycle_main(workflow_id: str, argv: Sequence[str] | None = None) -> int:
    manifest = workflow_manifest(workflow_id)
    if manifest is None:
        raise ValueError(f"Unsupported lifecycle workflow: {workflow_id}")
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
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

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
