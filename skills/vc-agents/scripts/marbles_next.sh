#!/usr/bin/env bash
set -euo pipefail
# Marbles chain trigger — called by success_hook inside agent launcher.
# Spawns the next loop iteration or writes CONVERGENCE.md when done.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

failed=0
if [[ "${1:-}" == "--failed" ]]; then
  failed=1
  shift
fi

state_dir="$1"
total_count="$2"
current="$3"
run_id="$4"
root_dir="$5"
runtime="$6"
scripts_dir="$7"
session_lock="$8"
store="${9:-$(spawn_marbles_store_dir "$root_dir")}"

state_file="$state_dir/state.json"
god_plan="$state_dir/god.md"
ancestor_plan="$state_dir/ancestor.md"
ancestor_slug="$(spawn_slug_from_path "$ancestor_plan")"
next=$((current + 1))
report_sync_timeout_s="${VIBECRAFTED_MARBLES_REPORT_TIMEOUT_S:-5400}"
case "$report_sync_timeout_s" in
  ''|*[!0-9]*)
    report_sync_timeout_s=5400
    ;;
esac
report_poll_s=5

_loop_child_plan() {
  local loop_nr="$1"
  spawn_marbles_child_plan_path "$store" "$ancestor_plan" "$loop_nr"
}

_find_meta_for_loop() {
  local loop_nr="$1"
  local expected_run_id="${run_id}-$(printf '%03d' "$loop_nr")"
  spawn_find_meta_for_run_id "$store/reports" "$expected_run_id"
}

_read_loop_state() {
  local loop_nr="$1"
  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

target = None
for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]):
        target = loop

if target is None:
    print("\t")
else:
    print(f"{target.get('status', '')}\t{target.get('report', '')}")
PY
  else
    printf '\t\n'
  fi
}

_read_session_id() {
  local loop_nr="$1"
  local meta_path=""
  meta_path="$(_find_meta_for_loop "$loop_nr")"
  if [[ -n "$meta_path" ]]; then
    spawn_read_meta_field "$meta_path" "session_id"
    return 0
  fi

  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]):
        print(loop.get("session_id", ""), end="")
        raise SystemExit(0)
PY
  fi
}

_read_loop_agent() {
  local loop_nr="$1"
  local meta_path=""
  local agent_name=""

  meta_path="$(_find_meta_for_loop "$loop_nr")"
  if [[ -n "$meta_path" ]]; then
    agent_name="$(spawn_read_meta_field "$meta_path" "agent")"
  fi

  if [[ -z "$agent_name" ]]; then
    local child_plan=""
    child_plan="$(_loop_child_plan "$loop_nr")"
    if [[ -f "$child_plan" ]]; then
      agent_name="$(spawn_frontmatter_field "$child_plan" "agent")"
    fi
  fi

  if [[ -z "$agent_name" && -f "$ancestor_plan" ]]; then
    agent_name="$(spawn_frontmatter_field "$ancestor_plan" "agent")"
  fi

  printf '%s' "$agent_name"
}

_loop_report_path() {
  local loop_nr="$1"
  local meta_path=""
  local report_path=""

  meta_path="$(_find_meta_for_loop "$loop_nr")"
  if [[ -n "$meta_path" ]]; then
    report_path="$(spawn_read_meta_field "$meta_path" "report")"
  fi

  printf '%s' "$report_path"
}

_wait_for_loop_report() {
  local loop_nr="$1"
  local timeout_s="${2:-0}"
  local elapsed=0
  local report_path=""

  while true; do
    report_path="$(_loop_report_path "$loop_nr")"
    if [[ -n "$report_path" && -s "$report_path" ]]; then
      printf '%s\n' "$report_path"
      return 0
    fi

    if [[ -f "$state_file" ]]; then
      local loop_state=""
      local loop_status=""
      loop_state="$(_read_loop_state "$loop_nr")"
      loop_status="${loop_state%%$'\t'*}"
      if [[ "$loop_status" == "timed_out" || "$loop_status" == "failed" || "$loop_status" == "stopped" ]]; then
        return 2
      fi
    fi

    local meta_path=""
    meta_path="$(_find_meta_for_loop "$loop_nr")"
    if [[ -n "$meta_path" ]]; then
      local meta_status=""
      meta_status="$(spawn_read_meta_field "$meta_path" "status")"
      if [[ "$meta_status" == "failed" ]]; then
        return 2
      fi
    fi

    if (( timeout_s > 0 && elapsed >= timeout_s )); then
      return 1
    fi

    sleep "$report_poll_s"
    (( elapsed += report_poll_s ))
  done
}

_update_lock() {
  local key="$1"
  local val="$2"
  [[ -f "$session_lock" ]] || return 0
  if sed --version >/dev/null 2>&1; then
    sed -i "s/^${key}=.*/${key}=${val}/" "$session_lock"
  else
    sed -i '' "s/^${key}=.*/${key}=${val}/" "$session_lock"
  fi
}

_prepare_next_loop_context() {
  local loop_nr="$1"
  local current_agent="$2"

  python3 - "$state_file" "$ancestor_plan" "$loop_nr" "$current_agent" <<'PY'
import datetime as dt
import json
import pathlib
import random
import sys

state_file, ancestor_plan, loop_nr_raw, current_agent = sys.argv[1:5]
loop_nr = int(loop_nr_raw)
state_path = pathlib.Path(state_file)
ancestor_path = pathlib.Path(ancestor_plan)


def mtime_iso(path: pathlib.Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return ""
    stamp = dt.datetime.fromtimestamp(stat.st_mtime_ns / 1_000_000_000, tz=dt.timezone.utc)
    return stamp.isoformat().replace("+00:00", "Z")


def read_frontmatter(path: pathlib.Path) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}, ""

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    fields: dict[str, str] = {}
    end_idx = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = idx
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        fields[key] = value

    if end_idx is None:
        return fields, text
    body = "".join(lines[end_idx + 1 :]).lstrip("\n")
    return fields, body


def write_frontmatter(path: pathlib.Path, fields: dict[str, str], body: str) -> None:
    ordered_keys = []
    for key in ("agent", "focus", "priority", "model"):
        if key in fields and fields[key] != "":
            ordered_keys.append(key)
    for key in fields:
        if key not in ordered_keys and fields[key] != "":
            ordered_keys.append(key)

    lines = ["---\n"]
    for key in ordered_keys:
        lines.append(f"{key}: {fields[key]}\n")
    lines.append("---\n")
    lines.append("\n")
    path.write_text("".join(lines) + body, encoding="utf-8")


def fallback_pool(agent_name: str) -> list[str]:
    base = ["codex", "claude", "gemini"]
    if agent_name not in base:
        agent_name = "codex"
    idx = base.index(agent_name)
    return base[idx:] + base[:idx]


try:
    payload = json.loads(state_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    payload = {}

rotation = payload.get("rotation") or "single"
rotation_pool = payload.get("rotation_pool")
if not isinstance(rotation_pool, list) or not rotation_pool:
    seed_agent = payload.get("agent") or current_agent or "codex"
    rotation_pool = fallback_pool(seed_agent)
    if rotation == "single":
        rotation_pool = rotation_pool[:1]
    elif rotation == "duo":
        rotation_pool = rotation_pool[:2]

stored_mtime = payload.get("ancestor_mtime") or ""
fields, body = read_frontmatter(ancestor_path)
current_mtime = mtime_iso(ancestor_path)

if current_mtime and stored_mtime and current_mtime != stored_mtime:
    next_agent = fields.get("agent") or current_agent or (rotation_pool[0] if rotation_pool else "codex")
    agent_source = "user"
else:
    if rotation == "single":
        next_agent = rotation_pool[0]
    elif rotation in {"duo", "trio"}:
        next_agent = rotation_pool[(loop_nr - 1) % len(rotation_pool)]
    elif rotation == "multi":
        next_agent = random.choice(rotation_pool)
    else:
        next_agent = rotation_pool[0]

    previous_agent = fields.get("agent", "")
    wrote_frontmatter = False
    if previous_agent != next_agent or "agent" not in fields:
        fields["agent"] = next_agent
        wrote_frontmatter = True
    if previous_agent and previous_agent != next_agent and "model" in fields:
        fields.pop("model", None)
        wrote_frontmatter = True
    if wrote_frontmatter:
        write_frontmatter(ancestor_path, fields, body)
        current_mtime = mtime_iso(ancestor_path)
        fields, body = read_frontmatter(ancestor_path)
    agent_source = "rotation"

payload["agent"] = next_agent
payload["rotation"] = rotation
payload["rotation_pool"] = rotation_pool
payload["ancestor_mtime"] = current_mtime
payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

loops = payload.setdefault("loops", [])
target = None
for loop in loops:
    if loop.get("loop") == loop_nr:
        target = loop
        break

if target is None:
    target = {"loop": loop_nr}
    loops.append(target)

target["agent"] = next_agent
target["agent_source"] = agent_source
target["focus"] = fields.get("focus", "")
target["ancestor_slug"] = "ancestor"
if fields.get("model"):
    target["model"] = fields["model"]
else:
    target.pop("model", None)

state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(
    "\t".join(
        [
            next_agent,
            agent_source,
            fields.get("focus", ""),
            fields.get("model", ""),
            current_mtime,
        ]
    ),
    end="",
)
PY
}

_choose_available_agent() {
  local preferred_agent="$1"
  local ordered_agents=""
  local candidate=""

  if command -v "$preferred_agent" >/dev/null 2>&1; then
    printf '%s\n' "$preferred_agent"
    return 0
  fi

  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    ordered_agents="$(python3 - "$state_file" "$preferred_agent" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

pool = payload.get("rotation_pool")
if not isinstance(pool, list):
    pool = []
preferred = sys.argv[2]
if preferred in pool:
    start = pool.index(preferred)
    pool = pool[start + 1 :] + pool[: start + 1]

for agent in pool:
    print(agent)
PY
)"
  fi

  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done <<EOF_AGENTS
$ordered_agents
EOF_AGENTS

  printf '%s\n' "$preferred_agent"
}

_apply_agent_override() {
  local loop_nr="$1"
  local agent_name="$2"
  local agent_source="$3"
  local ancestor_mtime=""

  spawn_frontmatter_set_field "$ancestor_plan" "agent" "$agent_name"
  spawn_frontmatter_set_field "$ancestor_plan" "model" "" 1
  ancestor_mtime="$(spawn_file_mtime_iso "$ancestor_plan")"

  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$agent_name" "$agent_source" "$ancestor_mtime" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

loop_nr = int(sys.argv[2])
agent_name = sys.argv[3]
agent_source = sys.argv[4]
ancestor_mtime = sys.argv[5]

payload["agent"] = agent_name
payload["ancestor_mtime"] = ancestor_mtime
payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

for loop in payload.get("loops", []):
    if loop.get("loop") == loop_nr:
        loop["agent"] = agent_name
        loop["agent_source"] = agent_source
        loop.pop("model", None)
        break

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_write_missing_report_failure() {
  local loop_nr="$1"
  local reason="$2"
  local loop_agent="$3"
  local convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"

  cat > "$convergence" <<CONV
---
run_id: $run_id
agent: $loop_agent
status: FAILED
failed_at_loop: $loop_nr
total_loops: $total_count
reason: missing_report
---

# Marbles Convergence — FAILED

Loop $loop_nr of $total_count did not produce an observed report.

- Reason: $reason
- Sync timeout: ${report_sync_timeout_s}s
- Effect: no further loops were spawned, so the loop budget was not consumed
- GOD: $god_plan
- ANCESTOR: $ancestor_plan
CONV

  _update_lock status failed
  printf '\n\033[31m ✗  Marbles blocked at loop %s/%s\033[0m\n' "$loop_nr" "$total_count"
  printf '    Missing report guard: %s\n' "$reason"
  printf '    Convergence: %s\n' "$convergence"
}

_write_invalid_ancestor_failure() {
  local loop_nr="$1"
  local invalid_agent="$2"
  local convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"

  cat > "$convergence" <<CONV
---
run_id: $run_id
agent: $invalid_agent
status: FAILED
failed_at_loop: $loop_nr
total_loops: $total_count
reason: invalid_ancestor_agent
---

# Marbles Convergence — FAILED

'ancestor.md' requested an invalid agent for loop $loop_nr.

- Invalid agent: ${invalid_agent:-<empty>}
- Expected: claude, codex, or gemini
- GOD: $god_plan
- ANCESTOR: $ancestor_plan
CONV

  _update_lock status failed
  printf '\n\033[31m ✗  Marbles blocked before loop %s/%s\033[0m\n' "$loop_nr" "$total_count"
  printf '    Invalid ancestor agent: %s\n' "${invalid_agent:-<empty>}"
  printf '    Convergence: %s\n' "$convergence"
}

_collect_reports() {
  local up_to="$1"
  local loop_nr=""
  local report_path=""

  for ((loop_nr = 1; loop_nr <= up_to; loop_nr++)); do
    report_path="$(_loop_report_path "$loop_nr")"
    if [[ -n "$report_path" && -f "$report_path" ]]; then
      printf '%s\n' "$report_path"
    fi
  done
}

_launch_verification() {
  local loop_nr="$1"
  local is_final="${2:-0}"
  local sid=""
  local loop_agent=""
  local report_path=""

  sid="$(_read_session_id "$loop_nr")"
  if [[ -z "$sid" ]]; then
    printf '    ⚠ No session_id for L%s — skipping verification\n' "$loop_nr"
    return 0
  fi

  report_path="$(_loop_report_path "$loop_nr")"
  if [[ -z "$report_path" ]]; then
    printf '    ⚠ No report path for L%s — skipping verification\n' "$loop_nr"
    return 0
  fi

  loop_agent="$(_read_loop_agent "$loop_nr")"
  [[ -n "$loop_agent" ]] || loop_agent="codex"

  local reports_list=""
  while IFS= read -r rpt; do
    [[ -n "$rpt" ]] || continue
    reports_list="${reports_list}
- ${rpt}"
  done < <(_collect_reports "$loop_nr")

  local verified_path="${report_path%.md}_verified.md"
  local prompt="You are resuming to self-audit your own report from marbles loop L${loop_nr}.

## Instructions
1. Read ALL reports from this batch:${reports_list}
2. Re-read your own report critically
3. Write a verified report to: ${verified_path}
4. The verified report should:
   - Confirm or correct your original findings
   - Note any contradictions with other loops' reports
   - Add anything you missed"

  if (( is_final )); then
    prompt="${prompt}

## Final Loop — Convergence Assessment
This is the final loop. Your verified report MUST include:
- **Convergence verdict**: Has the codebase converged? (yes/no/partial)
- **Remaining issues**: Any P0/P1 still open after all loops
- **Next workflow recommendation**: What should the team do next (e.g., ship, another marbles run with different focus, manual review of specific area)
"
  fi

  prompt="${prompt}

## Constraints
- Do NOT modify any code files — only write your verified report
- Be honest about uncertainty — flag anything you cannot verify
- Keep the verified report concise and actionable"

  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]):
        loop["verification_status"] = "pending"

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file" 2>/dev/null || true
  fi

  printf '    🔍 Verification L%s → session %s\n' "$loop_nr" "${sid:0:13}…"
  case "$loop_agent" in
    claude) nohup claude --resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    codex)  nohup codex resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    gemini) nohup gemini --resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    *) printf '    ⚠ Unknown loop agent %s — skipping verification\n' "$loop_agent" ;;
  esac
}

current_agent="$(_read_loop_agent "$current")"
[[ -n "$current_agent" ]] || current_agent="$(spawn_frontmatter_field "$ancestor_plan" "agent")"
[[ -n "$current_agent" ]] || current_agent="unknown"

if (( failed )); then
  convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"
  cat > "$convergence" <<CONV
---
run_id: $run_id
agent: $current_agent
status: FAILED
failed_at_loop: $current
total_loops: $total_count
---

# Marbles Convergence — FAILED

Loop $current of $total_count failed.
Check individual loop reports for details.

- GOD: $god_plan
- ANCESTOR: $ancestor_plan
CONV

  _update_lock status failed
  printf '\n\033[31m ✗  Marbles failed at loop %s/%s\033[0m\n' "$current" "$total_count"
  printf '    Convergence: %s\n' "$convergence"
  exit 0
fi

if _wait_for_loop_report "$current" "$report_sync_timeout_s" >/dev/null; then
  :
else
  wait_status=$?
  case "$wait_status" in
    2)
      _write_missing_report_failure "$current" "watcher or launcher marked loop as failed" "$current_agent"
      ;;
    *)
      _write_missing_report_failure "$current" "report not observed within ${report_sync_timeout_s}s" "$current_agent"
      ;;
  esac
  exit 0
fi

if [[ $next -gt $total_count ]]; then
  convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"

  {
    cat <<HEADER
---
run_id: $run_id
agent: $current_agent
status: completed
loops_completed: $total_count
god_plan: $god_plan
ancestor_plan: $ancestor_plan
---

# Marbles Convergence — Complete

$total_count loops completed successfully.

## Steering Surfaces
- GOD: $god_plan
- ANCESTOR: $ancestor_plan

## Loop Reports
HEADER

    while IFS= read -r rpt; do
      [[ -n "$rpt" ]] || continue
      printf '\n### %s\n\n' "$(basename "$rpt")"
      head -20 "$rpt" 2>/dev/null || printf '(report not readable)\n'
      printf '\n...\n'
    done < <(_collect_reports "$total_count")

    printf '\n---\n𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents (c)2024-2026 VetCoders\n'
  } > "$convergence"

  _launch_verification "$current" 1
  _update_lock status completed
  printf '\n\033[32m ✓  Marbles complete: %s loops · %s\033[0m\n' "$total_count" "$run_id"
  printf '    Convergence: %s\n' "$convergence"
  exit 0
fi

_launch_verification "$current" 0

IFS=$'\t' read -r next_agent next_agent_source next_focus next_model _ <<< "$(_prepare_next_loop_context "$next" "$current_agent")"
[[ -n "$next_agent" ]] || next_agent="$(spawn_frontmatter_field "$ancestor_plan" "agent")"
[[ -n "$next_agent" ]] || next_agent="$current_agent"
available_agent="$(_choose_available_agent "$next_agent")"
if [[ "$available_agent" != "$next_agent" ]]; then
  printf '    ⚠ scheduled agent unavailable, falling back %s → %s\n' "$next_agent" "$available_agent"
  next_agent="$available_agent"
  next_agent_source="rotation"
  next_model=""
  _apply_agent_override "$next" "$next_agent" "$next_agent_source"
fi
if [[ ! "$next_agent" =~ ^(claude|codex|gemini)$ ]]; then
  _write_invalid_ancestor_failure "$next" "$next_agent"
  exit 0
fi

_update_lock current "$next"
_update_lock agent "$next_agent"
printf '\n\033[38;5;173m ⚒  Marbles loop %s/%s starting...\033[0m\n' "$next" "$total_count"
if [[ -n "$next_agent_source" ]]; then
  printf '    steering: %s → %s\n' "$next_agent_source" "$next_agent"
fi
if [[ -n "$next_focus" ]]; then
  printf '    focus: %s\n' "$next_focus"
fi

next_plan="$(_loop_child_plan "$next")"
spawn_marbles_write_child_plan "$ancestor_plan" "$next_plan"

q_state="$(spawn_shell_quote "$state_dir")"
q_root="$(spawn_shell_quote "$root_dir")"
q_runtime="$(spawn_shell_quote "$runtime")"
q_scripts="$(spawn_shell_quote "$scripts_dir")"
q_lock="$(spawn_shell_quote "$session_lock")"
q_store="$(spawn_shell_quote "$store")"

success_hook="bash $q_scripts/marbles_next.sh $q_state $total_count $next $run_id $q_root $q_runtime $q_scripts $q_lock $q_store"
failure_hook="bash $q_scripts/marbles_next.sh --failed $q_state $total_count $next $run_id $q_root $q_runtime $q_scripts $q_lock $q_store"

export VIBECRAFTED_LOOP_NR=$next
export VIBECRAFTED_RUN_ID="${run_id}-$(printf '%03d' "$next")"

spawn_args=(
  --mode implement
  --runtime "$runtime"
  --root "$root_dir"
  --success-hook "$success_hook"
  --failure-hook "$failure_hook"
)
if [[ -n "$next_model" && "$next_agent" != "codex" ]]; then
  spawn_args+=(--model "$next_model")
fi

VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=right VIBECRAFTED_STORE_DIR="$store" bash "$scripts_dir/${next_agent}_spawn.sh" "${spawn_args[@]}" "$next_plan"
