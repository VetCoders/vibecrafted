from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vibecrafted_core import control_plane, workflow
from vibecrafted_core.events import append_event

MAX_TRANSCRIPT_BYTES = 64 * 1024


def _terminal(run: dict[str, Any] | None) -> bool:
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
        self.dry_run = dry_run
        self._dry_runs: dict[str, dict[str, Any]] = {}
        self._dry_audit_events: list[dict[str, Any]] = []

    def reserve_run_id(self, skill: str) -> str:
        return workflow.reserve_run_id(skill)

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
        if self.dry_run:
            self._dry_runs[run_id] = {
                "run_id": run_id,
                "state": "running",
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
                if on_poll is not None:
                    on_poll(dict(record))
                else:
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

    def record_hard_stop_override(
        self, run_id: str, *, category: str, evidence: str
    ) -> dict[str, Any]:
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
        if self.dry_run:
            record = self._dry_runs.get(run_id)
            if record is None:
                return {"accepted": False, "run_id": run_id, "reason": "run_not_found"}
            record["cancelled"] = True
            record["state"] = "stopped"
            return {"accepted": True, "run_id": run_id, "reason": reason}
        return workflow.stop_run(run_id, reason=reason)
