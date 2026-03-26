# VetCoders shell helpers
# Source this from ~/.zshrc to get consistent wrapper commands for the repo-owned
# spawn runtime installed canonically under ~/.agents/skills and exposed through
# ~/.{codex,claude,gemini}/skills symlink views.

_vetcoders_spawn_home() {
  local tool="$1"
  # We now resolve directly to the canonical store to avoid symlink duplication issues
  printf '%s/.agents/skills/vc-agents' "$HOME"
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

_vetcoders_frontier_root() {
  local repo_root
  repo_root="$(_vetcoders_repo_root)"
  if [[ -d "$repo_root/config/atuin" && -f "$repo_root/config/starship.toml" ]]; then
    printf '%s/config' "$repo_root"
    return 0
  fi

  local sidecar="${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/frontier"
  if [[ -d "$sidecar" ]]; then
    printf '%s' "$sidecar"
    return 0
  fi

  echo "VetCoders frontier config not found. Run vc-frontier-install from the repo checkout." >&2
  return 1
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

_vetcoders_skill() {
  local tool="$1"
  local skill="$2"
  shift 2
  local extra="$*"
  local prompt="Perform the vc-${skill} skill on this repository.${extra:+ }${extra}"
  _vetcoders_prompt "$tool" implement "$prompt"
}

codex-dou() { _vetcoders_skill codex dou "$@"; }
claude-dou() { _vetcoders_skill claude dou "$@"; }
gemini-dou() { _vetcoders_skill gemini dou "$@"; }

codex-hydrate() { _vetcoders_skill codex hydrate "$@"; }
claude-hydrate() { _vetcoders_skill claude hydrate "$@"; }
gemini-hydrate() { _vetcoders_skill gemini hydrate "$@"; }

codex-marbles() { _vetcoders_skill codex marbles "$@"; }
claude-marbles() { _vetcoders_skill claude marbles "$@"; }
gemini-marbles() { _vetcoders_skill gemini marbles "$@"; }

codex-decorate() { _vetcoders_skill codex decorate "$@"; }
claude-decorate() { _vetcoders_skill claude decorate "$@"; }
gemini-decorate() { _vetcoders_skill gemini decorate "$@"; }

skills-sync() {
  local script
  script="$(_vetcoders_spawn_script codex skills_sync.sh)" || return 1
  bash "$script" "$@"
}

vc-frontier-paths() {
  local root
  root="$(_vetcoders_frontier_root)" || return 1
  printf 'STARSHIP_CONFIG=%s/starship.toml\n' "$root"
  printf 'ATUIN_CONFIG=%s/atuin/config.toml\n' "$root"
  printf 'ZELLIJ_CONFIG=%s/zellij/config.kdl\n' "$root"
}

vc-frontier-install() {
  local repo_root script
  repo_root="$(_vetcoders_repo_root)"
  script="$repo_root/vc-agents/scripts/install-frontier-config.sh"
  [[ -f "$script" ]] || {
    echo "Frontier installer not found in current repo checkout: $script" >&2
    return 1
  }
  bash "$script" --source "$repo_root" "$@"
}
