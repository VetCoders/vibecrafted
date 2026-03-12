#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install.sh [--source <repo-root>] [--tool <codex|claude|gemini>]... [--dry-run] [--mirror] [--with-shell] [--no-zshrc] [--list]

Install the canonical skill directories from this repo into local tool homes:
  ~/.codex/skills
  ~/.claude/skills
  ~/.gemini/skills

Examples:
  bash vetcoders-spawn/scripts/install.sh
  bash vetcoders-spawn/scripts/install.sh --tool codex --tool claude
  bash vetcoders-spawn/scripts/install.sh --dry-run
  bash vetcoders-spawn/scripts/install.sh --mirror
  bash vetcoders-spawn/scripts/install.sh --with-shell
EOF_USAGE
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

foundation_preflight() {
  local missing=0

  printf 'Foundation preflight:\n'

  if command -v aicx >/dev/null 2>&1; then
    printf '  [ok] aicx -> %s\n' "$(command -v aicx)"
  else
    printf '  [missing] aicx\n'
    printf '    fix: cargo install aicx\n'
    missing=1
  fi

  if command -v loctree-mcp >/dev/null 2>&1; then
    printf '  [ok] loctree-mcp -> %s\n' "$(command -v loctree-mcp)"
  else
    printf '  [missing] loctree-mcp\n'
    printf '    fix: cargo install loctree-mcp\n'
    missing=1
  fi

  if command -v prview >/dev/null 2>&1; then
    printf '  [ok] prview -> %s\n' "$(command -v prview)"
  else
    printf '  [optional] prview not found\n'
    printf '    fix: cargo install prview\n'
  fi

  if (( missing )); then
    printf '\nProceeding with install, but ai-contexters / loctree-backed flows will stay degraded until the missing foundations are installed.\n\n'
  else
    printf '\n'
  fi
}

runtime_preflight() {
  local missing=0
  local tool

  printf 'Runtime preflight:\n'

  for cmd in zsh python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
      printf '  [ok] %s -> %s\n' "$cmd" "$(command -v "$cmd")"
    else
      printf '  [missing] %s\n' "$cmd"
      missing=1
    fi
  done

  if command -v osascript >/dev/null 2>&1; then
    printf '  [ok] osascript -> %s\n' "$(command -v osascript)"
  else
    printf '  [optional] osascript not found (headless spawn still works)\n'
  fi

  for tool in "${tools[@]}"; do
    if command -v "$tool" >/dev/null 2>&1; then
      printf '  [ok] %s -> %s\n' "$tool" "$(command -v "$tool")"
    else
      printf '  [missing] %s\n' "$tool"
      missing=1
    fi
  done

  if (( missing )); then
    printf '\nProceeding with install, but the selected spawn helpers will stay degraded until the missing runtime commands are installed.\n\n'
  else
    printf '\n'
  fi
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dry_run=0
mirror=0
list_only=0
with_shell=0
shell_no_zshrc=0
declare -a tools=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --source"
      repo_root="$1"
      ;;
    --tool)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --tool"
      case "$1" in
        codex|claude|gemini) tools+=("$1") ;;
        *) die "Unknown tool: $1" ;;
      esac
      ;;
    --dry-run|-n)
      dry_run=1
      ;;
    --mirror)
      mirror=1
      ;;
    --with-shell)
      with_shell=1
      ;;
    --no-zshrc)
      shell_no_zshrc=1
      ;;
    --list)
      list_only=1
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

[[ -d "$repo_root" ]] || die "Repo root not found: $repo_root"

foundation_preflight

skills=()
while IFS= read -r skill; do
  [[ -n "$skill" ]] || continue
  skills+=("$skill")
done < <(
  find "$repo_root" -mindepth 1 -maxdepth 1 -type d \
    ! -name '.git' \
    ! -name '.loctree' \
    ! -name 'docs' \
    ! -name '.github' \
    -exec test -f '{}/SKILL.md' ';' -print | sort
)

[[ ${#skills[@]} -gt 0 ]] || die "No top-level skill directories found under $repo_root"

if (( list_only )); then
  printf 'Repo root: %s\n' "$repo_root"
  printf 'Skills to install:\n'
  for skill in "${skills[@]}"; do
    printf '  - %s\n' "$(basename "$skill")"
  done
  exit 0
fi

if [[ ${#tools[@]} -eq 0 ]]; then
  tools=(codex claude gemini)
fi

runtime_preflight

rsync_args=(-az --exclude '.DS_Store' --exclude '.loctree')
if (( mirror )); then
  rsync_args+=(--delete)
fi
if (( dry_run )); then
  rsync_args+=(--dry-run --itemize-changes)
fi

printf 'Installing skills from %s\n' "$repo_root"
for tool in "${tools[@]}"; do
  target="$HOME/.${tool}/skills"
  mkdir -p "$target"
  printf -- '-- %s -> %s\n' "$tool" "$target"
  for skill in "${skills[@]}"; do
    name="$(basename "$skill")"
    mkdir -p "$target/$name"
    rsync "${rsync_args[@]}" "$skill/" "$target/$name/"
  done
  printf '\n'
done

printf 'Install complete.\n'

if (( with_shell )); then
  shell_args=(--source "$repo_root")
  if (( dry_run )); then
    shell_args+=(--dry-run)
  fi
  if (( shell_no_zshrc )); then
    shell_args+=(--no-zshrc)
  fi
  printf '\nInstalling optional zsh helper layer...\n'
  bash "$repo_root/vetcoders-spawn/scripts/install-shell.sh" "${shell_args[@]}"
fi
