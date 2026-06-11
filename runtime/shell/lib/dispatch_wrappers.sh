# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

codex-review() {
  _vetcoders_spawn_plan codex review "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-plan() {
  _vetcoders_spawn_plan codex plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-implement() {
  _vetcoders_spawn_plan codex implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-review() {
  _vetcoders_spawn_plan claude review "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-plan() {
  _vetcoders_spawn_plan claude plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-implement() {
  _vetcoders_spawn_plan claude implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-review() {
  _vetcoders_spawn_plan gemini review "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-plan() {
  _vetcoders_spawn_plan gemini plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-implement() {
  _vetcoders_spawn_plan gemini implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

agy-review() {
  _vetcoders_spawn_plan agy review "$1" --runtime "$(_vetcoders_default_runtime)"
}

agy-plan() {
  _vetcoders_spawn_plan agy plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

agy-implement() {
  _vetcoders_spawn_plan agy implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-review() {
  _vetcoders_spawn_plan junie review "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-plan() {
  _vetcoders_spawn_plan junie plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-implement() {
  _vetcoders_spawn_plan junie implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-review() {
  _vetcoders_spawn_plan grok review "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-plan() {
  _vetcoders_spawn_plan grok plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-implement() {
  _vetcoders_spawn_plan grok implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-research() {
  _vetcoders_spawn_plan codex research "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-research() {
  _vetcoders_spawn_plan claude research "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-research() {
  _vetcoders_spawn_plan gemini research "$1" --runtime "$(_vetcoders_default_runtime)"
}

agy-research() {
  _vetcoders_spawn_plan agy research "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-research() {
  _vetcoders_spawn_plan junie research "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-research() {
  _vetcoders_spawn_plan grok research "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-prompt() {
  _vetcoders_prompt codex implement "$@"
}

claude-prompt() {
  _vetcoders_prompt claude implement "$@"
}

gemini-prompt() {
  _vetcoders_prompt gemini implement "$@"
}

agy-prompt() {
  _vetcoders_prompt agy implement "$@"
}

junie-prompt() {
  _vetcoders_prompt junie implement "$@"
}

grok-prompt() {
  _vetcoders_prompt grok implement "$@"
}

codex-observe() {
  _vetcoders_observe codex "$@"
}

codex-await() {
  _vetcoders_await codex "$@"
}

claude-observe() {
  _vetcoders_observe claude "$@"
}

claude-await() {
  _vetcoders_await claude "$@"
}

gemini-observe() {
  _vetcoders_observe gemini "$@"
}

gemini-await() {
  _vetcoders_await gemini "$@"
}

agy-observe() {
  _vetcoders_observe agy "$@"
}

agy-await() {
  _vetcoders_await agy "$@"
}

junie-observe() {
  _vetcoders_observe junie "$@"
}

junie-await() {
  _vetcoders_await junie "$@"
}

grok-observe() {
  _vetcoders_observe grok "$@"
}

grok-await() {
  _vetcoders_await grok "$@"
}

_vetcoders_skill() {
  local tool="$1"
  local skill="$2"
  shift 2
  # shellcheck disable=SC2031
  local loop_nr="${VIBECRAFTED_LOOP_NR:-0}"
  local inherited_run_id
  local inherited_run_lock
  inherited_run_id="$(_vetcoders_effective_run_id 2>/dev/null || true)"
  inherited_run_lock="$(_vetcoders_effective_run_lock 2>/dev/null || true)"
  _vetcoders_parse_contract "$@" || return 1
  if [[ "$skill" == "polarize" && -n "$_vetcoders_contract_count" ]]; then
    _vetcoders_polarize_loop "$tool" "$@"
    return
  fi
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is only supported by vibecrafted resume." >&2
    return 1
  }
  local skill_code root run_id run_lock
  skill_code="$(_vetcoders_skill_prefix "$skill")"
  root="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  run_id="$inherited_run_id"
  [[ -n "$run_id" ]] || run_id="$(_vetcoders_generate_run_id "$skill_code")"
  run_lock="$inherited_run_lock"
  if [[ -z "$run_lock" || ! -f "$run_lock" ]]; then
    run_lock="$(_vetcoders_create_run_lock "$run_id" "$tool" "$skill" "$root")" || return 1
  fi
  # Default the prism_* locals: polarize only computes them when a --task is
  # given (see below). Without that, set -u must not trip on the band check at
  # dispatch time — an empty band falls through to a normal polarize dispatch.
  local prompt prism_payload="" prism_command="" prism_band="" prism_score="" memo_file=""
  if [[ "$skill" == "polarize" && -n "$_vetcoders_contract_task" ]]; then
    prism_payload="$(_vetcoders_write_polarize_prism_payload "$root" "$run_id" "$_vetcoders_contract_task" "$_vetcoders_contract_no_aicx")" || return 1
    prism_command="$(_vetcoders_polarize_prism_command_text "$root" "$_vetcoders_contract_task" "$_vetcoders_contract_no_aicx")"
    prism_band="$(_vetcoders_polarize_band_select "$prism_payload")" || return 1
    prism_score="$(_vetcoders_polarize_score "$prism_payload")" || return 1
    case "$prism_band" in
      abort)
        printf 'vc-polarize aborted: prism score %s/15 is below threshold. Inspect %s\n' "$prism_score" "$prism_payload" >&2
        return 12
        ;;
      memo)
        memo_file="$(_vetcoders_write_polarize_memo "$prism_payload" "$run_id" "$root" "$_vetcoders_contract_task" "$prism_band")" || return 1
        if [[ -z "$_vetcoders_contract_no_context_corpus" ]]; then
          _vetcoders_polarize_emit_context_pack "$tool" "" "$prism_payload" "$run_id" "$root" "$prism_band" "$_vetcoders_contract_task"
        else
          printf 'vc-polarize: --no-context-corpus set; skipped context-corpus emission.\n' >&2
        fi
        printf 'vc-polarize: emitted local memo (band %s, score %s/15). No agent dispatched. Memo: %s\n' "$(_vetcoders_polarize_band_range "$prism_band")" "$prism_score" "$memo_file"
        return 0
        ;;
      pass|doctrine)
        prompt="$(_vetcoders_compose_polarize_prompt "$_vetcoders_contract_prompt" "$_vetcoders_contract_file" "$_vetcoders_contract_task" "$prism_payload" "$prism_command" "$prism_band" "$prism_score")" || return 1
        ;;
      *)
        printf 'vc-polarize: unknown prism band %s from %s\n' "$prism_band" "$prism_payload" >&2
        return 1
        ;;
    esac
  else
    if [[ -n "$_vetcoders_contract_task" ]]; then
      if [[ -n "$_vetcoders_contract_prompt" ]]; then
        _vetcoders_contract_prompt+=$'\n\n'
      fi
      _vetcoders_contract_prompt+="Task: $_vetcoders_contract_task"
    fi
    prompt="$(_vetcoders_compose_skill_prompt "$skill" "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  fi
  local runtime
  runtime="$(_vetcoders_effective_runtime)"
  _vetcoders_prepare_operator_runtime "$runtime" || return 1
  local spawn_args=(--runtime "$runtime")
  [[ -z "$_vetcoders_contract_dry_run" ]] || spawn_args+=(--dry-run)
  [[ -n "$_vetcoders_contract_root" ]] && spawn_args+=(--root "$_vetcoders_contract_root")
  if [[ "$skill" == "polarize" && "$prism_band" =~ ^(pass|doctrine)$ ]]; then
    local dispatch_output dispatch_status agent_log session_uuid
    agent_log="$(_vetcoders_store_dir "$root")/polarize/$run_id/${tool}.stdout.log"
    mkdir -p "$(dirname "$agent_log")"
    dispatch_output="$(_vetcoders_dispatch_skill_prompt "$tool" "$skill" "$skill_code" "$loop_nr" "$run_id" "$run_lock" "$prompt" "${spawn_args[@]}")"
    dispatch_status=$?
    printf '%s\n' "$dispatch_output"
    printf '%s\n' "$dispatch_output" > "$agent_log"
    _vetcoders_print_launch_receipt "$tool" "$skill" "$run_id" "$root" "$dispatch_status"
    [[ "$dispatch_status" -eq 0 ]] || return "$dispatch_status"
    if [[ -z "$_vetcoders_contract_no_context_corpus" ]]; then
      session_uuid="$(_vetcoders_capture_session_uuid "$agent_log")"
      _vetcoders_polarize_emit_context_pack "$tool" "$session_uuid" "$prism_payload" "$run_id" "$root" "$prism_band" "$_vetcoders_contract_task"
    else
      printf 'vc-polarize: --no-context-corpus set; skipped context-corpus emission.\n' >&2
    fi
    return 0
  fi

  _vetcoders_dispatch_skill_prompt "$tool" "$skill" "$skill_code" "$loop_nr" "$run_id" "$run_lock" "$prompt" "${spawn_args[@]}"
  local _dispatch_rc=$?
  _vetcoders_print_launch_receipt "$tool" "$skill" "$run_id" "$root" "$_dispatch_rc"
  _vetcoders_maybe_spawn_await_pane "$tool" "$skill" "$run_id" "$root"
  return "$_dispatch_rc"
}

# Spawn a zellij side-pane running vibecrafted-await-watch for the just-fired
# worker, so the operator gets live transcript tail + automatic exit when the
# worker is done (status=completed/failed, or wrapper dies + transcript idle).
#
# Silent no-op unless:
#   - the operator is inside an active zellij session
#   - the await-watch helper is installed and executable
#   - jq is available (helper needs it to parse meta.json)
#
# Resolves meta.json by greping the artifacts dir for a meta whose .run_id
# matches the freshly-launched dispatch's run_id. Worker filename is
# prompt_id-based, not run_id-based, so content grep is the only reliable
# resolver.
_vetcoders_await_watch_helper() {
  local repo_root crafted_root candidate
  repo_root="$(_vetcoders_repo_root)"
  crafted_root="${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}/vibecrafted-current"

  for candidate in \
    "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/runtime/scripts/vibecrafted-await-watch.sh}" \
    "$repo_root/runtime/scripts/vibecrafted-await-watch.sh" \
    "$crafted_root/runtime/scripts/vibecrafted-await-watch.sh" \
    "$(_vetcoders_frontier_file "runtime/scripts/vibecrafted-await-watch.sh" 2>/dev/null || true)"
  do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    return 0
  done

  return 1
}

_vetcoders_maybe_spawn_await_pane() {
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  local tool="$1" skill="$2" run_id="$3" root="$4"
  local zellij_bin=""
  zellij_bin="$(_vetcoders_zellij_bin)" || return 0
  _vetcoders_in_zellij || return 0
  command -v jq >/dev/null 2>&1 || return 0

  local helper
  helper="$(_vetcoders_await_watch_helper 2>/dev/null || true)"
  [[ -n "$helper" && -x "$helper" ]] || return 0

  # Best effort: short delay so the wrapper has a moment to drop meta.json.
  ( sleep 1
    local pane_name="await:${tool}:${run_id##*-}"
    local cwd="${root:-$PWD}"
    "$zellij_bin" action new-pane \
      --name "$pane_name" \
      --close-on-exit \
      --cwd "$cwd" \
      -- "$helper" --run-id "$run_id" >/dev/null 2>&1 || true
  ) &
}

_vetcoders_skill_entry() {
  local tool="$1"
  local skill="$2"
  shift 2
  case "$skill" in
    marbles) _vetcoders_marbles "$tool" "$@" ;;
    polarize) _vetcoders_skill "$tool" polarize "$@" ;;
    *) _vetcoders_skill "$tool" "$skill" "$@" ;;
  esac
}
