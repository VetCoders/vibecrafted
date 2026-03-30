#!/usr/bin/env bash
set -euo pipefail
# Marbles chain trigger — called by success_hook inside agent launcher.
# Spawns next loop iteration or writes CONVERGENCE.md when done.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

failed=0
if [[ "${1:-}" == "--failed" ]]; then
  failed=1
  shift
fi

agent="$1"
original_plan="$2"
total_count="$3"
current="$4"
run_id="$5"
root_dir="$6"
runtime="$7"
scripts_dir="$8"
session_lock="$9"
store="${10:-$(spawn_marbles_store_dir "$root_dir")}"

next=$((current + 1))
plan_slug="$(spawn_slug_from_path "$original_plan")"

# ── Update lock ───────────────────────────────────────────────────────
_update_lock() {
  local key="$1" val="$2"
  [[ -f "$session_lock" ]] || return 0
  if sed --version >/dev/null 2>&1; then
    sed -i "s/^${key}=.*/${key}=${val}/" "$session_lock"
  else
    sed -i '' "s/^${key}=.*/${key}=${val}/" "$session_lock"
  fi
}

# ── Failed: write partial convergence ─────────────────────────────────
if (( failed )); then
  convergence="$store/reports/$(spawn_timestamp)_marbles-${plan_slug}_CONVERGENCE.md"
  cat > "$convergence" <<CONV
---
run_id: $run_id
agent: $agent
status: FAILED
failed_at_loop: $current
total_loops: $total_count
---

# Marbles Convergence — FAILED

Loop $current of $total_count failed.
Check individual loop reports for details.

Reports in: $store/reports/
Filter: marbles-${plan_slug}_L*
CONV

  _update_lock status failed
  printf '\n\033[31m ✗  Marbles failed at loop %s/%s\033[0m\n' "$current" "$total_count"
  printf '    Convergence: %s\n' "$convergence"
  exit 0
fi

# ── All loops done: write convergence summary ─────────────────────────
if [[ $next -gt $total_count ]]; then
  convergence="$store/reports/$(spawn_timestamp)_marbles-${plan_slug}_CONVERGENCE.md"

  {
    cat <<HEADER
---
run_id: $run_id
agent: $agent
status: completed
loops_completed: $total_count
---

# Marbles Convergence — Complete

$total_count loops completed successfully.

## Loop Reports
HEADER

    find "$store/reports" -name "marbles-${plan_slug}_L*.md" \
      ! -name '*.meta.json' ! -name '*.transcript.log' 2>/dev/null \
      | sort | while IFS= read -r rpt; do
        [[ -n "$rpt" ]] || continue
        printf '\n### %s\n\n' "$(basename "$rpt")"
        head -20 "$rpt" 2>/dev/null || printf '(report not readable)\n'
        printf '\n...\n'
      done

    printf '\n---\nVibeCrafted with AI Agents (c)2026 VetCoders\n'
  } > "$convergence"

  _update_lock status completed
  printf '\n\033[32m ✓  Marbles complete: %s loops · %s\033[0m\n' "$total_count" "$run_id"
  printf '    Convergence: %s\n' "$convergence"
  exit 0
fi

# ── More loops: spawn next iteration ──────────────────────────────────
_update_lock current "$next"
printf '\n\033[38;5;173m ⚒  Marbles loop %s/%s starting...\033[0m\n' "$next" "$total_count"

# Same plan content, loop-numbered filename
ln_plan="$store/plans/marbles-${plan_slug}_L${next}.md"
cp "$original_plan" "$ln_plan"

# Build hooks for next iteration (recursive chain)
q_agent="$(printf '%q' "$agent")"
q_plan="$(printf '%q' "$original_plan")"
q_root="$(printf '%q' "$root_dir")"
q_runtime="$(printf '%q' "$runtime")"
q_scripts="$(printf '%q' "$scripts_dir")"
q_lock="$(printf '%q' "$session_lock")"
q_store="$(printf '%q' "$store")"

success_hook="bash $q_scripts/marbles_next.sh $q_agent $q_plan $total_count $next $run_id $q_root $q_runtime $q_scripts $q_lock $q_store"
failure_hook="bash $q_scripts/marbles_next.sh --failed $q_agent $q_plan $total_count $next $run_id $q_root $q_runtime $q_scripts $q_lock $q_store"

# Set env for next iteration
export VIBECRAFT_LOOP_NR=$next
export VIBECRAFT_SKILL_CODE="marb"
export VIBECRAFT_RUN_ID="${run_id}-$(printf '%03d' "$next")"

spawn_args=(
  --mode marbles
  --runtime "$runtime"
  --root "$root_dir"
  --success-hook "$success_hook"
  --failure-hook "$failure_hook"
)

VIBECRAFT_STORE_DIR="$store" bash "$scripts_dir/${agent}_spawn.sh" "${spawn_args[@]}" "$ln_plan"
