#!/usr/bin/env bash
set -euo pipefail

# Codex interactive Marbles setup.
#
# This mirrors setup-marbles-loop.sh, but targets Codex's interactive session
# model. It does not spawn `codex exec`. It writes a small state file that the
# active Codex session must obey through the command protocol in
# orchestrator/commands/codex-marbles-loop.md.

usage() {
  cat <<'EOF'
Usage: setup-codex-loop.sh [PROMPT...] [OPTIONS]

Arguments:
  PROMPT...                    Fixed prompt to repeat between iterations

Options:
  --state-file <path>          State file (default: .codex/marbles.local.md)
  --max-iterations <n>         Maximum iterations before auto-stop (0 = unlimited)
  --completion-promise <text>  Promise phrase that permits completion
  -h, --help                   Show help

This script only initializes state. The active Codex session performs the loop
by calling codex-loop-step.sh next|complete and continuing in the same session.
EOF
}

prompt_parts=()
state_file=".codex/marbles.local.md"
max_iterations=0
completion_promise="null"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-file)
      shift; [[ $# -gt 0 ]] || { echo "Missing value for --state-file" >&2; exit 1; }
      state_file="$1"
      ;;
    --max-iterations)
      shift; [[ $# -gt 0 ]] || { echo "Missing value for --max-iterations" >&2; exit 1; }
      max_iterations="$1"
      ;;
    --completion-promise)
      shift; [[ $# -gt 0 ]] || { echo "Missing value for --completion-promise" >&2; exit 1; }
      completion_promise="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      prompt_parts+=("$1")
      ;;
  esac
  shift
done

case "$max_iterations" in
  ''|*[!0-9]*)
    echo "--max-iterations must be a non-negative integer" >&2
    exit 1
    ;;
esac

prompt="${prompt_parts[*]:-}"
if [[ -z "$prompt" ]]; then
  echo "No prompt provided" >&2
  usage >&2
  exit 1
fi

mkdir -p "$(dirname "$state_file")"

if [[ "$completion_promise" != "null" ]]; then
  completion_yaml="$(python3 - "$completion_promise" <<'PY'
import json, sys
print(json.dumps(sys.argv[1]))
PY
)"
else
  completion_yaml="null"
fi

cat > "$state_file" <<EOF_STATE
---
active: true
runtime: codex-interactive
iteration: 1
max_iterations: $max_iterations
completion_promise: $completion_yaml
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
updated_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

$prompt
EOF_STATE

cat <<EOF
Codex Marbles activated.

State: $state_file
Iteration: 1
Max iterations: $(if (( max_iterations > 0 )); then echo "$max_iterations"; else echo "unlimited"; fi)
Completion promise: $(if [[ "$completion_promise" != "null" ]]; then echo "<promise>$completion_promise</promise>"; else echo "none"; fi)

Interactive protocol:
1. Work on the prompt in the current Codex session.
2. Before finalizing, run:
   bash orchestrator/scripts/codex-loop-step.sh --state-file "$state_file" next
3. If it prints PROMPT, continue instead of finalizing.
4. Complete only with:
   bash orchestrator/scripts/codex-loop-step.sh --state-file "$state_file" complete --promise "<text>"
EOF
