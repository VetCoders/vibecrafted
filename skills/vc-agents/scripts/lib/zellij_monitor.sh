#!/usr/bin/env bash


# shellcheck disable=SC2120
spawn_workflow_label() {
  local skill_name="${1:-${SPAWN_SKILL_NAME:-${VIBECRAFTED_SKILL_NAME:-}}}"
  if [[ -n "$skill_name" ]]; then
    printf 'vc-%s\n' "$skill_name"
  else
    printf 'vc-workflow\n'
  fi
}

spawn_write_startup_monitor_script() {
  local script_path="$1"
  local common_path="$2"
  local meta_path="$3"
  local transcript_path="$4"
  local report_path="$5"
  local session_name="$6"
  local workflow_name="$7"
  local landing_kind="$8"
  local landing_name="$9"

  local q_common q_meta q_transcript q_report q_session q_workflow q_kind q_name
  q_common="$(spawn_shell_quote "$common_path")"
  q_meta="$(spawn_shell_quote "$meta_path")"
  q_transcript="$(spawn_shell_quote "$transcript_path")"
  q_report="$(spawn_shell_quote "$report_path")"
  q_session="$(spawn_shell_quote "$session_name")"
  q_workflow="$(spawn_shell_quote "$workflow_name")"
  q_kind="$(spawn_shell_quote "$landing_kind")"
  q_name="$(spawn_shell_quote "$landing_name")"

  cat > "$script_path" <<EOF_MONITOR
#!/usr/bin/env bash
set -euo pipefail
trap 'rm -f "\$0"' EXIT
source $q_common
session_name=$q_session
workflow_name=$q_workflow
landing_kind=$q_kind
landing_name=$q_name

printf 'Your vibecrafted session %s invoked the %s run that landed in %s %s.\\n' "\$session_name" "\$workflow_name" "\$landing_kind" "\$landing_name"
printf 'Watching startup for %ss...\\n\\n' "\${VIBECRAFTED_SPAWN_WATCH_SECONDS:-10}"
spawn_watch_startup $q_meta $q_transcript $q_report
EOF_MONITOR

  chmod +x "$script_path"
}

spawn_open_startup_monitor_pane() {
  local session_name="$1"
  local workflow_name="$2"
  local landing_kind="$3"
  local landing_name="$4"
  local root_dir="${5:-${SPAWN_ROOT:-$(pwd)}}"
  local common_path monitor_script cmd_script
  local tmp_root="${TMPDIR:-/tmp}"

  [[ -n "$session_name" ]] || return 1
  [[ -n "${SPAWN_META:-}" && -n "${SPAWN_TRANSCRIPT:-}" && -n "${SPAWN_REPORT:-}" ]] || return 1
  command -v zellij >/dev/null 2>&1 || return 1

  common_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)/common.sh"
  tmp_root="${tmp_root%/}"
  monitor_script="$(mktemp "${tmp_root}/vc-startup-monitor.XXXXXX")"
  cmd_script="$(mkdir -p "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tmp" && mktemp "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tmp/vc-spawn-cmd.XXXXXX")"

  spawn_write_startup_monitor_script \
    "$monitor_script" \
    "$common_path" \
    "${SPAWN_META:-}" \
    "${SPAWN_TRANSCRIPT:-}" \
    "${SPAWN_REPORT:-}" \
    "$session_name" \
    "$workflow_name" \
    "$landing_kind" \
    "$landing_name"

  spawn_write_command_script "$cmd_script" "bash '$monitor_script'; exit" || return 1

  zellij --session "$session_name" action new-pane \
    --direction down \
    --height 30% \
    --name "startup-monitor" \
    --cwd "$root_dir" \
    -- "$cmd_script"
}
