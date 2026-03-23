# VetCoders shell helpers
# Source this from ~/.zshrc to get consistent wrapper commands for the repo-owned
# spawn runtime installed canonically under ~/.agents/skills and exposed through
# ~/.{codex,claude,gemini}/skills symlink views.

_vetcoders_spawn_home() {
  local tool="$1"
  # We now resolve directly to the canonical store to avoid symlink duplication issues
  printf '%s/.agents/skills/vetcoders-agents' "$HOME"
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
