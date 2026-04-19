#!/usr/bin/env bash


spawn_in_zellij_context() {
  # ZELLIJ=0 is a valid pane index inside zellij — do NOT treat as false.
  # Only absent ZELLIJ means we're outside.
  [[ -n "${ZELLIJ_PANE_ID:-}" ]] || [[ -n "${ZELLIJ+set}" ]]
}

spawn_current_zellij_session_name() {
  printf '%s\n' "${ZELLIJ_SESSION_NAME:-}"
}

spawn_effective_operator_session() {
  spawn_normalize_ambient_context
  local session_name="${VIBECRAFTED_OPERATOR_SESSION:-}"
  if [[ -n "$session_name" ]]; then
    printf '%s\n' "$session_name"
    return 0
  fi

  session_name="${ZELLIJ_SESSION_NAME:-}"
  if [[ -n "$session_name" ]]; then
    printf '%s\n' "$session_name"
    return 0
  fi

  command -v zellij >/dev/null 2>&1 || return 1

  session_name="$(
    zellij list-sessions 2>/dev/null \
      | sed 's/\x1b\[[0-9;]*m//g' \
      | awk '/\(current\)/ {print $1; exit}'
  )"
  [[ -n "$session_name" ]] || return 1
  printf '%s\n' "$session_name"
}

spawn_in_target_zellij_session() {
  local target_session=""
  target_session="$(spawn_effective_operator_session 2>/dev/null || true)"
  spawn_in_zellij_context || return 1
  [[ -n "$target_session" ]] || return 0
  [[ "$(spawn_current_zellij_session_name)" == "$target_session" ]]
}

spawn_current_tab_id() {
  local raw=""
  command -v zellij >/dev/null 2>&1 || return 1
  raw="$(zellij action current-tab-info --json 2>/dev/null || true)"
  python3 - "$raw" <<'PY'
import json
import sys

raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
if not raw:
    raise SystemExit(1)
try:
    payload = json.loads(raw)
except Exception:
    raise SystemExit(1)

if isinstance(payload, list):
    payload = payload[0] if payload else {}
if not isinstance(payload, dict):
    raise SystemExit(1)

for key in ("tab_id", "id", "position", "index"):
    value = payload.get(key)
    if value not in (None, ""):
        print(value)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

spawn_tab_id_by_name() {
  local tab_name="${1:-}"
  local raw=""
  [[ -n "$tab_name" ]] || return 1
  command -v zellij >/dev/null 2>&1 || return 1
  raw="$(zellij action list-tabs --json 2>/dev/null || true)"
  python3 - "$tab_name" "$raw" <<'PY'
import json
import sys

target_name = sys.argv[1]
raw = (sys.argv[2] if len(sys.argv) > 2 else "").strip()
if not raw:
    raise SystemExit(1)
try:
    payload = json.loads(raw)
except Exception:
    raise SystemExit(1)

def extract_tab_id(node):
    for key in ("tab_id", "id", "position", "index"):
        value = node.get(key)
        if value not in (None, ""):
            return value
    return None

def visit(node):
    if isinstance(node, dict):
        name = node.get("name")
        if name in (None, ""):
            name = node.get("tab_name")
        if str(name or "") == target_name:
            tab_id = extract_tab_id(node)
            if tab_id is not None:
                print(tab_id)
                return True
        for value in node.values():
            if visit(value):
                return True
    elif isinstance(node, list):
        for value in node:
            if visit(value):
                return True
    return False

if not visit(payload):
    raise SystemExit(1)
PY
}

spawn_current_focused_pane_id() {
  local raw=""
  command -v zellij >/dev/null 2>&1 || return 1
  raw="$(zellij action list-panes --json --state 2>/dev/null || true)"
  python3 - "$raw" <<'PY'
import json
import sys

raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
if not raw:
    raise SystemExit(1)
try:
    payload = json.loads(raw)
except Exception:
    raise SystemExit(1)

def is_truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False

def pane_id(node):
    for key in ("pane_id", "id"):
        value = node.get(key)
        if value not in (None, ""):
            return value
    return None

def visit(node):
    if isinstance(node, dict):
        focused = node.get("is_focused")
        if focused is None:
            focused = node.get("focused")
        if is_truthy(focused):
            pid = pane_id(node)
            if pid is not None:
                print(pid)
                return True
        for value in node.values():
            if visit(value):
                return True
    elif isinstance(node, list):
        for value in node:
            if visit(value):
                return True
    return False

if not visit(payload):
    raise SystemExit(1)
PY
}

spawn_pane_direction() {
  # Grid policy: 4 per row, 8 per tab, 9th opens new tab.
  # Uses SPAWN_LOOP_NR (marbles) or VIBECRAFTED_PANE_SEQ (manual).
  # Fresh top-level spawns default to a new tab so they never land in a stale
  # operator tab by accident.
  local seq=""
  local max_per_row=4
  local max_per_tab=8

  if [[ -n "${SPAWN_LOOP_NR:-}" && "${SPAWN_LOOP_NR:-0}" -gt 0 ]]; then
    seq="${SPAWN_LOOP_NR}"
  elif [[ -n "${VIBECRAFTED_PANE_SEQ:-}" && "${VIBECRAFTED_PANE_SEQ:-0}" -gt 0 ]]; then
    seq="${VIBECRAFTED_PANE_SEQ}"
  else
    printf 'new-tab\n'
    return 0
  fi

  if (( seq >= max_per_tab )); then
    printf 'new-tab\n'
  elif (( seq > 0 && seq % max_per_row == 0 )); then
    printf 'down\n'
  else
    printf 'right\n'
  fi
}

spawn_current_tab_name() {
  # Return the name of the currently focused zellij tab via env.
  printf '%s\n' "${ZELLIJ_TAB_NAME:-}"
}

spawn_in_marbles_tab() {
  # Route a pane into the dedicated marbles tab without stealing operator focus.
  # Called only when SPAWN_LOOP_NR > 0 AND VIBECRAFTED_MARBLES_TAB_NAME is set.
  local launcher="$1"
  local pane_name="$2"
  local direction="$3"
  local marbles_tab="${VIBECRAFTED_MARBLES_TAB_NAME:-}"
  local original_tab_id=""
  local marbles_tab_id=""
  local cmd_script=""
  local launch_cmd="bash '$launcher'"
  local pane_direction="$direction"

  [[ -n "$marbles_tab" ]] || return 1

  if [[ "$pane_direction" == "new-tab" ]]; then
    pane_direction="right"
  fi

  cmd_script="$(spawn_tmp_script_path "vc-spawn-cmd" "${SPAWN_ROOT:-$(pwd)}")"
  spawn_write_command_script "$cmd_script" "$launch_cmd"

  marbles_tab_id="$(spawn_tab_id_by_name "$marbles_tab" 2>/dev/null || true)"
  if [[ -z "$marbles_tab_id" ]]; then
    original_tab_id="$(spawn_current_tab_id 2>/dev/null || true)"
    zellij action go-to-tab-name "$marbles_tab" --create >/dev/null 2>&1 || true
    marbles_tab_id="$(spawn_tab_id_by_name "$marbles_tab" 2>/dev/null || true)"
    if [[ -n "$original_tab_id" ]]; then
      zellij action go-to-tab-by-id "$original_tab_id" >/dev/null 2>&1 || true
    fi
  fi

  # Create the pane inside the marbles tab. If tab-id lookup fails, keep a
  # conservative fallback path that restores the active tab by stable ID.
  if [[ -n "$marbles_tab_id" ]]; then
    zellij action new-pane \
      --tab-id "$marbles_tab_id" \
      --direction "$pane_direction" \
      --name "$pane_name" \
      --cwd "${SPAWN_ROOT:-$(pwd)}" \
      -- "$cmd_script" >/dev/null
  else
    if [[ -z "$original_tab_id" ]]; then
      original_tab_id="$(spawn_current_tab_id 2>/dev/null || true)"
    fi
    zellij action go-to-tab-name "$marbles_tab" --create >/dev/null 2>&1 || true
    zellij action new-pane \
      --direction "$pane_direction" \
      --name "$pane_name" \
      --cwd "${SPAWN_ROOT:-$(pwd)}" \
      -- "$cmd_script" >/dev/null
    if [[ -n "$original_tab_id" ]]; then
      zellij action go-to-tab-by-id "$original_tab_id" >/dev/null 2>&1 || true
    fi
  fi

  return 0
}

spawn_in_zellij_pane() {
  local launcher="$1"
  local pane_name="${2:-agent}"
  local direction="${VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION:-$(spawn_pane_direction)}"
  local launch_cmd="bash '$launcher'"
  local session_name=""
  local workflow_name=""
  local cmd_script

  if spawn_in_zellij_context && command -v zellij >/dev/null 2>&1; then
    # If the operator explicitly targets another zellij session, do not open a
    # pane in the current live session. Fall through to spawn_in_operator_session().
    if ! spawn_in_target_zellij_session; then
      return 1
    fi

    # Marbles loop panes (L2, L3...) route to dedicated marbles tab to avoid
    # stealing operator focus.
    if [[ "${SPAWN_LOOP_NR:-0}" -gt 0 && -n "${VIBECRAFTED_MARBLES_TAB_NAME:-}" ]]; then
      if spawn_in_marbles_tab "$launcher" "$pane_name" "$direction"; then
        return 0
      fi
    fi

    session_name="$(spawn_effective_operator_session 2>/dev/null || true)"
    workflow_name="$(spawn_workflow_label)"
    if [[ "$direction" == "new-tab" && -n "$session_name" ]]; then
      if spawn_open_startup_monitor_pane "$session_name" "$workflow_name" "tab" "$pane_name" "${SPAWN_ROOT:-$(pwd)}"; then
        launch_cmd="VIBECRAFTED_INLINE_STARTUP_WATCH=0 bash '$launcher'"
      fi
    fi

    cmd_script="$(spawn_tmp_script_path "vc-spawn-cmd" "${SPAWN_ROOT:-$(pwd)}")"
    spawn_write_command_script "$cmd_script" "$launch_cmd"

    if [[ "$direction" == "new-tab" ]]; then
      zellij action new-tab \
        --name "$pane_name" \
        --cwd "${SPAWN_ROOT:-$(pwd)}" \
        -- "$cmd_script" >/dev/null
    else
      zellij action new-pane \
        --direction "$direction" \
        --name "$pane_name" \
        --cwd "${SPAWN_ROOT:-$(pwd)}" \
        -- "$cmd_script" >/dev/null
    fi
    return 0
  fi
  return 1
}

spawn_in_operator_session() {
  local launcher="$1"
  local pane_name="${2:-agent}"
  local session_name=""
  local direction="${VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION:-$(spawn_pane_direction)}"
  local effective_direction="$direction"
  local launch_cmd="bash '$launcher'"
  local workflow_name=""
  local cmd_script

  spawn_normalize_ambient_context

  session_name="$(spawn_effective_operator_session 2>/dev/null || true)"
  [[ -n "$session_name" ]] || return 1
  command -v zellij >/dev/null 2>&1 || return 1
  export VIBECRAFTED_OPERATOR_SESSION="$session_name"
  workflow_name="$(spawn_workflow_label)"

  # When routing into a session from outside its active pane context, always
  # open a fresh tab. Otherwise zellij targets whichever operator tab is
  # currently focused, which can be a stale marbles tab.
  if ! spawn_in_target_zellij_session; then
    effective_direction="new-tab"
  fi

  if [[ "$effective_direction" == "new-tab" ]]; then
    if spawn_open_startup_monitor_pane "$session_name" "$workflow_name" "tab" "$pane_name" "${SPAWN_ROOT:-$(pwd)}"; then
      launch_cmd="VIBECRAFTED_INLINE_STARTUP_WATCH=0 bash '$launcher'"
    fi
  fi

  cmd_script="$(spawn_tmp_script_path "vc-spawn-cmd" "${SPAWN_ROOT:-$(pwd)}")"
  spawn_write_command_script "$cmd_script" "$launch_cmd"

  # External spawn into existing operator session — route as pane or new tab per grid policy.
  if [[ "$effective_direction" == "new-tab" ]]; then
    zellij --session "$session_name" action new-tab \
      --name "$pane_name" \
      --cwd "${SPAWN_ROOT:-$(pwd)}" \
      -- "$cmd_script" >/dev/null
  else
    zellij --session "$session_name" action new-pane \
      --direction "$effective_direction" \
      --name "$pane_name" \
      --cwd "${SPAWN_ROOT:-$(pwd)}" \
      -- "$cmd_script" >/dev/null
  fi
}

spawn_probe() {
  local transcript_path="$1"
  local probe_seconds="${VIBECRAFTED_SPAWN_PROBE_SECONDS:-15}"
  local probe_delay="${VIBECRAFTED_SPAWN_PROBE_DELAY_SECONDS:-2}"
  local agent_name="${SPAWN_AGENT:-agent}"

  # Skip if disabled or not in zellij
  [[ "${VIBECRAFTED_SPAWN_PROBE:-1}" == "1" ]] || return 0
  spawn_in_zellij_context || return 0
  command -v zellij >/dev/null 2>&1 || return 0
  [[ -n "$transcript_path" ]] || return 0

  # Brief delay for transcript file to appear; a short floating probe surfaces
  # startup logs on the currently occupied tab and then closes.
  (
    local focused_pane_id=""
    local focused_tab_id=""
    local -a probe_cmd=()
    sleep "$probe_delay"
    [[ -f "$transcript_path" ]] || exit 0
    focused_pane_id="$(spawn_current_focused_pane_id 2>/dev/null || true)"
    focused_tab_id="$(spawn_current_tab_id 2>/dev/null || true)"
    probe_cmd=(
      zellij action new-pane
      --floating
      --close-on-exit
      --width 20%
      --x 80%
      --y 10%
      --height 40%
      --name "probe-${agent_name}"
    )
    if [[ -n "$focused_tab_id" ]]; then
      probe_cmd+=(--tab-id "$focused_tab_id")
    fi
    probe_cmd+=(-- timeout "$probe_seconds" tail -f "$transcript_path")
    "${probe_cmd[@]}" >/dev/null 2>&1 || true
    if [[ -n "$focused_pane_id" ]]; then
      zellij action focus-pane-id "$focused_pane_id" >/dev/null 2>&1 || true
    fi
  ) &
}
