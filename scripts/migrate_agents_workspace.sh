#!/usr/bin/env bash
set -euo pipefail

# Migration script for legacy `.ai-agents/` directories.
# Performs a "hard" move of legacy `.ai-agents/` folders
# into the central archive at $VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/
# Moves only these folders: plans, pipeline, reports, tmp
# Leaves any other files in .ai-agents/ untouched (for example GUIDELINES.md)
#
# Usage:
#   ./migrate_agents_workspace.sh [--dry-run] [dir1 dir2 ...]
#   By default it scans $VIBECRAFTED_ROOT/ or the current directory
#
# To verify org/repo you can also run: zsh -ic 'repo-full'

default_vibecrafted_home() {
  if [[ -n "${VIBECRAFTED_HOME:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_HOME"
    return
  fi
  if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_ROOT/.vibecrafted"
    return
  fi
  printf '%s\n' "$HOME/.vibecrafted"
}

default_search_root() {
  if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_ROOT/"
    return
  fi
  printf '%s\n' "$PWD"
}

VIBECRAFTED_HOME="$(default_vibecrafted_home)"
DEFAULT_SEARCH_ROOT="$(default_search_root)"

# Argument parsing: the first argument may be --dry-run, the rest are directories
DRY_RUN=""
SEARCH_DIRS=()
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
  else
    SEARCH_DIRS+=("$arg")
  fi
done
[[ ${#SEARCH_DIRS[@]} -eq 0 ]] && SEARCH_DIRS=("$DEFAULT_SEARCH_ROOT")

info()  { printf '  \033[32m[ok]\033[0m %s\n' "$*"; }
warn()  { printf '  \033[33m[skip]\033[0m %s\n' "$*"; }
dry()   { printf '  \033[36m[dry]\033[0m %s\n' "$*"; }

echo ""
echo "  Migrating legacy .ai-agents/ workspace folders to $VIBECRAFTED_HOME/artifacts/"
echo "  Searching: ${SEARCH_DIRS[*]}"
echo "  ─────────────────────────────────────────────────────────"
echo ""

# Extract the date from a filename (format: 20260324_...) -> 2026_0324
# If the filename has no date prefix, fall back to "legacy"
extract_date_prefix() {
  local fname="$1"
  local date_part
  date_part="$(echo "$fname" | grep -oE '^[0-9]{8}' || echo "")"
  if [[ -n "$date_part" ]]; then
    echo "${date_part:0:4}_${date_part:4:4}"
  else
    echo "legacy"
  fi
}

# Extract the date from the newest file in a directory (for subdirs in pipeline/)
newest_date_in_dir() {
  local dir="$1"
  local dirname_base
  dirname_base="$(basename "$dir")"

  # First try to find the date from files inside the directory.
  local newest_file
  # shellcheck disable=SC2012
  newest_file="$(ls -t "$dir" 2>/dev/null | head -1)" || true
  if [[ -n "$newest_file" ]]; then
    local file_date
    file_date="$(extract_date_prefix "$newest_file")"
    if [[ "$file_date" != "legacy" ]]; then
      echo "$file_date"
      return
    fi
  fi

  # Fallback: use the directory name itself (for example 20260307_loct_dist_...)
  local dir_date
  dir_date="$(extract_date_prefix "$dirname_base")"
  echo "$dir_date"
}

# Move a single file into the correct date bucket.
move_file() {
  local file="$1"
  local target_base="$2"
  local folder="$3"

  local fname
  fname="$(basename "$file")"
  local ymd
  ymd="$(extract_date_prefix "$fname")"
  local dest="$target_base/$ymd/$folder"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    dry "mv $file -> $dest/$fname"
  else
    mkdir -p "$dest"
    mv "$file" "$dest/"
  fi
}

# Move a subdirectory (for example pipeline/<slug>/) using the newest file date.
move_subdir() {
  local subdir="$1"
  local target_base="$2"
  local folder="$3"

  local slug
  slug="$(basename "$subdir")"
  local ymd
  ymd="$(newest_date_in_dir "$subdir")"
  local dest="$target_base/$ymd/$folder/$slug"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    dry "mv $subdir/ -> $dest/"
  else
    mkdir -p "$dest"
    rsync -a --remove-source-files "$subdir/" "$dest/"
    find "$subdir" -depth -type d -empty -delete 2>/dev/null || true
  fi
}

find "${SEARCH_DIRS[@]}" -maxdepth 4 -type d -name ".ai-agents" 2>/dev/null | while read -r agents_dir; do
  repo_root="$(dirname "$agents_dir")"

  # Derive <org>/<repo> from the git remote.
  org_repo="$(cd "$repo_root" && git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|' || true)"

  if [[ -z "$org_repo" ]]; then
    # Fallback when the repo has no origin remote: use the directory name.
    org_repo="local/$(basename "$repo_root")"
  fi

  target_base="$VIBECRAFTED_HOME/artifacts/$org_repo"
  moved_something=false

  echo "  Repo: $org_repo"

  for folder in plans pipeline reports tmp; do
    src_dir="$agents_dir/$folder"

    # Only process real directories; skip empty paths and symlinks.
    if [[ -d "$src_dir" && ! -L "$src_dir" ]]; then

      # Check whether the directory is empty.
      if [ "$(ls -A "$src_dir" 2>/dev/null)" ]; then

        if [[ "$DRY_RUN" == "--dry-run" ]]; then
          # In dry-run mode, only show what would happen.
          for item in "$src_dir"/*; do
            [[ -e "$item" ]] || continue
            if [[ -d "$item" ]]; then
              move_subdir "$item" "$target_base" "$folder"
            else
              move_file "$item" "$target_base" "$folder"
            fi
          done
        else
          # Real migration: move file by file with date-based routing.
          for item in "$src_dir"/*; do
            [[ -e "$item" ]] || continue
            if [[ -d "$item" ]]; then
              move_subdir "$item" "$target_base" "$folder"
            else
              move_file "$item" "$target_base" "$folder"
            fi
          done

          # Remove empty directories left behind after migration.
          find "$src_dir" -depth -type d -empty -delete 2>/dev/null || true

          # Compatibility symlink only for reports/ so old paths do not break.
          if [[ "$folder" == "reports" && ! -e "$src_dir" ]]; then
            # Point to the newest reports directory.
            # Linking to target_base/*/reports is not meaningful, so link to latest.
            latest_reports="$(find "$target_base" -type d -name "reports" | sort -r | head -1)" || true
            if [[ -n "$latest_reports" ]]; then
              ln -sf "$latest_reports" "$src_dir"
              info "symlink: $src_dir -> $latest_reports"
            fi
          fi

          info "$folder migrated (date-routed) -> $target_base/<date>/$folder/"
        fi
        moved_something=true
      else
        # If the folder is empty, remove the directory itself.
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
          rmdir "$src_dir" 2>/dev/null || true
        fi
      fi
    elif [[ -L "$src_dir" ]]; then
      # Clean up stray symlinks left by old migration tests.
      warn "$folder stands as symlink, removing link."
      if [[ "$DRY_RUN" != "--dry-run" ]]; then
        rm "$src_dir" 2>/dev/null || true
      fi
    fi
  done

  if [ "$moved_something" = false ]; then
    warn "nothing to move in $org_repo"
  fi

done

echo ""
echo "  Migration completed."
if [[ "$DRY_RUN" == "--dry-run" ]]; then
  echo "  (Simulation mode was active: --dry-run. Run the script without --dry-run to perform the move.)"
fi
echo ""
