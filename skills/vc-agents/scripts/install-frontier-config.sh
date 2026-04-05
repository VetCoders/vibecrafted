#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install-frontier-config.sh [--source <repo-root>] [--dry-run] [--mode symlink|copy]

Install the repo-owned frontier shell presets:
- starship
- atuin
- zellij (config + layouts)

By default this creates sidecar symlinks in $HOME/.config/vetcoders/frontier so the
repo remains the source of truth without taking over your global shell layout.
EOF_USAGE
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dry_run=0
mode="symlink"
timestamp="$(date +%Y%m%d_%H%M%S)"
frontier_root="${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/frontier"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --source"
      repo_root="$1"
      ;;
    --dry-run|-n)
      dry_run=1
      ;;
    --mode)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --mode"
      mode="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
  shift
done

case "$mode" in
  symlink|copy) ;;
  *) die "Invalid --mode '$mode' (expected symlink or copy)" ;;
esac

install_one() {
  local source_file="$1"
  local target_file="$2"
  local target_dir backup_file

  [[ -f "$source_file" ]] || die "Source file not found: $source_file"
  target_dir="$(dirname "$target_file")"
  backup_file="${target_file}.bak.${timestamp}"

  printf '  %s -> %s\n' "$source_file" "$target_file"

  if (( dry_run )); then
    if [[ -e "$target_file" || -L "$target_file" ]]; then
      printf '     dry-run: would back up existing target to %s\n' "$backup_file"
    fi
    printf '     dry-run: would %s config\n' "$mode"
    return 0
  fi

  mkdir -p "$target_dir"

  if [[ -L "$target_file" ]]; then
    local current_target
    current_target="$(readlink "$target_file")"
    if [[ "$mode" == "symlink" && "$current_target" == "$source_file" ]]; then
      printf '     already linked\n'
      return 0
    fi
    mv "$target_file" "$backup_file"
    printf '     backed up existing symlink to %s\n' "$backup_file"
  elif [[ -e "$target_file" ]]; then
    mv "$target_file" "$backup_file"
    printf '     backed up existing file to %s\n' "$backup_file"
  fi

  if [[ "$mode" == "symlink" ]]; then
    ln -s "$source_file" "$target_file"
  else
    cp "$source_file" "$target_file"
  fi

  printf '     installed\n'
}

printf 'Installing VetCoders frontier config\n'
printf '  source repo: %s\n' "$repo_root"
printf '  mode: %s\n' "$mode"
printf '  frontier root: %s\n' "$frontier_root"

install_one "$repo_root/config/starship.toml" "$frontier_root/starship.toml"
install_one "$repo_root/config/atuin/config.toml" "$frontier_root/atuin/config.toml"
install_one "$repo_root/config/zellij/config.kdl" "$frontier_root/zellij/config.kdl"
install_one "$repo_root/config/zellij/layouts/vc-research.kdl" "$frontier_root/zellij/layouts/vc-research.kdl"
install_one "$repo_root/config/zellij/layouts/vc-workflow.kdl" "$frontier_root/zellij/layouts/vc-workflow.kdl"
install_one "$repo_root/config/zellij/layouts/vc-marbles.kdl" "$frontier_root/zellij/layouts/vc-marbles.kdl"
install_one "$repo_root/config/zellij/layouts/vc-dashboard.kdl" "$frontier_root/zellij/layouts/vc-dashboard.kdl"
install_one "$repo_root/config/zellij/layouts/vibecrafted.kdl" "$frontier_root/zellij/layouts/vibecrafted.kdl"

printf 'Done.\n'
