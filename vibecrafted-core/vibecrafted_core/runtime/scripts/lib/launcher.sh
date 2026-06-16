#!/usr/bin/env bash


spawn_generate_launcher() {
  local launcher="$1"
  local meta_path="$2"
  local report_path="$3"
  local transcript_path="$4"
  local common_path="$5"
  local command="$6"
  local pre_hook="${7:-}"
  local success_hook="${8:-}"
  local failure_hook="${9:-}"

  [[ -n "$launcher" ]] || spawn_die "Missing launcher path."
  [[ -f "$common_path" ]] || spawn_die "common.sh not found: $common_path"
  [[ -n "$command" ]] || spawn_die "Missing command payload for launcher."

  local q_meta q_report q_transcript q_common q_ulimits q_cmd
  local q_root q_agent q_model q_prompt_id q_run_id q_run_lock q_loop_nr q_skill_code
  local q_skill_name q_operator_session q_spawn_direction q_marbles_tab q_marbles_watcher
  q_meta="$(spawn_shell_quote "$meta_path")"
  q_report="$(spawn_shell_quote "$report_path")"
  q_transcript="$(spawn_shell_quote "$transcript_path")"
  q_common="$(spawn_shell_quote "$common_path")"
  q_ulimits="$(spawn_shell_quote "$(dirname "$common_path")/lib/ulimits.sh")"
  q_cmd="$(spawn_shell_quote "$command")"
  q_root="$(spawn_shell_quote "${SPAWN_ROOT:-}")"
  q_agent="$(spawn_shell_quote "${SPAWN_AGENT:-}")"
  q_model="$(spawn_shell_quote "$(spawn_read_meta_field "$meta_path" "model")")"
  q_prompt_id="$(spawn_shell_quote "${SPAWN_PROMPT_ID:-}")"
  q_run_id="$(spawn_shell_quote "${SPAWN_RUN_ID:-}")"
  q_run_lock="$(spawn_shell_quote "${SPAWN_RUN_LOCK:-}")"
  q_loop_nr="$(spawn_shell_quote "${SPAWN_LOOP_NR:-${VIBECRAFTED_LOOP_NR:-0}}")"
  q_skill_code="$(spawn_shell_quote "${SPAWN_SKILL_CODE:-}")"
  q_skill_name="$(spawn_shell_quote "${SPAWN_SKILL_NAME:-${VIBECRAFTED_SKILL_NAME:-}}")"
  q_operator_session="$(spawn_shell_quote "${VIBECRAFTED_OPERATOR_SESSION:-}")"
  q_spawn_direction="$(spawn_shell_quote "${VIBECRAFTED_VC_FRAME_SPAWN_DIRECTION:-}")"
  q_marbles_tab="$(spawn_shell_quote "${VIBECRAFTED_MARBLES_TAB_NAME:-}")"
  q_marbles_watcher="$(spawn_shell_quote "${VIBECRAFTED_MARBLES_WATCHER:-}")"

  cat > "$launcher" <<EOF_LAUNCH
#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=lib/ulimits.sh
source $q_ulimits
vc_raise_launcher_limits
source $q_common

meta=$q_meta
report=$q_report
transcript=$q_transcript
SPAWN_CMD=$q_cmd
export SPAWN_ROOT=$q_root
export SPAWN_AGENT=$q_agent
export SPAWN_MODEL=$q_model
export SPAWN_PROMPT_ID=$q_prompt_id
export SPAWN_RUN_ID=$q_run_id
export SPAWN_RUN_LOCK=$q_run_lock
export SPAWN_LOOP_NR=$q_loop_nr
export SPAWN_SKILL_CODE=$q_skill_code
export SPAWN_SKILL_NAME=$q_skill_name
export VIBECRAFTED_RUN_ID=$q_run_id
export VIBECRAFTED_RUN_LOCK=$q_run_lock
export VIBECRAFTED_SKILL_CODE=$q_skill_code
export VIBECRAFTED_SKILL_NAME=\${VIBECRAFTED_SKILL_NAME:-$q_skill_name}
export VIBECRAFTED_OPERATOR_SESSION=\${VIBECRAFTED_OPERATOR_SESSION:-$q_operator_session}
export VIBECRAFTED_VC_FRAME_SPAWN_DIRECTION=\${VIBECRAFTED_VC_FRAME_SPAWN_DIRECTION:-$q_spawn_direction}
export VIBECRAFTED_MARBLES_TAB_NAME=\${VIBECRAFTED_MARBLES_TAB_NAME:-$q_marbles_tab}
export VIBECRAFTED_MARBLES_WATCHER=\${VIBECRAFTED_MARBLES_WATCHER:-$q_marbles_watcher}
startup_watch_pid=""

# Write this launcher's PID into meta.json so the watcher heartbeat and the
# spawn-time GC can validate liveness via kill -0. Dead launcher_pid = ghost.
spawn_update_meta_pid "\$meta" \$\$

rm -f "\$transcript" "\$report"
spawn_write_frontmatter "\$transcript" "\$SPAWN_AGENT" "\${SPAWN_MODEL:-unknown}" "transcript"
if [[ -n "\${SPAWN_ROOT:-}" ]]; then
  cd "\$SPAWN_ROOT"
fi
EOF_LAUNCH

if [[ -n "$pre_hook" ]]; then
    printf '%s\n' "$pre_hook" >> "$launcher"
  fi

  cat >> "$launcher" <<'EOF_LAUNCH'
spawn_export_frontier_sidecars
export PATH="${PATH:-/usr/local/bin:/usr/bin:/bin}"
spawn_prepend_agent_tool_paths
if [[ "${SPAWN_SKILL_NAME:-}" == "research" || "${SPAWN_SKILL_CODE:-}" == "rsch" || "${VIBECRAFTED_RESEARCH_MODE:-0}" == "1" ]]; then
  export VIBECRAFTED_RESEARCH_MODE=1
  export VIBECRAFTED_NO_GIT_WRITES=1
  if [[ "${VIBECRAFTED_ALLOW_RESEARCH_GIT_WRITE:-0}" != "1" ]] && command -v git >/dev/null 2>&1; then
    export VIBECRAFTED_REAL_GIT="$(command -v git)"
    git_guard_dir="${TMPDIR:-/tmp}/vibecrafted-research-git-guard-${SPAWN_RUN_ID:-research}-$$"
    mkdir -p "$git_guard_dir"
    cat > "$git_guard_dir/git" <<'EOF_GIT_GUARD'
#!/usr/bin/env bash
set -euo pipefail

subcmd=""
args=("$@")
i=0
while (( i < ${#args[@]} )); do
  arg="${args[$i]}"
  case "$arg" in
    -C|-c|--git-dir|--work-tree|--namespace|--exec-path|--super-prefix)
      (( i += 2 ))
      ;;
    --git-dir=*|--work-tree=*|--namespace=*|--exec-path=*|--super-prefix=*|-c*)
      (( i += 1 ))
      ;;
    --no-pager|--paginate|--bare|--no-replace-objects|--literal-pathspecs|--glob-pathspecs|--noglob-pathspecs|--icase-pathspecs)
      (( i += 1 ))
      ;;
    --*)
      (( i += 1 ))
      ;;
    -*)
      (( i += 1 ))
      ;;
    *)
      subcmd="$arg"
      break
      ;;
  esac
done

case "$subcmd" in
  add|am|apply|bisect|branch|checkout|cherry-pick|clean|commit|fetch|merge|mv|pull|push|rebase|reset|restore|revert|rm|stash|submodule|switch|tag|update-index|worktree)
    printf 'vibecrafted research mode blocks git write operation: git %s\n' "$subcmd" >&2
    printf 'Write findings to the research report instead of mutating the source repo.\n' >&2
    exit 126
    ;;
esac

exec "${VIBECRAFTED_REAL_GIT:-/usr/bin/git}" "$@"
EOF_GIT_GUARD
    chmod +x "$git_guard_dir/git"
    export PATH="$git_guard_dir:$PATH"
  fi
fi
if [[ "${VIBECRAFTED_INLINE_STARTUP_WATCH:-1}" != "0" ]]; then
  VIBECRAFTED_STARTUP_WATCH_ECHO=0 spawn_watch_startup "$meta" "$transcript" "$report" &
  startup_watch_pid=$!
fi
# Lifecycle truth: the spawner wrote "launching"; the launcher owns the run
# from here, so the agent command starting is the launching->running edge.
spawn_mark_meta_running "$meta"
if bash -c "$SPAWN_CMD"; then
  spawn_finish_meta "$meta" "completed" "0"
EOF_LAUNCH

  if [[ -n "$success_hook" ]]; then
    printf '%s\n' "$success_hook" >> "$launcher"
  fi
  cat >> "$launcher" <<'EOF_LAUNCH'
  # Final artifact closure is Python-owned; this shell call is the stable wrapper.
  spawn_finalize_artifacts "$meta" "$report" "$transcript"
  if [[ -n "$startup_watch_pid" ]]; then
    wait "$startup_watch_pid" 2>/dev/null || true
  fi
else
  exit_code=$?
  spawn_finish_meta "$meta" "failed" "$exit_code"
EOF_LAUNCH

  if [[ -n "$failure_hook" ]]; then
    printf '%s\n' "$failure_hook" >> "$launcher"
  fi
  cat >> "$launcher" <<'EOF_LAUNCH'
  # Final artifact closure is Python-owned; this shell call is the stable wrapper.
  spawn_finalize_artifacts "$meta" "$report" "$transcript"
  if [[ -n "$startup_watch_pid" ]]; then
    wait "$startup_watch_pid" 2>/dev/null || true
  fi
  exit "$exit_code"
fi
EOF_LAUNCH

  if ! spawn_check_shell_syntax "$launcher" "generated launcher"; then
    if [[ -f "$meta_path" ]]; then
      spawn_finish_meta "$meta_path" "failed" "1" 2>/dev/null || true
    fi
    spawn_die "Generated launcher has invalid shell syntax: $launcher"
  fi
}

spawn_launch_headless() {
  local launcher="$1"
  [[ -x "$launcher" ]] || spawn_die "Launcher is not executable: $launcher"
  nohup "$launcher" >/dev/null 2>&1 &
  local launcher_pid=$!
  printf 'Spawned headless launcher (pid=%s): %s\n' "$launcher_pid" "$launcher"
}

spawn_launch() {
  local launcher="$1"
  local runtime="${2:-terminal}"
  local dry_run="${3:-0}"
  local pane_name="${4:-$(basename "$launcher" .sh)}"

  pane_name="$(printf '%s' "$pane_name" | tr ' ' '-' | tr -cs '[:alnum:]._-' '-')"
  pane_name="${pane_name#-}"
  pane_name="${pane_name%-}"
  [[ -n "$pane_name" ]] || pane_name="agent"

  if [[ -z "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
    local discovered_session=""
    discovered_session="$(spawn_effective_operator_session 2>/dev/null || true)"
    if [[ -n "$discovered_session" ]]; then
      export VIBECRAFTED_OPERATOR_SESSION="$discovered_session"
    fi
  fi

  if (( dry_run )); then
    printf 'Dry run mode: launcher generated only: %s\n' "$launcher"
    return 0
  fi

  case "$runtime" in
    terminal|visible)
      if spawn_in_vc_frame_pane "$launcher" "$pane_name"; then
        :
      elif spawn_in_operator_session "$launcher" "$pane_name"; then
        :
      else
        # Degrade, don't die. No vc-frame operator session exists to host a
        # visible tab (e.g. dispatched from a plain terminal, outside vc-frame).
        # AppleScript/iTerm fallback stays forbidden — but a hard failure is
        # worse UX than running detached. Fall back to headless, show a short
        # honest live tail so the operator sees real progress, then hand off to
        # observe/await. Start from inside vc-start if you want a visible tab.
        printf 'No vc-frame operator session for %s runtime — running headless instead.\n' "$runtime" >&2
        spawn_launch_headless "$launcher"
        local _vc_transcript="${SPAWN_TRANSCRIPT:-}"
        local _vc_agent="${SPAWN_AGENT:-agent}"
        local _vc_run_id="${SPAWN_RUN_ID:-${VIBECRAFTED_RUN_ID:-}}"
        local _vc_tail_secs="${VIBECRAFTED_DEGRADE_TAIL_SECONDS:-10}"
        # The live tail is for a human at an interactive terminal. Skip it when
        # stderr is not a TTY (pipes, tests, CI, nested dispatch) so automated
        # callers are not blocked for 10s.
        if [[ -n "$_vc_transcript" && -t 2 && "$_vc_tail_secs" != "0" ]]; then
          local _vc_wait=0
          while [[ ! -s "$_vc_transcript" && $_vc_wait -lt 14 ]]; do
            sleep 0.5
            _vc_wait=$((_vc_wait + 1))
          done
          printf -- '--- live agent output (%ss) ------------------------------------\n' "$_vc_tail_secs" >&2
          tail -n 40 -F "$_vc_transcript" >&2 2>/dev/null &
          local _vc_tail_pid=$!
          sleep "$_vc_tail_secs"
          kill "$_vc_tail_pid" 2>/dev/null || true
          wait "$_vc_tail_pid" 2>/dev/null || true
          printf -- '----------------------------------------------------------------\n' >&2
        fi
        printf 'Agent is still running headless. Continue to observe it:\n' >&2
        printf '  vibecrafted %s observe --run-id %s\n' "$_vc_agent" "$_vc_run_id" >&2
        printf '  vibecrafted %s await   --run-id %s\n' "$_vc_agent" "$_vc_run_id" >&2
        return 0
      fi
      ;;
    headless|background|detached)
      spawn_launch_headless "$launcher"
      ;; 
    *)
      spawn_die "Unsupported runtime '$runtime'. Use terminal or headless."
      ;;
  esac

  # Spawn probe for operator observability (fire-and-forget)
  if [[ "$runtime" == "terminal" || "$runtime" == "visible" ]]; then
    spawn_probe "${SPAWN_TRANSCRIPT:-}" 2>/dev/null || true
  fi
}

spawn_print_launch() {
  local agent="$1"
  local mode="$2"
  local runtime="${3:-terminal}"
  local dry_run="${4:-0}"

  # ── 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. branded spawn output ──────────────────────────────
  local _dim='\033[2m'    _bold='\033[1m'
  local _copper='\033[38;5;173m'
  local _steel='\033[38;5;247m'
  local _reset='\033[0m'
  local _bar="${_steel}──────────────────────────────────${_reset}"

  printf '\n%b ⚒  𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. · %s-%s%b\n' "$_bold$_copper" "$agent" "$mode" "$_reset"
  printf '%b\n' "$_bar"
  printf '%b  plan:    %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_PLAN:-—}" "$_reset"
  printf '%b  report:  %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_REPORT:-—}" "$_reset"
  printf '%b  trace:   %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_TRANSCRIPT:-—}" "$_reset"
  printf '%b  runtime: %b%s%b\n'   "$_steel" "$_reset" "$runtime" "$_reset"
  printf '%b\n' "$_bar"
  if [[ "$dry_run" == "1" ]]; then
    printf '%b  Dry run: launcher generated only.%b\n\n' "$_dim" "$_reset"
  else
    printf '%b  Agent launched.%b\n\n' "$_dim" "$_reset"
  fi
}
