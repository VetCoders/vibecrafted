from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

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


def codex_sessions_dir() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    return Path(
        os.environ.get("CODEX_SESSIONS_DIR", str(codex_home / "sessions"))
    ).expanduser()


def normalize_path(value: str) -> str:
    if not value:
        return ""
    try:
        return str(Path(value).expanduser().resolve())
    except OSError:
        return str(Path(value).expanduser())


def hook_project_dir(payload: dict[str, object]) -> str:
    raw = str(
        payload.get("cwd")
        or payload.get("project_dir")
        or payload.get("repository")
        or os.environ.get("CODEX_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )
    return normalize_path(raw)


def session_meta_from_jsonl(path: Path) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if (
                    '"type":"session_meta"' not in line
                    and '"type": "session_meta"' not in line
                ):
                    continue
                event = json.loads(line)
                payload = event.get("payload") if isinstance(event, dict) else None
                if not isinstance(payload, dict):
                    continue
                return {
                    "id": str(payload.get("id") or "").strip(),
                    "cwd": normalize_path(str(payload.get("cwd") or "")),
                }
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def session_id_from_jsonl(path: Path) -> str:
    return session_meta_from_jsonl(path).get("id", "")


def latest_codex_session_path(project_dir: str = "") -> Path | None:
    root = codex_sessions_dir()
    if not root.is_dir():
        return None
    candidates = [path for path in root.glob("**/*.jsonl") if path.is_file()]
    if project_dir:
        scoped: list[Path] = []
        for path in candidates:
            meta = session_meta_from_jsonl(path)
            if meta.get("cwd") == project_dir:
                scoped.append(path)
        if scoped:
            candidates = scoped
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def codex_session_path_for(session_id: str) -> Path | None:
    if not session_id:
        return None
    root = codex_sessions_dir()
    if not root.is_dir():
        return None
    for path in root.glob(f"**/*{session_id}*.jsonl"):
        if path.is_file():
            return path
    for path in root.glob("**/*.jsonl"):
        if path.is_file() and session_id_from_jsonl(path) == session_id:
            return path
    return None


def resolve_session_id(payload: dict[str, object], agent: str) -> str:
    explicit = str(
        payload.get("session_id") or payload.get("conversation_id") or ""
    ).strip()
    if agent != "codex":
        return explicit

    transcript = str(
        payload.get("transcript_path")
        or payload.get("transcript")
        or payload.get("session_path")
        or ""
    ).strip()
    if transcript:
        transcript_path = Path(transcript).expanduser()
        if transcript_path.is_file():
            parsed = session_id_from_jsonl(transcript_path)
            if parsed:
                return parsed

    if explicit:
        session_path = codex_session_path_for(explicit)
        if session_path:
            parsed = session_id_from_jsonl(session_path)
            return parsed or explicit
        return explicit

    latest = latest_codex_session_path(hook_project_dir(payload))
    if latest:
        return session_id_from_jsonl(latest)
    return ""


def compact_state_path() -> Path:
    return Path(
        os.environ.get(
            "VIBECRAFTED_COMPACT_STATE",
            str(vibecrafted_home() / "runtime" / "compact-hook-state.json"),
        )
    ).expanduser()


def load_compact_state() -> dict[str, Any]:
    path = compact_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_compact_state(state: dict[str, Any]) -> None:
    path = compact_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        return


def delta_lines(
    agent: str,
    session_id: str,
    extract: Path,
    raw_lines: list[str],
    project_dir: str,
) -> tuple[list[str], int, int]:
    state = load_compact_state()
    sessions = state.setdefault("sessions", {})
    key = f"{agent}:{session_id}"
    previous = sessions.get(key, {}) if isinstance(sessions, dict) else {}
    previous_count = (
        int(previous.get("raw_line_count", 0) or 0) if isinstance(previous, dict) else 0
    )
    if previous_count < 0 or previous_count > len(raw_lines):
        previous_count = 0
    delta = raw_lines[previous_count:]
    if isinstance(sessions, dict):
        sessions[key] = {
            "agent": agent,
            "session_id": session_id,
            "project_dir": project_dir,
            "extract": str(extract),
            "raw_line_count": len(raw_lines),
            "updated_at": utc_now(),
        }
        save_compact_state(state)
    return delta, previous_count, len(raw_lines)


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
    agent = hook_agent()
    session_id = resolve_session_id(payload, agent)
    if not session_id:
        return 0
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
                "- for active workers: use vibecrafted <agent> await --run-id <id> and vibecrafted <agent> observe --run-id <id>; do not hand-roll sleep/ps/stat probes",
                "",
                "Do not treat the lossy compact summary as full temporal truth.",
            ]
        )
    )


def postcompact(stdin: str) -> int:
    payload = load_hook_input(stdin)
    agent = hook_agent()
    session_id = resolve_session_id(payload, agent)
    if not session_id:
        print("{}")
        return 0
    if shutil.which("aicx"):
        run_aicx_extract(agent, session_id)
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

    project_dir = hook_project_dir(payload)
    scoped_lines, previous_count, current_count = delta_lines(
        agent, session_id, extract, raw_lines, project_dir
    )
    lines = scoped_lines
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
            context = "\n".join(
                [
                    f"Session {session_id} was just compacted. AICX has no new delta since the previous compact recall.",
                    "",
                    "Context discipline after compaction:",
                    "- Keep continuity through AICX, not lossy compact memory.",
                    "- Dispatcher continuity: use vibecrafted <agent> await --run-id <id> and vibecrafted <agent> observe --run-id <id>; never replace them with manual sleep/ps/stat/git probes.",
                    f"- Full raw extract remains available: {extract}",
                    f"- Cursor: raw lines {previous_count}..{current_count} for project {project_dir or '<unknown>'}.",
                ]
            )
            print(emit_postcompact_context(clean_context(context)))
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
            f"Session {session_id} was just compacted. AICX delta recall is available as bounded chunks.",
            "",
            "Context discipline after compaction:",
            "- LOOP is the foundation: run or inspect vibecrafted loop status before claiming continuity.",
            "- Loctree + AICX are the constant context: refresh with loct context --full --markdown and aicx intents/search when earlier turns matter.",
            "- Dispatcher continuity: use vibecrafted <agent> await --run-id <id> and vibecrafted <agent> observe --run-id <id>; never replace them with manual sleep/ps/stat/git probes.",
            f"- Delta cursor: raw lines {previous_count}..{current_count} for project {project_dir or '<unknown>'}.",
            f"- Delta recall chunks: {chunk_dir}/chunk-000 through {last_chunk} ({len(chunks)} chunks, skill-stripped + deduped, {reduction_pct}% smaller).",
            f"- Full raw extract: {extract}",
            "",
            "Only the new recovered delta is loaded below. Remember: when the task seems to be touching earlier decisions, you obligatory must recall previous intents, claims, or unresolved operator choices via `aicx intents`.",
            "",
            f"== VERBATIM AICX DELTA ({last_chunk.name}) ==",
            last_chunk.read_text(encoding="utf-8", errors="replace"),
            "== END AICX DELTA ==",
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
