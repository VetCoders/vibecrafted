#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF
Usage: marbles_spawn.sh --agent <agent> [--depth <n>|--task <file>|--prompt <text>] [--count <n>] [--runtime <rt>] [--root <dir>]

Marbles convergence loop orchestrator.
Runs <agent> in a loop of <count> iterations against the same plan.
Convergence happens through code state, not report chaining.

Options:
  --agent <name>      claude, codex, or gemini (required)
  --depth <n>         Crawl last n sessions as context
  --task <file>       Use specific plan file
  --prompt <text>     Inline prompt string
  --count <n>         Number of loops (default: 3)
  --runtime <rt>      terminal, headless (default: terminal)
  --root <dir>        Repository root
EOF
}

agent=""
depth=""
task=""
prompt=""
count=3
runtime="terminal"
root=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)   shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --agent";   agent="$1" ;;
    --depth)   shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --depth";   depth="$1" ;;
    --task)    shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --task";    task="$1" ;;
    --prompt)  shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --prompt";  prompt="$1" ;;
    --count)   shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --count";   count="$1" ;;
    --runtime) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --runtime"; runtime="$1" ;;
    --root)    shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --root";    root="$1" ;;
    -h|--help) usage; exit 0 ;;
    *) spawn_die "Unknown argument: $1" ;;
  esac
  shift
done

# ── Validate ───────────────────────────────────────────────────────────
[[ -n "$agent" ]] || spawn_die "Missing --agent"
[[ "$agent" =~ ^(claude|codex|gemini)$ ]] || spawn_die "Invalid agent: $agent"
spawn_validate_runtime "$runtime"

sources=0
[[ -n "$depth" ]]  && ((sources++)) || true
[[ -n "$task" ]]   && ((sources++)) || true
[[ -n "$prompt" ]] && ((sources++)) || true
[[ $sources -eq 1 ]] || spawn_die "Exactly one of --depth, --task, or --prompt is required"

# ── Resolve root & store ──────────────────────────────────────────────
root_dir="${root:-$(spawn_repo_root)}"
store="$(spawn_marbles_store_dir "$root_dir")"
mkdir -p "$store/plans" "$store/reports"

# ── Marbles session ───────────────────────────────────────────────────
marbles_run_id="marb-$(date +%H%M%S)"

# ── Resolve plan file ─────────────────────────────────────────────────
if [[ -n "$task" ]]; then
  original_plan="$(spawn_abspath "$task")"
  spawn_require_file "$original_plan"
elif [[ -n "$prompt" ]]; then
  ts="$(spawn_timestamp)"
  slug="$(printf '%s' "$prompt" | tr '\n' ' ' | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48)"
  [[ -n "$slug" ]] || slug="marbles-prompt"
  original_plan="$store/plans/${ts}_marbles-${slug}.md"
  prompt_id="marbles-${slug}_${ts%%_*}"
  cat > "$original_plan" <<EOF_PROMPT
---
agent: $agent
run_id: $marbles_run_id
prompt_id: $prompt_id
started_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
model: pending
---

$prompt
EOF_PROMPT
elif [[ -n "$depth" ]]; then
  original_plan="$(VIBECRAFT_STORE_DIR="$store" bash "$SCRIPT_DIR/marbles_plan.sh" --agent "$agent" --run-id "$marbles_run_id" --depth "$depth" --root "$root_dir")"
fi

org_repo=""
if cd "$root_dir" && git remote get-url origin >/dev/null 2>&1; then
  org_repo="$(git remote get-url origin | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|')"
fi
[[ -n "$org_repo" ]] || org_repo="$(basename "$root_dir")"
lock_dir="$HOME/.vibecrafted/locks/$org_repo"
mkdir -p "$lock_dir"

session_lock="$lock_dir/${marbles_run_id}.lock"
cat > "$session_lock" <<LOCK
run_id=$marbles_run_id
agent=$agent
plan=$original_plan
count=$count
current=1
runtime=$runtime
root=$root_dir
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=running
LOCK

# ── Banner ────────────────────────────────────────────────────────────
_bold='\033[1m' _copper='\033[38;5;173m' _steel='\033[38;5;247m' _reset='\033[0m'
printf '\n%b ⚒  Marbles Loop · %s × %s%b\n' "$_bold$_copper" "$agent" "$count" "$_reset"
printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
printf '%b  plan:    %b%s\n'   "$_steel" "$_reset" "$original_plan"
printf '%b  loops:   %b%s\n'   "$_steel" "$_reset" "$count"
printf '%b  run_id:  %b%s\n'   "$_steel" "$_reset" "$marbles_run_id"
printf '%b  lock:    %b%s\n'   "$_steel" "$_reset" "$session_lock"
printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"

# ── Create L1 plan (same content, loop-numbered name) ─────────────────
plan_slug="$(spawn_slug_from_path "$original_plan")"
l1_plan="$store/plans/marbles-${plan_slug}_L1.md"
cp "$original_plan" "$l1_plan"

# ── Build hooks for chaining ──────────────────────────────────────────
q_agent="$(printf '%q' "$agent")"
q_plan="$(printf '%q' "$original_plan")"
q_root="$(printf '%q' "$root_dir")"
q_runtime="$(printf '%q' "$runtime")"
q_scripts="$(printf '%q' "$SCRIPT_DIR")"
q_lock="$(printf '%q' "$session_lock")"
q_store="$(printf '%q' "$store")"

success_hook="bash $q_scripts/marbles_next.sh $q_agent $q_plan $count 1 $marbles_run_id $q_root $q_runtime $q_scripts $q_lock $q_store"
failure_hook="bash $q_scripts/marbles_next.sh --failed $q_agent $q_plan $count 1 $marbles_run_id $q_root $q_runtime $q_scripts $q_lock $q_store"

# ── Spawn first iteration ────────────────────────────────────────────
export VIBECRAFT_LOOP_NR=1
export VIBECRAFT_SKILL_CODE="marb"
export VIBECRAFT_RUN_ID="${marbles_run_id}-001"

spawn_args=(
  --mode marbles
  --runtime "$runtime"
  --success-hook "$success_hook"
  --failure-hook "$failure_hook"
)
[[ -z "$root" ]] || spawn_args+=(--root "$root_dir")

VIBECRAFT_STORE_DIR="$store" bash "$SCRIPT_DIR/${agent}_spawn.sh" "${spawn_args[@]}" "$l1_plan"
