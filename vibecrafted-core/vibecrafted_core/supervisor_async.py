from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from .artifacts import ArtifactValidation, validate_artifacts
from .events import append_event
from .lifecycle import EventKind, RunState


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AsyncRunHandle:
    run_id: str
    command: tuple[str, ...]
    root: Path
    process: asyncio.subprocess.Process
    started_at: datetime
    meta_path: Path | None = None
    report_path: Path | None = None
    transcript_path: Path | None = None
    pgid: int | None = None
    states: list[RunState] = field(default_factory=lambda: [RunState.CREATED])
    exit_code: int | None = None
    completed_at: datetime | None = None
    artifact_validation: ArtifactValidation | None = None
    first_output_seen: bool = False

    @property
    def state(self) -> RunState:
        return self.states[-1]


class AsyncSupervisor:
    def __init__(self) -> None:
        self._runs: dict[str, AsyncRunHandle] = {}

    def get(self, run_id: str) -> AsyncRunHandle | None:
        return self._runs.get(run_id)

    async def spawn(
        self,
        *,
        run_id: str,
        command: Sequence[str],
        root: str | Path = ".",
        env: Mapping[str, str] | None = None,
        meta_path: str | Path | None = None,
        report_path: str | Path | None = None,
        transcript_path: str | Path | None = None,
    ) -> AsyncRunHandle:
        if not command:
            raise ValueError("command must not be empty")
        cwd = Path(root).resolve()
        transcript = Path(transcript_path) if transcript_path is not None else None
        if transcript is not None:
            transcript.parent.mkdir(parents=True, exist_ok=True)

        started_at = _utc_now()

        await self._emit(
            run_id,
            RunState.CREATED,
            "async supervisor run created",
            payload={
                "root": str(cwd),
                "command": list(command),
                "meta": str(meta_path or ""),
                "report": str(report_path or ""),
                "transcript": str(transcript_path or ""),
                "started_at": started_at.isoformat(),
            },
        )
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            env=merged_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        handle = AsyncRunHandle(
            run_id=run_id,
            command=tuple(command),
            root=cwd,
            process=process,
            started_at=started_at,
            meta_path=Path(meta_path) if meta_path is not None else None,
            report_path=Path(report_path) if report_path is not None else None,
            transcript_path=transcript,
        )
        try:
            handle.pgid = os.getpgid(process.pid)
        except ProcessLookupError:
            handle.pgid = None
        self._runs[run_id] = handle
        await self._transition(
            handle,
            RunState.PROCESS_SPAWNED,
            "process spawned",
            payload={
                "worker_pid": handle.process.pid,
                "worker_pgid": handle.pgid,
                "meta": str(handle.meta_path or ""),
                "report": str(handle.report_path or ""),
                "transcript": str(handle.transcript_path or ""),
            },
        )
        return handle

    async def run(
        self,
        *,
        run_id: str,
        command: Sequence[str],
        root: str | Path = ".",
        env: Mapping[str, str] | None = None,
        meta_path: str | Path | None = None,
        report_path: str | Path | None = None,
        transcript_path: str | Path | None = None,
        timeout: float | None = None,
        require_report: bool = True,
        require_transcript_output: bool = False,
    ) -> AsyncRunHandle:
        handle = await self.spawn(
            run_id=run_id,
            command=command,
            root=root,
            env=env,
            meta_path=meta_path,
            report_path=report_path,
            transcript_path=transcript_path,
        )
        try:
            if timeout is None:
                await self._watch_process(handle)
            else:
                await asyncio.wait_for(self._watch_process(handle), timeout=timeout)
        except asyncio.TimeoutError:
            await self._terminate(handle)
            handle.exit_code = handle.process.returncode
            handle.completed_at = _utc_now()
            await self._transition(
                handle,
                RunState.STALLED,
                "process timed out",
                payload={
                    "exit_code": handle.exit_code,
                    "completed_at": handle.completed_at.isoformat(),
                    "liveness": "terminal",
                },
            )
            return handle

        handle.exit_code = handle.process.returncode
        handle.completed_at = _utc_now()
        if handle.exit_code == 0:
            await self._transition(
                handle,
                RunState.COMPLETED,
                "process completed",
                payload={
                    "exit_code": handle.exit_code,
                    "completed_at": handle.completed_at.isoformat(),
                    "liveness": "terminal",
                },
            )
        else:
            await self._transition(
                handle,
                RunState.FAILED,
                f"process failed with exit code {handle.exit_code}",
                payload={
                    "exit_code": handle.exit_code,
                    "completed_at": handle.completed_at.isoformat(),
                    "liveness": "terminal",
                },
            )

        handle.artifact_validation = validate_artifacts(
            meta_path=handle.meta_path,
            report_path=handle.report_path,
            transcript_path=handle.transcript_path,
            require_report=require_report,
            require_transcript_output=require_transcript_output,
        )
        await self._emit(
            handle.run_id,
            RunState.ARTIFACT_SEEN,
            "artifacts inspected",
            payload={
                "event_kind": EventKind.ARTIFACT.value,
                "meta": str(handle.meta_path or ""),
                "report": str(handle.report_path or ""),
                "transcript": str(handle.transcript_path or ""),
                **handle.artifact_validation.as_payload(),
            },
        )
        if handle.artifact_validation.ok:
            await self._transition(
                handle, RunState.REPORT_VALIDATED, "artifact contract validated"
            )
        else:
            failed_state = (
                RunState.REPORT_MISSING
                if "report_missing" in handle.artifact_validation.errors
                else RunState.REPORT_INVALID
            )
            await self._transition(
                handle,
                failed_state,
                "artifact contract failed",
                payload={
                    **handle.artifact_validation.as_payload(),
                    "liveness": "terminal",
                },
            )
        return handle

    async def _watch_process(self, handle: AsyncRunHandle) -> None:
        assert handle.process.stdout is not None
        while True:
            chunk = await handle.process.stdout.readline()
            if not chunk:
                break
            if handle.transcript_path is not None:
                with handle.transcript_path.open("ab") as transcript:
                    transcript.write(chunk)
            if not handle.first_output_seen:
                handle.first_output_seen = True
                await self._transition(
                    handle,
                    RunState.FIRST_OUTPUT_SEEN,
                    "first output observed",
                    payload={
                        "heartbeat_at": _utc_now().isoformat(),
                    },
                )
                await self._transition(
                    handle,
                    RunState.ACTIVE,
                    "process active",
                    payload={
                        "liveness": "pid_alive",
                        "heartbeat_at": _utc_now().isoformat(),
                    },
                )
        await handle.process.wait()

    async def _terminate(self, handle: AsyncRunHandle) -> None:
        if handle.process.returncode is not None:
            return
        try:
            if handle.pgid is not None:
                os.killpg(handle.pgid, signal.SIGTERM)
            else:
                handle.process.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(handle.process.wait(), timeout=3)
        except asyncio.TimeoutError:
            try:
                if handle.pgid is not None:
                    os.killpg(handle.pgid, signal.SIGKILL)
                else:
                    handle.process.kill()
            except ProcessLookupError:
                pass
            await handle.process.wait()

    async def _transition(
        self,
        handle: AsyncRunHandle,
        state: RunState,
        message: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> None:
        handle.states.append(state)
        await self._emit(handle.run_id, state, message, payload=payload)

    async def _emit(
        self,
        run_id: str,
        state: RunState,
        message: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> None:
        event_payload: dict[str, object] = {
            "event_kind": EventKind.LIFECYCLE.value,
            "state": state.value,
        }
        if payload:
            event_payload.update(payload)
        await asyncio.to_thread(
            append_event,
            kind=f"{EventKind.LIFECYCLE.value}:{state.value}",
            run_id=run_id,
            message=message,
            payload=event_payload,
        )
