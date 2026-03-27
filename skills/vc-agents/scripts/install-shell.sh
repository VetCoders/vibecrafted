#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install-shell.sh [--source <repo-root>] [--dry-run] [--no-zshrc] [--no-bashrc]

Install the VetCoders shell helper layer. The helpers work in both bash and zsh.
By default, sources the helper from ~/.bashrc and ~/.zshrc for shells that are
available. Use --no-zshrc or --no-bashrc to skip a shell.
EOF_USAGE
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dry_run=0
update_zshrc=1
update_bashrc=1

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
    --no-zshrc)
      update_zshrc=0
      ;;
    --no-bashrc)
      update_bashrc=0
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

# Find source file (new name first, then legacy)
source_file="$repo_root/skills/vc-agents/shell/vetcoders.sh"
[[ -f "$source_file" ]] || source_file="$repo_root/skills/vc-agents/shell/vetcoders.zsh"
[[ -f "$source_file" ]] || source_file="$repo_root/vc-agents/shell/vetcoders.zsh"
[[ -f "$source_file" ]] || die "Helper file not found"

# Canonical install location (shell-agnostic)
config_base="${XDG_CONFIG_HOME:-$HOME/.config}"
target_dir="$config_base/vetcoders"
target_file="$target_dir/vc-skills.sh"

# Legacy compat location for existing zsh installs
legacy_dir="$config_base/zsh"
legacy_file="$legacy_dir/vc-skills.zsh"

# Source line — same syntax works in both bash and zsh
source_line='[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"'

printf 'Installing VetCoders shell helpers\n'
printf '  source: %s\n' "$source_file"
printf '  target: %s\n' "$target_file"

if (( dry_run )); then
  printf '  (dry run)\n'
else
  mkdir -p "$target_dir"
  cp "$source_file" "$target_file"
  # Legacy compat symlink so old .zshrc source lines still work
  mkdir -p "$legacy_dir"
  ln -sfn "$target_file" "$legacy_file"
fi

_update_rcfile() {
  local rcfile="$1"
  local shell_name="$2"

  # Already present — nothing to do
  if [[ -f "$rcfile" ]] && grep -Fq "vetcoders/vc-skills.sh" "$rcfile"; then
    printf '  %s: already sourced\n' "$rcfile"
    return 0
  fi

  # Respect locked/immutable files
  if [[ -f "$rcfile" ]] && ! touch -c "$rcfile" 2>/dev/null; then
    printf '\033[33m[warn]\033[0m %s is locked — add manually:\n' "$rcfile"
    printf '       %s\n' "$source_line"
    return 0
  fi

  if (( dry_run )); then
    printf '  %s: would add source line\n' "$rcfile"
    return 0
  fi

  {
    printf '\n# VetCoders shell helpers\n'
    printf '%s\n' "$source_line"
  } >> "$rcfile"

  printf '  %s: updated\n' "$rcfile"
}

if (( update_zshrc )); then
  if command -v zsh >/dev/null 2>&1 || [[ -f "$HOME/.zshrc" ]]; then
    _update_rcfile "$HOME/.zshrc" "zsh"
  fi
fi

if (( update_bashrc )); then
  if [[ -f "$HOME/.bashrc" ]] || [[ "${SHELL##*/}" == "bash" ]]; then
    _update_rcfile "$HOME/.bashrc" "bash"
  fi
fi
