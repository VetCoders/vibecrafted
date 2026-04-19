#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF_USAGE'
Usage: await.sh [claude|codex|gemini] [--last] [--run-id <id>] [--research] [--describe] [--interval <sec>] [--timeout <sec>] [targets...]

Targets may be:
  - *.meta.json
  - *.transcript.log
  - *.md report path
  - generated launcher *.sh

Examples:
  await.sh codex --last
  await.sh claude --run-id impl-123456
  await.sh --research --run-id rsch-123456
  await.sh --describe /tmp/vc-research-claude.sh /tmp/vc-research-codex.sh /tmp/vc-research-gemini.sh
  await.sh /path/to/report.meta.json /path/to/other.meta.json
EOF_USAGE
}

root="${VIBECRAFTED_ROOT:-$(spawn_repo_root)}"
reports_dir="$(spawn_store_dir "$root")/reports"
export VIBECRAFTED_AWAIT_REPORTS_DIR="$reports_dir"

exec python3 - "$@" <<'PY'
import json
import os
import shlex
import sys
import time
from pathlib import Path


def usage() -> None:
    print(
        "Usage: await.sh [claude|codex|gemini] [--last] [--run-id <id>] "
        "[--research] [--describe] [--interval <sec>] [--timeout <sec>] [targets...]"
    )


argv = sys.argv[1:]
agent = ""
use_last = False
describe_only = False
research_mode = False
run_id = ""
interval = 30
timeout = 0
targets: list[str] = []

i = 0
while i < len(argv):
    arg = argv[i]
    if arg in {"claude", "codex", "gemini"} and not agent:
        agent = arg
    elif arg == "--last":
        use_last = True
    elif arg == "--describe":
        describe_only = True
    elif arg == "--research":
        research_mode = True
    elif arg == "--run-id":
        i += 1
        if i >= len(argv):
            print("Missing value for --run-id", file=sys.stderr)
            sys.exit(1)
        run_id = argv[i]
    elif arg == "--interval":
        i += 1
        if i >= len(argv):
            print("Missing value for --interval", file=sys.stderr)
            sys.exit(1)
        interval = max(int(argv[i]), 1)
    elif arg == "--timeout":
        i += 1
        if i >= len(argv):
            print("Missing value for --timeout", file=sys.stderr)
            sys.exit(1)
        timeout = max(int(argv[i]), 0)
    elif arg in {"-h", "--help", "help"}:
        usage()
        sys.exit(0)
    else:
        targets.append(arg)
    i += 1

reports_dir = Path(os.environ.get("VIBECRAFTED_AWAIT_REPORTS_DIR", "")).expanduser()


def parse_launcher(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {"launcher": str(path)}
    if not path.is_file():
        return payload
    wanted = {"meta", "report", "transcript", "SPAWN_RUN_ID", "SPAWN_AGENT"}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        key = key.strip()
        if key not in wanted:
            continue
        raw = raw.strip()
        try:
            parts = shlex.split(raw)
            value = parts[0] if parts else raw
        except ValueError:
            value = raw.strip("'\"")
        if key == "meta":
            payload["meta"] = value
        elif key == "report":
            payload["report"] = value
        elif key == "transcript":
            payload["transcript"] = value
        elif key == "SPAWN_RUN_ID":
            payload["run_id"] = value
        elif key == "SPAWN_AGENT":
            payload["agent"] = value
    return payload


def backfill_from_meta(descriptor: dict[str, str]) -> dict[str, str]:
    meta_path = descriptor.get("meta", "")
    if not meta_path:
        return descriptor
    path = Path(meta_path)
    if not path.is_file():
        return descriptor
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return descriptor
    for key in ("agent", "status", "mode", "model", "input", "report", "transcript", "launcher", "exit_code", "updated_at", "run_id"):
        value = data.get(key)
        if value is None:
            continue
        descriptor[key] = str(value)
    return descriptor


def descriptor_from_target(raw: str) -> dict[str, str]:
    path = Path(raw).expanduser()
    desc: dict[str, str] = {"source": raw}
    if raw.endswith(".meta.json"):
        desc["meta"] = str(path)
    elif raw.endswith(".transcript.log"):
        desc["transcript"] = str(path)
        desc["meta"] = str(path).replace(".transcript.log", ".meta.json")
    elif raw.endswith(".md"):
        desc["report"] = str(path)
        desc["meta"] = str(path).rsplit(".md", 1)[0] + ".meta.json"
    elif raw.endswith(".sh"):
        desc.update(parse_launcher(path))
    else:
        desc["meta"] = str(path)
    return backfill_from_meta(desc)


def list_meta_files() -> list[Path]:
    if not reports_dir.is_dir():
        return []
    return sorted(reports_dir.glob("*.meta.json"))


def load_meta(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def descriptors_for_last() -> list[dict[str, str]]:
    metas = list_meta_files()
    if research_mode:
        last_research = None
        for meta_path in reversed(metas):
            payload = load_meta(meta_path)
            if not payload:
                continue
            if payload.get("skill_code") == "rsch":
                last_research = str(payload.get("run_id") or "")
                if last_research:
                    break
        if last_research:
            return descriptors_for_run_id(last_research)
        return []

    if agent:
        for meta_path in reversed(metas):
            payload = load_meta(meta_path)
            if not payload:
                continue
            if payload.get("agent") == agent:
                return [backfill_from_meta({"meta": str(meta_path)})]
        return []

    if metas:
        return [backfill_from_meta({"meta": str(metas[-1])})]
    return []


def descriptors_for_run_id(target_run_id: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for meta_path in list_meta_files():
        payload = load_meta(meta_path)
        if not payload:
            continue
        if str(payload.get("run_id") or "") == target_run_id:
            matches.append(backfill_from_meta({"meta": str(meta_path)}))
    return matches


def resolve_descriptors() -> list[dict[str, str]]:
    if targets:
        return [descriptor_from_target(t) for t in targets]
    if run_id:
        return descriptors_for_run_id(run_id)
    if use_last or (not targets and not run_id):
        return descriptors_for_last()
    return []


def print_card(items: list[dict[str, str]]) -> None:
    print("⚒  Await")
    print("─────────────────────────────────────────")
    if reports_dir:
        print(f"  reports: {reports_dir}")
    print(f"  tracks:  {len(items)}")
    print("─────────────────────────────────────────")
    for idx, item in enumerate(items, start=1):
        print()
        print(f"--- Track {idx} ---")
        for key in ("agent", "run_id", "status", "mode", "model", "meta", "report", "transcript", "launcher", "exit_code", "updated_at"):
            value = item.get(key, "")
            if value:
                print(f"  {key:10s} {value}")


def all_completed(items: list[dict[str, str]]) -> tuple[bool, list[dict[str, str]]]:
    resolved: list[dict[str, str]] = []
    for item in items:
        current = backfill_from_meta(dict(item))
        meta_path = current.get("meta", "")
        if not meta_path or not Path(meta_path).is_file():
            return False, items
        exit_code = current.get("exit_code", "")
        if exit_code in {"", "None"}:
            return False, items
        resolved.append(current)
    return True, resolved


deadline = time.time() + timeout if timeout > 0 else None
items = resolve_descriptors()

if describe_only:
    if not items:
        print("No matching launchers or metadata found yet.", file=sys.stderr)
        sys.exit(1)
    print_card(items)
    sys.exit(0)

if not items:
    print("No matching launchers or metadata found yet. Waiting...", file=sys.stderr)

while True:
    items = resolve_descriptors()
    if items:
        done, resolved = all_completed(items)
        if done:
            print_card(resolved)
            all_zero = all(str(item.get("exit_code", "1")) == "0" for item in resolved)
            sys.exit(0 if all_zero else 1)
    if deadline is not None and time.time() >= deadline:
        print("Timed out while waiting for metadata completion.", file=sys.stderr)
        sys.exit(124)
    time.sleep(interval)
PY
