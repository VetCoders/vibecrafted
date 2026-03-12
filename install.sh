#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install.sh [--repo-url <git-url>] [--checkout <dir>] [installer args...]

Bootstrap the vetcoders-skills repo into a local checkout and then run the
portable installer from vetcoders-spawn/scripts/install.sh.

Examples:
  curl -fsSL <raw-install-url> | bash
  curl -fsSL <raw-install-url> | bash -s -- --tool codex --with-shell
  bash install.sh --checkout "$HOME/.local/share/vetcoders-skills"
EOF_USAGE
}

default_checkout="${VETCODERS_SKILLS_HOME:-$HOME/.local/share/vetcoders-skills}"
default_repo_url="${VETCODERS_SKILLS_REPO_URL:-https://github.com/VetCoders/vetcoders-skills.git}"
checkout="$default_checkout"
repo_url="$default_repo_url"
declare -a installer_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url)
      shift
      [[ $# -gt 0 ]] || { echo 'Error: Missing value for --repo-url' >&2; exit 1; }
      repo_url="$1"
      ;;
    --checkout)
      shift
      [[ $# -gt 0 ]] || { echo 'Error: Missing value for --checkout' >&2; exit 1; }
      checkout="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      installer_args+=("$1")
      ;;
  esac
  shift
done

command -v git >/dev/null 2>&1 || { echo 'Error: git is required.' >&2; exit 1; }
command -v rsync >/dev/null 2>&1 || { echo 'Error: rsync is required.' >&2; exit 1; }

mkdir -p "$(dirname "$checkout")"
if [[ -d "$checkout/.git" ]]; then
  printf 'Updating existing checkout at %s\n' "$checkout"
  git -C "$checkout" pull --ff-only
else
  printf 'Cloning %s into %s\n' "$repo_url" "$checkout"
  git clone "$repo_url" "$checkout"
fi

exec bash "$checkout/vetcoders-spawn/scripts/install.sh" --source "$checkout" "${installer_args[@]}"
