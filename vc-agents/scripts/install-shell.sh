#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install-shell.sh [--source <repo-root>] [--dry-run] [--no-zshrc]

Install the optional VetCoders zsh helper layer. This does not copy a whole
personal shell config or banner/theme; it installs the distilled repo-owned
helper file and, unless --no-zshrc is used, sources it from ~/.zshrc.
EOF_USAGE
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dry_run=0
update_zshrc=1

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

source_file="$repo_root/vc-agents/shell/vetcoders.zsh"
[[ -f "$source_file" ]] || die "Helper file not found: $source_file"

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"
target_file="$config_dir/vc-skills.zsh"
zshrc_file="$HOME/.zshrc"
source_line='[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh"'

printf 'Installing VetCoders zsh helpers\n'
printf '  source: %s\n' "$source_file"
printf '  target: %s\n' "$target_file"

if (( dry_run )); then
  printf 'Dry run: would copy helper file to %s\n' "$target_file"
else
  mkdir -p "$config_dir"
  cp "$source_file" "$target_file"
fi

if (( ! update_zshrc )); then
  printf 'Skipping ~/.zshrc update (--no-zshrc).\n'
  exit 0
fi

if [[ -f "$zshrc_file" ]] && grep -Fq "$source_line" "$zshrc_file"; then
  printf 'Helper source line already present in %s\n' "$zshrc_file"
  exit 0
fi

# Respect locked/immutable files — never write without permission
if [[ -f "$zshrc_file" ]] && ! touch -c "$zshrc_file" 2>/dev/null; then
  printf '\033[33m[warn]\033[0m %s is locked (uchg/immutable) — skipping .zshrc update\n' "$zshrc_file"
  printf '       Add this line manually:\n'
  printf '       %s\n' "$source_line"
  exit 0
fi

if (( dry_run )); then
  printf 'Dry run: would append helper source line to %s\n' "$zshrc_file"
  exit 0
fi

{
  printf '\n# VetCoders shell helpers\n'
  printf '%s\n' "$source_line"
} >> "$zshrc_file"

printf 'Updated %s\n' "$zshrc_file"
