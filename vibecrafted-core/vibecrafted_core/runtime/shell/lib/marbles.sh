# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_marbles() {
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  local tool="$1"
  shift
  local script marbles_cmd quoted_args quoted_env operator_session root_dir marbles_run_id runtime launch_ts launch_report
  local loop_skill_name loop_skill_code loop_label loop_file_prefix
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

  loop_skill_name="${VIBECRAFTED_LOOP_SKILL_NAME:-marbles}"
  loop_skill_code="${VIBECRAFTED_LOOP_SKILL_CODE:-$(_vetcoders_skill_prefix "$loop_skill_name")}"
  loop_label="${VIBECRAFTED_LOOP_LABEL:-Marbles}"
  loop_file_prefix="${VIBECRAFTED_LOOP_FILE_PREFIX:-$loop_skill_name}"

  # shellcheck disable=SC2031
  [[ -n "${VIBECRAFTED_SKILL_NAME:-}" ]] || export VIBECRAFTED_SKILL_NAME="$loop_skill_name"
  # shellcheck disable=SC2031
  export VIBECRAFTED_SKILL_CODE="$loop_skill_code"

  root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  marbles_run_id="${VIBECRAFTED_MARBLES_RUN_ID:-${VIBECRAFTED_LOOP_RUN_ID:-$(_vetcoders_generate_run_id "$loop_skill_code")}}"
  runtime="$(_vetcoders_effective_runtime)"
  marbles_env=(
    VIBECRAFTED_MARBLES_RUN_ID="$marbles_run_id"
    VIBECRAFTED_LOOP_SKILL_NAME="$loop_skill_name"
    VIBECRAFTED_LOOP_SKILL_CODE="$loop_skill_code"
    VIBECRAFTED_LOOP_LABEL="$loop_label"
    VIBECRAFTED_LOOP_FILE_PREFIX="$loop_file_prefix"
  )
  local marbles_args=(--agent "$tool" --runtime "$runtime" --skill-name "$loop_skill_name" --skill-code "$loop_skill_code" --loop-label "$loop_label" --loop-file-prefix "$loop_file_prefix")
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
  if [[ -z "$operator_session" ]] && _vetcoders_in_vc_frame; then
    operator_session="$(_vetcoders_current_vc_frame_session_name)"
  fi
  if [[ -z "$operator_session" ]]; then
    operator_session="$(_vetcoders_operator_session_name)"
  fi

  # Inside vc_frame: each marbles run_id gets its own tab named
  # "marbles-<run_id>". Subsequent loops (L2, L3, ...) inherit
  # VIBECRAFTED_MARBLES_TAB_NAME via env and stay in the same tab — one
  # run_id = one tab, no crossover. The "marbles-" prefix distinguishes
  # the tab from workflow/research tabs which also carry run_ids.
  # Temp script keeps vc_frame args ASCII-safe (no inline UTF-8 prompt bytes).
  local vc_frame_bin=""
  if [[ "$runtime" =~ ^(terminal|visible)$ ]] && _vetcoders_in_vc_frame && vc_frame_bin="$(_vetcoders_vc_frame_bin)"; then
    local cmd_script marbles_tab_name
    VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_vc_frame_session_name)"
    export VIBECRAFTED_OPERATOR_SESSION
    marbles_tab_name="${loop_file_prefix}-${marbles_run_id}"
    export VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name"
    marbles_env+=(VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name")
    quoted_env="$(_vetcoders_shell_quote_join "${marbles_env[@]}")"
    marbles_cmd="env ${quoted_env} bash $(_vetcoders_shell_quote "$script") ${quoted_args}"
    cmd_script="$(_vetcoders_tmp_script_path "vibecrafted-marbles" "$root_dir")"
    _vetcoders_write_command_script "$cmd_script" "$marbles_cmd" || return 1
    
    local original_tab
    original_tab="${VC_FRAME_TAB_NAME:-}"
    
    "$vc_frame_bin" action go-to-tab-name "$marbles_tab_name" --create >/dev/null 2>&1 || true
    "$vc_frame_bin" action new-pane \
      --name "$marbles_run_id" \
      --cwd "$root_dir" \
      -- "$cmd_script" >/dev/null || return 1

    printf '%s run launched in vc_frame tab: %s\n' "$loop_label" "$marbles_tab_name"
    printf '  run_id:  %s\n' "$marbles_run_id"
    printf '  inspect: vc-marbles inspect %s\n' "$marbles_run_id"
      
    if [[ -n "$original_tab" ]]; then
      "$vc_frame_bin" action go-to-tab-name "$original_tab" >/dev/null 2>&1 || true
    fi
    
    _vetcoders_marbles_emit_probe "$root_dir" "$marbles_run_id" "launched"
  elif [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
      _vetcoders_spawn_into_operator_session "marbles" "$marbles_cmd" || return 1
      printf '%s run launched in operator session: %s\n' "$loop_label" "$VIBECRAFTED_OPERATOR_SESSION"
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
  # Positional form: `vc-resume <agent> <session_id> [prompt words...]`.
  # Without --session the shared parser routes positionals into tail/prompt,
  # but a resume cannot run without a session — promote the first tail token.
  if [[ -z "$_vetcoders_contract_session" && -n "$_vetcoders_contract_tail" ]]; then
    local -a _resume_positional=()
    read -r -a _resume_positional <<<"$_vetcoders_contract_tail"
    _vetcoders_contract_session="${_resume_positional[0]}"
    local _resume_rest="${_vetcoders_contract_tail#"${_resume_positional[0]}"}"
    _resume_rest="${_resume_rest# }"
    if [[ "$_vetcoders_contract_prompt" == "$_vetcoders_contract_tail" ]]; then
      _vetcoders_contract_prompt="$_resume_rest"
    fi
    _vetcoders_contract_tail="$_resume_rest"
  fi
  [[ -n "$_vetcoders_contract_session" ]] || {
    echo "Usage: vc-resume [<claude|codex|gemini|agy|junie|grok>] <session_id> [prompt ...] | --session <session_id> [--prompt <text>] [--file <path>]" >&2
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
  local runtime
  local resume_cmd
  resume_prompt="$(_vetcoders_compose_input_context "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  runtime="$(_vetcoders_effective_runtime)"
  resume_cmd="$(_vetcoders_resume_command "$tool" "$_vetcoders_contract_session" "$resume_prompt")" || return 1

  # prepare_operator_runtime can create or attach an operator surface only when
  # we are already in vc_frame, know an operator session, or have an interactive
  # terminal. Plain headless resume falls back to the agent CLI directly.
  if [[ "$runtime" =~ ^(terminal|visible)$ ]] && {
    _vetcoders_in_vc_frame || [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]] || [[ -t 0 && -t 1 ]]
  }; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
      _vetcoders_spawn_into_operator_session "resume-${tool}" "$resume_cmd" || return 1
      printf 'Resume launched in operator session: %s\n' "$VIBECRAFTED_OPERATOR_SESSION"
      printf '  agent:   %s\n' "$tool"
      printf '  session: %s\n' "$_vetcoders_contract_session"
      return 0
    fi
  fi

  # No operator surface (piped / async-supervisor baton-pass): run the agent's
  # NON-INTERACTIVE resume invocation directly. Recompute in headless mode so we
  # don't eval an interactive command that would hang without a tty.
  resume_cmd="$(_vetcoders_resume_command "$tool" "$_vetcoders_contract_session" "$resume_prompt" headless)" || return 1
  eval "$resume_cmd"
}

_vetcoders_resume_command() {
  local tool="$1"
  local session_id="$2"
  local resume_prompt="${3:-}"
  # mode: "interactive" (resume into a visible operator pane) | "headless"
  # (direct eval / async-supervisor baton-pass — no tty). Per-agent resume flags
  # differ; the headless invocations were verified against each agent's --help.
  local mode="${4:-interactive}"
  local quoted_session quoted_prompt
  quoted_session="$(_vetcoders_shell_quote "$session_id")"
  if [[ -n "$resume_prompt" ]]; then
    quoted_prompt="$(_vetcoders_shell_quote "$resume_prompt")"
  fi

  case "$tool" in
    claude)
      # headless resume needs --print (+ skip-permissions); plain --resume opens
      # an interactive session and would hang under eval with no tty.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'claude --print --dangerously-skip-permissions --resume %s %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'claude --print --dangerously-skip-permissions --resume %s\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'claude --resume %s %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'claude --resume %s\n' "$quoted_session"
      fi
      ;;
    codex)
      # headless = `codex exec resume` (non-interactive); `codex resume` is the
      # interactive picker and cannot run under a pipe.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'codex exec --dangerously-bypass-approvals-and-sandbox resume %s %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'codex exec --dangerously-bypass-approvals-and-sandbox resume %s\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'codex resume %s %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'codex resume %s\n' "$quoted_session"
      fi
      ;;
    gemini)
      # NOTE: gemini --resume takes an index or "latest", NOT a session UUID;
      # resuming a specific session by id is a known gap (use --session-file for
      # that). Best-effort: -p makes it headless.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'gemini --approval-mode yolo --resume %s -p %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'gemini --approval-mode yolo --resume %s -p ""\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'gemini --resume %s %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'gemini --resume %s\n' "$quoted_session"
      fi
      ;;
    agy)
      # agy resumes by --conversation <id>; headless needs --print <prompt>.
      # Since agy 1.1 --print takes the prompt as its VALUE (Go flags) and
      # print mode reads no stdin — flags first, prompt as the flag value.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'agy --dangerously-skip-permissions --conversation %s --print %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'agy --dangerously-skip-permissions --conversation %s --print "Continue."\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'agy --conversation %s --prompt-interactive %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'agy --conversation %s\n' "$quoted_session"
      fi
      ;;
    junie)
      # junie is non-interactive by construction (runs a task and exits); the
      # same command serves both modes.
      if [[ -n "$resume_prompt" ]]; then
        printf 'junie --session-id=%s --resume --task=%s --project=. --skip-update-check\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'junie --session-id=%s --resume --project=. --skip-update-check\n' "$quoted_session"
      fi
      ;;
    grok)
      # grok --single is one-shot non-interactive. NEVER pass --restore-code: it
      # checks out the original session's commit and would clobber the working tree.
      # Use streaming-json (matching verified python lane + grok 0.2.97 headless)
      # so session/usage parse via JSON_TOKEN_PATTERNS works from transcript.
      if [[ -n "$resume_prompt" ]]; then
        printf 'grok --resume %s --cwd . --permission-mode bypassPermissions --no-alt-screen --output-format streaming-json --single %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'grok --resume %s --cwd . --permission-mode bypassPermissions --no-alt-screen --output-format streaming-json\n' "$quoted_session"
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
    echo "Usage: vc-resume [<claude|codex|gemini|agy|junie|grok>] <session_id> [prompt ...] | --session <session_id> [--prompt <text>] [--file <path>]" >&2
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
