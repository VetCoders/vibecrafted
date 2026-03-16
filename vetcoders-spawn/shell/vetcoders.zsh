# VetCoders shell helpers
# Source this from ~/.zshrc to get consistent wrapper commands for the repo-owned
# spawn runtime installed under ~/.{codex,claude,gemini}/skills.

_vetcoders_spawn_home() {
  local tool="$1"
  printf '%s/.%s/skills/vetcoders-spawn' "$HOME" "$tool"
}

_vetcoders_spawn_script() {
  local tool="$1"
  local script_name="$2"
  local base
  base="$(_vetcoders_spawn_home "$tool")"
  [[ -f "$base/scripts/$script_name" ]] || {
    echo "VetCoders spawn script not found: $base/scripts/$script_name" >&2
    return 1
  }
  printf '%s/scripts/%s' "$base" "$script_name"
}

_vetcoders_repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

_vetcoders_default_runtime() {
  printf '%s\n' "${VETCODERS_SPAWN_RUNTIME:-terminal}"
}

_vetcoders_prompt_file() {
  local agent="$1"
  shift
  if [[ $# -eq 0 ]]; then
    echo "Usage: ${agent}-prompt <prompt>" >&2
    return 1
  fi

  local root ts prompt_text slug prompt_file
  root="$(_vetcoders_repo_root)"
  ts="$(date +%Y%m%d_%H%M)"
  prompt_text="$*"
  slug="$(printf '%s' "$prompt_text" | tr '\n' ' ' | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48)"
  [[ -n "$slug" ]] || slug="adhoc-prompt"

  mkdir -p "$root/.ai-agents/tmp"
  prompt_file="$root/.ai-agents/tmp/${ts}_${slug}_${agent}_prompt.md"
  printf '%s\n' "$prompt_text" > "$prompt_file"
  printf '%s\n' "$prompt_file"
}

_vetcoders_spawn_plan() {
  local tool="$1"
  local mode="$2"
  local plan_file="$3"
  shift 3
  local script
  script="$(_vetcoders_spawn_script "$tool" "${tool}_spawn.sh")" || return 1
  bash "$script" --mode "$mode" "$plan_file" "$@"
}

_vetcoders_prompt() {
  local tool="$1"
  local mode="$2"
  shift 2
  local prompt_file
  prompt_file="$(_vetcoders_prompt_file "$tool" "$@")" || return 1
  _vetcoders_spawn_plan "$tool" "$mode" "$prompt_file" --runtime "$(_vetcoders_default_runtime)"
}

_vetcoders_observe() {
  local tool="$1"
  shift
  local script
  script="$(_vetcoders_spawn_script "$tool" "observe.sh")" || return 1
  bash "$script" "$tool" "$@"
}

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

codex-research() {
  _vetcoders_spawn_plan codex research "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-research() {
  _vetcoders_spawn_plan claude research "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-research() {
  _vetcoders_spawn_plan gemini research "$1" --runtime "$(_vetcoders_default_runtime)"
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

codex-observe() {
  _vetcoders_observe codex "$@"
}

claude-observe() {
  _vetcoders_observe claude "$@"
}

gemini-observe() {
  _vetcoders_observe gemini "$@"
}

skills-sync() {
  local script
  script="$(_vetcoders_spawn_script codex skills_sync.sh)" || return 1
  bash "$script" "$@"
}

_vetcoders_gemini_keychain_api_key() {
  local value=""

  if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    printf '%s' "$GEMINI_API_KEY"
    return 0
  fi

  command -v security >/dev/null 2>&1 || return 1

  value="$(security find-generic-password -w -s GEMINI_API_KEY -a GEMINI_API_KEY 2>/dev/null || true)"
  [[ -n "$value" ]] && {
    printf '%s' "$value"
    return 0
  }

  local service_name
  for service_name in GEMINI_API_KEY gemini-cli google-generative-ai GoogleAIStudio; do
    value="$(security find-generic-password -w -s "$service_name" 2>/dev/null || true)"
    [[ -n "$value" ]] && {
      printf '%s' "$value"
      return 0
    }
  done

  local account_name
  for account_name in GEMINI_API_KEY gemini-cli gemini google; do
    value="$(security find-generic-password -w -a "$account_name" 2>/dev/null || true)"
    [[ -n "$value" ]] && {
      printf '%s' "$value"
      return 0
    }
  done

  return 1
}

gemini-keychain-set() {
  local key="${1:-${GEMINI_API_KEY:-}}"
  if [[ -z "$key" ]]; then
    echo "Usage: gemini-keychain-set <api-key>"
    echo "   or: GEMINI_API_KEY=... gemini-keychain-set"
    return 1
  fi

  command -v security >/dev/null 2>&1 || {
    echo "security CLI not available on this system"
    return 1
  }

  security add-generic-password -U -s GEMINI_API_KEY -a GEMINI_API_KEY -l GEMINI_API_KEY -w "$key"
  echo "Saved GEMINI_API_KEY to macOS Keychain (service/account: GEMINI_API_KEY)."
}

gemini-keychain-get() {
  if _vetcoders_gemini_keychain_api_key >/dev/null; then
    _vetcoders_gemini_keychain_api_key
    printf '\n'
    return 0
  fi
  echo "No GEMINI_API_KEY found in env or Keychain."
  return 1
}

gemini-keychain-clear() {
  command -v security >/dev/null 2>&1 || {
    echo "security CLI not available on this system"
    return 1
  }

  security delete-generic-password -s GEMINI_API_KEY -a GEMINI_API_KEY >/dev/null 2>&1 || true
  echo "Removed GEMINI_API_KEY from macOS Keychain (if it existed)."
}

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  _vetcoders_gemini_keychain_api_key >/dev/null 2>&1 && export GEMINI_API_KEY="$(_vetcoders_gemini_keychain_api_key)"
fi
