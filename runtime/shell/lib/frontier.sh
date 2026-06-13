# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_frontier_candidates() {
  local repo_root crafted_sidecar candidate seen=""
  repo_root="$(_vetcoders_repo_root)"
  crafted_sidecar="${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}/vibecrafted-current/config"

  for candidate in \
    "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/frontier" \
    "$crafted_sidecar" \
    "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/config}" \
    "$repo_root/config"
  do
    [[ -n "$candidate" && -d "$candidate" ]] || continue
    case ":$seen:" in
      *":$candidate:"*) continue ;;
    esac
    seen="${seen:+$seen:}$candidate"
    printf '%s\n' "$candidate"
  done
}

_vetcoders_frontier_root() {
  local candidate
  while IFS= read -r candidate; do
    if [[ -f "$candidate/starship.toml" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done < <(_vetcoders_frontier_candidates)

  echo "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. frontier config not found. Run vc-frontier-install from the repo checkout." >&2
  return 1
}

# Resolve each frontier asset independently so repo-owned prompt/history presets
# can coexist with an external session companion repo.
_vetcoders_frontier_file() {
  local relative_path="$1"
  local candidate
  while IFS= read -r candidate; do
    if [[ -f "$candidate/$relative_path" ]]; then
      printf '%s/%s\n' "$candidate" "$relative_path"
      return 0
    fi
  done < <(_vetcoders_frontier_candidates)
  return 1
}

_vetcoders_frontier_source_root() {
  local repo_root crafted_root candidate seen=""
  repo_root="$(_vetcoders_repo_root)"
  crafted_root="${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}/vibecrafted-current"

  for candidate in \
    "${VIBECRAFTED_ROOT:-}" \
    "$repo_root" \
    "$crafted_root"
  do
    [[ -n "$candidate" ]] || continue
    case ":$seen:" in
      *":$candidate:"*) continue ;;
    esac
    seen="${seen:+$seen:}$candidate"
    if [[ -f "$candidate/config/starship.toml" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

_vetcoders_load_frontier_sidecars() {
  local starship_config atuin_config zellij_config zellij_config_dir
  local xdg_config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
  starship_config="$(_vetcoders_frontier_file "starship.toml" 2>/dev/null || true)"
  atuin_config="$(_vetcoders_frontier_file "atuin/config.toml" 2>/dev/null || true)"
  zellij_config="$(_vetcoders_frontier_file "zellij/config.kdl" 2>/dev/null || true)"

  # Frontier tools (starship, atuin, zellij) are suggested for the runtime,
  # not required. Never override a user's existing config — only set env vars
  # when the user has no config of their own. Users opt in explicitly.
  if command -v starship >/dev/null 2>&1 \
    && [[ -n "$starship_config" && -z "${STARSHIP_CONFIG:-}" ]] \
    && [[ ! -e "$xdg_config_home/starship.toml" ]]; then
    export STARSHIP_CONFIG="$starship_config"
  fi

  if command -v atuin >/dev/null 2>&1 \
    && [[ -n "$atuin_config" && -z "${ATUIN_CONFIG:-}" ]] \
    && [[ ! -e "$xdg_config_home/atuin/config.toml" ]]; then
    export ATUIN_CONFIG="$atuin_config"
  fi

  if _vetcoders_zellij_bin >/dev/null 2>&1 \
    && [[ -n "$zellij_config" && -z "${ZELLIJ_CONFIG_DIR:-}" ]] \
    && [[ ! -e "$xdg_config_home/zellij/config.kdl" ]]; then
    zellij_config_dir="$(dirname "$zellij_config")"
    export ZELLIJ_CONFIG_DIR="$zellij_config_dir"
  fi
}

_vetcoders_load_frontier_sidecars

_vetcoders_normalize_ambient_context

_VETCODERS_ATUIN_BIN="$(_vetcoders_atuin_bin 2>/dev/null || true)"
