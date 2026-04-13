#!/usr/bin/env python3
"""Resilient bridge from Codex JSONL to human transcript output.

This parser is intentionally tolerant: malformed or truncated JSON lines should
never crash the live stream path. The Codex process exit code remains the
source of truth for success/failure; this bridge only formats observable
activity and preserves raw output for forensics.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def stamp() -> str:
    return time.strftime("%H:%M:%S", time.localtime())


def stringish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return stringish(
            value.get("message") or value.get("error") or value.get("detail") or value
        )
    if isinstance(value, list):
        return ", ".join(stringish(item) for item in value)
    return json.dumps(value, ensure_ascii=False)


def tool_tag(name: str) -> str:
    return f"\x1b[36m[{stamp()} {name}]\x1b[0m"


def truncate_block(text: str) -> str:
    lines = text.splitlines()
    if len(lines) > 12:
        preview = "\n".join(lines[:5])
        return f"\x1b[2m{preview}\n  ... ({len(lines)} lines)\x1b[0m\n"
    return f"\x1b[2m{text}\x1b[0m\n"


def format_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "")

    if event_type == "thread.started":
        return f"\x1b[33m[{stamp()}] session: {event.get('thread_id', '?')}\x1b[0m\n"

    if event_type == "item.started":
        item = event.get("item") or {}
        item_type = item.get("type")
        if item_type == "command_execution":
            return "\n" + tool_tag(f"$ {item.get('command', 'cmd')}") + "\n"
        if item_type == "mcp_tool_call":
            return (
                tool_tag(
                    f"{item.get('server', '')}:{item.get('tool') or item.get('name') or '?'}"
                )
                + " "
            )
        if item_type == "web_search":
            return tool_tag("search") + " "
        if item_type == "plan_update":
            return f"\x1b[35m[{stamp()} plan]\x1b[0m "
        return ""

    if event_type == "item.completed":
        item = event.get("item") or {}
        item_type = item.get("type")
        if item_type == "agent_message":
            return "\n" + str(item.get("text") or "") + "\n"
        if item_type == "reasoning":
            return f"\x1b[2m{item.get('text', '')}\x1b[0m\n"
        if item_type == "command_execution":
            output = str(item.get("output") or "")
            return truncate_block(output) if output else ""
        if item_type == "mcp_tool_call":
            content = (((item.get("result") or {}).get("content")) or [{}])[0]
            output = str(content.get("text") or "")
            return truncate_block(output) if output else ""
        if item_type == "file_changes":
            return f"\x1b[32m[{stamp()} write: {item.get('path', '?')}]\x1b[0m\n"
        return ""

    if event_type in {"turn.completed", "turn_completed"}:
        usage = event.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        if input_tokens is None:
            return ""
        cached = usage.get("cached_input_tokens")
        cached_fragment = f" ({cached} cached)" if cached is not None else ""
        return (
            f"\n\x1b[2m[{stamp()}] tokens: {input_tokens} in"
            f"{cached_fragment} / {usage.get('output_tokens', 0)} out\x1b[0m\n"
        )

    if event_type in {"turn.failed", "turn_failed"}:
        error_value = event.get("error") or event.get("message") or "turn failed"
        return f"\n\x1b[31m[{stamp()} error] {stringish(error_value)}\x1b[0m\n"

    if event_type in {"turn.aborted", "turn_aborted"}:
        reason_value = (
            event.get("message")
            or event.get("reason")
            or event.get("error")
            or "turn aborted"
        )
        return f"\n\x1b[31m[{stamp()} abort] {stringish(reason_value)}\x1b[0m\n"

    return ""


def append(handle, text: str) -> None:
    if not text:
        return
    handle.write(text)
    handle.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--raw", required=True)
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    raw_path = Path(args.raw)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        transcript_path.open("a", encoding="utf-8") as transcript,
        raw_path.open("a", encoding="utf-8") as raw,
    ):
        for raw_line in sys.stdin:
            append(raw, raw_line)
            stripped = raw_line.lstrip()
            if not stripped.startswith("{"):
                append(
                    transcript, raw_line if raw_line.endswith("\n") else raw_line + "\n"
                )
                continue

            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                append(
                    transcript,
                    raw_line if raw_line.endswith("\n") else raw_line + "\n",
                )
                continue

            rendered = format_event(event)
            if rendered:
                append(transcript, rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
