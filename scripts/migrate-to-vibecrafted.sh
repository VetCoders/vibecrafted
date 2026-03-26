#!/usr/bin/env bash
set -euo pipefail

# Migrate .ai-agents/reports/ from per-repo to ~/.vibecrafted/artifacts/
# Convention: ~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/

VIBECRAFTED_HOME="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
DRY_RUN="${1:-}"

info()  { printf '  \033[32m[ok]\033[0m %s\n' "$*"; }
warn()  { printf '  \033[33m[skip]\033[0m %s\n' "$*"; }
dry()   { printf '  \033[36m[dry]\033[0m %s\n' "$*"; }

echo ""
echo "  Migrating .ai-agents/ artifacts to ~/.vibecrafted/artifacts/"
echo "  ─────────────────────────────────────────────────────────"
echo ""

# Discover repos with .ai-agents/reports/
SEARCH_DIRS=(
  "$HOME/hosted"
)

migrated=0
skipped=0

find "${SEARCH_DIRS[@]}" -maxdepth 4 -type d -name ".ai-agents" 2>/dev/null | while read -r agents_dir; do
  repo_root="$(dirname "$agents_dir")"
  reports_dir="$agents_dir/reports"

  # Skip if no reports
  [[ -d "$reports_dir" ]] || continue
  # Skip if already a symlink (already migrated)
  [[ -L "$reports_dir" ]] && { warn "$repo_root — already symlinked"; skipped=$((skipped+1)); continue; }
  # Skip if empty
  report_count="$(find "$reports_dir" -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')"
  [[ "$report_count" -gt 0 ]] || { warn "$repo_root — empty reports/"; continue; }

  # Extract org/repo from git remote
  org_repo="$(cd "$repo_root" && git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|' || true)"
  if [[ -z "$org_repo" ]]; then
    warn "$repo_root — no git remote, skipping"
    skipped=$((skipped+1))
    continue
  fi

  # Group files by date (YYYYMMDD prefix in filenames)
  echo "  Repo: $org_repo ($report_count files)"

  find "$reports_dir" -maxdepth 1 -type f | while read -r file; do
    fname="$(basename "$file")"
    # Extract date from filename (format: YYYYMMDD_HHMM_...)
    file_date="$(echo "$fname" | sed -E 's/^([0-9]{8})_.*/\1/' || true)"
    if [[ "$file_date" =~ ^[0-9]{8}$ ]]; then
      date_dir="${file_date:0:4}_${file_date:4:4}"
    else
      date_dir="undated"
    fi

    target_dir="$VIBECRAFTED_HOME/artifacts/$org_repo/$date_dir/reports"

    if [[ "$DRY_RUN" == "--dry-run" ]]; then
      dry "$fname → $target_dir/"
    else
      mkdir -p "$target_dir"
      mv "$file" "$target_dir/$fname"
    fi
  done

  # After moving all files, replace reports/ dir with symlink to latest date
  if [[ "$DRY_RUN" != "--dry-run" ]]; then
    # Find today's store dir for the symlink target
    today_dir="$(date +%Y_%m%d)"
    target_reports="$VIBECRAFTED_HOME/artifacts/$org_repo/$today_dir/reports"
    mkdir -p "$target_reports"

    # Remove now-empty reports dir and symlink
    rmdir "$reports_dir" 2>/dev/null || true
    if [[ ! -d "$reports_dir" ]]; then
      ln -sfn "$target_reports" "$reports_dir"
      info "$org_repo — migrated, symlinked"
    else
      warn "$org_repo — reports/ not empty after move, skipping symlink"
    fi
  fi

  migrated=$((migrated+1))
done

echo ""
echo "  Done. Store: $VIBECRAFTED_HOME/artifacts/"
if [[ "$DRY_RUN" == "--dry-run" ]]; then
  echo "  (dry-run — no files moved. Run without --dry-run to migrate)"
fi
echo ""
