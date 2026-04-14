#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

today_date="$(date +%Y%m%d)"
# We only want artifacts for the current project.
# In operator-console.sh, VIBECRAFTED_ROOT is usually available or we can derive the project name.
# Or we can just scan MC_ARTIFACT_ROOT. But MC_ARTIFACT_ROOT contains all projects:
# artifacts/<org>/<repo>/<YYYY_MMDD>/reports/*.meta.json
# Actually, VIBECRAFTED_ROOT is the repo root.
if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
  repo_name="$(basename "$VIBECRAFTED_ROOT")"
  search_dir="$MC_ARTIFACT_ROOT/local/$repo_name"
  [[ -d "$search_dir" ]] || search_dir="$MC_ARTIFACT_ROOT"
else
  search_dir="$MC_ARTIFACT_ROOT"
fi

if [[ ! -d "$search_dir" ]]; then
  exit 0
fi

orphaned_jobs=()
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  
  # Check if status is launching, running or in-progress
  status="$(jq -r '.status // empty' "$file" 2>/dev/null || true)"
  if [[ ! "$status" =~ ^(launching|running|in-progress)$ ]]; then
    continue
  fi

  # Check if it's from a previous day
  # Format of date folder: artifacts/<org>/<repo>/YYYY_MMDD/...
  # Or we can just get the YYYYMMDD from the updated_at field or from the file path
  # Actually, the file name usually starts with YYYYMMDD_
  fname="$(basename "$file")"
  job_date="${fname%%_*}"
  if [[ "$job_date" == "$today_date" || ! "$job_date" =~ ^20[0-9]{6}$ ]]; then
    continue
  fi

  launcher="$(jq -r '.launcher // empty' "$file" 2>/dev/null || true)"
  if [[ -n "$launcher" && -x "$launcher" ]]; then
    orphaned_jobs+=("$launcher")
  fi
done < <(find "$search_dir" -type f -name '*.meta.json' 2>/dev/null | sort)

total="${#orphaned_jobs[@]}"
if (( total == 0 )); then
  exit 0
fi

# We need to render the KDL layout for the restored jobs
chunk_size=8
panes_per_row=4

tab_idx=1
for (( i=0; i<total; i+=chunk_size )); do
  chunk=("${orphaned_jobs[@]:i:chunk_size}")
  layout_file="$(mktemp "${TMPDIR:-/tmp}/vc-restored-layout-XXXXXX.kdl")"
  
  cat > "$layout_file" <<EOF
layout {
    tab name="Restored #${tab_idx}" {
        pane split_direction="horizontal" {
EOF

  # First row (up to 4 panes)
  cat >> "$layout_file" <<EOF
            pane split_direction="vertical" {
EOF
  for (( j=0; j<panes_per_row && j<${#chunk[@]}; j++ )); do
    launcher="${chunk[j]}"
    cmd_script="$(mktemp "${TMPDIR:-/tmp}/vc-restore-cmd-XXXXXX.sh")"
    echo "#!/usr/bin/env bash" > "$cmd_script"
    echo "bash '$launcher'" >> "$cmd_script"
    chmod +x "$cmd_script"
    cat >> "$layout_file" <<EOF
                pane command="bash" { args "$cmd_script"; }
EOF
  done
  cat >> "$layout_file" <<EOF
            }
EOF

  # Second row (up to 4 panes)
  if (( ${#chunk[@]} > panes_per_row )); then
    cat >> "$layout_file" <<EOF
            pane split_direction="vertical" {
EOF
    for (( j=panes_per_row; j<${#chunk[@]}; j++ )); do
      launcher="${chunk[j]}"
      cmd_script="$(mktemp "${TMPDIR:-/tmp}/vc-restore-cmd-XXXXXX.sh")"
      echo "#!/usr/bin/env bash" > "$cmd_script"
      echo "bash '$launcher'" >> "$cmd_script"
      chmod +x "$cmd_script"
      cat >> "$layout_file" <<EOF
                  pane command="bash" { args "$cmd_script"; }
EOF
    done
    cat >> "$layout_file" <<EOF
            }
EOF
  fi

  cat >> "$layout_file" <<EOF
        }
    }
}
EOF

  zellij action new-tab --layout "$layout_file" >/dev/null 2>&1 || true
  rm -f "$layout_file"
  tab_idx=$((tab_idx + 1))
done

# Return focus to the operator tab
zellij action go-to-tab-name "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Operator" >/dev/null 2>&1 || true
