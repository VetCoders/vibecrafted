#!/usr/bin/env bash
set -euo pipefail

# Bootstrap installer: clone/update the vc-skills repo, then run
# the Smart Installer from it.
#
# Usage:
#   curl -fsSL <raw-url>/install.sh | bash
#   curl -fsSL <raw-url>/install.sh | bash -s -- --with-shell
#   bash install.sh --checkout "$HOME/.local/share/vc-skills"

usage() {
  cat <<'EOF_USAGE'
Usage: install.sh [--repo-url <git-url>] [--checkout <dir>] [installer args...]

Bootstrap the vc-skills repo into a local checkout and then run the
Smart Installer (Python).

Examples:
  curl -fsSL <raw-install-url> | bash
  curl -fsSL <raw-install-url> | bash -s -- --with-shell
  bash install.sh --checkout "$HOME/.local/share/vc-skills"
  bash install.sh doctor
EOF_USAGE
}

default_checkout="${VETCODERS_SKILLS_HOME:-$HOME/.local/share/vc-skills}"
default_repo_url="${VETCODERS_SKILLS_REPO_URL:-https://github.com/VetCoders/vc-skills.git}"
checkout="$default_checkout"
repo_url="$default_repo_url"
subcommand="install"
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
    doctor|list)
      subcommand="$1"
      ;;
    *)
      installer_args+=("$1")
      ;;
  esac
  shift
done

# Preflight
command -v git >/dev/null 2>&1 || { echo 'Error: git is required.' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'Error: python3 is required.' >&2; exit 1; }

# Clone or update
mkdir -p "$(dirname "$checkout")"
if [[ -d "$checkout/.git" ]]; then
  printf 'Updating existing checkout at %s\n' "$checkout"
  git -C "$checkout" pull --ff-only 2>/dev/null || true
else
  printf 'Cloning %s into %s\n' "$repo_url" "$checkout"
  git clone "$repo_url" "$checkout"
fi

# Delegate to Smart Installer
installer="$checkout/scripts/vetcoders_install.py"
if [[ ! -f "$installer" ]]; then
  echo "Error: Smart Installer not found at $installer" >&2
  echo "The repo may be outdated. Try: git -C $checkout pull" >&2
  exit 1
fi

if [[ "$subcommand" == "install" ]]; then
  exec python3 "$installer" install --source "$checkout" "${installer_args[@]}"
else
  exec python3 "$installer" "$subcommand" "${installer_args[@]}"
fi
