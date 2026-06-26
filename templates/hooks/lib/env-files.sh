# shellcheck shell=bash
# vibecrafted-husky-template :: lib/env-files.sh
#
# Guards against accidentally committing .env / credentials files.

# Only docs/.env.example.md or similar reference files are allowed to live
# in git; everything else is blocked.
HUSKY_ENV_FILE_ALLOWED_PATTERNS='^(docs/\.env\.example\.md|\.env\.example|env\.example)$'

# husky_env_files_scan_staged
# Returns 0 (block) if a tracked .env-shaped file is in the staged set.
husky_env_files_scan_staged() {
  local candidates
  candidates="$(git diff --cached --name-only --diff-filter=ACMR \
    | grep -E '(^|/)\.env([^/]*)?$|(^|/)\.environment$|^env\.(production|local|staging|vm)$' \
    || true)"
  [ -z "$candidates" ] && return 0

  local offending
  offending="$(printf '%s\n' "$candidates" | grep -Ev "$HUSKY_ENV_FILE_ALLOWED_PATTERNS" || true)"
  if [ -n "$offending" ]; then
    husky_err ".env / credentials file(s) detected in staging:"
    printf '%s\n' "$offending" | sed 's/^/    • /' >&2
    husky_err "Remove or relocate before committing."
    husky_err "Only files matching this regex are permitted: $HUSKY_ENV_FILE_ALLOWED_PATTERNS"
    return 1
  fi
  return 0
}
