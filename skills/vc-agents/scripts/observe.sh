#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF_USAGE
Usage: observe.sh [codex|claude|gemini] [--last|path-to-meta|path-to-transcript|path-to-report]

Examples:
  observe.sh codex --last
  observe.sh claude /path/to/report.meta.json
  observe.sh /path/to/transcript.log
EOF_USAGE
}

agent=""
target="--last"

while [[ $# -gt 0 ]]; do
  case "$1" in
    codex|claude|gemini)
      [[ -z "$agent" ]] || spawn_die "Agent already set to $agent"
      agent="$1"
      ;;
    --last)
      target="--last"
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
store_dir="$(spawn_store_dir "$root")/reports"
meta=""
report=""
transcript=""

if [[ "$target" == "--last" ]]; then
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
print(f"Status:     {data.get('status')}")
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
