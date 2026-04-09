#!/usr/bin/env bash

spawn_preferred_shell() {
  if command -v zsh >/dev/null 2>&1;
 then
    command -v zsh
  elif [[ -n "${SHELL:-}" ]] && command -v "${SHELL##*/}" >/dev/null 2>&1;
 then
    printf '%s\n' "$SHELL"
  else
    command -v bash
  fi
}

spawn_frontier_root() {
  local candidate
  while IFS= read -r candidate;
 do
    if [[ -f "$candidate/starship.toml" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(spawn_frontier_candidates)

  return 1
}

spawn_frontier_candidates() {
  local script_root candidate seen=""
  script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd || true)"

  for candidate in \
    "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/frontier" \
    "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tools/vibecrafted-current/config" \
    "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/config}" \
    "${SPAWN_ROOT:+$SPAWN_ROOT/config}" \
    "${script_root:+$script_root/config}"
  do
    [[ -n "$candidate" && -d "$candidate" ]] || continue
    case ":$seen:" in
      *":$candidate:"*) continue ;;
    esac
    seen="${seen:+$seen:}$candidate"
    printf '%s\n' "$candidate"
  done

  return 0
}

# Resolve each frontier asset independently so repo-owned prompt/history presets
# can coexist with an external session companion repo.
spawn_frontier_file() {
  local relative_path="$1"
  local candidate
  while IFS= read -r candidate;
 do
    if [[ -f "$candidate/$relative_path" ]]; then
      printf '%s/%s\n' "$candidate" "$relative_path"
      return 0
    fi
  done < <(spawn_frontier_candidates)
  return 1
}

spawn_export_frontier_sidecars() {
  local starship_config atuin_config zellij_config zellij_config_dir
  starship_config="$(spawn_frontier_file "starship.toml" 2>/dev/null || true)"
  atuin_config="$(spawn_frontier_file "atuin/config.toml" 2>/dev/null || true)"
  zellij_config="$(spawn_frontier_file "zellij/config.kdl" 2>/dev/null || true)"

  # Re-pin the active frontier assets every time so spawned sessions do not
  # inherit stale shell config from an unrelated install or repo.
  if command -v starship >/dev/null 2>&1 && [[ -n "$starship_config" ]]; then
    export STARSHIP_CONFIG="$starship_config"
  fi

  if command -v atuin >/dev/null 2>&1 && [[ -n "$atuin_config" ]]; then
    export ATUIN_CONFIG="$atuin_config"
  fi

  if command -v zellij >/dev/null 2>&1 && [[ -n "$zellij_config" ]]; then
    zellij_config_dir="$(dirname "$zellij_config")"
    export ZELLIJ_CONFIG_DIR="$zellij_config_dir"
  fi
}
