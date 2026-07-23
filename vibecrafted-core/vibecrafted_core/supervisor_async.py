from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from .agent_stream import (
    AgentStreamParser,
    is_grok_ignorable_transport_error,
    resolve_default_model,
)
from .artifacts import ArtifactValidation, validate_artifacts
from .control_plane import ensure_session_id, normalize_run_root
from .events import append_event
from .lifecycle import EventKind, RunState
from .model_overrides import _model_override_receipt
from .report_contract import CLAIM_DIGEST_ENV

STDIO_LIMIT_BYTES = 16 * 1024 * 1024


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _infer_agent(command: Sequence[str]) -> str:
    if not command:
        return "agent"
    name = Path(str(command[0])).name
    if name in {"claude", "codex", "agy", "junie", "grok"}:
        return name
    if name in {"python", "python3"}:
        return "python"
    return name or "agent"


def _json_text_fragment(event: dict[str, object]) -> str:
    event_type = str(event.get("type") or "")
    if event_type == "thought":
        return ""
    if event_type == "text":
        value = event.get("data")
        return value if isinstance(value, str) else ""
    for key in ("message", "text", "content", "data"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    return ""


def _fallback_report_body(transcript_text: str) -> str:
    text_fragments: list[str] = []
    plain_lines: list[str] = []
    for line in transcript_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("{"):
            try:
                loaded = json.loads(stripped)
            except json.JSONDecodeError:
                if not is_grok_ignorable_transport_error(line):
                    plain_lines.append(line)
                continue
            if isinstance(loaded, dict):
                text_fragments.append(_json_text_fragment(loaded))
            continue
        if is_grok_ignorable_transport_error(line):
            continue
        plain_lines.append(line)
    body = "".join(text_fragments).strip()
    if body:
        return body + "\n"
    return "\n".join(plain_lines).strip() + ("\n" if plain_lines else "")


def _tokens_total(
    input_tokens: int, cached_input_tokens: int, output_tokens: int
) -> int:
    """Sum usage without double-counting provider-specific cache shapes.

    Claude/Codex: ``input`` already includes cache hits (cached ≤ input).
    Junie-style: ``input`` is non-cached only and ``cached`` is additive
    (cached can exceed input). Detect by comparing magnitudes.
    """
    inp = max(0, int(input_tokens or 0))
    cached = max(0, int(cached_input_tokens or 0))
    out = max(0, int(output_tokens or 0))
    if cached and cached > inp:
        return inp + cached + out
    return inp + out


def _handle_tokens_total(handle: AsyncRunHandle) -> int:
    return _tokens_total(
        handle.tokens_input, handle.tokens_cached_input, handle.tokens_output
    )


def _origin_fields_from_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Durable origin identity for post-run triage (dispatcher has no pane env)."""
    source = env if env is not None else os.environ

    def _get(*names: str) -> str:
        for name in names:
            value = str(source.get(name, "") or "").strip()
            if value:
                return value
        return ""

    fields: dict[str, str] = {}
    session = _get(
        "VIBECRAFTED_WORKER_SESSION",
        "VIBECRAFTED_OPERATOR_SESSION",
        "VC_FRAME_SESSION_NAME",
        "ZELLIJ_SESSION_NAME",
    )
    if session:
        fields["origin_session"] = session
        fields["operator_session"] = session
    tab = _get("VC_FRAME_TAB_NAME", "VIBECRAFTED_RUN_ID", "SPAWN_RUN_ID")
    if tab:
        fields["origin_tab"] = tab
    pane = _get("VC_FRAME_PANE_ID", "ZELLIJ_PANE_ID")
    if pane:
        fields["origin_pane_id"] = pane
    return fields


def _cache_write_line(prefix: str, value: int | None) -> str:
    return f"{prefix}tokens_cache_write: {value}\n" if value is not None else ""


def _render_fallback_report(handle: AsyncRunHandle, transcript_text: str) -> str:
    body = _fallback_report_body(transcript_text)
    if not body:
        body = (
            "Worker exited successfully without writing a standalone report and "
            "without captured transcript text.\n"
        )
    now = (
        handle.completed_at.isoformat()
        if handle.completed_at
        else _utc_now().isoformat()
    )
    from .report_contract import render_minimal_frontmatter

    skill = handle.skill or str(
        os.environ.get("VIBECRAFTED_SKILL_NAME")
        or os.environ.get("VIBECRAFTED_SKILL_CODE")
        or "unknown"
    )
    header = render_minimal_frontmatter(
        run_id=handle.run_id,
        agent=handle.agent or "unknown",
        skill=skill,
        status="completed",
        extra={
            "claim_status": "completed",
            "claim_kind": skill,
            "session_id": handle.agent_session_id or "unknown",
            "tokens_input": handle.tokens_input,
            "tokens_cached_input": handle.tokens_cached_input,
            "tokens_output": handle.tokens_output,
            "tokens_total": _handle_tokens_total(handle),
            "cost_usd": handle.cost_usd if handle.cost_usd is not None else "unknown",
            "completed_at": now,
            "fallback_report": "true",
            **(
                {"tokens_cache_write": handle.tokens_cache_write}
                if handle.tokens_cache_write is not None
                else {}
            ),
        },
    )
    return (
        header
        + f"{body}\n"
        + "## Runtime fallback\n\n"
        + "The worker exited with code 0 but did not write "
        + "`VIBECRAFTED_REPORT_PATH`; Vibecrafted salvaged this report from the "
        + "captured transcript.\n"
    )


def _terminal_frontmatter(handle: AsyncRunHandle) -> str:
    model_requested = (
        f"model_requested: {handle.model_requested}\n" if handle.model_requested else ""
    )
    return (
        "---\n"
        "runner: vibecrafted\n"
        f"run_id: {handle.run_id}\n"
        f"agent: {handle.agent}\n"
        f"{model_requested}"
        f"root: {handle.root}\n"
        f"report: {handle.report_path or ''}\n"
        f"transcript: {handle.transcript_path or ''}\n"
        "status: launching\n"
        "---\n"
    )


def _terminal_footer(handle: AsyncRunHandle) -> str:
    model_requested = (
        f"model_requested: {handle.model_requested}\n" if handle.model_requested else ""
    )
    override_skipped = (
        f"model_override_skipped: {str(handle.model_override_skipped).lower()}\n"
        if handle.model_requested
        else ""
    )
    cost_source = f"cost_source: {handle.cost_source}\n" if handle.cost_source else ""
    return (
        "\n---\n"
        "runner: vibecrafted\n"
        f"run_id: {handle.run_id}\n"
        f"status: {handle.state.value}\n"
        f"exit_code: {handle.exit_code if handle.exit_code is not None else 'unknown'}\n"
        f"session_id: {handle.agent_session_id or 'unknown'}\n"
        f"model: {handle.agent_model or 'unknown'}\n"
        f"{model_requested}"
        f"{override_skipped}"
        f"tokens_input: {handle.tokens_input}\n"
        f"tokens_cached_input: {handle.tokens_cached_input}\n"
        f"{_cache_write_line('', handle.tokens_cache_write)}"
        f"tokens_output: {handle.tokens_output}\n"
        f"tokens_total: {_handle_tokens_total(handle)}\n"
        f"cost_usd: {handle.cost_usd if handle.cost_usd is not None else 'unknown'}\n"
        f"{cost_source}"
        f"resume: {handle.resume_command}\n"
        f"report: {handle.report_path or ''}\n"
        f"transcript: {handle.transcript_path or ''}\n"
        "---\n"
    )


def _write_terminal(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


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
    session_id: str = ""
    agent: str = ""
    skill: str = ""
    agent_session_id: str = ""
    agent_model: str = ""
    claim_digest: str = ""
    model_requested: str = ""
    model_override_supported: bool = False
    model_override_skipped: bool = False
    model_override_skip_reason: str = ""
    tokens_input: int = 0
    tokens_cached_input: int = 0
    tokens_cache_write: int | None = None
    tokens_output: int = 0
    cost_usd: float | None = None
    cost_source: str | None = None
    resume_command: str = ""

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
        prompt_file_path: str | Path | None = None,
    ) -> AsyncRunHandle:
        if not command:
            raise ValueError("command must not be empty")
        cwd = Path(normalize_run_root(root))
        transcript = Path(transcript_path) if transcript_path is not None else None
        if transcript is not None:
            transcript.parent.mkdir(parents=True, exist_ok=True)
        prompt_file = Path(prompt_file_path).expanduser() if prompt_file_path else None

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        session_id = ensure_session_id(merged_env.get("VIBECRAFTED_SESSION_ID"))
        merged_env["VIBECRAFTED_SESSION_ID"] = session_id
        if meta_path is not None:
            merged_env["VIBECRAFTED_META_PATH"] = str(meta_path)
        if report_path is not None:
            merged_env["VIBECRAFTED_REPORT_PATH"] = str(report_path)
        if transcript_path is not None:
            merged_env["VIBECRAFTED_TRANSCRIPT_PATH"] = str(transcript_path)
        if prompt_file is not None:
            merged_env["VIBECRAFTED_PROMPT_PATH"] = str(prompt_file)
        agent = str(merged_env.get("VIBECRAFTED_AGENT") or _infer_agent(command))
        skill = str(
            merged_env.get("VIBECRAFTED_SKILL_NAME")
            or merged_env.get("VIBECRAFTED_SKILL_CODE")
            or merged_env.get("VIBECRAFTED_SKILL")
            or "unknown"
        )
        claim_digest = str(merged_env.get(CLAIM_DIGEST_ENV) or "").strip()
        agent_model = resolve_default_model(agent, command=command, env=merged_env)
        model_receipt = _model_override_receipt(
            agent, str(merged_env.get("VIBECRAFTED_MODEL_REQUESTED") or "")
        )
        started_at = _utc_now()
        if report_path is not None:
            from .report_contract import materialize_launcher_report_template

            materialize_launcher_report_template(
                report_path,
                run_id=run_id,
                agent=agent,
                skill=skill,
                claim_digest=claim_digest,
            )

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
                "prompt_file": str(prompt_file or ""),
                "started_at": started_at.isoformat(),
                "session_id": session_id,
                "identity_required": True,
                "agent": agent,
                "skill": skill,
                "agent_model": agent_model,
                **({"claim_digest": claim_digest} if claim_digest else {}),
                **model_receipt,
            },
        )

        stdin_handle = None
        try:
            if prompt_file is not None:
                stdin_handle = prompt_file.open("rb")
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd),
                env=merged_env,
                stdin=stdin_handle,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
                limit=STDIO_LIMIT_BYTES,
            )
        finally:
            if stdin_handle is not None:
                stdin_handle.close()
        handle = AsyncRunHandle(
            run_id=run_id,
            command=tuple(command),
            root=cwd,
            process=process,
            started_at=started_at,
            meta_path=Path(meta_path) if meta_path is not None else None,
            report_path=Path(report_path) if report_path is not None else None,
            transcript_path=transcript,
            session_id=session_id,
            agent=agent,
            skill=skill,
            agent_model=agent_model,
            claim_digest=claim_digest,
            model_requested=str(model_receipt.get("model_requested") or ""),
            model_override_supported=bool(
                model_receipt.get("model_override_supported")
            ),
            model_override_skipped=bool(model_receipt.get("model_override_skipped")),
            model_override_skip_reason=str(
                model_receipt.get("model_override_skip_reason") or ""
            ),
        )
        try:
            handle.pgid = os.getpgid(process.pid)
        except ProcessLookupError:
            handle.pgid = None
        self._runs[run_id] = handle
        # Seed durable origin identity as soon as the worker exists so triage
        # still works when the finisher has no ambient VC_FRAME pane env.
        if handle.meta_path is not None:
            try:
                seed: dict[str, object] = {}
                if handle.meta_path.exists():
                    loaded = json.loads(handle.meta_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        seed.update(loaded)
                origin = _origin_fields_from_env(merged_env)
                if (
                    origin.get("origin_session")
                    and not str(seed.get("origin_session") or "").strip()
                ):
                    seed["origin_session"] = origin["origin_session"]
                    seed["operator_session"] = origin.get(
                        "operator_session", origin["origin_session"]
                    )
                if not str(seed.get("origin_tab") or "").strip():
                    seed["origin_tab"] = origin.get("origin_tab") or run_id
                if (
                    origin.get("origin_pane_id")
                    and not str(seed.get("origin_pane_id") or "").strip()
                ):
                    seed["origin_pane_id"] = origin["origin_pane_id"]
                seed.setdefault("run_id", run_id)
                seed.setdefault("root", str(cwd))
                seed.setdefault("agent", agent)
                seed.setdefault("skill", skill)
                if claim_digest:
                    seed["claim_digest"] = claim_digest
                handle.meta_path.parent.mkdir(parents=True, exist_ok=True)
                handle.meta_path.write_text(
                    json.dumps(seed, indent=2, ensure_ascii=False, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
            except (OSError, json.JSONDecodeError, TypeError):
                pass
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
        prompt_file_path: str | Path | None = None,
        timeout: float | None = None,
        require_report: bool = True,
        require_transcript_output: bool = False,
        tee_output: bool = False,
    ) -> AsyncRunHandle:
        handle = await self.spawn(
            run_id=run_id,
            command=command,
            root=root,
            env=env,
            meta_path=meta_path,
            report_path=report_path,
            transcript_path=transcript_path,
            prompt_file_path=prompt_file_path,
        )
        if tee_output:
            _write_terminal(_terminal_frontmatter(handle))
        try:
            if timeout is None:
                await self._watch_process(handle, tee_output=tee_output)
            else:
                await asyncio.wait_for(
                    self._watch_process(handle, tee_output=tee_output),
                    timeout=timeout,
                )
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
        self._write_report_fallback(handle)
        self._write_meta_summary(handle)
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
        artifact_payload = {
            "event_kind": EventKind.ARTIFACT.value,
            "meta": str(handle.meta_path or ""),
            "report": str(handle.report_path or ""),
            "transcript": str(handle.transcript_path or ""),
            "agent": handle.agent,
            "agent_session_id": handle.agent_session_id,
            "agent_model": handle.agent_model,
            "tokens_input": handle.tokens_input,
            "tokens_cached_input": handle.tokens_cached_input,
            "tokens_output": handle.tokens_output,
            "tokens_total": _handle_tokens_total(handle),
            "cost_usd": handle.cost_usd,
            "resume_command": handle.resume_command,
            **handle.artifact_validation.as_payload(),
        }
        if handle.tokens_cache_write is not None:
            artifact_payload["tokens_cache_write"] = handle.tokens_cache_write
        await self._emit(
            handle.run_id,
            RunState.ARTIFACT_SEEN,
            "artifacts inspected",
            payload=artifact_payload,
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
        if tee_output:
            _write_terminal(_terminal_footer(handle))
        return handle

    async def _watch_process(
        self, handle: AsyncRunHandle, *, tee_output: bool = False
    ) -> None:
        assert handle.process.stdout is not None
        parser = AgentStreamParser(handle.agent, default_model=handle.agent_model)
        while True:
            chunk = await handle.process.stdout.readline()
            if not chunk:
                break
            if handle.transcript_path is not None:
                with handle.transcript_path.open("ab") as transcript:
                    transcript.write(chunk)
            display_text = parser.feed_line(chunk)
            previous_agent_session_id = handle.agent_session_id
            self._sync_stream_summary(handle, parser)
            if (
                handle.report_path is not None
                and handle.agent_session_id
                and handle.agent_session_id != previous_agent_session_id
            ):
                from .report_contract import stamp_launcher_report_identity

                stamp_launcher_report_identity(
                    handle.report_path,
                    run_id=handle.run_id,
                    session_id=handle.agent_session_id,
                    agent=handle.agent,
                    skill=handle.skill,
                    status="pending",
                    model=handle.agent_model,
                    claim_digest=handle.claim_digest,
                )
            if tee_output:
                if display_text:
                    sys.stdout.buffer.write(display_text.encode("utf-8"))
                    sys.stdout.buffer.flush()
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
        self._sync_stream_summary(handle, parser)

    def _write_report_fallback(self, handle: AsyncRunHandle) -> None:
        report = handle.report_path
        if report is None:
            return
        if not report.exists():
            if handle.exit_code != 0 or handle.agent != "grok":
                return
            transcript_text = ""
            if handle.transcript_path is not None and handle.transcript_path.exists():
                try:
                    transcript_text = handle.transcript_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    transcript_text = ""
            rendered = _render_fallback_report(handle, transcript_text)
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(rendered, encoding="utf-8")
            return

        # Reports are worker-authored evidence, but the runtime owns their
        # transport contract. Normalize an existing substantive report before
        # strict validation so a good handoff cannot become report_invalid only
        # because the worker omitted the dashboard frontmatter. Preserve the
        # body and any explicit claim (blocked/partial/failed) verbatim.
        try:
            if report.stat().st_size == 0:
                return
            text = report.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        from .report_contract import parse_report_text, stamp_launcher_report_identity

        fields, _, has_frontmatter = parse_report_text(text)
        if (
            handle.exit_code == 0
            and handle.agent == "grok"
            and has_frontmatter
            and fields.get("launcher_template", "").strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            transcript_text = ""
            if handle.transcript_path is not None and handle.transcript_path.exists():
                try:
                    transcript_text = handle.transcript_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    transcript_text = ""
            report.write_text(
                _render_fallback_report(handle, transcript_text),
                encoding="utf-8",
            )

        status = "completed" if handle.exit_code == 0 else "failed"
        stamp_launcher_report_identity(
            report,
            run_id=handle.run_id,
            session_id=handle.agent_session_id,
            agent=handle.agent or "unknown",
            skill=handle.skill or "unknown",
            status=status,
            model=handle.agent_model,
            claim_digest=handle.claim_digest,
        )

    def _sync_stream_summary(
        self, handle: AsyncRunHandle, parser: AgentStreamParser
    ) -> None:
        handle.agent_session_id = parser.session_id
        handle.agent_model = parser.model_id
        handle.tokens_input = parser.tokens_input
        handle.tokens_cached_input = parser.tokens_cached_input
        handle.tokens_cache_write = parser.tokens_cache_write
        handle.tokens_output = parser.tokens_output
        handle.cost_usd = parser.cost_usd
        handle.cost_source = parser.cost_source
        handle.resume_command = parser.resume_command(handle.root)

    def _write_meta_summary(self, handle: AsyncRunHandle) -> None:
        if handle.meta_path is None:
            return
        payload: dict[str, object] = {}
        if handle.meta_path.exists():
            try:
                loaded = json.loads(handle.meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                payload.update(loaded)
        summary = {
            "run_id": handle.run_id,
            "agent": handle.agent,
            "session_id": handle.agent_session_id,
            "agent_session_id": handle.agent_session_id,
            "agent_model": handle.agent_model,
            "runtime_session_id": handle.session_id,
            "root": str(handle.root),
            "report": str(handle.report_path or ""),
            "transcript": str(handle.transcript_path or ""),
            "tokens_input": handle.tokens_input,
            "tokens_cached_input": handle.tokens_cached_input,
            "tokens_output": handle.tokens_output,
            "tokens_total": _handle_tokens_total(handle),
            "cost_usd": handle.cost_usd if handle.cost_usd is not None else "unknown",
            "cost_source": handle.cost_source or "unknown",
            "resume_command": handle.resume_command,
            "exit_code": handle.exit_code,
            "completed_at": handle.completed_at.isoformat()
            if handle.completed_at
            else "",
            "status": "completed"
            if handle.exit_code == 0
            else ("failed" if handle.exit_code is not None else "running"),
        }
        # Stamp origin for triage-run: dispatcher finishes outside the worker
        # pane, so ambient VC_FRAME_* is often empty at triage time. Prefer
        # values already in meta (launch path) over live env.
        origin = _origin_fields_from_env()
        if not str(payload.get("origin_session") or "").strip():
            if origin.get("origin_session"):
                summary["origin_session"] = origin["origin_session"]
                summary["operator_session"] = origin.get(
                    "operator_session", origin["origin_session"]
                )
        if not str(payload.get("origin_tab") or "").strip():
            summary["origin_tab"] = origin.get("origin_tab") or handle.run_id
        if (
            origin.get("origin_pane_id")
            and not str(payload.get("origin_pane_id") or "").strip()
        ):
            summary["origin_pane_id"] = origin["origin_pane_id"]
        if handle.model_requested:
            summary["model_requested"] = handle.model_requested
            summary["model_override_supported"] = handle.model_override_supported
            summary["model_override_skipped"] = handle.model_override_skipped
            if handle.model_override_skip_reason:
                summary["model_override_skip_reason"] = (
                    handle.model_override_skip_reason
                )
        if handle.tokens_cache_write is not None:
            summary["tokens_cache_write"] = handle.tokens_cache_write
        else:
            payload.pop("tokens_cache_write", None)
        payload.update(summary)
        handle.meta_path.parent.mkdir(parents=True, exist_ok=True)
        handle.meta_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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
        event_payload: dict[str, object] = {
            "root": str(handle.root),
            "session_id": handle.session_id,
            "identity_required": True,
        }
        if payload:
            event_payload.update(payload)
        await self._emit(handle.run_id, state, message, payload=event_payload)

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
