#!/usr/bin/env bash


spawn_osascript_bin() {
  local override="${VIBECRAFTED_OSASCRIPT_BIN:-}"
  if [[ -n "$override" && -x "$override" ]]; then
    printf '%s\n' "$override"
    return 0
  fi

  command -v osascript 2>/dev/null || return 1
}

# Detect preferred terminal app. Priority:
#   1. VIBECRAFTED_TERMINAL env (explicit override: iterm, terminal)
#   2. iTerm2 installed at /Applications
#   3. TERM_PROGRAM from current session
#   4. Fallback: terminal (Terminal.app)
spawn_preferred_terminal() {
  local pref="${VIBECRAFTED_TERMINAL:-}"
  if [[ -n "$pref" ]]; then
    printf '%s\n' "$pref"
    return 0
  fi
  # Detect installed terminal apps (survives agent/vscode context)
  if [[ -d "/Applications/iTerm.app" ]]; then
    printf 'iterm\n'
    return 0
  fi
  # Session-level detection as last resort
  case "${TERM_PROGRAM:-}" in
    iTerm.app) printf 'iterm\n' ;; 
    *) printf 'terminal\n' ;; 
  esac
}

spawn_open_terminal() {
  local launcher="$1"
  local osascript_bin
  osascript_bin="$(spawn_osascript_bin)" || spawn_die "osascript is required for visible Terminal spawns."

  local command_json
  command_json="$(python3 - "$launcher" "${SPAWN_ROOT:-}" <<'PY'
import json
import shlex
import sys

launcher = sys.argv[1]
root = sys.argv[2] if len(sys.argv) > 2 else ""
parts = []
if root:
    parts.append("cd " + shlex.quote(root))
parts.append("bash " + shlex.quote(launcher))
print(json.dumps(" && ".join(parts)))
PY
)"

  "$osascript_bin" <<EOF_APPLE
 tell application "Terminal" 
   activate 
   do script $command_json
 end tell
EOF_APPLE
}

spawn_open_iterm() {
  local launcher="$1"
  local osascript_bin
  osascript_bin="$(spawn_osascript_bin)" || return 1
  [[ "$(spawn_preferred_terminal)" == "iterm" ]] || return 1

  local command_json
  command_json="$(python3 - "$launcher" "${SPAWN_ROOT:-}" <<'PY'
import json
import shlex
import sys

launcher = sys.argv[1]
root = sys.argv[2] if len(sys.argv) > 2 else ""
parts = []
if root:
    parts.append("cd " + shlex.quote(root))
parts.append("bash " + shlex.quote(launcher))
print(json.dumps(" && ".join(parts)))
PY
)"

  "$osascript_bin" <<EOF_APPLE
tell application "iTerm2"
  tell current window
    create tab with default profile
    tell current session of current tab
      write text $command_json
    end tell
  end tell
end tell
EOF_APPLE
}

