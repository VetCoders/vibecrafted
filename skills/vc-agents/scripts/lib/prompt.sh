#!/usr/bin/env bash

spawn_write_command_script() {
  local script_path="$1"
  local command_text="$2"
  local shell_bin

  shell_bin="$(spawn_preferred_shell)"
  mkdir -p "$(dirname "$script_path")"
  # shellcheck disable=SC2016
  printf '#!/usr/bin/env bash
set -euo pipefail
%s -lc %s
' \
    "$(spawn_shell_quote "$shell_bin")" \
    "$(spawn_shell_quote "$command_text")" \
    > "$script_path"
  chmod +x "$script_path"
}

spawn_frontmatter_field() {
  local source_file="$1"
  local field_name="$2"

  python3 - "$source_file" "$field_name" <<'PY'
import pathlib
import sys

source_file, field_name = sys.argv[1:3]
try:
    text = pathlib.Path(source_file).read_text(encoding="utf-8")
except OSError:
    raise SystemExit(0)

lines = text.splitlines()
if not lines or lines[0].strip() != "---":
    raise SystemExit(0)

for line in lines[1:]:
    if line.strip() == "---":
        break
    if ":" not in line:
        continue
    key, value = line.split(":", 1)
    if key.strip() != field_name:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(value, end="")
    raise SystemExit(0)
PY
}

spawn_strip_frontmatter_to_file() {
  local source_file="$1"
  local target_file="$2"

  python3 - "$source_file" "$target_file" <<'PY'
import pathlib
import sys

source_file, target_file = sys.argv[1:3]
text = pathlib.Path(source_file).read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

if lines and lines[0].strip() == "---":
    body_start = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = idx + 1
            break
    if body_start is not None:
        text = "".join(lines[body_start:]).lstrip("\n")

pathlib.Path(target_file).write_text(text, encoding="utf-8")
PY
}

spawn_write_frontmatter() {
  local target_file="$1"
  local agent="${2:-${SPAWN_AGENT:-unknown}}"
  local model="${3:-${SPAWN_MODEL:-unknown}}"
  local status="${4:-pending}"

  cat > "$target_file" <<EOF_FM
---
run_id: ${SPAWN_RUN_ID:-unknown}
prompt_id: ${SPAWN_PROMPT_ID:-unknown}
agent: $agent
skill: ${SPAWN_SKILL_CODE:-unknown}
model: $model
status: $status
---

EOF_FM
}

spawn_build_runtime_prompt() {
  local source_file="$1"
  local runtime_file="$2"
  local report_path="$3"
  local agent="${4:-${SPAWN_AGENT:-agent}}"
  local model="${5:-${SPAWN_MODEL:-unknown}}"

  spawn_write_frontmatter "$runtime_file" "$agent" "$model" "prompt"

  # Strip existing frontmatter (so we don't have double) and append the plan
  awk \
    '\
    BEGIN { in_fm=0; fm_done=0; }
    NR==1 && /^---[ 	]*$/ { in_fm=1; next; }
    in_fm && /^---[ 	]*$/ { in_fm=0; fm_done=1; next; }
    in_fm { next; }
    { print }
  ' "$source_file" >> "$runtime_file"

  local run_id="${SPAWN_RUN_ID:-unknown}"
  cat >> "$runtime_file" <<EOF_LABEL
---
## Exit Contract
- **COMMIT**: mandatory. One commit when done.
- **REPORT**: mandatory. Write to the report path given at the end of this prompt.
- **SCOPE**: do your work, commit, report, stop.
EOF_LABEL

  cat >> "$runtime_file" <<EOF_PROMPT

At the end of the task, write your final human-readable report to this exact path:
Report path: $report_path

Keep streaming useful progress to stdout while you work. If you cannot write a
standalone report file, finish normally and let the transcript act as the fallback
artifact.

When writing your report file, include YAML frontmatter at the top (use the exact frontmatter that this prompt starts with, but change status to 'completed' or 'failed').
EOF_PROMPT
}
