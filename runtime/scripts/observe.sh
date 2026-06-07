#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF_USAGE
Usage: observe.sh [codex|claude|gemini|agy|junie] [--last|--run-id <id>|path-to-meta|path-to-transcript|path-to-report]

Examples:
  observe.sh codex --last
  observe.sh codex --run-id impl-123456
  observe.sh claude /path/to/report.meta.json
  observe.sh /path/to/transcript.log
EOF_USAGE
}

agent=""
target="--last"
run_id=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    codex|claude|gemini|agy|junie)
      [[ -z "$agent" ]] || spawn_die "Agent already set to $agent"
      agent="$1"
      ;;
    --last)
      target="--last"
      ;;
    --run-id)
      shift
      [[ $# -gt 0 ]] || spawn_die "Missing value for --run-id"
      run_id="$1"
      target="--run-id"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      target="$1"
      ;;
  esac
  shift
done

root="$(spawn_repo_root)"
store_root="${VIBECRAFTED_AWAIT_STORE_DIR:-$(spawn_store_dir "$root")}"
store_dir="${VIBECRAFTED_AWAIT_REPORTS_DIR:-$store_root/reports}"
meta=""
report=""
transcript=""

if [[ -n "$run_id" ]]; then
  meta="$(python3 - "$store_root" "$run_id" <<'PY'
import json
import sys
from pathlib import Path

store_root = Path(sys.argv[1])
target_run_id = sys.argv[2]
patterns = [
    "reports/*.meta.json",
    "research/*/logs/*.meta.json",
    "research/*/reports/*.meta.json",
]
for pattern in patterns:
    for path in sorted(store_root.glob(pattern), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(payload.get("run_id") or "") == target_run_id:
            print(path)
            raise SystemExit(0)
PY
)"
  [[ -n "$meta" ]] || spawn_die "No metadata found for --run-id $run_id under $store_root. Use await --run-id $run_id to wait for metadata, or pass an explicit meta/report/transcript path."
elif [[ "$target" == "--last" ]]; then
  if [[ -n "$agent" ]]; then
    meta="$(find "$store_dir" -maxdepth 1 -type f -name "*_${agent}.meta.json" 2>/dev/null | sort | tail -n 1)"
    [[ -z "$meta" ]] && transcript="$(find "$store_dir" -maxdepth 1 -type f -name "*_${agent}.transcript.log" 2>/dev/null | sort | tail -n 1)"
  else
    meta="$(find "$store_dir" -maxdepth 1 -type f -name '*.meta.json' 2>/dev/null | sort | tail -n 1)"
    [[ -z "$meta" ]] && transcript="$(find "$store_dir" -maxdepth 1 -type f -name '*.transcript.log' 2>/dev/null | sort | tail -n 1)"
  fi
elif [[ -f "$target" ]]; then
  case "$target" in
    *.json)
      meta="$target"
      ;;
    *.transcript.log)
      transcript="$target"
      ;;
    *)
      report="$target"
      ;;
  esac
else
  usage
  exit 1
fi

if [[ -n "$meta" ]]; then
  python3 - "$meta" <<'PY'
import json
import sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    data = json.load(fh)
print(f"Agent:      {data.get('agent')}")
print(f"Run ID:     {data.get('run_id')}")
print(f"Status:     {data.get('status')}")
print(f"Liveness:   {data.get('liveness')}")
print(f"Updated:    {data.get('updated_at')}")
print(f"Mode:       {data.get('mode')}")
print(f"Model:      {data.get('model') or '-'}")
print(f"Input:      {data.get('input')}")
print(f"Report:     {data.get('report')}")
print(f"Transcript: {data.get('transcript')}")
print(f"Launcher:   {data.get('launcher')}")
print(f"Exit code:  {data.get('exit_code')}")
PY
  transcript="$(python3 - "$meta" <<'PY'
import json
import sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    data = json.load(fh)
print(data.get('transcript') or '')
PY
)"
  report="$(python3 - "$meta" <<'PY'
import json
import sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    data = json.load(fh)
print(data.get('report') or '')
PY
)"
fi

if [[ -n "$report" && -s "$report" ]]; then
  echo '--- report tail ---'
  tail -n 80 "$report"
  exit 0
fi

if [[ -n "$transcript" && -f "$transcript" ]]; then
  echo '--- transcript tail ---'
  tail -n 80 "$transcript"
  exit 0
fi

spawn_die 'No report or transcript found yet.'
