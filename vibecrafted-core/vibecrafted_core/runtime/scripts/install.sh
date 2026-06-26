#!/usr/bin/env bash
set -euo pipefail

# Thin shim: delegates to the Python Smart Installer.
# All arguments are forwarded directly to:
#   python3 scripts/vetcoders_install.py install [args...]
#
# Supported flags (all handled by Python CLI):
#   --source <path>     Repo root
#   --dry-run / -n      Preview mode
#   --non-interactive   Skip prompts
#   --advanced          Selective install UI
#   --with-shell        Install zsh helpers
#   --tool <runtime>    Limit to specific runtimes (repeatable)
#   --skill <name>      Install specific skills (repeatable)
#   --mirror            Delete extra files in installed dirs
#   --list              Show available skills (redirects to list subcommand)

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
installer="$repo_root/scripts/vetcoders_install.py"

if [[ ! -f "$installer" ]]; then
  echo "Error: Smart Installer not found at $installer" >&2
  echo "Are you running from the vc-skills repo root?" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not found." >&2
  exit 1
fi

# Intercept --list as a subcommand redirect
for arg in "$@"; do
  if [[ "$arg" == "--list" ]]; then
    exec python3 "$installer" list --source "$repo_root"
  fi
done

# Forward everything; ensure --source is set
has_source=0
for arg in "$@"; do
  [[ "$arg" == "--source" ]] && has_source=1
done

if (( has_source )); then
  exec python3 "$installer" install "$@"
else
  exec python3 "$installer" install --source "$repo_root" "$@"
fi
