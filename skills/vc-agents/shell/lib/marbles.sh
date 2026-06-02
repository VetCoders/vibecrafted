# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_marbles() {
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  local tool="$1"
  shift
  local script marbles_cmd quoted_args quoted_env operator_session root_dir marbles_run_id runtime launch_ts launch_report
  local -a marbles_env
  script="$(_vetcoders_spawn_script "$tool" "marbles_spawn.sh")" || return 1
  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is only supported by vibecrafted resume." >&2
    return 1
  }
  if [[ -n "$_vetcoders_contract_task" ]]; then
    [[ -z "$_vetcoders_contract_file" ]] || {
      echo "Marbles accepts one file source: use either --task or --file, not both." >&2
      return 1
    }
    _vetcoders_contract_file="$_vetcoders_contract_task"
  fi

  local source_count=0
  [[ -n "$_vetcoders_contract_depth" ]] && ((source_count+=1))
  [[ -n "$_vetcoders_contract_file" ]] && ((source_count+=1))
  [[ -n "$_vetcoders_contract_prompt" ]] && ((source_count+=1))
  [[ $source_count -le 1 ]] || {
    echo "Marbles accepts one source at a time: use exactly one of --depth, --file, or --prompt." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_count" ]] || _vetcoders_require_positive_int "$_vetcoders_contract_count" "--count" || return 1
  [[ -z "$_vetcoders_contract_depth" ]] || _vetcoders_require_positive_int "$_vetcoders_contract_depth" "--depth" || return 1

  # shellcheck disable=SC2031
  [[ -n "${VIBECRAFTED_SKILL_NAME:-}" ]] || export VIBECRAFTED_SKILL_NAME="marbles"
  # shellcheck disable=SC2031
  export VIBECRAFTED_SKILL_CODE="marb"

  root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  marbles_run_id="${VIBECRAFTED_MARBLES_RUN_ID:-$(_vetcoders_generate_run_id "marb")}"
  runtime="$(_vetcoders_effective_runtime)"
  marbles_env=(VIBECRAFTED_MARBLES_RUN_ID="$marbles_run_id")
  local marbles_args=(--agent "$tool" --runtime "$runtime")
  local source_args=()
  [[ -n "$_vetcoders_contract_root" ]] && marbles_args+=(--root "$_vetcoders_contract_root")
  [[ -n "$_vetcoders_contract_count" ]] && marbles_args+=(--count "$_vetcoders_contract_count")

  if [[ -n "$_vetcoders_contract_file" ]]; then
    source_args=(--file "$_vetcoders_contract_file")
  elif [[ -n "$_vetcoders_contract_prompt" ]]; then
    source_args=(--prompt "$_vetcoders_contract_prompt")
  else
    source_args=(--depth "${_vetcoders_contract_depth:-3}")
  fi
  if [[ "$runtime" == "headless" ]]; then
    marbles_args+=(--no-watch)
    launch_ts="$(_vetcoders_spawn_timestamp)"
    launch_report="$(_vetcoders_marbles_l1_report_path "$root_dir" "$launch_ts" "$tool")"
    marbles_env+=(VIBECRAFTED_SPAWN_TS="$launch_ts" VIBECRAFTED_SUPPRESS_REPORT_HINT=1)
    printf 'Agent launched. Report will land at: %s\n' "$launch_report"
  fi
  marbles_args+=("${source_args[@]}")

  quoted_env="$(_vetcoders_shell_quote_join "${marbles_env[@]}")"
  quoted_args="$(_vetcoders_shell_quote_join "${marbles_args[@]}")"
  marbles_cmd="env ${quoted_env} bash $(_vetcoders_shell_quote "$script") ${quoted_args}"
  operator_session="${VIBECRAFTED_OPERATOR_SESSION:-}"
  if [[ -z "$operator_session" ]] && _vetcoders_in_zellij; then
    operator_session="$(_vetcoders_current_zellij_session_name)"
  fi
  if [[ -z "$operator_session" ]]; then
    operator_session="$(_vetcoders_operator_session_name)"
  fi

  # Inside zellij: each marbles run_id gets its own tab named
  # "marbles-<run_id>". Subsequent loops (L2, L3, ...) inherit
  # VIBECRAFTED_MARBLES_TAB_NAME via env and stay in the same tab — one
  # run_id = one tab, no crossover. The "marbles-" prefix distinguishes
  # the tab from workflow/research tabs which also carry run_ids.
  # Temp script keeps zellij args ASCII-safe (no inline UTF-8 prompt bytes).
  if [[ "$runtime" =~ ^(terminal|visible)$ ]] && _vetcoders_in_zellij && command -v zellij >/dev/null 2>&1; then
    local cmd_script marbles_tab_name
    VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_zellij_session_name)"
    export VIBECRAFTED_OPERATOR_SESSION
    marbles_tab_name="marbles-${marbles_run_id}"
    export VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name"
    marbles_env+=(VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name")
    quoted_env="$(_vetcoders_shell_quote_join "${marbles_env[@]}")"
    marbles_cmd="env ${quoted_env} bash $(_vetcoders_shell_quote "$script") ${quoted_args}"
    cmd_script="$(_vetcoders_tmp_script_path "vibecrafted-marbles" "$root_dir")"
    _vetcoders_write_command_script "$cmd_script" "$marbles_cmd" || return 1
    
    local original_tab
    original_tab="${ZELLIJ_TAB_NAME:-}"
    
    zellij action go-to-tab-name "$marbles_tab_name" --create >/dev/null 2>&1 || true
    zellij action new-pane \
      --name "$marbles_run_id" \
      --cwd "$root_dir" \
      -- "$cmd_script" >/dev/null || return 1

    printf 'Marbles run launched in zellij tab: %s\n' "$marbles_tab_name"
    printf '  run_id:  %s\n' "$marbles_run_id"
    printf '  inspect: vc-marbles inspect %s\n' "$marbles_run_id"
      
    if [[ -n "$original_tab" ]]; then
      zellij action go-to-tab-name "$original_tab" >/dev/null 2>&1 || true
    fi
    
    _vetcoders_marbles_emit_probe "$root_dir" "$marbles_run_id" "launched"
  elif [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
      _vetcoders_spawn_into_operator_session "marbles" "$marbles_cmd" || return 1
      printf 'Marbles run launched in operator session: %s\n' "$VIBECRAFTED_OPERATOR_SESSION"
      printf '  run_id:  %s\n' "$marbles_run_id"
      printf '  inspect: vc-marbles inspect %s\n' "$marbles_run_id"
      _vetcoders_marbles_emit_probe "$root_dir" "$marbles_run_id" "launched"
    else
      env "${marbles_env[@]}" bash "$script" "${marbles_args[@]}"
    fi
  else
    env "${marbles_env[@]}" bash "$script" "${marbles_args[@]}"
  fi
}

_vetcoders_resume_agent() {
  local tool="$1"
  shift
  _vetcoders_parse_contract "$@" || return 1
  [[ -n "$_vetcoders_contract_session" ]] || {
    echo "Usage: vc-resume [<claude|codex|gemini|agy|junie|grok>] --session <session_id> [--prompt <text>] [--file <path>]" >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is only supported by vibecrafted marbles." >&2
    return 1
  }

  local resume_prompt
  resume_prompt="$(_vetcoders_compose_input_context "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1

  case "$tool" in
    claude)
      if [[ -n "$resume_prompt" ]]; then
        claude --resume "$_vetcoders_contract_session" "$resume_prompt"
      else
        claude --resume "$_vetcoders_contract_session"
      fi
      ;;
    codex)
      if [[ -n "$resume_prompt" ]]; then
        codex resume "$_vetcoders_contract_session" "$resume_prompt"
      else
        codex resume "$_vetcoders_contract_session"
      fi
      ;;
    gemini)
      if [[ -n "$resume_prompt" ]]; then
        gemini --resume "$_vetcoders_contract_session" "$resume_prompt"
      else
        gemini --resume "$_vetcoders_contract_session"
      fi
      ;;
    agy)
      if [[ -n "$resume_prompt" ]]; then
        agy --conversation "$_vetcoders_contract_session" --prompt-interactive "$resume_prompt"
      else
        agy --conversation "$_vetcoders_contract_session"
      fi
      ;;
    junie)
      if [[ -n "$resume_prompt" ]]; then
        junie --session-id="$_vetcoders_contract_session" --resume --task="$resume_prompt" --project=. --skip-update-check
      else
        junie --session-id="$_vetcoders_contract_session" --resume --project=. --skip-update-check
      fi
      ;;
    grok)
      if [[ -n "$resume_prompt" ]]; then
        grok --resume "$_vetcoders_contract_session" --cwd . --permission-mode bypassPermissions --no-alt-screen --single "$resume_prompt"
      else
        grok --resume "$_vetcoders_contract_session" --cwd . --permission-mode bypassPermissions --no-alt-screen
      fi
      ;;
    *)
      echo "Unknown agent for resume: $tool" >&2
      return 1
      ;;
  esac
}

_vetcoders_agent_for_session() {
  local session_id="$1"
  [[ -n "$session_id" ]] || return 1
  python3 - "$session_id" "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/artifacts" <<'PY'
import json
import pathlib
import sys

session_id, artifacts_root = sys.argv[1:3]
root = pathlib.Path(artifacts_root)
if not root.is_dir():
    raise SystemExit(1)

matches = []
for meta_path in root.rglob("*.meta.json"):
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    if payload.get("session_id") != session_id:
        continue
    agent = payload.get("agent")
    if agent:
        try:
            mtime = meta_path.stat().st_mtime
        except OSError:
            mtime = 0
        matches.append((mtime, agent))

if not matches:
    raise SystemExit(1)
print(sorted(matches)[-1][1])
PY
}

vc-resume() {
  local tool="${1:-}"
  [[ -n "$tool" ]] || {
    echo "Usage: vc-resume [<claude|codex|gemini|agy|junie|grok>] --session <session_id> [--prompt <text>] [--file <path>]" >&2
    return 1
  }
  if [[ "$tool" == "--session" ]]; then
    _vetcoders_parse_contract "$@" || return 1
    tool="$(_vetcoders_agent_for_session "$_vetcoders_contract_session")" || {
      echo "Could not infer agent for session: $_vetcoders_contract_session" >&2
      echo "Usage: vc-resume <claude|codex|gemini|agy|junie|grok> --session $_vetcoders_contract_session" >&2
      return 1
    }
  else
    shift || true
  fi
  _vetcoders_resume_agent "$tool" "$@"
}

codex-marbles() { _vetcoders_marbles codex "$@"; }
claude-marbles() { _vetcoders_marbles claude "$@"; }
gemini-marbles() { _vetcoders_marbles gemini "$@"; }
agy-marbles() { _vetcoders_marbles agy "$@"; }
junie-marbles() { _vetcoders_marbles junie "$@"; }
grok-marbles() { _vetcoders_marbles grok "$@"; }

# Marbles control subcommands
marbles-pause()   { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" pause "$@"; }
marbles-stop()    { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" stop "$@"; }
marbles-resume()  { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" resume "$@"; }
marbles-session() { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" session "$@"; }
marbles-inspect() { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" inspect "$@"; }
marbles-delete()  { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" delete "$@"; }
marbles-gc()      { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" gc "$@"; }
