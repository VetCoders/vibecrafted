"""Regression tests for skills/vc-agents/scripts/codex_stream_bridge.py.

The bridge parses Codex JSONL events into a human-readable transcript. It must
be tolerant: malformed lines, unknown event types, and an EOF mid-stream must
never crash — the Codex process's exit code is the source of truth, the bridge
only formats observable activity and preserves the raw stream for forensics.

These tests run entirely offline: they feed stdin via subprocess, covering:

- Graceful EOF after a clean JSON event.
- Malformed JSON → preserved verbatim in the transcript.
- Error-style event payloads → rendered with an [error] prefix.
- Non-JSON lines (plain stdout) → pass through unchanged.
- Known-event formatting (thread.started, item.completed/agent_message,
  turn.failed).

All assertions are on the resulting transcript + raw files and the bridge's
exit code.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "codex_stream_bridge.py"


# ---------------------------------------------------------------------------
# Direct-import helpers — for unit-testing pure functions without spawning a
# subprocess (fast, deterministic, covers every branch of format_event).
# ---------------------------------------------------------------------------


def _load_bridge_module():
    spec = importlib.util.spec_from_file_location(
        "codex_stream_bridge_under_test", BRIDGE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIDGE = _load_bridge_module()


def _strip_ansi(text: str) -> str:
    """Remove ANSI SGR sequences so assertions focus on content, not color."""
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ---------------------------------------------------------------------------
# Subprocess-level integration — exercises the `main()` loop (sys.stdin path).
# ---------------------------------------------------------------------------


def _run_bridge(tmp_path: Path, stdin_text: str) -> tuple[int, str, str, str]:
    transcript = tmp_path / "transcript.txt"
    raw = tmp_path / "raw.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(BRIDGE_PATH),
            "--transcript",
            str(transcript),
            "--raw",
            str(raw),
        ],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return (
        proc.returncode,
        proc.stderr,
        transcript.read_text(encoding="utf-8") if transcript.exists() else "",
        raw.read_text(encoding="utf-8") if raw.exists() else "",
    )


def test_bridge_handles_clean_eof_on_empty_stdin(tmp_path: Path) -> None:
    """EOF on empty stdin → zero exit, empty files, no crash."""
    rc, err, transcript, raw = _run_bridge(tmp_path, "")
    assert rc == 0, f"stderr={err!r}"
    assert transcript == ""
    assert raw == ""


def test_bridge_handles_eof_after_partial_json_line(tmp_path: Path) -> None:
    """EOF mid-JSON (no closing brace) → line preserved, no crash."""
    truncated = '{"type": "thread.started", "thread_id": "abc"'  # no newline, no `}`
    rc, err, transcript, raw = _run_bridge(tmp_path, truncated)
    assert rc == 0, f"stderr={err!r}"
    # Raw must always contain exactly what came in.
    assert raw == truncated
    # Because the JSON never closed, the parser falls back to writing the raw
    # line to the transcript. The bridge adds a trailing newline when the
    # incoming line had none.
    assert truncated in transcript
    assert transcript.endswith("\n")


def test_bridge_preserves_malformed_json_line(tmp_path: Path) -> None:
    """Edge: a line that starts with `{` but isn't valid JSON falls through."""
    bad = '{"type": broken, "msg":}\n'
    rc, err, transcript, raw = _run_bridge(tmp_path, bad)
    assert rc == 0, f"stderr={err!r}"
    assert raw == bad
    # Transcript keeps the raw line verbatim (no trailing newline added — the
    # original line already ended with \n).
    assert transcript == bad


def test_bridge_passes_through_non_json_line(tmp_path: Path) -> None:
    """Edge: plain stdout (no `{` prefix) must be forwarded to the transcript."""
    line = "plain text noise from stderr\n"
    rc, err, transcript, raw = _run_bridge(tmp_path, line)
    assert rc == 0, f"stderr={err!r}"
    assert raw == line
    assert transcript == line


def test_bridge_formats_turn_failed_as_error_line(tmp_path: Path) -> None:
    """Error payload path: turn.failed → transcript marked with [error]."""
    event = {"type": "turn.failed", "error": "429 rate limit"}
    stdin = json.dumps(event) + "\n"
    rc, err, transcript, raw = _run_bridge(tmp_path, stdin)
    assert rc == 0, f"stderr={err!r}"
    cleaned = _strip_ansi(transcript)
    # The format helper emits "[HH:MM:SS error] 429 rate limit".
    assert "error" in cleaned.lower()
    assert "429 rate limit" in cleaned
    # Raw must retain the exact JSON line.
    assert json.loads(raw.strip()) == event


def test_bridge_formats_agent_message_into_transcript(tmp_path: Path) -> None:
    """Happy path: item.completed/agent_message → text appears in transcript."""
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "Hello from Codex"},
    }
    stdin = json.dumps(event) + "\n"
    rc, _err, transcript, raw = _run_bridge(tmp_path, stdin)
    assert rc == 0
    assert "Hello from Codex" in transcript
    assert json.loads(raw.strip()) == event


def test_bridge_can_echo_rendered_output_to_stdout(tmp_path: Path) -> None:
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "Visible in pane"},
    }
    transcript = tmp_path / "transcript.txt"
    raw = tmp_path / "raw.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(BRIDGE_PATH),
            "--transcript",
            str(transcript),
            "--raw",
            str(raw),
            "--echo-stdout",
        ],
        input=json.dumps(event) + "\n",
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Visible in pane" in proc.stdout
    assert "Visible in pane" in transcript.read_text(encoding="utf-8")


def test_bridge_main_handles_keyboard_interrupt_cleanly(
    tmp_path: Path, monkeypatch
) -> None:
    """KeyboardInterrupt inside the stdin loop should return 130 without crashing."""
    transcript = tmp_path / "transcript.txt"
    raw = tmp_path / "raw.jsonl"

    class _InterruptingStdin:
        def __iter__(self):
            return self

        def __next__(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(BRIDGE_PATH),
            "--transcript",
            str(transcript),
            "--raw",
            str(raw),
            "--echo-stdout",
        ],
    )
    monkeypatch.setattr(sys, "stdin", _InterruptingStdin())

    rc = BRIDGE.main()

    assert rc == 130
    transcript_text = transcript.read_text(encoding="utf-8")
    assert "interrupted by operator" in _strip_ansi(transcript_text)


# ---------------------------------------------------------------------------
# Unit-level — format_event / stringish / truncate_block
# ---------------------------------------------------------------------------


def test_format_event_unknown_type_returns_empty_string() -> None:
    """Unknown / missing type → no formatting, no crash."""
    assert BRIDGE.format_event({}) == ""
    assert BRIDGE.format_event({"type": "something.unseen"}) == ""


def test_format_event_turn_failed_prefers_error_over_message() -> None:
    text = BRIDGE.format_event(
        {"type": "turn.failed", "error": "boom", "message": "ignored"}
    )
    cleaned = _strip_ansi(text)
    assert "boom" in cleaned
    assert "ignored" not in cleaned


def test_format_event_turn_aborted_falls_back_through_fields() -> None:
    """reason / error / 'turn aborted' default chain — covers stringish branches."""
    # When neither `message` nor `reason` nor `error` is given, the default literal wins.
    default = BRIDGE.format_event({"type": "turn.aborted"})
    assert "turn aborted" in _strip_ansi(default)

    # `reason` wins over the default and over `error` per the code order
    # (message → reason → error → default).
    reason = BRIDGE.format_event(
        {"type": "turn.aborted", "reason": "user_quit", "error": "ignored"}
    )
    cleaned_reason = _strip_ansi(reason)
    assert "user_quit" in cleaned_reason
    assert "ignored" not in cleaned_reason


def test_truncate_block_collapses_long_output() -> None:
    short = "line-a\nline-b\n"
    long = "\n".join(f"line-{i}" for i in range(20))
    short_rendered = _strip_ansi(BRIDGE.truncate_block(short))
    long_rendered = _strip_ansi(BRIDGE.truncate_block(long))

    assert "line-a" in short_rendered
    assert "line-b" in short_rendered
    # Long: only the first five lines + an ellipsis line survive.
    assert "line-0" in long_rendered
    assert "line-4" in long_rendered
    assert "line-19" not in long_rendered
    assert "... (20 lines)" in long_rendered


def test_stringish_unwraps_dict_message_field() -> None:
    """Known-key dict unwrapping — the three fields the error renderer relies on."""
    assert BRIDGE.stringish({"message": "hi"}) == "hi"
    assert BRIDGE.stringish({"error": "err"}) == "err"
    assert BRIDGE.stringish({"detail": "d"}) == "d"


def test_stringish_priority_message_beats_error_beats_detail() -> None:
    """Explicit priority order — message wins, then error, then detail."""
    assert BRIDGE.stringish({"message": "m", "error": "e", "detail": "d"}) == "m"
    assert BRIDGE.stringish({"error": "e", "detail": "d"}) == "e"


def test_stringish_handles_primitives_and_lists() -> None:
    assert BRIDGE.stringish(None) == ""
    assert BRIDGE.stringish("hi") == "hi"
    assert BRIDGE.stringish(42) == "42"
    assert BRIDGE.stringish(True) == "True"
    assert BRIDGE.stringish(["a", "b"]) == "a, b"


# ---------------------------------------------------------------------------
# Argparse — missing required flags must fail loudly (regression: no silent
# fallback to /dev/null that would hide bridge crashes in production).
# ---------------------------------------------------------------------------


def test_bridge_rejects_missing_required_arguments() -> None:
    proc = subprocess.run(
        [sys.executable, str(BRIDGE_PATH)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert proc.returncode != 0
    assert "--transcript" in proc.stderr or "--transcript" in proc.stdout


def test_bridge_creates_raw_parent_directory(tmp_path: Path) -> None:
    """main() must mkdir(parents=True) for the raw path — regression guard."""
    transcript = tmp_path / "out" / "transcript.txt"
    raw = tmp_path / "out" / "nested" / "raw.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    # raw parent is intentionally missing to prove the bridge creates it.
    assert not raw.parent.exists()

    proc = subprocess.run(
        [
            sys.executable,
            str(BRIDGE_PATH),
            "--transcript",
            str(transcript),
            "--raw",
            str(raw),
        ],
        input="",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    assert raw.parent.is_dir()
