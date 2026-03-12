#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: skills_sync.sh <host> [--source <repo-root>] [--tool <codex|claude|gemini>]... [--dry-run] [--mirror] [--with-shell] [--no-zshrc] [--no-verify]

Sync canonical skill directories from this repo to another machine's tool homes:
  ~/.codex/skills
  ~/.claude/skills
  ~/.gemini/skills

Examples:
  bash vetcoders-spawn/scripts/skills_sync.sh mgbook16
  bash vetcoders-spawn/scripts/skills_sync.sh mgbook16 --tool codex --tool claude
  bash vetcoders-spawn/scripts/skills_sync.sh mgbook16 --dry-run
  bash vetcoders-spawn/scripts/skills_sync.sh mgbook16 --mirror
  bash vetcoders-spawn/scripts/skills_sync.sh mgbook16 --with-shell
EOF_USAGE
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

remote_foundation_check() {
  local host="$1"
  printf 'Foundation preflight on %s\n' "$host"
  ssh -n "$host" '
if command -v aicx >/dev/null 2>&1; then
  printf "  [ok] aicx -> %s\\n" "$(command -v aicx)"
else
  printf "  [missing] aicx\\n"
  printf "    fix: cargo install aicx\\n"
fi
if command -v loctree-mcp >/dev/null 2>&1; then
  printf "  [ok] loctree-mcp -> %s\\n" "$(command -v loctree-mcp)"
else
  printf "  [missing] loctree-mcp\\n"
  printf "    fix: cargo install loctree-mcp\\n"
fi
if command -v prview >/dev/null 2>&1; then
  printf "  [ok] prview -> %s\\n" "$(command -v prview)"
else
  printf "  [optional] prview not found\\n"
  printf "    fix: cargo install prview\\n"
fi
printf "\\n"
'
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
verify=1
dry_run=0
mirror=0
with_shell=0
shell_no_zshrc=0
host=""
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
    --no-verify)
      verify=0
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    -*)
      die "Unknown option: $1"
      ;;
    *)
      [[ -z "$host" ]] || die "Host already set to $host"
      host="$1"
      ;;
  esac
  shift
done

[[ -n "$host" ]] || {
  usage
  exit 1
}
[[ -d "$repo_root" ]] || die "Repo root not found: $repo_root"

source_line='[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vetcoders-skills.zsh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vetcoders-skills.zsh"'

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

if [[ ${#tools[@]} -eq 0 ]]; then
  tools=(codex claude gemini)
fi

rsync_args=(-az --exclude '.DS_Store' --exclude '.loctree' -e ssh)
if (( mirror )); then
  rsync_args+=(--delete)
fi
if (( dry_run )); then
  rsync_args+=(--dry-run --itemize-changes)
fi

printf 'Syncing skills from %s to %s\n' "$repo_root" "$host"
for tool in "${tools[@]}"; do
  remote_target="~/.${tool}/skills"
  printf -- '-- %s -> %s:%s\n' "$tool" "$host" "$remote_target"
  ssh -n "$host" "mkdir -p $remote_target" || die "Could not prepare $remote_target on $host"
  for skill in "${skills[@]}"; do
    name="$(basename "$skill")"
    ssh -n "$host" "mkdir -p $remote_target/$name" || die "Could not create $remote_target/$name on $host"
    rsync "${rsync_args[@]}" "$skill/" "$host:$remote_target/$name/"
  done
  printf '\n'
done

if (( with_shell )); then
  shell_source="$repo_root/vetcoders-spawn/shell/vetcoders.zsh"
  [[ -f "$shell_source" ]] || die "Shell helper file not found: $shell_source"

  remote_config_dir='${XDG_CONFIG_HOME:-$HOME/.config}/zsh'
  remote_shell_target="$remote_config_dir/vetcoders-skills.zsh"

  printf 'Syncing optional zsh helper layer to %s\n' "$host"
  ssh -n "$host" "mkdir -p $remote_config_dir" || die "Could not prepare $remote_config_dir on $host"
  rsync "${rsync_args[@]}" "$shell_source" "$host:$remote_shell_target"

  if (( shell_no_zshrc )); then
    printf 'Skipping remote ~/.zshrc update (--no-zshrc).\n'
  else
    ssh -n "$host" "touch ~/.zshrc && if ! grep -Fqx '$source_line' ~/.zshrc; then printf '\n# VetCoders shell helpers\n%s\n' '$source_line' >> ~/.zshrc; fi" \
      || die "Could not update ~/.zshrc on $host"
  fi

  printf '\n'
fi

if (( ! verify )); then
  printf 'Sync complete. Verification skipped.\n'
  exit 0
fi

printf 'Verifying portable spawn runtime on %s\n' "$host"
ssh -n "$host" 'for f in \
  ~/.codex/skills/vetcoders-spawn/scripts/codex_spawn.sh \
  ~/.claude/skills/vetcoders-spawn/scripts/claude_spawn.sh \
  ~/.gemini/skills/vetcoders-spawn/scripts/gemini_spawn.sh \
  ~/.codex/skills/vetcoders-spawn/scripts/observe.sh; do
  if [ -e "$f" ]; then
    echo "OK $f"
  else
    echo "MISSING $f"
  fi
done'

if (( with_shell )); then
  ssh -n "$host" 'if [ -f "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vetcoders-skills.zsh" ]; then
  echo "OK ${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vetcoders-skills.zsh"
else
  echo "MISSING ${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vetcoders-skills.zsh"
fi'
fi

remote_foundation_check "$host"

printf 'Sync complete.\n'
