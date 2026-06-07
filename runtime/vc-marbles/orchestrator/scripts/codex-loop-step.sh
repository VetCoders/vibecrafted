#!/usr/bin/env bash
set -euo pipefail

# State transition helper for Codex interactive Marbles.
# It never launches Codex. It only tells the current session whether to stop
# or continue with the same prompt.

usage() {
  cat <<'EOF'
Usage: codex-loop-step.sh [--state-file <path>] <status|next|complete|cancel> [options]

Commands:
  status                 Print current loop state
  next                   Advance to the next iteration and print the fixed prompt
  complete --promise X   Stop only if X equals completion_promise
  cancel                 Stop the loop unconditionally

Options:
  --state-file <path>    State file (default: .codex/marbles.local.md)
  --promise <text>       Promise text for complete
EOF
}

state_file=".codex/marbles.local.md"
command_name=""
promise=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-file)
      shift; [[ $# -gt 0 ]] || { echo "Missing value for --state-file" >&2; exit 1; }
      state_file="$1"
      ;;
    --promise)
      shift; [[ $# -gt 0 ]] || { echo "Missing value for --promise" >&2; exit 1; }
      promise="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    status|next|complete|cancel)
      [[ -z "$command_name" ]] || { echo "Only one command is allowed" >&2; exit 1; }
      command_name="$1"
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

[[ -n "$command_name" ]] || { usage >&2; exit 1; }
[[ -f "$state_file" ]] || { echo "No active Codex Marbles state: $state_file"; exit 2; }

frontmatter() {
  sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$state_file"
}

field() {
  local key="$1"
  frontmatter | awk -F: -v k="$key" '$1 == k {sub(/^[ \t]+/, "", $2); print $2; exit}' | sed 's/^"\(.*\)"$/\1/'
}

prompt_body() {
  awk '/^---$/{i++; next} i>=2' "$state_file"
}

set_field() {
  local key="$1"
  local value="$2"
  local tmp="${state_file}.tmp.$$"
  if grep -q "^${key}:" "$state_file"; then
    sed "s|^${key}:.*|${key}: ${value}|" "$state_file" > "$tmp"
  else
    awk -v key="$key" -v value="$value" '
      BEGIN { inserted=0; fence=0 }
      /^---$/ {
        fence++
        if (fence == 2 && !inserted) {
          print key ": " value
          inserted=1
        }
      }
      { print }
    ' "$state_file" > "$tmp"
  fi
  mv "$tmp" "$state_file"
}

active="$(field active || true)"
iteration="$(field iteration || true)"
max_iterations="$(field max_iterations || true)"
completion_promise="$(field completion_promise || true)"

case "$iteration" in ''|*[!0-9]*) echo "Invalid iteration in $state_file: $iteration" >&2; exit 1 ;; esac
case "$max_iterations" in ''|*[!0-9]*) echo "Invalid max_iterations in $state_file: $max_iterations" >&2; exit 1 ;; esac

case "$command_name" in
  status)
    printf 'active=%s\niteration=%s\nmax_iterations=%s\ncompletion_promise=%s\nstate_file=%s\n' \
      "$active" "$iteration" "$max_iterations" "$completion_promise" "$state_file"
    ;;

  cancel)
    set_field active false
    set_field stopped_at "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
    set_field stop_reason cancel
    printf 'Cancelled Codex Marbles at iteration %s.\n' "$iteration"
    ;;

  complete)
    if [[ "$completion_promise" == "null" || -z "$completion_promise" ]]; then
      set_field active false
      set_field stopped_at "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
      set_field stop_reason complete
      printf 'Completed Codex Marbles.\n'
      exit 0
    fi
    if [[ "$promise" != "$completion_promise" ]]; then
      printf 'Promise mismatch. Expected: %s\n' "$completion_promise" >&2
      exit 3
    fi
    set_field active false
    set_field stopped_at "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
    set_field stop_reason promise
    printf 'Completed Codex Marbles with <promise>%s</promise>.\n' "$completion_promise"
    ;;

  next)
    if [[ "$active" != "true" ]]; then
      printf 'STOP: Codex Marbles inactive.\n'
      exit 0
    fi
    if (( max_iterations > 0 && iteration >= max_iterations )); then
      set_field active false
      set_field stopped_at "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
      set_field stop_reason max_iterations
      printf 'STOP: max iterations reached (%s).\n' "$max_iterations"
      exit 0
    fi

    next_iteration=$((iteration + 1))
    set_field iteration "$next_iteration"
    set_field updated_at "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""

    printf 'CONTINUE: Codex Marbles iteration %s\n' "$next_iteration"
    if [[ "$completion_promise" != "null" && -n "$completion_promise" ]]; then
      printf 'Completion promise: <promise>%s</promise> only when completely true.\n' "$completion_promise"
    fi
    printf '\n--- PROMPT ---\n'
    prompt_body
    ;;
esac
