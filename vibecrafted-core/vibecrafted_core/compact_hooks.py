from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .runtime_paths import vibecrafted_home


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_hook_input(stdin: str) -> dict[str, object]:
    try:
        payload = json.loads(stdin or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def hook_agent() -> str:
    return os.environ.get("VIBECRAFTED_COMPACT_AGENT") or os.environ.get(
        "VIBECRAFTED_AGENT", "claude"
    )


def emit_postcompact_context(text: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostCompact",
                "additionalContext": text,
            }
        },
        ensure_ascii=False,
    )


def append_journal(
    event: str, agent: str, session_id: str, status: str, detail: str
) -> None:
    journal = Path(
        os.environ.get(
            "VIBECRAFTED_COMPACT_JOURNAL",
            str(vibecrafted_home() / "runtime" / "compact-hooks.jsonl"),
        )
    ).expanduser()
    try:
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "ts": utc_now(),
                        "event": event,
                        "agent": agent,
                        "session_id": session_id,
                        "status": status,
                        "detail": detail,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
    except OSError:
        return


def run_aicx_extract(agent: str, session_id: str, *, user_only: bool = False) -> None:
    if not shutil.which("aicx"):
        return
    command = [
        "aicx",
        "extract",
        "--agent",
        agent,
        "--session",
        session_id,
        "--conversation",
    ]
    if user_only:
        command.append("--user-only")
    subprocess.run(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    )


def precompact(stdin: str) -> int:
    payload = load_hook_input(stdin)
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return 0
    agent = hook_agent()
    if not shutil.which("aicx"):
        append_journal("precompact", agent, session_id, "skipped", "aicx not found")
        return 0
    run_aicx_extract(agent, session_id)
    run_aicx_extract(agent, session_id, user_only=True)
    append_journal(
        "precompact", agent, session_id, "extracted", "conversation and user-only"
    )
    return 0


def extract_candidates(agent: str, session_id: str) -> list[Path]:
    candidates = [
        Path.home() / ".aicx" / "extracts" / agent / f"{session_id}_conversation.md",
        Path.home() / ".aicx" / "extracts" / agent / f"{session_id}.md",
    ]
    if agent != "claude":
        candidates.extend(
            [
                Path.home()
                / ".aicx"
                / "extracts"
                / "claude"
                / f"{session_id}_conversation.md",
                Path.home() / ".aicx" / "extracts" / "claude" / f"{session_id}.md",
            ]
        )
    return candidates


def strip_skill_bodies(lines: list[str]) -> list[str]:
    output: list[str] = []
    in_skill = False
    for line in lines:
        if line.startswith("Base directory for this skill: "):
            skill_name = Path(line.strip().rsplit("/", 1)[-1]).name or "unknown"
            output.append(f"[SKILL BODY STRIPPED: {skill_name}]\n")
            in_skill = True
            continue
        if in_skill and line.strip() == "````":
            in_skill = False
            continue
        if not in_skill:
            output.append(line)
    return output


def dedupe_adjacent(lines: list[str]) -> list[str]:
    output: list[str] = []
    previous: str | None = None
    for line in lines:
        if line == previous:
            continue
        output.append(line)
        previous = line
    return output


def clean_context(text: str) -> str:
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)


def fallback(reason: str, extract_path: Path | None = None) -> str:
    extract = str(extract_path) if extract_path else "<none>"
    return emit_postcompact_context(
        "\n".join(
            [
                f"POSTCOMPACT RECALL DEGRADED: {reason}",
                "",
                "Your turn-by-turn memory was just compacted and rich AICX recall could not be built.",
                "Before acting on earlier session state, recover context explicitly:",
                f"- inspect the raw extract if it exists: {extract}",
                "- run: loct context --full --markdown",
                "- run: aicx intents -p <project> --limit 20 --emit markdown",
                "- fallback: aicx search --no-semantic -p <project> 'recent intent agent claims verified outcomes unresolved human decisions'",
                "- run: vibecrafted loop status",
                "",
                "Do not treat the lossy compact summary as full temporal truth.",
            ]
        )
    )


def postcompact(stdin: str) -> int:
    payload = load_hook_input(stdin)
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        print("{}")
        return 0
    agent = hook_agent()
    candidates = extract_candidates(agent, session_id)
    extract = next((candidate for candidate in candidates if candidate.is_file()), None)
    if extract is None:
        print(
            fallback(
                f"aicx extract not found for agent={agent}, session={session_id}",
                candidates[0],
            )
        )
        return 0

    raw_lines = extract.read_text(encoding="utf-8", errors="replace").splitlines(
        keepends=True
    )
    if not raw_lines:
        print(fallback("extract is empty", extract))
        return 0

    lines = raw_lines
    if os.environ.get("AICX_RECALL_STRIP_SKILLS", "1") == "1":
        lines = strip_skill_bodies(lines)
    if os.environ.get("AICX_RECALL_DEDUP", "1") == "1":
        lines = dedupe_adjacent(lines)

    chunk_size = max(int(os.environ.get("AICX_RECALL_CHUNK_LINES", "400") or "400"), 1)
    recall_root = Path(
        os.environ.get(
            "VIBECRAFTED_RECALL_DIR",
            str(Path(os.environ.get("TMPDIR", "/tmp")) / "vibecrafted-aicx-recall"),
        )
    ).expanduser()
    chunk_dir = recall_root / agent / session_id
    try:
        chunk_dir.mkdir(parents=True, exist_ok=True)
        for stale in chunk_dir.glob("chunk-*"):
            if stale.is_file():
                stale.unlink()
        chunks = [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]
        if not chunks:
            print(fallback("chunking produced no recall chunks", extract))
            return 0
        for idx, chunk in enumerate(chunks):
            (chunk_dir / f"chunk-{idx:03d}").write_text(
                "".join(chunk),
                encoding="utf-8",
            )
    except OSError as exc:
        print(fallback(f"could not build recall chunks: {exc}", extract))
        return 0

    reduction_pct = 0
    if raw_lines:
        reduction_pct = 100 - (len(lines) * 100 // len(raw_lines))
    last_chunk = chunk_dir / f"chunk-{len(chunks) - 1:03d}"
    context = "\n".join(
        [
            f"Session {session_id} was just compacted. AICX recall is available as bounded chunks.",
            "",
            "Context discipline after compaction:",
            "- LOOP is the foundation: run or inspect vibecrafted loop status before claiming continuity.",
            "- Loctree + AICX are the constant context: refresh with loct context --full --markdown and aicx intents/search when earlier turns matter.",
            f"- Earlier recall chunks: {chunk_dir}/chunk-000 through {last_chunk} ({len(chunks)} chunks, skill-stripped + deduped, {reduction_pct}% smaller).",
            f"- Full raw extract: {extract}",
            "",
            "Most recent recovered context is already loaded below. Read older chunks only when the next task touches earlier decisions, claims, or unresolved operator choices.",
            "",
            f"== VERBATIM MOST-RECENT CONTEXT ({last_chunk.name}) ==",
            last_chunk.read_text(encoding="utf-8", errors="replace"),
            "== END MOST-RECENT CONTEXT ==",
        ]
    )
    print(emit_postcompact_context(clean_context(context)))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vibecrafted compact-hook")
    parser.add_argument("event", choices=("precompact", "postcompact"))
    args = parser.parse_args(argv)
    stdin = sys.stdin.read()
    if args.event == "precompact":
        return precompact(stdin)
    return postcompact(stdin)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
