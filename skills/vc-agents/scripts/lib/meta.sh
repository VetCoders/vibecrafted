#!/usr/bin/env bash

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
}
if model != "__NONE__":
    payload["model"] = model
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
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

# Parse session_id from transcript (strip ANSI, match "session: <uuid>")
transcript_path = payload.get("transcript", "")
if transcript_path:
    try:
        with open(transcript_path, "r", errors="replace") as tf:
            raw = tf.read(64 * 1024)  # first 64KB is enough
        clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
        m = re.search(r'session: ([a-f0-9-]{8,})', clean)
        if m:
            payload["session_id"] = m.group(1)
    except (OSError, IOError):
        pass  # transcript not readable — skip silently

with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}
