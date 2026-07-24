from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HardStop:
    category: str
    evidence: str


_HARD_STOP_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("git-push", re.compile(r"\bgit\s+push\b", re.IGNORECASE)),
    (
        "git-history",
        re.compile(
            r"\bgit\s+(?:reset\s+--hard|rebase\s+-i|stash\s+drop)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "git-merge",
        re.compile(
            r"\b(?:git\s+merge|gh\s+pr\s+(?:merge|close|review\s+--approve))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "publish",
        re.compile(
            r"\b(?:cargo|npm|pnpm|yarn|uv|twine)\s+publish\b|\bdocker\s+push\b",
            re.IGNORECASE,
        ),
    ),
    (
        "deploy",
        re.compile(
            r"\b(?:fly(?:ctl)?\s+deploy|vercel(?:\s+deploy)?|"
            r"netlify\s+deploy|kubectl\s+apply|helm\s+(?:install|upgrade))\b",
            re.IGNORECASE,
        ),
    ),
)


def _searchable_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def classify_hard_stop(raw_input: Any) -> HardStop | None:
    """Classify operator-button actions conservatively from raw tool/prompt input."""
    text = _searchable_text(raw_input)
    for category, pattern in _HARD_STOP_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return HardStop(category=category, evidence=match.group(0))
    return None


def permission_request(
    *, session_id: str, tool_call_id: str, hard_stop: HardStop, raw_input: Any
) -> dict[str, Any]:
    """Build the only permission shape hard-stops accept: allow once or reject."""
    return {
        "sessionId": session_id,
        "toolCall": {
            "toolCallId": tool_call_id,
            "title": f"Operator button required: {hard_stop.category}",
            "kind": "execute",
            "status": "pending",
            "rawInput": {"input": _searchable_text(raw_input)},
        },
        "options": [
            {
                "optionId": "allow-once",
                "name": "Allow once",
                "kind": "allow_once",
            },
            {
                "optionId": "reject-once",
                "name": "Reject",
                "kind": "reject_once",
            },
        ],
    }


def allowed_once(response: Any) -> bool:
    """Fail closed unless the client explicitly selected this one-shot grant."""
    if not isinstance(response, dict):
        return False
    outcome = response.get("outcome")
    return (
        isinstance(outcome, dict)
        and outcome.get("outcome") == "selected"
        and outcome.get("optionId") == "allow-once"
    )
