from __future__ import annotations

import json
import os
import re
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping, Sequence

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SESSION_PATTERN = re.compile(
    r"(?:^|\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]\s+)session:\s*([A-Za-z0-9][A-Za-z0-9._:-]*)",
    re.MULTILINE,
)
TOKEN_PATTERN = re.compile(
    r"tokens:\s*([0-9]+)\s+in(?:\s*\(([0-9]+)\s+cached\))?\s*/\s*([0-9]+)\s+out",
    re.IGNORECASE,
)
MODEL_PATTERN = re.compile(r"model:\s*([^\s]+)", re.IGNORECASE)
MODEL_ENV_VARS = (
    "VIBECRAFTED_PARENT_MODEL",
    "CLAUDE_MODEL",
    "CODEX_MODEL",
    "GEMINI_MODEL",
    "GROK_MODEL",
    "JUNIE_MODEL",
    "AGY_MODEL",
)
MODEL_PLACEHOLDERS = {"", "none", "null", "unknown", "pending"}
COST_PATTERNS = (
    re.compile(r"cost(?:_usd)?\s*[:=]\s*\$?([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE),
    re.compile(r"\$([0-9]+\.[0-9]+)\s*(?:usd)?", re.IGNORECASE),
)
GROK_IGNORABLE_TRANSPORT_ERROR = "worker quit with fatal: Transport channel closed"


def stamp() -> str:
    return time.strftime("%H:%M:%S", time.localtime())


def tool_tag(name: str) -> str:
    return f"\x1b[36m[{stamp()} {name}]\x1b[0m "


def _stringish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return _stringish(
            value.get("message") or value.get("error") or value.get("detail") or value
        )
    if isinstance(value, list):
        return ", ".join(_stringish(item) for item in value)
    return json.dumps(value, ensure_ascii=False)


def _truncate_block(text: str, *, max_chars: int = 4000) -> str:
    lines = text.splitlines()
    if len(text) > max_chars:
        preview = text[:max_chars]
        return f"\x1b[2m{preview}\n  ... ({len(text)} chars)\x1b[0m\n"
    if len(lines) > 12:
        preview = "\n".join(lines[:5])
        return f"\x1b[2m{preview}\n  ... ({len(lines)} lines)\x1b[0m\n"
    return f"\x1b[2m{text}\x1b[0m\n"


def is_grok_ignorable_transport_error(text: str) -> bool:
    clean = ANSI_PATTERN.sub("", text or "")
    if GROK_IGNORABLE_TRANSPORT_ERROR not in clean:
        return False
    return any(
        marker in clean
        for marker in (
            "AuthorizationRequired",
            "AuthRequired",
            "tcp connect error",
            "dns error",
        )
    )


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _clean_model(value: object) -> str:
    raw = str(value or "").strip()
    return "" if raw.lower() in MODEL_PLACEHOLDERS else raw


def _command_model(command: Sequence[str] | None) -> str:
    if not command:
        return ""
    items = [str(item) for item in command]
    for index, item in enumerate(items):
        if item in {"--model", "-m"} and index + 1 < len(items):
            model = _clean_model(items[index + 1])
            if model:
                return model
        if item.startswith("--model="):
            model = _clean_model(item.split("=", 1)[1])
            if model:
                return model
    return ""


def _codex_config_model(env: Mapping[str, str]) -> str:
    codex_home = Path(env.get("CODEX_HOME") or Path.home() / ".codex")
    config = codex_home / "config.toml"
    try:
        with config.open("rb") as handle:
            loaded = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    if isinstance(loaded, dict):
        return _clean_model(loaded.get("model"))
    return ""


def resolve_default_model(
    agent: str,
    *,
    command: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    model = _command_model(command)
    if model:
        return model
    source_env = env or os.environ
    for key in MODEL_ENV_VARS:
        model = _clean_model(source_env.get(key))
        if model:
            return model
    if agent == "codex":
        return _codex_config_model(source_env)
    return ""


class AgentStreamParser:
    def __init__(self, agent: str, *, default_model: str = "") -> None:
        self.agent = agent
        self.session_id = ""
        self._rendered_session_ids: set[str] = set()
        self.model_id = _clean_model(default_model)
        self.tokens_input = 0
        self.tokens_cached_input = 0
        self.tokens_cache_write: int | None = None
        self.tokens_output = 0
        self.cost_usd: float | None = None

    def feed_line(self, chunk: bytes) -> str:
        text = chunk.decode("utf-8", errors="replace")
        if self.agent == "grok" and is_grok_ignorable_transport_error(text):
            return ""
        stripped = text.lstrip()
        if not stripped.startswith("{"):
            self._scan_text(text)
            return text
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            self._scan_text(text)
            return text
        if not isinstance(event, dict):
            return ""
        return self._format_json_event(event)

    def resume_command(self, root: str | Path) -> str:
        session = self.session_id or "<session_id>"
        root_text = str(root)
        if self.agent == "claude":
            return f"cd {root_text} && claude --resume {session}"
        if self.agent == "codex":
            return f"cd {root_text} && codex resume {session}"
        if self.agent == "gemini":
            return f"cd {root_text} && gemini --resume {session}"
        if self.agent == "agy":
            return f"cd {root_text} && agy --conversation {session}"
        if self.agent == "junie":
            return f"cd {root_text} && junie --resume --session-id {session}"
        if self.agent == "grok":
            return f"cd {root_text} && grok --resume {session}"
        return f"cd {root_text} && vc-resume --session {session}"

    def _scan_text(self, text: str) -> None:
        clean = ANSI_PATTERN.sub("", text or "")
        session_matches = SESSION_PATTERN.findall(clean)
        if session_matches:
            self.session_id = session_matches[-1]
        for raw_in, raw_cached, raw_out in TOKEN_PATTERN.findall(clean):
            self.tokens_input += int(raw_in)
            self.tokens_cached_input += int(raw_cached or 0)
            self.tokens_output += int(raw_out)
        model_matches = MODEL_PATTERN.findall(clean)
        if model_matches:
            self.model_id = model_matches[-1]
        for pattern in COST_PATTERNS:
            matches = pattern.findall(clean)
            if matches:
                self.cost_usd = _as_float(matches[-1])

    def _record_model(self, event: dict[str, Any]) -> None:
        for key in ("model", "model_id", "modelId", "model_name", "modelName"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                self.model_id = value.strip()
                return
        message = event.get("message")
        if isinstance(message, dict):
            for key in ("model", "model_id", "modelId", "model_name", "modelName"):
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    self.model_id = value.strip()
                    return

    def _record_usage(self, usage: dict[str, Any]) -> None:
        self.tokens_input += _as_int(usage.get("input_tokens"))
        cached_input = usage.get("cached_input_tokens")
        if cached_input is None:
            cached_input = usage.get("cache_read_input_tokens")
        self.tokens_cached_input += _as_int(cached_input)
        if "cache_creation_input_tokens" in usage:
            self.tokens_cache_write = (self.tokens_cache_write or 0) + _as_int(
                usage.get("cache_creation_input_tokens")
            )
        self.tokens_output += _as_int(usage.get("output_tokens"))

    def _record_cost(self, event: dict[str, Any]) -> None:
        cost = _as_float(
            event.get("total_cost_usd")
            or event.get("cost_usd")
            or event.get("cost")
            or event.get("total_cost")
        )
        if cost is not None:
            self.cost_usd = cost

    def _session_banner(self, session_id: str, suffix: str = "") -> str:
        if not session_id or session_id == "?":
            return ""
        self.session_id = session_id
        if session_id in self._rendered_session_ids:
            return ""
        self._rendered_session_ids.add(session_id)
        model_suffix = f" model: {self.model_id}" if self.model_id else ""
        return (
            f"\x1b[33m[{stamp()}] session: {session_id}{model_suffix}\x1b[0m{suffix}\n"
        )

    def _format_json_event(self, event: dict[str, Any]) -> str:
        if self.agent in {"claude", "agy"}:
            return self._format_claude_event(event)
        if self.agent == "codex":
            return self._format_codex_event(event)
        if self.agent == "gemini":
            return self._format_gemini_event(event)
        if self.agent == "junie":
            return self._format_junie_event(event)
        if self.agent == "grok":
            return self._format_grok_event(event)
        return ""

    def _format_claude_event(self, event: dict[str, Any]) -> str:
        self._record_model(event)
        event_type = str(event.get("type") or "")
        session_id = event.get("session_id")
        if isinstance(session_id, str) and session_id:
            self.session_id = session_id

        if (
            event_type == "system"
            and session_id
            and str(event.get("subtype") or "init") == "init"
        ):
            return self._session_banner(str(session_id))

        if event_type == "assistant":
            out: list[str] = []
            if isinstance(session_id, str) and session_id:
                out.append(self._session_banner(session_id))
            message = event.get("message") or {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        out.append("\n" + str(item.get("text") or "") + "\n")
                    elif item.get("type") == "thinking":
                        out.append(f"\n\x1b[2m{item.get('thinking') or ''}\x1b[0m\n")
                    elif item.get("type") == "tool_use":
                        out.append(tool_tag(str(item.get("name") or "?")))
            return "".join(out)

        if event_type == "stream_event":
            stream = event.get("event") or {}
            if not isinstance(stream, dict):
                return ""
            if stream.get("type") == "content_block_delta":
                delta = stream.get("delta") or {}
                if not isinstance(delta, dict):
                    return ""
                if delta.get("type") == "text_delta":
                    return str(delta.get("text") or "")
                if delta.get("type") == "thinking_delta":
                    return f"\x1b[2m{delta.get('thinking') or ''}\x1b[0m"
            if stream.get("type") == "content_block_start":
                block = stream.get("content_block") or {}
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    return "\n" + tool_tag(str(block.get("name") or "?"))
            return ""

        if event_type == "result":
            usage = event.get("usage")
            if isinstance(usage, dict):
                self._record_usage(usage)
            self._record_cost(event)
            return f"\n\x1b[32m[{stamp()}] {event.get('result') or 'done'}\x1b[0m\n"

        return ""

    def _format_codex_event(self, event: dict[str, Any]) -> str:
        self._record_model(event)
        event_type = str(event.get("type") or "")
        if event_type == "thread.started":
            session_id = str(event.get("thread_id") or "?")
            return self._session_banner(session_id)

        if event_type == "item.started":
            item = event.get("item") or {}
            if not isinstance(item, dict):
                return ""
            item_type = item.get("type")
            if item_type == "command_execution":
                return "\n" + tool_tag(f"$ {item.get('command', 'cmd')}") + "\n"
            if item_type == "mcp_tool_call":
                return tool_tag(
                    f"{item.get('server', '')}:{item.get('tool') or item.get('name') or '?'}"
                )
            if item_type == "web_search":
                return tool_tag("search")
            if item_type == "plan_update":
                return f"\x1b[35m[{stamp()} plan]\x1b[0m "
            return ""

        if event_type == "item.completed":
            item = event.get("item") or {}
            if not isinstance(item, dict):
                return ""
            item_type = item.get("type")
            if item_type == "agent_message":
                return "\n" + str(item.get("text") or "") + "\n"
            if item_type == "reasoning":
                return f"\x1b[2m{item.get('text', '')}\x1b[0m\n"
            if item_type == "command_execution":
                output = str(item.get("output") or "")
                return _truncate_block(output) if output else ""
            if item_type == "mcp_tool_call":
                result = item.get("result") or {}
                content = result.get("content") if isinstance(result, dict) else None
                first = content[0] if isinstance(content, list) and content else {}
                output = str(first.get("text") or "") if isinstance(first, dict) else ""
                return _truncate_block(output) if output else ""
            if item_type == "file_changes":
                return f"\x1b[32m[{stamp()} write: {item.get('path', '?')}]\x1b[0m\n"
            return ""

        if event_type in {"turn.completed", "turn_completed"}:
            usage = event.get("usage") or {}
            if isinstance(usage, dict):
                self._record_usage(usage)
                cached = usage.get("cached_input_tokens")
                cached_fragment = f" ({cached} cached)" if cached is not None else ""
                return (
                    f"\n\x1b[2m[{stamp()}] tokens: {usage.get('input_tokens', 0)} in"
                    f"{cached_fragment} / {usage.get('output_tokens', 0)} out\x1b[0m\n"
                )
            return ""

        if event_type in {"turn.failed", "turn_failed"}:
            return f"\n\x1b[31m[{stamp()} error] {_stringish(event.get('error') or event.get('message') or 'turn failed')}\x1b[0m\n"
        if event_type in {"turn.aborted", "turn_aborted"}:
            return f"\n\x1b[31m[{stamp()} abort] {_stringish(event.get('message') or event.get('reason') or event.get('error') or 'turn aborted')}\x1b[0m\n"
        return ""

    def _format_gemini_event(self, event: dict[str, Any]) -> str:
        self._record_model(event)
        event_type = str(event.get("type") or "")
        if event_type == "init":
            session_id = str(event.get("session_id") or "?")
            return self._session_banner(session_id)
        if event_type == "gemini":
            out: list[str] = []
            for thought in event.get("thoughts") or []:
                if isinstance(thought, dict):
                    out.append(
                        f"\x1b[2m[{stamp()} thinking] {thought.get('subject') or '?'}: {thought.get('description') or ''}\x1b[0m\n"
                    )
            content = str(event.get("content") or "")
            if content:
                out.append(content)
            for call in event.get("toolCalls") or []:
                if isinstance(call, dict):
                    out.append("\n" + tool_tag(str(call.get("name") or "?")))
            return "".join(out)
        if event_type == "message" and event.get("role") == "assistant":
            return str(event.get("content") or "")
        if event_type == "tool_use":
            return "\n" + tool_tag(
                str(event.get("tool_name") or event.get("name") or "?")
            )
        if event_type == "tool_result":
            output = str(event.get("output") or "")
            return _truncate_block(output) if output else ""
        if event_type == "error":
            return f"\x1b[31m[{stamp()} error] {event.get('message') or event.get('error') or 'unknown'}\x1b[0m\n"
        if event_type == "result":
            stats = event.get("stats") or {}
            status_line = (
                f"\n\x1b[32m[{stamp()}] {event.get('status') or 'done'}\x1b[0m\n"
            )
            if not isinstance(stats, dict):
                return status_line
            self._record_usage(stats)
            input_tokens = _as_int(stats.get("input_tokens"))
            output_tokens = _as_int(stats.get("output_tokens"))
            # Render the human-readable token line (same shape as codex/claude)
            # so the regex-based token extractor in spawn.py picks gemini usage
            # up from the transcript; without it research-swarm meta lands at 0.
            if input_tokens or output_tokens:
                cached = stats.get("cached_input_tokens") or stats.get(
                    "cache_read_input_tokens"
                )
                cached_fragment = f" ({_as_int(cached)} cached)" if cached else ""
                tokens_line = (
                    f"\x1b[2m[{stamp()}] tokens: {input_tokens} in"
                    f"{cached_fragment} / {output_tokens} out\x1b[0m\n"
                )
                return tokens_line + status_line
            return status_line
        return ""

    def _format_junie_event(self, event: dict[str, Any]) -> str:
        self._record_model(event)
        for key in ("session_id", "sessionId"):
            value = event.get(key)
            if isinstance(value, str) and value:
                self.session_id = value
                break
        usage = event.get("usage")
        if isinstance(usage, dict):
            self._record_usage(usage)
        message = (
            event.get("message")
            or event.get("text")
            or event.get("content")
            or event.get("details")
            or event.get("data")
        )
        text = _stringish(message)
        if not text or text == "None":
            return ""
        name = _stringish(event.get("name"))
        if name and event.get("type") == "step":
            return f"{name}: {text}\n"
        return text + "\n"

    def _format_grok_event(self, event: dict[str, Any]) -> str:
        self._record_model(event)
        for key in ("session_id", "sessionId", "conversation_id"):
            value = event.get(key)
            if isinstance(value, str) and value:
                self.session_id = value
                break
        usage = event.get("usage") or event.get("stats")
        if isinstance(usage, dict):
            self._record_usage(usage)
        self._record_cost(event)
        event_type = str(event.get("type") or "")
        if event_type == "end":
            value = event.get("sessionId") or event.get("session_id")
            if isinstance(value, str) and value:
                self.session_id = value
            return ""
        if event_type == "thought":
            text = _stringish(event.get("data"))
            return f"\x1b[2m{text}\x1b[0m" if text else ""
        if event_type == "text":
            return _stringish(event.get("data"))
        if event_type in {"tool", "tool_use", "tool_call"}:
            name = event.get("name") or event.get("tool") or event.get("toolName")
            return "\n" + tool_tag(_stringish(name) or "?")
        if event_type == "error":
            message = event.get("message") or event.get("error") or event.get("data")
            text = _stringish(message)
            return f"\n\x1b[31m[{stamp()} error] {text or 'unknown'}\x1b[0m\n"

        message = (
            event.get("message")
            or event.get("text")
            or event.get("content")
            or event.get("data")
        )
        text = _stringish(message)
        if not text or text == "None":
            return ""
        return text + "\n"
