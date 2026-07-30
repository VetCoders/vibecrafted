#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install-frontier-config.sh [--source <repo-root>] [--dry-run] [--mode symlink|copy]

Install the repo-owned frontier shell presets:
- starship
- atuin
- vc-frame (config + layouts)

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

# Prefer staged tools store when present; fall back to checkout (--source).
vc_frame_src="$repo_root/config/vc-frame"
if [[ -n "${VIBECRAFTED_PREFER_REPO_VC_FRAME:-}" ]]; then
  vc_frame_src="$repo_root/config/vc-frame"
elif [[ -d "${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools/vibecrafted-current/config/vc-frame" ]]; then
  vc_frame_src="${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools/vibecrafted-current/config/vc-frame"
elif [[ -d "$HOME/.local/share/vibecrafted/tools/vibecrafted-current/config/vc-frame" ]]; then
  vc_frame_src="$HOME/.local/share/vibecrafted/tools/vibecrafted-current/config/vc-frame"
fi

install_one "$repo_root/config/starship.toml" "$frontier_root/starship.toml"
install_one "$repo_root/config/atuin/config.toml" "$frontier_root/atuin/config.toml"
install_one "$vc_frame_src/config.kdl" "$frontier_root/vc-frame/config.kdl"
install_one "$vc_frame_src/layouts/research.kdl" "$frontier_root/vc-frame/layouts/research.kdl"
install_one "$vc_frame_src/layouts/workflow.kdl" "$frontier_root/vc-frame/layouts/workflow.kdl"
install_one "$vc_frame_src/layouts/marbles.kdl" "$frontier_root/vc-frame/layouts/marbles.kdl"
install_one "$vc_frame_src/layouts/dashboard.kdl" "$frontier_root/vc-frame/layouts/dashboard.kdl"
install_one "$vc_frame_src/layouts/operator.kdl" "$frontier_root/vc-frame/layouts/operator.kdl"
install_one "$vc_frame_src/auto-theme.sh" "$frontier_root/vc-frame/auto-theme.sh"

# themes/ — link each theme file (and keep directory shape)
if [[ -d "$vc_frame_src/themes" ]]; then
  while IFS= read -r -d '' theme_file; do
    rel="${theme_file#"$vc_frame_src/"}"
    install_one "$theme_file" "$frontier_root/vc-frame/$rel"
  done < <(find "$vc_frame_src/themes" -type f -print0 2>/dev/null)
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
