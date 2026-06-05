#!/usr/bin/env bash

spawn_control_plane_script() {
  local candidate
  for candidate in \
    "${VIBECRAFTED_ROOT:-}/scripts/control_plane_state.py" \
    "${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-${HOME}/.local/share}/vibecrafted/tools}/vibecrafted-current/scripts/control_plane_state.py" \
    "$(spawn_repo_root 2>/dev/null)/scripts/control_plane_state.py"
  do
    [[ -n "$candidate" && -f "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    return 0
  done
  return 1
}

spawn_sync_control_plane() {
  local script_path
  script_path="$(spawn_control_plane_script 2>/dev/null || true)"
  [[ -n "$script_path" ]] || return 0
  python3 "$script_path" sync >/dev/null 2>&1 || true
}

spawn_find_meta_for_run_id() {
  local reports_dir="$1"
  local target_run_id="$2"

  python3 - "$reports_dir" "$target_run_id" <<'PY'
import json
import os
import sys

reports_dir, target_run_id = sys.argv[1:3]
if not os.path.isdir(reports_dir):
    raise SystemExit(0)

for fname in sorted(os.listdir(reports_dir), reverse=True):
    if not fname.endswith(".meta.json"):
        continue
    fpath = os.path.join(reports_dir, fname)
    try:
        with open(fpath, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        continue
    if payload.get("run_id") == target_run_id:
        print(fpath)
        raise SystemExit(0)
PY
}

spawn_read_meta_field() {
  local meta_path="$1"
  local field_name="$2"

  python3 - "$meta_path" "$field_name" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)

value = payload.get(sys.argv[2], "")
if value is None:
    value = ""
print(value, end="")
PY
}

spawn_write_meta() {
  local meta_path="$1"
  local status="$2"
  local agent="$3"
  local mode="$4"
  local root="$5"
  local input_ref="$6"
  local report="$7"
  local transcript="$8"
  local launcher="$9"
  local model="${10:-__NONE__}"
  local prompt_id="${SPAWN_PROMPT_ID:-}"
  local run_id="${SPAWN_RUN_ID:-}"
  local loop_nr="${SPAWN_LOOP_NR:-0}"
  local skill_code="${SPAWN_SKILL_CODE:-}"
  local framework_version
  framework_version="$(spawn_framework_version)"

  python3 - "$meta_path" "$status" "$agent" "$mode" "$root" "$input_ref" "$report" "$transcript" "$launcher" "$model" "$prompt_id" "$run_id" "$loop_nr" "$skill_code" "$framework_version" <<'PY'
import datetime as dt
import json
import sys

meta_path, status, agent, mode, root, input_ref, report, transcript, launcher, model, prompt_id, run_id, loop_nr, skill_code, framework_version = sys.argv[1:16]
try:
    loop_nr_value = int(loop_nr)
except ValueError:
    loop_nr_value = loop_nr
payload = {
    "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "status": status,
    "agent": agent,
    "mode": mode,
    "root": root,
    "input": input_ref,
    "report": report,
    "transcript": transcript,
    "launcher": launcher,
    "prompt_id": prompt_id,
    "run_id": run_id,
    "loop_nr": loop_nr_value,
    "skill_code": skill_code,
    "framework_version": framework_version,
    "exit_code": None,
    # launcher_pid is set by the launcher itself once it starts (see
    # spawn_update_meta_pid). Dead launcher_pid → ghost state, out.
    "launcher_pid": None,
    "liveness": "pid_pending",
}
if model != "__NONE__":
    payload["model"] = model
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  spawn_sync_control_plane
}

spawn_update_meta_pid() {
  # Called by the generated launcher as soon as it starts. Writes the
  # launcher's own PID into the meta.json so the watcher and the
  # spawn-time GC can validate liveness via `kill -0`. Dead PID = ghost.
  local meta_path="$1"
  local pid="$2"

  [[ -f "$meta_path" ]] || return 0
  [[ -n "$pid" ]] || return 0

  python3 - "$meta_path" "$pid" <<'PY'
import json
import sys

meta_path, pid = sys.argv[1:3]
try:
    with open(meta_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(0)

try:
    payload["launcher_pid"] = int(pid)
    payload["liveness"] = "pid_alive"
except (TypeError, ValueError):
    payload["launcher_pid"] = None
    payload["liveness"] = "unknown_legacy"

with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

spawn_pid_alive() {
  # Returns 0 if pid is alive, 1 if dead or invalid. Uses kill -0 semantics;
  # treats permission denied as alive (kernel says: exists, not yours).
  local pid="$1"
  [[ -n "$pid" && "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

spawn_reap_dead_run() {
  # Given a meta.json whose launcher_pid is dead, flip status to "ghost",
  # release any lock file referenced in the meta, and sync control plane.
  # Idempotent — callable from spawn-time GC and from watcher heartbeat.
  local meta_path="$1"
  [[ -f "$meta_path" ]] || return 0

  python3 - "$meta_path" <<'PY'
import datetime as dt
import json
import os
import sys

meta_path = sys.argv[1]
try:
    with open(meta_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(0)

status = payload.get("status")
if status not in ("launching", "running", "in-progress"):
    sys.exit(0)

now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
payload["status"] = "ghost"
payload["updated_at"] = now_iso
payload.setdefault("completed_at", now_iso)
payload.setdefault("exit_code", 137)  # canonical kill-killed code, for parity
payload["ghost_reason"] = "launcher_pid dead at reap"
payload["liveness"] = "pid_dead"

with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

# Best-effort lock cleanup — meta may reference a lock path.
lock_path = payload.get("run_lock") or payload.get("lock")
if lock_path and os.path.isfile(lock_path):
    try:
        os.unlink(lock_path)
    except OSError:
        pass
PY
  spawn_sync_control_plane
}

spawn_mark_unknown_liveness() {
  # Older live meta without launcher_pid is not safe to reap. Mark it
  # explicitly so dashboards stop pretending it is verified-live.
  local meta_path="$1"
  [[ -f "$meta_path" ]] || return 0

  python3 - "$meta_path" <<'PY'
import datetime as dt
import json
import sys

meta_path = sys.argv[1]
try:
    with open(meta_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(0)

if payload.get("status") not in ("launching", "running", "in-progress"):
    sys.exit(0)

pid = payload.get("launcher_pid")
if pid not in (None, "", "None"):
    sys.exit(0)

payload["liveness"] = "unknown_legacy"
payload.setdefault("liveness_reason", "live status without launcher_pid")
payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  spawn_sync_control_plane
}

spawn_gc_dead_runs() {
  # Scan a reports directory for meta.json files whose status is live
  # (launching/running/in-progress) but whose launcher_pid is dead.
  # Flip those to ghost. Safe to call at spawn-time before taking locks.
  local reports_dir="$1"
  [[ -d "$reports_dir" ]] || return 0

  local meta_path pid_value
  while IFS= read -r -d '' meta_path; do
    pid_value="$(spawn_read_meta_field "$meta_path" "launcher_pid")"
    # Safe reap contract: only reap when we can VERIFY the PID is dead.
    # Missing launcher_pid = pre-GC-era meta or older launcher that never
    # wrote it — we cannot prove death, so we leave it alone. This avoids
    # false-positive reaping of still-running agents whose meta was written
    # by an older launcher template. TTL-based cleanup is a separate path.
    if [[ -z "$pid_value" || "$pid_value" == "None" ]]; then
      spawn_mark_unknown_liveness "$meta_path"
      continue
    fi
    if ! spawn_pid_alive "$pid_value"; then
      spawn_reap_dead_run "$meta_path"
    fi
  done < <(find "$reports_dir" -type f -name '*.meta.json' -print0 2>/dev/null)
}

spawn_finish_meta() {
  local meta_path="$1"
  local status="$2"
  local exit_code="${3:-0}"

  python3 - "$meta_path" "$status" "$exit_code" <<'PY'
import datetime as dt
import json
import re
import sys

meta_path, status, exit_code = sys.argv[1:4]
with open(meta_path, "r", encoding="utf-8") as fh:
    payload = json.load(fh)
completed_at = dt.datetime.now(dt.timezone.utc)
started_at = payload.get("updated_at")
duration_s = None
if isinstance(started_at, str):
    try:
        started_dt = dt.datetime.fromisoformat(started_at)
    except ValueError:
        started_dt = None
    if started_dt is not None:
        duration_s = round((completed_at - started_dt).total_seconds(), 3)
payload["updated_at"] = completed_at.isoformat()
payload["completed_at"] = completed_at.isoformat()
payload["duration_s"] = duration_s
payload["status"] = status
payload["exit_code"] = int(exit_code)
payload["liveness"] = "terminal"

# Parse session_id from transcript (strip ANSI, match "session: <uuid>")
transcript_path = payload.get("transcript", "")
if transcript_path:
    try:
        with open(transcript_path, "r", errors="replace") as tf:
            raw = tf.read(64 * 1024)  # first 64KB is enough
        clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
        m = re.search(r'(?:^|\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]\s+)session: ([A-Za-z0-9][A-Za-z0-9-]*)', clean, re.MULTILINE)
        if m:
            payload["session_id"] = m.group(1)
    except (OSError, IOError):
        pass  # transcript not readable — skip silently

with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  spawn_sync_control_plane
}

spawn_finalize_artifacts() {
  local meta_path="$1"
  local report_path="${2:-}"
  local transcript_path="${3:-}"

  [[ -f "$meta_path" ]] || return 0

  python3 - "$meta_path" "$report_path" "$transcript_path" <<'PY'
import datetime as dt
import json
import os
import pathlib
import re
import sys

meta_path = pathlib.Path(sys.argv[1])
report_arg = sys.argv[2]
transcript_arg = sys.argv[3]

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SESSION_PATTERNS = [
    re.compile(r"(?:^|\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]\s+)session:\s*([A-Za-z0-9][A-Za-z0-9._:-]*)", re.MULTILINE),
    re.compile(r"\b(?:thread|conversation|session)[_-]?id['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9][A-Za-z0-9._:-]*)", re.IGNORECASE),
]
TOKEN_PATTERN = re.compile(
    r"tokens:\s*([0-9]+)\s+in(?:\s*\(([0-9]+)\s+cached\))?\s*/\s*([0-9]+)\s+out",
    re.IGNORECASE,
)
COST_PATTERNS = [
    re.compile(r"cost(?:_usd)?\s*[:=]\s*\$?([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE),
    re.compile(r"\$([0-9]+\.[0-9]+)\s*(?:usd)?", re.IGNORECASE),
]


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def clean_text(text: str) -> str:
    return ANSI.sub("", text)


def extract_session(text: str) -> str:
    clean = clean_text(text)
    for pattern in SESSION_PATTERNS:
        matches = pattern.findall(clean)
        if matches:
            return matches[-1]
    return ""


def extract_tokens(text: str) -> dict[str, int]:
    clean = clean_text(text)
    found = TOKEN_PATTERN.findall(clean)
    if not found:
        return {"input": 0, "cached_input": 0, "output": 0, "total": 0}
    input_tokens = cached_tokens = output_tokens = 0
    for raw_in, raw_cached, raw_out in found:
        input_tokens += int(raw_in)
        cached_tokens += int(raw_cached or 0)
        output_tokens += int(raw_out)
    return {
        "input": input_tokens,
        "cached_input": cached_tokens,
        "output": output_tokens,
        "total": input_tokens + output_tokens,
    }


def extract_cost(text: str):
    clean = clean_text(text)
    for pattern in COST_PATTERNS:
        matches = pattern.findall(clean)
        if matches:
            try:
                return round(float(matches[-1]), 6)
            except ValueError:
                pass
    return None


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}, text
    data: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return data, body


def render_frontmatter(data: dict[str, object]) -> str:
    order = [
        "run_id",
        "prompt_id",
        "agent",
        "skill",
        "model",
        "status",
        "date",
        "session_id",
        "artifact_stem",
        "artifact_kind",
        "repo_path",
        "tokens_input",
        "tokens_output",
        "tokens_total",
        "cost_usd",
    ]
    lines = ["---"]
    emitted = set()
    for key in order:
        if key in data:
            value = data.get(key)
            lines.append(f"{key}: {value if value not in (None, '') else 'unknown'}")
            emitted.add(key)
    for key in sorted(k for k in data if k not in emitted):
        value = data.get(key)
        lines.append(f"{key}: {value if value not in (None, '') else 'unknown'}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def slug_component(value: object, fallback: str) -> str:
    raw = str(value or fallback)
    raw = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")
    return raw or fallback


def same_file(left: pathlib.Path, right: pathlib.Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return left == right


def infer_artifact_store(meta: pathlib.Path):
    reports_dir = meta.parent
    if reports_dir.name != "reports":
        return None
    day_dir = reports_dir.parent
    if not re.fullmatch(r"[0-9]{4}_[0-9]{4}", day_dir.name):
        return None
    repo_dir = day_dir.parent
    org_dir = repo_dir.parent
    if not org_dir.name or not repo_dir.name:
        return None
    yyyy, mmdd = day_dir.name.split("_", 1)
    return {
        "reports_dir": reports_dir,
        "day": f"{yyyy}-{mmdd[:2]}-{mmdd[2:]}",
        "org": org_dir.name,
        "repo": repo_dir.name,
    }


def unique_stem(reports_dir: pathlib.Path, stem: str, sources: list[pathlib.Path], disambiguator: str) -> str:
    candidates = [stem]
    if disambiguator:
        candidates.append(f"{stem}-{slug_component(disambiguator, 'run')}")
    for index in range(2, 100):
        candidates.append(f"{stem}-{index}")

    suffixes = [".md", ".transcript.log", ".meta.json"]
    for candidate in candidates:
        blocked = False
        for suffix in suffixes:
            target = reports_dir / f"{candidate}{suffix}"
            if not target.exists():
                continue
            if any(source and source.exists() and same_file(target, source) for source in sources):
                continue
            blocked = True
            break
        if not blocked:
            return candidate
    return candidates[-1]


def move_artifact(source: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    if not str(source) or not source.is_file() or same_file(source, target):
        return source
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return target


def footer(marker: str, payload: dict[str, object]) -> str:
    return "\n".join(
        [
            "",
            f"<!-- vibecrafted-artifact-footer:{marker} -->",
            "---",
            "run_closure:",
            f"  run_id: {payload.get('run_id', 'unknown')}",
            f"  session_id: {payload.get('session_id') or 'unknown'}",
            f"  tokens_input: {payload.get('tokens_input', 0)}",
            f"  tokens_output: {payload.get('tokens_output', 0)}",
            f"  tokens_total: {payload.get('tokens_total', 0)}",
            f"  cost_usd: {payload.get('cost_usd') if payload.get('cost_usd') is not None else 'unknown'}",
            f"  status: {payload.get('status', 'unknown')}",
            f"  completed_at: {payload.get('completed_at', 'unknown')}",
            f"  resume_hint: \"{payload.get('resume_hint', '')}\"",
            "---",
            "",
        ]
    )


def normalize_markdown_artifact(path: pathlib.Path, payload: dict[str, object], *, fallback_body: str = "") -> None:
    text = read_text(path)
    if not text and fallback_body:
        text = fallback_body
    if not text:
        return
    fm, body = parse_frontmatter(text)
    fm.update(
        {
            "run_id": payload.get("run_id", "unknown"),
            "prompt_id": payload.get("prompt_id", "unknown"),
            "agent": payload.get("agent", "unknown"),
            "skill": payload.get("skill_code") or payload.get("skill") or "unknown",
            "model": payload.get("model", "unknown"),
            "status": payload.get("status", "unknown"),
            "date": payload.get("date", "unknown"),
            "session_id": payload.get("session_id") or "unknown",
            "artifact_stem": payload.get("artifact_stem", "unknown"),
            "artifact_kind": payload.get("artifact_kind", "unknown"),
            "repo_path": payload.get("root", "unknown"),
            "tokens_input": payload.get("tokens_input", 0),
            "tokens_output": payload.get("tokens_output", 0),
            "tokens_total": payload.get("tokens_total", 0),
            "cost_usd": payload.get("cost_usd") if payload.get("cost_usd") is not None else "unknown",
        }
    )
    marker = str(payload.get("run_id") or "unknown")
    new_text = render_frontmatter(fm) + body.rstrip() + "\n"
    if f"vibecrafted-artifact-footer:{marker}" not in new_text:
        new_text += footer(marker, payload)
    write_text(path, new_text)


try:
    payload = json.loads(read_text(meta_path))
except json.JSONDecodeError:
    raise SystemExit(0)

report_path = pathlib.Path(report_arg or payload.get("report", ""))
transcript_path = pathlib.Path(transcript_arg or payload.get("transcript", ""))
transcript_text = read_text(transcript_path) if str(transcript_path) else ""
report_text = read_text(report_path) if str(report_path) else ""
combined_text = "\n".join([transcript_text, report_text])

session_id = payload.get("session_id") or extract_session(combined_text)
tokens = extract_tokens(combined_text)
cost = extract_cost(combined_text)
completed_at = payload.get("completed_at") or dt.datetime.now(dt.timezone.utc).isoformat()
artifact_time = dt.datetime.now().astimezone().isoformat(timespec="seconds")
root = payload.get("root") or os.getcwd()
resume_hint = (
    f"Use `cd {root} && vc-resume --session {session_id}` to continue work with this Agent."
    if session_id
    else f"Use `cd {root} && vc-resume --session <session_id>` to continue work with this Agent."
)

payload["session_id"] = session_id or payload.get("session_id") or ""
payload["tokens_input"] = tokens["input"]
payload["tokens_cached_input"] = tokens["cached_input"]
payload["tokens_output"] = tokens["output"]
payload["tokens_total"] = tokens["total"]
payload["token_usage"] = tokens
payload["cost_usd"] = cost
payload["resume_hint"] = resume_hint
payload["artifact_contract"] = "vibecrafted.agent-artifact.v1"
payload["date"] = payload.get("date") or artifact_time

store = infer_artifact_store(meta_path)
if store:
    session_for_name = session_id or payload.get("session_id") or payload.get("run_id") or "unknown-session"
    stem = (
        f"{store['day']}_"
        f"{slug_component(store['org'], 'org')}_"
        f"{slug_component(store['repo'], 'repo')}_"
        f"{slug_component(session_for_name, 'session')}-report"
    )
    stem = unique_stem(
        store["reports_dir"],
        stem,
        [report_path, transcript_path, meta_path],
        str(payload.get("run_id") or ""),
    )
    final_report = store["reports_dir"] / f"{stem}.md"
    final_transcript = store["reports_dir"] / f"{stem}.transcript.log"
    final_meta = store["reports_dir"] / f"{stem}.meta.json"

    report_path = move_artifact(report_path, final_report)
    transcript_path = move_artifact(transcript_path, final_transcript)
    payload["report"] = str(report_path)
    payload["transcript"] = str(transcript_path)
    payload["meta"] = str(final_meta)
    payload["artifact_stem"] = stem
    payload["artifact_kind"] = "report"

payload["artifact_footer"] = {
    "run_id": payload.get("run_id", "unknown"),
    "session_id": payload.get("session_id") or "",
    "tokens_total": tokens["total"],
    "cost_usd": cost,
    "resume_hint": resume_hint,
}
payload.setdefault("completed_at", completed_at)
payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

target_meta_path = pathlib.Path(str(payload.get("meta") or meta_path))
target_meta_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
if not same_file(meta_path, target_meta_path) and meta_path.exists():
    meta_path.unlink()
meta_path = target_meta_path

footer_payload = {
    **payload,
    "tokens_input": tokens["input"],
    "tokens_output": tokens["output"],
    "tokens_total": tokens["total"],
    "cost_usd": cost,
}

if str(transcript_path):
    normalize_markdown_artifact(transcript_path, footer_payload)
if str(report_path) and report_path.exists() and report_path.suffix.lower() in {".md", ".markdown"}:
    normalize_markdown_artifact(report_path, footer_payload)
PY
  spawn_sync_control_plane
}
