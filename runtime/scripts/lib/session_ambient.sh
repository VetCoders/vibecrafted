#!/usr/bin/env bash


spawn_normalize_ambient_context() {
  local run_id lock expected_lock operator_session expected_session

  run_id="${VIBECRAFTED_RUN_ID:-}"
  lock="${VIBECRAFTED_RUN_LOCK:-}"
  operator_session="${VIBECRAFTED_OPERATOR_SESSION:-}"

  [[ -n "$run_id" ]] || {
    unset VIBECRAFTED_RUN_LOCK VIBECRAFTED_SKILL_CODE VIBECRAFTED_SKILL_NAME VIBECRAFTED_LOOP_NR
    return 0
  }

  [[ -n "$lock" ]] || return 0

  expected_lock="$(spawn_expected_run_lock_path "$run_id" 2>/dev/null || true)"
  if [[ -n "$expected_lock" && "$lock" == "$expected_lock" && -f "$lock" ]]; then
    return 0
  fi

  expected_session="$(spawn_operator_session_name_for_run_id "$run_id")"
  unset VIBECRAFTED_RUN_LOCK VIBECRAFTED_SKILL_CODE VIBECRAFTED_SKILL_NAME VIBECRAFTED_LOOP_NR

  if [[ "$(basename "$lock")" != "${run_id}.lock" ]]; then
    if [[ -n "$operator_session" && "$operator_session" != "$expected_session" ]]; then
      unset VIBECRAFTED_OPERATOR_SESSION
    fi
    return 0
  fi

  unset VIBECRAFTED_RUN_ID
  if [[ -n "$operator_session" ]]; then
    unset VIBECRAFTED_OPERATOR_SESSION
  fi
}

spawn_has_ambient_run_context() {
  [[ -n "${SPAWN_AGENT:-}" ]] || return 1
  [[ -n "${SPAWN_RUN_ID:-}" ]] || return 1
  [[ -n "${VIBECRAFTED_RUN_ID:-}" ]] || return 1
  [[ "${SPAWN_RUN_ID}" == "${VIBECRAFTED_RUN_ID}" ]] || return 1
  [[ -z "${VIBECRAFTED_OPERATOR_SESSION:-}" ]] || return 1
  spawn_in_zellij_context && return 1
  return 0
}

spawn_effective_run_id() {
  spawn_normalize_ambient_context
  spawn_has_ambient_run_context && return 1
  [[ -n "${VIBECRAFTED_RUN_ID:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_RUN_ID}"
}

spawn_effective_skill_code() {
  spawn_normalize_ambient_context
  spawn_has_ambient_run_context && return 1
  [[ -n "${VIBECRAFTED_SKILL_CODE:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_SKILL_CODE}"
}
