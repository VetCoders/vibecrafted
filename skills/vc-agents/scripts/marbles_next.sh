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

# ── State directory (watcher writes session_id here) ─────────────────
state_dir="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/marbles/$run_id"
state_file="$state_dir/state.json"

# ── Read session_id for a loop from state.json ───────────────────────
_read_session_id() {
  local loop_nr="$1"
  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 -c "
import json, sys
with open('$state_file') as f: d = json.load(f)
for loop in d.get('loops', []):
    if loop.get('loop') == $loop_nr:
        print(loop.get('session_id', ''))
        sys.exit(0)
print('')
" 2>/dev/null || true
  fi
}

# ── Collect report paths for loops L(1)..L(n) ───────────────────────
_collect_reports() {
  local up_to="$1"
  find "$store/reports" -name "*_marbles-${plan_slug}_L*.md" \
    ! -name '*_verified.md' \
    ! -name '*.meta.json' ! -name '*.transcript.log' 2>/dev/null \
    | sort | while IFS= read -r rpt; do
      # Extract loop number from filename
      local lnum
      lnum=$(printf '%s' "$(basename "$rpt")" | grep -oE '_L[0-9]+_' | tr -dc '0-9')
      if [[ -n "$lnum" ]] && (( lnum <= up_to )); then
        printf '%s\n' "$rpt"
      fi
    done
}

# ── Fire-and-forget verification resume ──────────────────────────────
_launch_verification() {
  local loop_nr="$1" is_final="${2:-0}"

  local sid
  sid="$(_read_session_id "$loop_nr")"
  if [[ -z "$sid" ]]; then
    printf '    ⚠ No session_id for L%s — skipping verification\n' "$loop_nr"
    return 0
  fi

  # Collect all reports up to this loop
  local reports_list=""
  while IFS= read -r rpt; do
    [[ -n "$rpt" ]] || continue
    reports_list="${reports_list}
- ${rpt}"
  done < <(_collect_reports "$loop_nr")

  # Expected verified report path
  local verified_report
  verified_report=$(find "$store/reports" -name "*_marbles-${plan_slug}_L${loop_nr}_${agent}.md" \
    ! -name '*_verified*' 2>/dev/null | sort | tail -1 || true)
  local verified_path="${verified_report%.md}_verified.md"

  # Build verification prompt
  local prompt="You are resuming to self-audit your own report from marbles loop L${loop_nr}.

## Instructions
1. Read ALL reports from this batch:${reports_list}
2. Re-read your own report critically
3. Write a verified report to: ${verified_path}
4. The verified report should:
   - Confirm or correct your original findings
   - Note any contradictions with other loops' reports
   - Add anything you missed"

  if (( is_final )); then
    prompt="${prompt}

## Final Loop — Convergence Assessment
This is the final loop. Your verified report MUST include:
- **Convergence verdict**: Has the codebase converged? (yes/no/partial)
- **Remaining issues**: Any P0/P1 still open after all loops
- **Next workflow recommendation**: What should the team do next (e.g., ship, another marbles run with different focus, manual review of specific area)
"
  fi

  prompt="${prompt}

## Constraints
- Do NOT modify any code files — only write your verified report
- Be honest about uncertainty — flag anything you cannot verify
- Keep the verified report concise and actionable"

  # Record verification start in state.json
  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import json, sys, datetime
with open(sys.argv[1]) as f: d = json.load(f)
d["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in d["loops"]:
    if loop["loop"] == int(sys.argv[2]):
        loop["verification_status"] = "pending"
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file" 2>/dev/null || true
  fi

  # Fire-and-forget: resume the agent with verification prompt
  printf '    🔍 Verification L%s → session %s\n' "$loop_nr" "${sid:0:13}…"
  case "$agent" in
    claude) nohup claude --resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    codex)  nohup codex resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    gemini) nohup gemini --resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
  esac
}

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

    find "$store/reports" -name "*_marbles-${plan_slug}_L*.md" \
      ! -name '*_verified.md' \
      ! -name '*.meta.json' ! -name '*.transcript.log' 2>/dev/null \
      | sort | while IFS= read -r rpt; do
        [[ -n "$rpt" ]] || continue
        printf '\n### %s\n\n' "$(basename "$rpt")"
        head -20 "$rpt" 2>/dev/null || printf '(report not readable)\n'
        printf '\n...\n'
      done

    printf '\n---\n𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents (c)2024-2026 VetCoders\n'
  } > "$convergence"

  # Launch final-loop verification (is_final=1 → includes convergence assessment)
  _launch_verification "$current" 1

  _update_lock status completed
  printf '\n\033[32m ✓  Marbles complete: %s loops · %s\033[0m\n' "$total_count" "$run_id"
  printf '    Convergence: %s\n' "$convergence"
  exit 0
fi

# ── Verification for current loop (fire-and-forget, runs concurrently with L(n+1))
_launch_verification "$current" 0

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
export VIBECRAFTED_LOOP_NR=$next
export VIBECRAFTED_SKILL_CODE="marb"
export VIBECRAFTED_RUN_ID="${run_id}-$(printf '%03d' "$next")"

spawn_args=(
  --mode marbles
  --runtime "$runtime"
  --root "$root_dir"
  --success-hook "$success_hook"
  --failure-hook "$failure_hook"
)

VIBECRAFTED_STORE_DIR="$store" bash "$scripts_dir/${agent}_spawn.sh" "${spawn_args[@]}" "$ln_plan"
