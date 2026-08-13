#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install-frontier-config.sh [--source <repo-root>] [--dry-run] [--mode symlink|copy]

Install the repo-owned frontier shell presets:
- starship
- atuin
- optional host-terminal sidecars

By default this creates sidecar symlinks in $HOME/.config/vetcoders/frontier so the
repo remains the source of truth without taking over your global shell layout.
vc-frame config projections are owned exclusively by vc_frame_delivery.py.
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
    if [[ -f "$target_file" ]]; then
      cp -pL "$target_file" "$backup_file"
      printf '     preserved existing symlink content as regular backup %s\n' "$backup_file"
    else
      printf 'legacy_symlink_target=%s\n' "$current_target" > "$backup_file"
      printf '     recorded unreadable legacy symlink as regular migration receipt %s\n' "$backup_file"
    fi
    rm -f "$target_file"
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

migrate_legacy_backup_links() {
  local backup_link backup_target temporary
  [[ -d "$frontier_root" ]] || return 0
  while IFS= read -r -d '' backup_link; do
    backup_target="$(readlink "$backup_link")"
    if (( dry_run )); then
      printf '  dry-run: would materialize legacy backup link: %s\n' "$backup_link"
      continue
    fi
    temporary="${backup_link}.materialized.$$"
    if [[ -f "$backup_link" ]]; then
      cp -pL "$backup_link" "$temporary"
    else
      printf 'legacy_symlink_target=%s\n' "$backup_target" > "$temporary"
    fi
    rm -f "$backup_link"
    mv "$temporary" "$backup_link"
    printf '  materialized legacy backup link: %s\n' "$backup_link"
  done < <(find "$frontier_root" -type l -name '*.bak.*' -print0 2>/dev/null)
}

printf 'Installing Vetcoders frontier config\n'
printf '  source repo: %s\n' "$repo_root"
printf '  mode: %s\n' "$mode"
printf '  frontier root: %s\n' "$frontier_root"

migrate_legacy_backup_links

install_one "$repo_root/config/starship.toml" "$frontier_root/starship.toml"
install_one "$repo_root/config/atuin/config.toml" "$frontier_root/atuin/config.toml"
# Host-terminal sidecars (optional — only when present in this generation).
# Never overwrite ~/.config/alacritty; operators import/copy deliberately.
if [[ -f "$repo_root/config/alacritty/vc-frame.toml" ]]; then
  install_one "$repo_root/config/alacritty/vc-frame.toml" "$frontier_root/alacritty/vc-frame.toml"
fi
if [[ -f "$repo_root/config/alacritty/launch-primary-shell.zsh" ]]; then
  install_one "$repo_root/config/alacritty/launch-primary-shell.zsh" "$frontier_root/alacritty/launch-primary-shell.zsh"
fi
if [[ -f "$repo_root/config/shell/atuin-up.zsh" ]]; then
  install_one "$repo_root/config/shell/atuin-up.zsh" "$frontier_root/shell/atuin-up.zsh"
fi
# Legacy zombie cleanup: remove dangling symlinks under frontier (incl. old zellij/)
if (( ! dry_run )); then
  if [[ -d "$frontier_root" ]]; then
    while IFS= read -r -d '' zombie; do
      printf '  removing dangling frontier link: %s\n' "$zombie"
      rm -f "$zombie"
    done < <(find "$frontier_root" -type l ! -exec test -e {} \; -print0 2>/dev/null)
  fi
else
  if [[ -d "$frontier_root" ]]; then
    while IFS= read -r -d '' zombie; do
      printf '  dry-run: would remove dangling frontier link: %s\n' "$zombie"
    done < <(find "$frontier_root" -type l ! -exec test -e {} \; -print0 2>/dev/null)
  fi
fi

printf 'Done.\n'
