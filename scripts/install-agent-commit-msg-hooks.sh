#!/usr/bin/env bash
# Seed the Vibecrafted agent/runtime commit-message standard into sibling repos.

set -euo pipefail

usage() {
    cat >&2 <<'USAGE'
usage:
  scripts/install-agent-commit-msg-hooks.sh [base-dir] [--dry-run] [--allow-worktree-hook-paths]

Copies scripts/hooks/prepare-commit-msg and scripts/hooks/commit-msg into every
direct child git repository under
base-dir (default: parent of this repo). Respects each repository's active
core.hooksPath; if unset, installs into .git/hooks. Repositories
whose core.hooksPath points at tracked worktree files are skipped by default so
this helper does not dirty sibling checkouts.
USAGE
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
source_hooks=(
    "$repo_root/scripts/hooks/prepare-commit-msg"
    "$repo_root/scripts/hooks/commit-msg"
)
base_dir="$(cd "$repo_root/.." && pwd)"
dry_run=0
allow_worktree_hook_paths=0

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            dry_run=1
            shift
            ;;
        --allow-worktree-hook-paths)
            allow_worktree_hook_paths=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            base_dir="$(cd "$1" && pwd)"
            shift
            ;;
    esac
done

for source_hook in "${source_hooks[@]}"; do
    if [ ! -f "$source_hook" ]; then
        printf 'seed-commit-msg-hooks: source hook missing: %s\n' "$source_hook" >&2
        exit 2
    fi
done

printf 'seed-commit-msg-hooks: source=%s\n' "$repo_root/scripts/hooks"
printf 'seed-commit-msg-hooks: base=%s\n' "$base_dir"

found=0
for git_dir in "$base_dir"/*/.git; do
    [ -d "$git_dir" ] || continue
    found=1
    repo="${git_dir%/.git}"
    repo_name="$(basename "$repo")"
    hooks_path="$(git -C "$repo" config --get core.hooksPath 2>/dev/null || true)"
    if [ -z "$hooks_path" ] || [ "$hooks_path" = ".git/hooks" ]; then
        hook_dir="$repo/.git/hooks"
        hook_path_desc=".git/hooks"
    elif [ "${hooks_path#/}" != "$hooks_path" ]; then
        hook_dir="$hooks_path"
        hook_path_desc="$hooks_path"
    else
        hook_dir="$repo/$hooks_path"
        hook_path_desc="$hooks_path"
    fi

    case "$hook_dir" in
        "$repo/.git"/*|"$repo/.git/hooks"|"$repo_root"/scripts/hooks) ;;
        *)
            if [ "$allow_worktree_hook_paths" != "1" ]; then
                printf '  %-24s -> skip (%s is inside worktree; pass --allow-worktree-hook-paths)\n' "$repo_name" "$hook_path_desc"
                continue
            fi
            ;;
    esac

    printf '  %-24s -> %s\n' "$repo_name" "$hook_path_desc"
    if [ "$dry_run" = "1" ]; then
        continue
    fi
    mkdir -p "$hook_dir"
    for source_hook in "${source_hooks[@]}"; do
        hook_name="$(basename "$source_hook")"
        if [ "$hook_dir/$hook_name" = "$source_hook" ]; then
            printf '    %s already managed by source hook\n' "$hook_name"
            continue
        fi
        install -m 0755 "$source_hook" "$hook_dir/$hook_name"
    done
done

if [ "$found" -ne 1 ]; then
    printf 'seed-commit-msg-hooks: no direct child git repositories found under %s\n' "$base_dir" >&2
    exit 1
fi
