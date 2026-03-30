#!/usr/bin/env bash
set -euo pipefail
# Marbles plan builder for --depth mode.
# Scans recent session reports and builds a convergence plan.
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
store="${VIBECRAFT_STORE_DIR:-$(spawn_marbles_store_dir "$root_dir")}"
artifacts_parent="$(dirname "$day_store")"

# Scan recent reports across today and previous days
reports=()
while IFS= read -r day_dir; do
  [[ -d "$day_dir/reports" ]] || continue
  while IFS= read -r rpt; do
    [[ -n "$rpt" ]] || continue
    reports+=("$rpt")
    [[ ${#reports[@]} -ge $depth ]] && break
  done < <(find "$day_dir/reports" -name '*.md' \
    ! -name '*.meta.json' ! -name '*.transcript.log' ! -name '*CONVERGENCE*' ! -name '*_marbles-*' \
    2>/dev/null | sort -r)
  [[ ${#reports[@]} -ge $depth ]] && break
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
  printf '# Marbles Convergence — Depth Crawl (%s sessions)\n\n' "$depth"

  if [[ ${#reports[@]} -eq 0 ]]; then
    cat <<'EMPTY'
## Context

No recent session reports found. Starting from clean state.

## Task

Run quality gates on the current repository state.
Fix any issues found. Report what you fixed and what remains.
EMPTY
  else
    printf '## Context: Recent Sessions\n'
    for rpt in "${reports[@]}"; do
      printf '\n### %s\n\n' "$(basename "$rpt")"
      head -50 "$rpt" 2>/dev/null || printf '(not readable)\n'
      printf '\n---\n'
    done

    cat <<'TASK'

## Task

Review the above session history. Identify:
- Unfinished work (started but not completed)
- Quality regressions (things that were working and broke)
- Convergence gaps (things that need polish to ship)

Then fix the highest-priority issues you find.
Run quality gates after each fix.
TASK
  fi
} > "$plan_file"

printf '%s\n' "$plan_file"
