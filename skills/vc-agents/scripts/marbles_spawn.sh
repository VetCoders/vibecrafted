#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF
Usage: marbles_spawn.sh --agent <agent> [--depth <n>|--file <file>|--prompt <text>] [--count <n>] [--rotation <mode>] [--runtime <rt>] [--root <dir>]

Marbles convergence loop orchestrator.
Runs <agent> in a loop of <count> iterations against a live ancestor plan.
Convergence happens through code state, not report chaining.

Options:
  --agent <name>      claude, codex, or gemini (required)
  --depth <n>         Crawl last n plan files as context (default: 3 when no source is given)
  --file <file>       Use specific plan/input file
  --prompt <text>     Inline prompt string; captures the rest of the command line
  --count <n>         Number of loops (default: 3)
  --rotation <mode>   single, duo, trio, or multi (default: single)
  --runtime <rt>      terminal, headless (default: terminal)
  --root <dir>        Repository root
  --no-watch          Skip watcher UI and run chaining directly
EOF
}

agent=""
depth=""
task=""
prompt=""
count=3
rotation="single"
runtime="terminal"
root=""
use_watcher=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)   shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --agent"; agent="$1" ;;
    --depth)   shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --depth"; depth="$1" ;;
    --task|--file|-f) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --file"; task="$1" ;;
    --prompt|-p) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --prompt"; prompt="$*"; break ;;
    --count)   shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --count"; count="$1" ;;
    --rotation) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --rotation"; rotation="$1" ;;
    --runtime) shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --runtime"; runtime="$1" ;;
    --root)    shift; [[ $# -gt 0 ]] || spawn_die "Missing value for --root"; root="$1" ;;
    --no-watch) use_watcher=0 ;;
    -h|--help) usage; exit 0 ;;
    *) spawn_die "Unknown argument: $1" ;;
  esac
  shift
done

[[ -n "$agent" ]] || spawn_die "Missing --agent"
[[ "$agent" =~ ^(claude|codex|gemini)$ ]] || spawn_die "Invalid agent: $agent"
spawn_validate_runtime "$runtime"
spawn_require_positive_int "$count" "--count"
spawn_rotation_validate_mode "$rotation"
[[ -z "$depth" ]] || spawn_require_positive_int "$depth" "--depth"

spawn_require_shell_syntax "$SCRIPT_DIR/common.sh" "shared spawn library"
spawn_require_shell_syntax "$SCRIPT_DIR/${agent}_spawn.sh" "${agent} spawn"
spawn_require_shell_syntax "$SCRIPT_DIR/marbles_next.sh" "marbles next hop"
if (( use_watcher )); then
  spawn_require_shell_syntax "$SCRIPT_DIR/marbles_watcher.sh" "marbles watcher"
fi

sources=0
[[ -n "$depth" ]]  && ((sources++)) || true
[[ -n "$task" ]]   && ((sources++)) || true
[[ -n "$prompt" ]] && ((sources++)) || true
[[ $sources -le 1 ]] || spawn_die "Use at most one source: --depth, --file, or --prompt"
if [[ $sources -eq 0 ]]; then
  depth=3
fi

root_dir="${root:-$(spawn_repo_root)}"
store="$(spawn_marbles_store_dir "$root_dir")"
mkdir -p "$store/plans" "$store/reports"

marbles_run_id="${VIBECRAFTED_MARBLES_RUN_ID:-marb-$(date +%H%M%S)}"
state_dir="$(spawn_marbles_state_dir "$marbles_run_id")"
state_file="$state_dir/state.json"
god_plan="$state_dir/god.md"
ancestor_plan="$state_dir/ancestor.md"
mkdir -p "$state_dir"

seed_source_file=""
input_kind=""
if [[ -n "$task" ]]; then
  seed_source_file="$(spawn_abspath "$task")"
  spawn_require_file "$seed_source_file"
  input_kind="file"
elif [[ -n "$prompt" ]]; then
  input_kind="prompt"
elif [[ -n "$depth" ]]; then
  seed_source_file="$(VIBECRAFTED_STORE_DIR="$store" VIBECRAFTED_STORE_ROOT="$root_dir" bash "$SCRIPT_DIR/marbles_plan.sh" --agent "$agent" --run-id "$marbles_run_id" --depth "$depth" --root "$root_dir")"
  spawn_require_file "$seed_source_file"
  input_kind="depth"
fi

body_file="$state_dir/.seed-body.md"
if [[ -n "$seed_source_file" ]]; then
  spawn_strip_frontmatter_to_file "$seed_source_file" "$body_file"
else
  printf '%s\n' "$prompt" > "$body_file"
fi

ancestor_focus=""
ancestor_priority=""
ancestor_model=""
if [[ -n "$seed_source_file" ]]; then
  ancestor_focus="$(spawn_frontmatter_field "$seed_source_file" "focus")"
  ancestor_priority="$(spawn_frontmatter_field "$seed_source_file" "priority")"
  ancestor_model="$(spawn_frontmatter_field "$seed_source_file" "model")"
fi
[[ -n "$ancestor_focus" ]] || ancestor_focus="initial prompt"
[[ -n "$ancestor_priority" ]] || ancestor_priority="P0"

created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  cat <<EOF
---
kind: god
run_id: $marbles_run_id
created_at: $created_at
input_kind: $input_kind
EOF
  if [[ -n "$seed_source_file" ]]; then
    printf 'source_path: %s\n' "$seed_source_file"
  fi
  cat <<'EOF'
---

EOF
  cat "$body_file"
} > "$god_plan"
chmod 0444 "$god_plan"

{
  cat <<EOF
---
agent: $agent
focus: $ancestor_focus
priority: $ancestor_priority
EOF
  if [[ -n "$ancestor_model" ]]; then
    printf 'model: %s\n' "$ancestor_model"
  fi
  cat <<'EOF'
---

EOF
  cat "$body_file"
} > "$ancestor_plan"
rm -f "$body_file"

ancestor_mtime="$(spawn_ancestor_mtime_iso "$ancestor_plan")"
rotation_pool_json="$(spawn_rotation_pool_json)"

cat > "$state_file" <<EOF
{
  "run_id": "$marbles_run_id",
  "agent": "$agent",
  "mode": "steered",
  "rotation": "$rotation",
  "rotation_pool": $rotation_pool_json,
  "ancestor_mtime": "$ancestor_mtime",
  "plan": "$ancestor_plan",
  "god_plan": "$god_plan",
  "ancestor_plan": "$ancestor_plan",
  "root": "$root_dir",
  "runtime": "$runtime",
  "total_loops": $count,
  "current_loop": 0,
  "status": "initialized",
  "started_at": "$created_at",
  "loops": [],
  "trajectory": []
}
EOF

org_repo=""
if cd "$root_dir" && git remote get-url origin >/dev/null 2>&1; then
  org_repo="$(git remote get-url origin | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|')"
fi
[[ -n "$org_repo" ]] || org_repo="$(basename "$root_dir")"
lock_dir="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/locks/$org_repo"
mkdir -p "$lock_dir"

session_lock="$lock_dir/${marbles_run_id}.lock"
cat > "$session_lock" <<LOCK
run_id=$marbles_run_id
agent=$agent
plan=$ancestor_plan
count=$count
current=1
runtime=$runtime
root=$root_dir
state_dir=$state_dir
started=$created_at
status=running
LOCK

_bold='\033[1m' _copper='\033[38;5;173m' _steel='\033[38;5;247m' _reset='\033[0m'
printf '\n%b ⚒  Marbles Loop · %s × %s%b\n' "$_bold$_copper" "$agent" "$count" "$_reset"
printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
printf '%b  god:     %b%s\n'   "$_steel" "$_reset" "$god_plan"
printf '%b  ancestor:%b%s\n'   "$_steel" "$_reset" "$ancestor_plan"
printf '%b  loops:   %b%s\n'   "$_steel" "$_reset" "$count"
printf '%b  run_id:  %b%s\n'   "$_steel" "$_reset" "$marbles_run_id"
printf '%b  lock:    %b%s\n'   "$_steel" "$_reset" "$session_lock"
printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"

l1_plan="$(spawn_marbles_child_plan_path "$store" "$ancestor_plan" 1)"
spawn_marbles_write_child_plan "$ancestor_plan" "$l1_plan"

q_state="$(spawn_shell_quote "$state_dir")"
q_root="$(spawn_shell_quote "$root_dir")"
q_runtime="$(spawn_shell_quote "$runtime")"
q_scripts="$(spawn_shell_quote "$SCRIPT_DIR")"
q_lock="$(spawn_shell_quote "$session_lock")"
q_store="$(spawn_shell_quote "$store")"

success_hook="bash $q_scripts/marbles_next.sh $q_state $count 1 $marbles_run_id $q_root $q_runtime $q_scripts $q_lock $q_store"
failure_hook="bash $q_scripts/marbles_next.sh --failed $q_state $count 1 $marbles_run_id $q_root $q_runtime $q_scripts $q_lock $q_store"

export VIBECRAFTED_LOOP_NR=1
export VIBECRAFTED_RUN_ID="${marbles_run_id}-001"
export VIBECRAFTED_SKILL_CODE="marb"
export VIBECRAFTED_SKILL_NAME="marbles"
export VIBECRAFTED_MARBLES_TAB_NAME="marbles-${marbles_run_id}"

spawn_args=(
  --mode implement
  --runtime "$runtime"
  --root "$root_dir"
  --success-hook "$success_hook"
  --failure-hook "$failure_hook"
)
if [[ -n "$ancestor_model" && "$agent" != "codex" ]]; then
  spawn_args+=(--model "$ancestor_model")
fi

if (( use_watcher )); then
  VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=right VIBECRAFTED_STORE_DIR="$store" VIBECRAFTED_STORE_ROOT="$root_dir" bash "$SCRIPT_DIR/${agent}_spawn.sh" "${spawn_args[@]}" "$l1_plan" &

  exec bash "$SCRIPT_DIR/marbles_watcher.sh" \
    "$marbles_run_id" "$state_dir" "$count" \
    "$root_dir" "$runtime" "$store" "$session_lock"
else
  VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=right VIBECRAFTED_STORE_DIR="$store" VIBECRAFTED_STORE_ROOT="$root_dir" bash "$SCRIPT_DIR/${agent}_spawn.sh" "${spawn_args[@]}" "$l1_plan"
fi
