from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from vibecrafted_core.agent_stream import ANSI_PATTERN, AgentStreamParser

from . import __version__
from .bridge import RuntimeBridge
from .policy import allowed_once, classify_hard_stop, permission_request

PROTOCOL_VERSION = 1
SCHEMA_VERSION = "schema-v1.20.0"
_TRUTHY = {"1", "true", "yes", "on"}
_LOGGER = logging.getLogger(__name__)


class JsonWriter:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self._lock = threading.Lock()

    def send(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.stream.write(line + "\n")
            self.stream.flush()


class ClientRequests:
    """Route agent→client JSON-RPC requests while stdin stays responsive."""

    def __init__(self, writer: JsonWriter) -> None:
        self.writer = writer
        self._condition = threading.Condition()
        self._counter = 0
        self._responses: dict[str, dict[str, Any]] = {}
        self._closed = False

    def resolve(self, message: dict[str, Any]) -> None:
        request_id = str(message.get("id"))
        with self._condition:
            self._responses[request_id] = message
            self._condition.notify_all()

    def request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float,
        cancel_event: threading.Event | None = None,
    ) -> Any:
        with self._condition:
            self._counter += 1
            request_id = f"vibecrafted-permission-{self._counter}"
        self.writer.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        with self._condition:
            while (
                request_id not in self._responses
                and not self._closed
                and not (cancel_event is not None and cancel_event.is_set())
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=min(remaining, 0.1))
            message = self._responses.pop(request_id, None)
        if not isinstance(message, dict) or "error" in message:
            return None
        return message.get("result")

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def wake(self) -> None:
        with self._condition:
            self._condition.notify_all()


@dataclass
class Session:
    session_id: str
    cwd: str
    agent: str
    skill: str
    runtime: str
    parser: AgentStreamParser
    prompt_started: bool = False
    launched: bool = False
    cancelled: bool = False
    cancel_event: threading.Event = field(default_factory=threading.Event)
    transcript_offset: int = 0
    pending_stream: bytes = b""
    lock: threading.Lock = field(default_factory=threading.Lock)


class ACPServer:
    def __init__(self, *, bridge: RuntimeBridge, output: TextIO) -> None:
        self.bridge = bridge
        self.writer = JsonWriter(output)
        self.client = ClientRequests(self.writer)
        self.initialized = False
        self.sessions: dict[str, Session] = {}
        self._threads: list[threading.Thread] = []

    def _response(self, request_id: Any, result: dict[str, Any]) -> None:
        self.writer.send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _error(self, request_id: Any, code: int, message: str) -> None:
        self.writer.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    def _update(self, session_id: str, update: dict[str, Any]) -> None:
        self.writer.send(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {"sessionId": session_id, "update": update},
            }
        )

    def handle_message(self, message: dict[str, Any]) -> None:
        if "method" not in message and "id" in message:
            self.client.resolve(message)
            return
        request_id = message.get("id")
        if message.get("jsonrpc") != "2.0" or not isinstance(
            message.get("method"), str
        ):
            self._error(request_id, -32600, "Invalid Request")
            return
        method = str(message["method"])
        params = message.get("params") or {}
        if not isinstance(params, dict):
            self._error(request_id, -32602, "params must be an object")
            return
        if method == "initialize":
            self._initialize(request_id)
        elif method == "session/new":
            self._new_session(request_id, params)
        elif method == "session/prompt":
            self._start_prompt(request_id, params)
        elif method == "session/cancel":
            self._cancel(request_id, params)
        else:
            self._error(request_id, -32601, f"Method not found: {method}")

    def _initialize(self, request_id: Any) -> None:
        self.initialized = True
        self._response(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "agentCapabilities": {
                    "promptCapabilities": {
                        "image": False,
                        "audio": False,
                        "embeddedContext": False,
                    },
                    "sessionCapabilities": {},
                },
                "agentInfo": {
                    "name": "vibecrafted-acp",
                    "title": "Vibecrafted",
                    "version": __version__,
                },
                "authMethods": [],
                "_meta": {"vibecrafted": {"schema": SCHEMA_VERSION}},
            },
        )

    def _new_session(self, request_id: Any, params: dict[str, Any]) -> None:
        if not self.initialized:
            self._error(request_id, -32002, "initialize must be called first")
            return
        cwd = str(params.get("cwd") or "").strip()
        if not cwd or not Path(cwd).is_absolute():
            self._error(request_id, -32602, "cwd must be an absolute path")
            return
        mcp_servers = params.get("mcpServers")
        if not isinstance(mcp_servers, list):
            self._error(request_id, -32602, "mcpServers must be an array")
            return
        if mcp_servers:
            self._error(
                request_id,
                -32602,
                "MCP passthrough is not advertised by this MVP",
            )
            return
        meta = params.get("_meta") or {}
        settings = meta.get("vibecrafted") if isinstance(meta, dict) else {}
        settings = settings if isinstance(settings, dict) else {}
        agent = str(settings.get("agent") or "codex").strip()
        skill = str(settings.get("skill") or "implement").strip()
        runtime = str(settings.get("runtime") or "headless").strip()
        session_id = self.bridge.reserve_run_id(skill)
        self.sessions[session_id] = Session(
            session_id=session_id,
            cwd=cwd,
            agent=agent,
            skill=skill,
            runtime=runtime,
            parser=AgentStreamParser(agent),
        )
        self._response(request_id, {"sessionId": session_id})

    @staticmethod
    def _prompt_text(params: dict[str, Any]) -> str:
        prompt = params.get("prompt")
        if not isinstance(prompt, list):
            return ""
        parts: list[str] = []
        for block in prompt:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif block.get("type") == "resource":
                resource = block.get("resource")
                if isinstance(resource, dict):
                    parts.append(str(resource.get("text") or ""))
            elif block.get("type") == "resource_link":
                parts.append(str(block.get("uri") or ""))
        return "\n".join(part for part in parts if part).strip()

    def _start_prompt(self, request_id: Any, params: dict[str, Any]) -> None:
        session_id = str(params.get("sessionId") or "")
        session = self.sessions.get(session_id)
        if session is None:
            self._error(request_id, -32602, "unknown sessionId")
            return
        prompt = self._prompt_text(params)
        if not prompt:
            self._error(request_id, -32602, "prompt must contain text")
            return
        with session.lock:
            if session.prompt_started:
                self._error(request_id, -32001, "MVP permits one prompt per session")
                return
            session.prompt_started = True
        thread = threading.Thread(
            target=self._prompt_worker,
            args=(request_id, session, prompt),
            name=f"acp-{session_id}",
        )
        self._threads.append(thread)
        thread.start()

    def _prompt_worker(self, request_id: Any, session: Session, prompt: str) -> None:
        hard_stop = classify_hard_stop(prompt)
        permission_tool_id = ""
        if hard_stop is not None:
            permission_tool_id = f"hard-stop-{session.session_id}"
            self._update(
                session.session_id,
                {
                    "sessionUpdate": "tool_call",
                    "toolCallId": permission_tool_id,
                    "title": f"Operator button required: {hard_stop.category}",
                    "kind": "execute",
                    "status": "pending",
                    "rawInput": {"prompt": prompt},
                },
            )
            timeout = float(os.environ.get("VIBECRAFTED_ACP_PERMISSION_TIMEOUT", "30"))
            decision = self.client.request(
                "session/request_permission",
                permission_request(
                    session_id=session.session_id,
                    tool_call_id=permission_tool_id,
                    hard_stop=hard_stop,
                    raw_input=prompt,
                ),
                timeout_seconds=timeout,
                cancel_event=session.cancel_event,
            )
            if not allowed_once(decision):
                cancelled = session.cancel_event.is_set()
                self._update(
                    session.session_id,
                    {
                        "sessionUpdate": "tool_call_update",
                        "toolCallId": permission_tool_id,
                        "status": "failed",
                        "content": [
                            {
                                "type": "content",
                                "content": {
                                    "type": "text",
                                    "text": (
                                        "Cancelled by client."
                                        if cancelled
                                        else "Denied: explicit allow_once was not selected."
                                    ),
                                },
                            }
                        ],
                    },
                )
                self._response(
                    request_id,
                    {"stopReason": "cancelled" if cancelled else "refusal"},
                )
                return
            self.bridge.record_hard_stop_override(
                session.session_id,
                category=hard_stop.category,
                evidence=hard_stop.evidence,
            )
            self._update(
                session.session_id,
                {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": permission_tool_id,
                    "status": "in_progress",
                },
            )

        with session.lock:
            if session.cancelled:
                self._response(request_id, {"stopReason": "cancelled"})
                return
        try:
            launch = self.bridge.launch(
                run_id=session.session_id,
                root=session.cwd,
                prompt=prompt,
                agent=session.agent,
                skill=session.skill,
                runtime=session.runtime,
            )
            if not launch.get("accepted") or launch.get("run_id") != session.session_id:
                raise RuntimeError("core launch did not accept the reserved run_id")
            with session.lock:
                session.launched = True
                cancelled = session.cancelled
            if cancelled:
                self.bridge.stop(session.session_id)

            result = self.bridge.await_run(
                session.session_id,
                on_poll=lambda _run: self._pump_once(session),
                timeout_seconds=float(os.environ.get("VIBECRAFTED_ACP_TIMEOUT", "300")),
                interval_seconds=0.25,
            )
            self._pump_once(session, final=True)
            run = result.get("run") or {}
            stopped = session.cancelled or str(run.get("state") or "") == "stopped"
            stop_reason = (
                "cancelled"
                if stopped
                else "end_turn"
                if result.get("completed")
                else "refusal"
            )
            if permission_tool_id:
                self._update(
                    session.session_id,
                    {
                        "sessionUpdate": "tool_call_update",
                        "toolCallId": permission_tool_id,
                        "status": "completed"
                        if stop_reason == "end_turn"
                        else "failed",
                    },
                )
            self._response(request_id, {"stopReason": stop_reason})
        except Exception as exc:
            _LOGGER.exception("ACP prompt failed")
            self._update(
                session.session_id,
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {
                        "type": "text",
                        "text": f"Vibecrafted runtime error: {type(exc).__name__}",
                    },
                },
            )
            self._response(request_id, {"stopReason": "refusal"})

    def _pump_once(self, session: Session, *, final: bool = False) -> None:
        observed = self.bridge.observe(
            session.session_id, offset=session.transcript_offset
        )
        session.transcript_offset = int(
            observed.get("next_offset") or session.transcript_offset
        )
        data = session.pending_stream + bytes(observed.get("text") or b"")
        lines = data.splitlines(keepends=True)
        session.pending_stream = b""
        if lines and not lines[-1].endswith((b"\n", b"\r")) and not final:
            session.pending_stream = lines.pop()
        if final and session.pending_stream:
            lines.append(session.pending_stream)
            session.pending_stream = b""
        for line in lines:
            rendered = session.parser.feed_line(line)
            if rendered:
                rendered = ANSI_PATTERN.sub("", rendered)
                self._update(
                    session.session_id,
                    {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": rendered},
                    },
                )

    def _cancel(self, request_id: Any, params: dict[str, Any]) -> None:
        session_id = str(params.get("sessionId") or "")
        session = self.sessions.get(session_id)
        if session is None:
            if request_id is not None:
                self._error(request_id, -32602, "unknown sessionId")
            return
        with session.lock:
            session.cancelled = True
            session.cancel_event.set()
            launched = session.launched
        self.client.wake()
        if launched:
            self.bridge.stop(session_id)
        if request_id is not None:
            self._response(request_id, {})

    def wait(self) -> None:
        for thread in list(self._threads):
            thread.join()

    def close(self) -> None:
        self.client.close()


def serve(
    input_stream: TextIO,
    output_stream: TextIO,
    *,
    bridge: RuntimeBridge,
) -> int:
    server = ACPServer(bridge=bridge, output=output_stream)
    for raw_line in input_stream:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            server._error(None, -32700, "Parse error")
            continue
        if not isinstance(message, dict):
            server._error(None, -32600, "Invalid Request")
            continue
        server.handle_message(message)
    server.close()
    server.wait()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vibecrafted acp",
        description=(
            f"ACP v1 stdio adapter ({SCHEMA_VERSION}) over Vibecrafted control_plane"
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="use the deterministic fake worker stream without launching an agent",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    dry_run = (
        args.dry_run or os.environ.get("VIBECRAFTED_ACP_DRY_RUN", "").lower() in _TRUTHY
    )
    return serve(sys.stdin, sys.stdout, bridge=RuntimeBridge(dry_run=dry_run))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
