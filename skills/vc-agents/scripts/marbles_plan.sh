#!/usr/bin/env bash
set -euo pipefail
# Marbles plan builder for --depth mode.
# Scans recent plan files and builds a convergence plan without leaking old loop reports.
# Outputs the plan file path to stdout.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

depth=""
root=""
agent="marbles"
run_id=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --agent"; agent="$1" ;;
    --run-id) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --run-id"; run_id="$1" ;;
    --depth) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --depth"; depth="$1" ;;
    --root)  shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --root";  root="$1" ;;
    -h|--help) printf 'Usage: marbles_plan.sh --depth <n> [--root <dir>] [--agent <name>] [--run-id <id>]\n'; exit 0 ;;
    *) spawn_die "Unknown argument: $1" ;;
  esac
  shift
done

[[ -n "$depth" ]] || spawn_die "Missing --depth"
root_dir="${root:-$(spawn_repo_root)}"
day_store="$(spawn_store_dir "$root_dir")"
store="${VIBECRAFTED_STORE_DIR:-$(spawn_marbles_store_dir "$root_dir")}"
artifacts_parent="$(dirname "$day_store")"

# Scan recent plan files across today and previous days.
# Marbles loops must not ingest prior loop reports; they only crawl prior plans.
plans=()
while IFS= read -r day_dir; do
  [[ -d "$day_dir/plans" ]] || continue
  while IFS= read -r plan; do
    [[ -n "$plan" ]] || continue
    plans+=("$plan")
    [[ ${#plans[@]} -ge $depth ]] && break
  done < <(find "$day_dir/plans" -name '*.md' \
    ! -name '*_marbles-*' ! -name 'marbles-*' \
    2>/dev/null | sort -r)
  [[ ${#plans[@]} -ge $depth ]] && break
done < <(find "$artifacts_parent" -maxdepth 1 -type d -name '20*' 2>/dev/null | sort -r)

# Build plan file
ts="$(spawn_timestamp)"
plan_file="$store/plans/${ts}_marbles-depth-${depth}.md"
prompt_id="marbles-depth-${depth}_${ts%%_*}"
mkdir -p "$store/plans"

{
  cat <<EOF_FRONTMATTER
---
agent: $agent
run_id: ${run_id:-marb-000000}
prompt_id: $prompt_id
started_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
model: pending
---

EOF_FRONTMATTER
  printf '# Marbles Convergence — Depth Crawl (%s plans)\n\n' "$depth"

  if [[ ${#plans[@]} -eq 0 ]]; then
    cat <<'EMPTY'
## Context

No recent plan files found. Starting from clean state.

## Task

Run quality gates on the current repository state.
Fix any issues found. Report what you fixed and what remains.
EMPTY
  else
    printf '## Context: Recent Plans\n'
    for plan in "${plans[@]}"; do
      printf '\n### %s\n\n' "$(basename "$plan")"
      head -80 "$plan" 2>/dev/null || printf '(not readable)\n'
      printf '\n---\n'
    done

    cat <<'TASK'

## Task

Review the above prior plans. Identify:
- Unfinished work (started but not completed)
- Quality regressions (things that were working and broke)
- Convergence gaps (things that need polish to ship)

Then fix the highest-priority issues you find.
Run quality gates after each fix.
TASK
  fi
} > "$plan_file"

printf '%s\n' "$plan_file"
