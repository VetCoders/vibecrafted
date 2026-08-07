"""RuntimeBridge: ACP session glue over vibecrafted_core's workflow/control-plane APIs."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from vibecrafted_core import control_plane, workflow
from vibecrafted_core.events import append_event
from vibecrafted_core.lifecycle_runner import (
    LIFECYCLE_SCHEMA_ID,
    LifecycleRunner,
    LifecycleRunSpec,
    write_lifecycle_report,
    write_lifecycle_state,
)
from vibecrafted_core.workflows.registry import (
    WORKFLOW_MANIFESTS,
    workflow_manifest_payload,
)

MAX_TRANSCRIPT_BYTES = 64 * 1024
MAX_RESUME_BYTES = 1024 * 1024
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _terminal(run: dict[str, Any] | None) -> bool:
    """Return True when ``run``'s operator_state/health/liveness/state marks it finished."""
    if not run:
        return False
    return (
        str(run.get("operator_state") or "")
        in {"completed", "blocked", "failed", "stopped"}
        or str(run.get("health") or "") == "final"
        or str(run.get("liveness") or "") == "terminal"
        or str(run.get("state") or "")
        in {
            "completed",
            "failed",
            "report_validated",
            "report_missing",
            "report_invalid",
            "contract_failed",
            "closed",
            "stopped",
            "timed_out",
            "ghost",
        }
    )


class RuntimeBridge:
    """Thin ACP glue over the existing workflow and control-plane APIs."""

    def __init__(self, *, dry_run: bool = False) -> None:
        """Set up the bridge; ``dry_run`` swaps real workflow launches for an in-memory fake."""
        self.dry_run = dry_run
        self._dry_runs: dict[str, dict[str, Any]] = {}
        self._dry_audit_events: list[dict[str, Any]] = []

    def reserve_run_id(self, skill: str) -> str:
        """Reserve a fresh control-plane run id for ``skill``."""
        return workflow.reserve_run_id(skill)

    @property
    def supports_resume(self) -> bool:
        """Always True: this bridge implements session/load and session/resume."""
        return True

    def launch(
        self,
        *,
        run_id: str,
        root: str,
        prompt: str,
        agent: str,
        skill: str,
        runtime: str,
    ) -> dict[str, Any]:
        """Launch a workflow run for ``run_id``, or record a scripted dry-run stub."""
        if self.dry_run:
            self._dry_runs[run_id] = {
                "run_id": run_id,
                "state": "running",
                "root": root,
                "prompt": prompt,
                "agent": agent,
                "skill": skill,
                "runtime": runtime,
                "index": 0,
                "cancelled": False,
                "chunks": [
                    f"dry-run worker accepted {skill} for {Path(root).name}\n".encode(),
                    b"dry-run worker completed\n",
                ],
            }
            return {
                "accepted": True,
                "run_id": run_id,
                "agent": agent,
                "skill": skill,
                "root": root,
                "status": "launching",
                "dry_run": True,
            }

        payload = {
            "run_id": run_id,
            "root": root,
            "prompt": prompt,
            "agent": agent,
            "skill": skill,
            "runtime": runtime,
            "mode": skill,
        }
        spec = workflow.normalize_launch_spec(payload, root)
        return workflow.launch_workflow(spec, root, env=dict(os.environ))

    def observe(self, run_id: str, *, offset: int = 0) -> dict[str, Any]:
        """Read transcript bytes for ``run_id`` starting at ``offset``, real or dry-run."""
        if self.dry_run:
            record = self._dry_runs.get(run_id)
            if record is None:
                return {
                    "run_id": run_id,
                    "found": False,
                    "text": b"",
                    "next_offset": offset,
                    "terminal": False,
                    "run": None,
                }
            chunks = record["chunks"]
            index = int(record["index"])
            text = b""
            if index < len(chunks) and not record["cancelled"]:
                text = chunks[index]
                record["index"] = index + 1
            terminal = bool(record["cancelled"] or record["index"] >= len(chunks))
            if terminal:
                record["state"] = "stopped" if record["cancelled"] else "completed"
            return {
                "run_id": run_id,
                "found": True,
                "text": text,
                "next_offset": offset + len(text),
                "terminal": terminal,
                "run": dict(record),
            }

        run = control_plane.lookup_run(run_id)
        transcript = None
        try:
            transcript = control_plane.resolve_run(run_id).transcript
        except control_plane.RunNotResolved:
            pass
        text = b""
        next_offset = max(int(offset), 0)
        if transcript is not None:
            try:
                size = transcript.stat().st_size
                start = min(next_offset, size)
                with transcript.open("rb") as handle:
                    handle.seek(start)
                    text = handle.read(MAX_TRANSCRIPT_BYTES)
                next_offset = start + len(text)
            except OSError:
                text = b""
        return {
            "run_id": run_id,
            "found": run is not None or transcript is not None,
            "text": text,
            "next_offset": next_offset,
            "terminal": _terminal(run),
            "run": run,
        }

    def await_run(
        self,
        run_id: str,
        *,
        on_poll: Callable[[dict[str, Any] | None], None] | None = None,
        timeout_seconds: float = 300,
        interval_seconds: float = 0.25,
    ) -> dict[str, Any]:
        """Block until ``run_id`` reaches a terminal state, polling ``on_poll`` along the way."""
        if self.dry_run:
            record = self._dry_runs.get(run_id)
            if record is None:
                return {
                    "run_id": run_id,
                    "found": False,
                    "completed": False,
                    "reason": "run_not_found",
                    "run": None,
                }
            while not record["cancelled"] and record["index"] < len(record["chunks"]):
                before = int(record["index"])
                if on_poll is not None:
                    on_poll(dict(record))
                if int(record["index"]) == before:
                    self.observe(run_id)
            if on_poll is not None:
                on_poll(dict(record))
            stopped = bool(record["cancelled"])
            record["state"] = "stopped" if stopped else "completed"
            return {
                "run_id": run_id,
                "found": True,
                "completed": True,
                "reason": "terminal",
                "worker_alive": False,
                "run": dict(record),
            }
        return control_plane.await_run(
            run_id,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
            on_poll=on_poll,
        )

    def run_lifecycle(
        self,
        *,
        parent_run_id: str,
        root: str,
        prompt: str,
        agent: str,
        runtime: str,
        dry_stages: int = 2,
        on_stage: Callable[[str, str, list[str], str], None] | None = None,
        on_chunk: Callable[[str, bytes], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Run vc-ship with the ACP session as parent and CP-visible children."""
        self._validate_run_id(parent_run_id)
        if self.dry_run:
            return self._run_dry_lifecycle(
                parent_run_id=parent_run_id,
                root=root,
                prompt=prompt,
                agent=agent,
                runtime=runtime,
                dry_stages=dry_stages,
                on_stage=on_stage,
                on_chunk=on_chunk,
                cancelled=cancelled,
            )

        child_run_ids: list[str] = []
        child_stages: dict[str, str] = {}
        offsets: dict[str, int] = {}

        def emit_stage(stage: str, status: str, active_child: str = "") -> None:
            if on_stage is not None:
                on_stage(stage, status, list(child_run_ids), active_child)

        def launch_child(
            spec: workflow.WorkflowLaunchSpec, source_dir: str | Path
        ) -> dict[str, Any]:
            if cancelled is not None and cancelled():
                raise RuntimeError("lifecycle cancelled before child launch")
            child_run_id = self.reserve_run_id(spec.skill)
            launch_spec = replace(spec, run_id=child_run_id)
            launch = workflow.launch_workflow(
                launch_spec,
                source_dir,
                env=dict(os.environ),
            )
            if not launch.get("accepted") or launch.get("run_id") != child_run_id:
                raise RuntimeError("core lifecycle child launch was not accepted")
            child_run_ids.append(child_run_id)
            child_stages[child_run_id] = spec.skill
            offsets[child_run_id] = 0
            emit_stage(spec.skill, "in_progress", child_run_id)
            return launch

        def pump_child(child_run_id: str) -> None:
            observed = self.observe(
                child_run_id,
                offset=offsets.get(child_run_id, 0),
            )
            offsets[child_run_id] = int(
                observed.get("next_offset") or offsets.get(child_run_id, 0)
            )
            data = bytes(observed.get("text") or b"")
            if data and on_chunk is not None:
                on_chunk(child_run_id, data)

        def await_child(payload: dict[str, Any]) -> dict[str, Any]:
            child_run_id = str(payload.get("run_id") or "")
            result = control_plane.await_run(
                child_run_id,
                timeout_seconds=float(os.environ.get("VIBECRAFTED_ACP_TIMEOUT", "300")),
                interval_seconds=0.25,
                on_poll=lambda _run: pump_child(child_run_id),
            )
            pump_child(child_run_id)
            if cancelled is not None and cancelled():
                raise RuntimeError("lifecycle cancelled while child was running")
            stage = child_stages.get(child_run_id, "")
            stage_status = (
                "completed"
                if result.get("completed") and result.get("artifact_ok")
                else "in_progress"
            )
            emit_stage(stage, stage_status)
            return result

        runner = LifecycleRunner(launcher=launch_child, awaiter=await_child)
        state = asyncio.run(
            runner.run(
                LifecycleRunSpec(
                    workflow_id="vc-ship",
                    agent=agent,
                    run_id=parent_run_id,
                    prompt=prompt,
                    root=root,
                    runtime=runtime,
                    await_stages=True,
                )
            )
        )
        state["child_run_ids"] = list(child_run_ids)
        write_lifecycle_state(Path(str(state["state_path"])), state)
        write_lifecycle_report(Path(str(state["report_path"])), state)
        return state

    def _run_dry_lifecycle(
        self,
        *,
        parent_run_id: str,
        root: str,
        prompt: str,
        agent: str,
        runtime: str,
        dry_stages: int,
        on_stage: Callable[[str, str, list[str], str], None] | None,
        on_chunk: Callable[[str, bytes], None] | None,
        cancelled: Callable[[], bool] | None,
    ) -> dict[str, Any]:
        """Run a deterministic vc-ship dry-run fixture: launch/observe each stage's dry worker."""
        manifest = WORKFLOW_MANIFESTS["vc-ship"]
        stage_limit = max(1, min(int(dry_stages), len(manifest.stages)))
        run_dir = control_plane.control_plane_home() / "lifecycle_runs" / parent_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        state_path = run_dir / "state.json"
        report_path = run_dir / "report.md"
        transcript_path = run_dir / "transcript.log"
        transcript_path.write_text("", encoding="utf-8")
        child_run_ids: list[str] = []
        state: dict[str, Any] = {
            "schema": LIFECYCLE_SCHEMA_ID,
            "run_id": parent_run_id,
            "workflow": manifest.id,
            "agent": agent,
            "root": root,
            "status": "running",
            "await_stages": True,
            "parent_run_id": "",
            "child_run_ids": child_run_ids,
            "state_path": str(state_path),
            "report_path": str(report_path),
            "transcript_path": str(transcript_path),
            "supervisor": "vibecrafted_acp.bridge.RuntimeBridge",
            "human_controls": list(manifest.human_controls),
            "context_atlas": {"ok": True, "dry_run": True},
            "manifest": workflow_manifest_payload(manifest.id),
            "spec": {
                "workflow_id": manifest.id,
                "agent": agent,
                "prompt": prompt,
                "root": root,
                "runtime": runtime,
                "dry_stages": stage_limit,
            },
            "stages": [],
            "baton": {
                "from_stage": "",
                "next_stage": manifest.first_stage.id,
                "next_agent": agent,
                "reason": "dry_fixture",
                "previous_reports": [],
                "dou_index": None,
            },
            "operator_actions": [],
            "accepted_dou_findings": [],
        }
        write_lifecycle_state(state_path, state)

        for stage in manifest.stages[:stage_limit]:
            if cancelled is not None and cancelled():
                state["status"] = "stopped"
                break
            child_run_id = self.reserve_run_id(stage.workflow)
            launch = self.launch(
                run_id=child_run_id,
                root=root,
                prompt=prompt,
                agent=agent,
                skill=stage.workflow,
                runtime=runtime,
            )
            child_run_ids.append(child_run_id)
            if on_stage is not None:
                on_stage(
                    stage.id,
                    "in_progress",
                    list(child_run_ids),
                    child_run_id,
                )
            chunks: list[bytes] = []
            offset = 0
            while True:
                observed = self.observe(child_run_id, offset=offset)
                offset = int(observed.get("next_offset") or offset)
                data = bytes(observed.get("text") or b"")
                if data:
                    chunks.append(data)
                    if on_chunk is not None:
                        on_chunk(child_run_id, data)
                if observed.get("terminal"):
                    break
            with transcript_path.open("ab") as handle:
                handle.write(
                    f"[stage={stage.id} child_run_id={child_run_id}]\n".encode()
                )
                for chunk in chunks:
                    handle.write(chunk)
            state["stages"].append(
                {
                    "id": stage.id,
                    "name": stage.name,
                    "workflow": stage.workflow,
                    "phase": stage.phase,
                    "agent": agent,
                    "status": "completed",
                    "launch": launch,
                    "await": {
                        "completed": True,
                        "artifact_ok": True,
                        "state": "completed",
                        "exit_code": 0,
                    },
                }
            )
            state["baton"] = {
                "from_stage": stage.id,
                "next_stage": stage.next_stage,
                "next_agent": agent,
                "reason": "dry_fixture_stage_completed",
                "previous_reports": [],
                "dou_index": None,
            }
            write_lifecycle_state(state_path, state)
            if on_stage is not None:
                on_stage(stage.id, "completed", list(child_run_ids), "")

        if state["status"] != "stopped":
            state["status"] = "completed"
        write_lifecycle_state(state_path, state)
        write_lifecycle_report(report_path, state)
        return state

    def load_session(self, run_id: str) -> dict[str, Any]:
        """Restore a session only when both report and transcript are present."""
        self._validate_run_id(run_id)
        lifecycle_dir = control_plane.control_plane_home() / "lifecycle_runs" / run_id
        if lifecycle_dir.is_dir():
            return self._load_lifecycle_session(run_id, lifecycle_dir)

        try:
            resolved = control_plane.resolve_run(run_id)
        except control_plane.RunNotResolved as exc:
            raise RuntimeError(f"session artifacts not found: {run_id}") from exc
        meta = self._read_json(resolved.meta)
        report = resolved.report
        transcript = resolved.transcript
        self._require_artifacts(report=report, transcript=transcript)
        raw_custom = meta.get("_meta")
        custom: dict[str, Any] = (
            dict(raw_custom) if isinstance(raw_custom, dict) else {}
        )
        raw_vibecrafted = custom.get("vibecrafted")
        vibecrafted: dict[str, Any] = (
            dict(raw_vibecrafted) if isinstance(raw_vibecrafted, dict) else {}
        )
        return {
            "session_id": run_id,
            "cwd": str(meta.get("root") or ""),
            "agent": str(meta.get("agent") or "codex"),
            "skill": str(meta.get("skill") or "implement"),
            "runtime": str(meta.get("runtime") or "headless"),
            "parent_run_id": str(vibecrafted.get("parent_run_id") or run_id),
            "child_run_ids": list(vibecrafted.get("child_run_ids") or []),
            "stage": str(vibecrafted.get("stage") or ""),
            "report": self._read_artifact(report),
            "transcript": self._read_artifact(transcript),
            "transcript_truncated": self._is_truncated(transcript),
        }

    def _load_lifecycle_session(self, run_id: str, run_dir: Path) -> dict[str, Any]:
        """Rebuild resume payload for a vc-ship lifecycle run from its state.json + artifacts."""
        state = self._read_json(run_dir / "state.json")
        if not state:
            raise RuntimeError("session resume unavailable: lifecycle state missing")
        report = Path(str(state.get("report_path") or run_dir / "report.md"))
        transcript = Path(
            str(state.get("transcript_path") or run_dir / "transcript.log")
        )
        self._require_artifacts(report=report, transcript=transcript)
        stages = [
            stage for stage in state.get("stages") or [] if isinstance(stage, dict)
        ]
        children = [
            str((stage.get("launch") or {}).get("run_id") or "") for stage in stages
        ]
        children = [child for child in children if child]
        raw_spec = state.get("spec")
        spec: dict[str, Any] = dict(raw_spec) if isinstance(raw_spec, dict) else {}
        return {
            "session_id": run_id,
            "cwd": str(state.get("root") or spec.get("root") or ""),
            "agent": str(state.get("agent") or spec.get("agent") or "codex"),
            "skill": str(state.get("workflow") or "vc-ship").removeprefix("vc-"),
            "runtime": str(spec.get("runtime") or "headless"),
            "parent_run_id": run_id,
            "child_run_ids": children,
            "stage": str(stages[-1].get("id") or "") if stages else "",
            "plan_stages": [
                {
                    "id": str(stage.get("id") or ""),
                    "status": str(stage.get("status") or ""),
                }
                for stage in stages
            ],
            "report": self._read_artifact(report),
            "transcript": self._read_artifact(transcript),
            "transcript_truncated": self._is_truncated(transcript),
        }

    @staticmethod
    def _read_json(path: Path | None) -> dict[str, Any]:
        """Best-effort JSON object read; returns ``{}`` on missing/unreadable/non-dict input."""
        if path is None:
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _require_artifacts(*, report: Path | None, transcript: Path | None) -> None:
        """Raise RuntimeError unless both report and transcript are non-empty files."""
        missing: list[str] = []
        if report is None or not report.is_file() or report.stat().st_size == 0:
            missing.append("report")
        if (
            transcript is None
            or not transcript.is_file()
            or transcript.stat().st_size == 0
        ):
            missing.append("transcript")
        if missing:
            raise RuntimeError(
                "session resume unavailable; missing non-empty artifacts: "
                + ", ".join(missing)
            )

    @staticmethod
    def _read_artifact(path: Path | None) -> str:
        """Read up to MAX_RESUME_BYTES of ``path`` as UTF-8 text; "" when path is None."""
        if path is None:
            return ""
        with path.open("rb") as handle:
            return handle.read(MAX_RESUME_BYTES).decode("utf-8", errors="replace")

    @staticmethod
    def _is_truncated(path: Path | None) -> bool:
        """Return True when ``path`` exceeds MAX_RESUME_BYTES (resume read was partial)."""
        return bool(path is not None and path.stat().st_size > MAX_RESUME_BYTES)

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        """Raise ValueError unless ``run_id`` matches the safe run-id shape."""
        if not _SAFE_RUN_ID.fullmatch(str(run_id or "")):
            raise ValueError("invalid sessionId")

    def record_hard_stop_override(
        self, run_id: str, *, category: str, evidence: str
    ) -> dict[str, Any]:
        """Record an audit event for an operator's allow-once hard-stop approval."""
        payload = {
            "category": category,
            "evidence": evidence,
            "approval": "allow_once",
            "source": "acp",
        }
        if self.dry_run:
            event = {
                "kind": "hard_stop_override",
                "run_id": run_id,
                "message": "ACP hard-stop allowed once",
                "payload": payload,
            }
            self._dry_audit_events.append(event)
            return event
        return append_event(
            kind="hard_stop_override",
            run_id=run_id,
            message="ACP hard-stop allowed once",
            payload=payload,
        )

    def stop(
        self, run_id: str, *, reason: str = "ACP session cancelled"
    ) -> dict[str, Any]:
        """Cancel ``run_id``, real or dry-run, marking it stopped."""
        if self.dry_run:
            record = self._dry_runs.get(run_id)
            if record is None:
                return {"accepted": False, "run_id": run_id, "reason": "run_not_found"}
            record["cancelled"] = True
            record["state"] = "stopped"
            return {"accepted": True, "run_id": run_id, "reason": reason}
        return workflow.stop_run(run_id, reason=reason)
