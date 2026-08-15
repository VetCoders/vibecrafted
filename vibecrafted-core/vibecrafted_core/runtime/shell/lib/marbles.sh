# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_marbles() {
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  local tool="$1"
  shift
  local script marbles_cmd quoted_args quoted_env operator_session root_dir marbles_run_id runtime launch_ts launch_report
  local loop_skill_name loop_skill_code loop_label loop_file_prefix
  local -a marbles_env
  script="$(_vetcoders_spawn_script "$tool" "marbles_spawn.sh")" || return 1
  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is only supported by vibecrafted resume." >&2
    return 1
  }
  if [[ -n "$_vetcoders_contract_task" ]]; then
    [[ -z "$_vetcoders_contract_file" ]] || {
      echo "Marbles accepts one file source: use either --task or --file, not both." >&2
      return 1
    }
    _vetcoders_contract_file="$_vetcoders_contract_task"
  fi

  local source_count=0
  [[ -n "$_vetcoders_contract_depth" ]] && ((source_count+=1))
  [[ -n "$_vetcoders_contract_file" ]] && ((source_count+=1))
  [[ -n "$_vetcoders_contract_prompt" ]] && ((source_count+=1))
  [[ $source_count -le 1 ]] || {
    echo "Marbles accepts one source at a time: use exactly one of --depth, --file, or --prompt." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_count" ]] || _vetcoders_require_positive_int "$_vetcoders_contract_count" "--count" || return 1
  [[ -z "$_vetcoders_contract_depth" ]] || _vetcoders_require_positive_int "$_vetcoders_contract_depth" "--depth" || return 1

  loop_skill_name="${VIBECRAFTED_LOOP_SKILL_NAME:-marbles}"
  loop_skill_code="${VIBECRAFTED_LOOP_SKILL_CODE:-$(_vetcoders_skill_prefix "$loop_skill_name")}"
  loop_label="${VIBECRAFTED_LOOP_LABEL:-Marbles}"
  loop_file_prefix="${VIBECRAFTED_LOOP_FILE_PREFIX:-$loop_skill_name}"

  # shellcheck disable=SC2031
  [[ -n "${VIBECRAFTED_SKILL_NAME:-}" ]] || export VIBECRAFTED_SKILL_NAME="$loop_skill_name"
  # shellcheck disable=SC2031
  export VIBECRAFTED_SKILL_CODE="$loop_skill_code"

  root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  marbles_run_id="${VIBECRAFTED_MARBLES_RUN_ID:-${VIBECRAFTED_LOOP_RUN_ID:-$(_vetcoders_generate_run_id "$loop_skill_code")}}"
  runtime="$(_vetcoders_effective_runtime)"
  marbles_env=(
    VIBECRAFTED_MARBLES_RUN_ID="$marbles_run_id"
    VIBECRAFTED_LOOP_SKILL_NAME="$loop_skill_name"
    VIBECRAFTED_LOOP_SKILL_CODE="$loop_skill_code"
    VIBECRAFTED_LOOP_LABEL="$loop_label"
    VIBECRAFTED_LOOP_FILE_PREFIX="$loop_file_prefix"
  )
  local marbles_args=(--agent "$tool" --runtime "$runtime" --skill-name "$loop_skill_name" --skill-code "$loop_skill_code" --loop-label "$loop_label" --loop-file-prefix "$loop_file_prefix")
  local source_args=()
  [[ -n "$_vetcoders_contract_root" ]] && marbles_args+=(--root "$_vetcoders_contract_root")
  [[ -n "$_vetcoders_contract_count" ]] && marbles_args+=(--count "$_vetcoders_contract_count")

  if [[ -n "$_vetcoders_contract_file" ]]; then
    source_args=(--file "$_vetcoders_contract_file")
  elif [[ -n "$_vetcoders_contract_prompt" ]]; then
    source_args=(--prompt "$_vetcoders_contract_prompt")
  else
    source_args=(--depth "${_vetcoders_contract_depth:-3}")
  fi
  if [[ "$runtime" == "headless" ]]; then
    marbles_args+=(--no-watch)
    launch_ts="$(_vetcoders_spawn_timestamp)"
    launch_report="$(_vetcoders_marbles_l1_report_path "$root_dir" "$launch_ts" "$tool")"
    marbles_env+=(VIBECRAFTED_SPAWN_TS="$launch_ts" VIBECRAFTED_SUPPRESS_REPORT_HINT=1)
    printf 'Agent launched. Report will land at: %s\n' "$launch_report"
  fi
  marbles_args+=("${source_args[@]}")

  quoted_env="$(_vetcoders_shell_quote_join "${marbles_env[@]}")"
  quoted_args="$(_vetcoders_shell_quote_join "${marbles_args[@]}")"
  marbles_cmd="env ${quoted_env} bash $(_vetcoders_shell_quote "$script") ${quoted_args}"
  operator_session="${VIBECRAFTED_OPERATOR_SESSION:-}"
  if [[ -z "$operator_session" ]] && _vetcoders_in_vc_frame; then
    operator_session="$(_vetcoders_current_vc_frame_session_name)"
  fi
  if [[ -z "$operator_session" ]]; then
    operator_session="$(_vetcoders_operator_session_name)"
  fi

  # Inside vc_frame: each marbles run_id gets its own tab named
  # "marbles-<run_id>". Subsequent loops (L2, L3, ...) inherit
  # VIBECRAFTED_MARBLES_TAB_NAME via env and stay in the same tab — one
  # run_id = one tab, no crossover. The "marbles-" prefix distinguishes
  # the tab from workflow/research tabs which also carry run_ids.
  # Temp script keeps vc_frame args ASCII-safe (no inline UTF-8 prompt bytes).
  local vc_frame_bin=""
  if [[ "$runtime" =~ ^(terminal|visible)$ ]] && _vetcoders_in_vc_frame && vc_frame_bin="$(_vetcoders_vc_frame_bin)"; then
    local cmd_script marbles_tab_name
    VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_vc_frame_session_name)"
    export VIBECRAFTED_OPERATOR_SESSION
    marbles_tab_name="${loop_file_prefix}-${marbles_run_id}"
    export VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name"
    marbles_env+=(VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name")
    quoted_env="$(_vetcoders_shell_quote_join "${marbles_env[@]}")"
    marbles_cmd="env ${quoted_env} bash $(_vetcoders_shell_quote "$script") ${quoted_args}"
    cmd_script="$(_vetcoders_tmp_script_path "vibecrafted-marbles" "$root_dir")"
    _vetcoders_write_command_script "$cmd_script" "$marbles_cmd" || return 1
    
    local original_tab
    original_tab="${VC_FRAME_TAB_NAME:-}"
    
    "$vc_frame_bin" action go-to-tab-name "$marbles_tab_name" --create >/dev/null 2>&1 || true
    "$vc_frame_bin" action new-pane \
      --name "$marbles_run_id" \
      --cwd "$root_dir" \
      -- "$cmd_script" >/dev/null || return 1

    printf '%s run launched in vc_frame tab: %s\n' "$loop_label" "$marbles_tab_name"
    printf '  run_id:  %s\n' "$marbles_run_id"
    printf '  inspect: vc-marbles inspect %s\n' "$marbles_run_id"
      
    if [[ -n "$original_tab" ]]; then
      "$vc_frame_bin" action go-to-tab-name "$original_tab" >/dev/null 2>&1 || true
    fi
    
    _vetcoders_marbles_emit_probe "$root_dir" "$marbles_run_id" "launched"
  elif [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
      _vetcoders_spawn_into_operator_session "marbles" "$marbles_cmd" || return 1
      printf '%s run launched in operator session: %s\n' "$loop_label" "$VIBECRAFTED_OPERATOR_SESSION"
      printf '  run_id:  %s\n' "$marbles_run_id"
      printf '  inspect: vc-marbles inspect %s\n' "$marbles_run_id"
      _vetcoders_marbles_emit_probe "$root_dir" "$marbles_run_id" "launched"
    else
      env "${marbles_env[@]}" bash "$script" "${marbles_args[@]}"
    fi
  else
    env "${marbles_env[@]}" bash "$script" "${marbles_args[@]}"
  fi
}

# When resume has no session_id: assemble a bounded multi-agent continuity pack
# from AICX (last 48h by default) via sessions list + intents + overlay.
# Emits KEY=value lines on stdout:
#   SESSION_ID=...   (may be empty → NEW session)
#   CONTEXT_FILE=...
#   SESSION_COUNT=...
#   MODE=native_resume|new_session
_vetcoders_aicx_resume_fallback() {
  local agent="$1"
  local root="${2:-$(_vetcoders_repo_root)}"
  local hours="${VIBECRAFTED_RESUME_AICX_HOURS:-48}"
  local tmp_dir context_file meta_file aicx_bin
  aicx_bin="$(_vetcoders_aicx_bin 2>/dev/null)" || {
    echo "aicx foundation not found in the Vibecrafted runtime, ~/.local/bin, ~/.cargo/bin, or PATH." >&2
    echo "Install the AICX foundation or pass --session <session_id>." >&2
    return 1
  }
  tmp_dir="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tmp"
  mkdir -p "$tmp_dir" 2>/dev/null || tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/vc-resume.XXXXXX")"
  context_file="$tmp_dir/resume-aicx-${agent}-$(date +%Y%m%d_%H%M%S).md"
  meta_file="${context_file}.meta.json"

  python3 - "$agent" "$root" "$hours" "$context_file" "$meta_file" "$aicx_bin" <<'PY' || return 1
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import sys

agent, root, hours_s, context_file, meta_file, aicx_bin = sys.argv[1:7]
hours = int(hours_s)
now = dt.datetime.now(dt.timezone.utc)
cutoff = now - dt.timedelta(hours=hours)
since = cutoff.date().isoformat()
root_path = pathlib.Path(root).resolve()
project = root_path.name
degradations: list[str] = []
max_pack_chars = 48_000


def run(cmd: list[str], timeout: float) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", "not_found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def parse_ts(value: object) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return stamp.astimezone(dt.timezone.utc)


sessions: list[dict] = []
for flags in (["--cwd"], []):
    code, out, err = run(
        [
            aicx_bin,
            "sessions",
            "list",
            "--format",
            "json",
            "--since",
            since,
            "--limit",
            "40",
            *flags,
        ],
        timeout=18,
    )
    if code != 0 or not out.strip():
        degradations.append(
            f"sessions_list{flags or ['_all']}:{code}:{(err or out)[:160]}"
        )
        continue
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        degradations.append(f"sessions_list_json_invalid{flags or ['_all']}")
        continue
    if isinstance(payload, list) and payload:
        sessions = payload
        if flags == ["--cwd"]:
            break

filtered: list[dict] = []
for item in sessions:
    if not isinstance(item, dict):
        continue
    stamp = parse_ts(item.get("updated_at") or item.get("started_at"))
    if stamp is None or stamp >= cutoff:
        filtered.append(item)

def locally_resumable(item: dict) -> bool:
    # aicx retains extracts long after providers prune their local session
    # store; a native resume of a pruned session dies with "No conversation
    # found". Only sessions the provider still holds are launch targets.
    src = str(item.get("source_path") or "")
    if src:
        return pathlib.Path(src).exists()
    if agent == "claude":
        sid = str(item.get("session_id") or "")
        return bool(sid) and any(
            pathlib.Path.home().glob(f".claude/projects/*/{sid}.jsonl")
        )
    return True


resumable_same_agent: list[dict] = []
for item in filtered:
    if str(item.get("agent") or "") != agent:
        continue
    if locally_resumable(item):
        resumable_same_agent.append(item)
    else:
        degradations.append(
            f"native_candidate_missing_local:{item.get('session_id')}"
        )

candidate: dict | None = None
for item in resumable_same_agent:
    repo = str(item.get("repo_path") or "")
    try:
        if repo and pathlib.Path(repo).resolve() == root_path:
            candidate = item
            break
    except OSError:
        pass
if candidate is None and resumable_same_agent:
    candidate = resumable_same_agent[0]

# Prefer aicx tail (default window 48h, fast snapshot) before full intents.
# Overlay is best-effort and often slow on large repos — never block resume.
intents_md = ""
code, out, err = run(
    [aicx_bin, "tail", "-H", str(hours), "--limit", "20", "-p", project],
    timeout=12,
)
if code == 0 and out.strip():
    intents_md = out.strip()
else:
    degradations.append(f"tail:{code}:{(err or out)[:160]}")
    for project_args in ([project], []):
        cmd = [
            aicx_bin,
            "intents",
            "-H",
            str(hours),
            "--limit",
            "15",
            "--emit",
            "markdown",
        ]
        if project_args:
            cmd.extend(["-p", project_args[0]])
        code, out, err = run(cmd, timeout=12)
        if code == 0 and out.strip():
            intents_md = out.strip()
            break
        degradations.append(f"intents:{code}:{(err or out)[:160]}")

overlay_blob = ""
code, out, err = run(
    [aicx_bin, "overlay", "--repo", str(root_path), "--format", "json"],
    timeout=8,
)
if code == 0 and out.strip():
    try:
        overlay_obj = json.loads(out)
        overlay_blob = json.dumps(overlay_obj, indent=2, ensure_ascii=False)[:12_000]
    except json.JSONDecodeError:
        overlay_blob = out[:8_000]
        degradations.append("overlay_json_invalid")
else:
    degradations.append(f"overlay:{code}:{(err or out)[:160]}")

lines: list[str] = [
    "# Resume continuity pack (no session_id)",
    "",
    "Fallback path: AICX multi-agent context for the last "
    f"{hours}h (sessions list + intents + overlay).",
    "",
    f"- agent: `{agent}`",
    f"- root: `{root_path}`",
    f"- window: last {hours}h across all agents",
    f"- assembled_at: `{now.isoformat()}`",
]
if candidate:
    lines.append(
        f"- native_resume_candidate: `{candidate.get('session_id')}` "
        f"(agent={candidate.get('agent')}, project={candidate.get('project')})"
    )
    lines.append(
        "- mode: prefer native resume of that session with this pack as the "
        "continuation prompt"
    )
else:
    lines.append("- native_resume_candidate: none")
    lines.append(
        "- mode: NEW provider session — continuity only (not a native resume)"
    )
if degradations:
    lines.append("- degradations:")
    for item in degradations:
        lines.append(f"  - `{item}`")

lines.extend(["", "## Session catalog (48h, multi-agent)", ""])
if not filtered:
    lines.append("_(no sessions discovered in window)_")
else:
    lines.append("| agent | session_id | project | updated_at | title |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in filtered[:30]:
        title = str(item.get("title") or "").replace("|", "/").replace("\n", " ")
        if len(title) > 72:
            title = title[:69] + "..."
        lines.append(
            "| {agent} | `{sid}` | {proj} | {updated} | {title} |".format(
                agent=item.get("agent") or "?",
                sid=item.get("session_id") or "?",
                proj=item.get("project") or "?",
                updated=item.get("updated_at") or "?",
                title=title or "—",
            )
        )

lines.extend(["", "## Intents (aicx, window)", ""])
lines.append(intents_md[:20_000] if intents_md else "_(empty or unavailable)_")

if overlay_blob:
    lines.extend(
        [
            "",
            "## AICX overlay (bounded JSON)",
            "",
            "```json",
            overlay_blob,
            "```",
        ]
    )

lines.extend(
    [
        "",
        "## Operator instruction",
        "",
        "Continue work in this repository with continuity from the multi-agent "
        "session catalog, intents, and overlay above.",
        "Historical paths and foreign-agent sessions are evidence only — not "
        "launch destinations unless native_resume_candidate was selected.",
        "Re-read files before editing (Living Tree). Prefer runtime truth over "
        "remembered state.",
        "",
    ]
)

body = "\n".join(lines)
if len(body) > max_pack_chars:
    body = body[: max_pack_chars - 80] + "\n\n_(truncated for resume pack budget)_\n"

pathlib.Path(context_file).write_text(body, encoding="utf-8")
meta = {
    "schema": "vibecrafted.resume.aicx_fallback.v1",
    "agent": agent,
    "root": str(root_path),
    "hours": hours,
    "session_id": str((candidate or {}).get("session_id") or ""),
    "session_count": len(filtered),
    "mode": "native_resume" if candidate else "new_session",
    "context_file": context_file,
    "degradations": degradations,
}
pathlib.Path(meta_file).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(f"SESSION_ID={meta['session_id']}")
print(f"CONTEXT_FILE={context_file}")
print(f"SESSION_COUNT={meta['session_count']}")
print(f"MODE={meta['mode']}")
PY
}

# Resolve one Python >=3.11 that can import the live vibecrafted_core package.
# Output is: <python-path><TAB><optional-PYTHONPATH-import-root>.
_vetcoders_core_python_spec() {
  local py="" candidate package_parent="" source_dir=""
  for candidate in \
    "${VIBECRAFTED_PYTHON:-}" \
    "${XDG_DATA_HOME:-$HOME/.local/share}/uv/tools/vibecrafted-core/bin/python3" \
    python3.13 python3.12 python3.11 python3; do
    [[ -n "$candidate" ]] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
      >/dev/null 2>&1; then
      py="$(command -v "$candidate")"
      break
    fi
  done
  [[ -n "$py" ]] || {
    echo "Vibecrafted core requires Python >=3.11; no eligible interpreter found." >&2
    return 1
  }
  if "$py" -c 'import vibecrafted_core' >/dev/null 2>&1; then
    printf '%s\t\n' "$py"
    return 0
  fi
  source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd 2>/dev/null || true)"
  # Packaged layout: shell/lib → … → vibecrafted-core (parent of
  # vibecrafted_core). Checkout layout is a hardlinked runtime twin under
  # <repo>/runtime, so its import root is <repo>/vibecrafted-core instead.
  if [[ -n "$source_dir" ]]; then
    package_parent="$(cd "$source_dir/../../../.." && pwd 2>/dev/null || true)"
    if [[ ! -d "$package_parent/vibecrafted_core" ]]; then
      package_parent="$(cd "$source_dir/../../.." && pwd 2>/dev/null || true)/vibecrafted-core"
    fi
  fi
  if [[ -n "$package_parent" && -d "$package_parent/vibecrafted_core" ]] &&
    PYTHONPATH="$package_parent${PYTHONPATH:+:$PYTHONPATH}" \
      "$py" -c 'import vibecrafted_core' >/dev/null 2>&1; then
    printf '%s\t%s\n' "$py" "$package_parent"
    return 0
  fi
  echo "Vibecrafted core unavailable: cannot import vibecrafted_core." >&2
  return 1
}

_vetcoders_run_core_cli() {
  local python_spec py import_root
  python_spec="$(_vetcoders_core_python_spec)" || return 1
  py="${python_spec%%$'\t'*}"
  import_root="${python_spec#*$'\t'}"
  if [[ -n "$import_root" ]]; then
    PYTHONPATH="$import_root${PYTHONPATH:+:$PYTHONPATH}" \
      "$py" -m vibecrafted_core.cli "$@"
  else
    "$py" -m vibecrafted_core.cli "$@"
  fi
}

_vetcoders_core_source_dir() {
  local python_spec py import_root
  python_spec="$(_vetcoders_core_python_spec)" || return 1
  py="${python_spec%%$'\t'*}"
  import_root="${python_spec#*$'\t'}"
  if [[ -n "$import_root" ]]; then
    PYTHONPATH="$import_root${PYTHONPATH:+:$PYTHONPATH}" \
      "$py" -c 'from vibecrafted_core.package_resources import package_root; print(package_root())'
  else
    "$py" -c 'from vibecrafted_core.package_resources import package_root; print(package_root())'
  fi
}

# Print a shell-safe filter pipeline fragment for non-interactive
# streaming-json agents through the same core-Python resolver as launch paths.
_vetcoders_agent_stream_filter_cmd() {
  local agent="$1"
  local raw_file="${2:-}"
  local python_spec py import_root python_prefix
  local quoted_agent quoted_raw quoted_parent quoted_py
  python_spec="$(_vetcoders_core_python_spec)" || return 1
  py="${python_spec%%$'\t'*}"
  import_root="${python_spec#*$'\t'}"
  quoted_py="$(_vetcoders_shell_quote "$py")"
  quoted_agent="$(_vetcoders_shell_quote "$agent")"
  if [[ -n "$raw_file" ]]; then
    quoted_raw="$(_vetcoders_shell_quote "$raw_file")"
  else
    quoted_raw=""
  fi
  if [[ -n "$import_root" ]]; then
    quoted_parent="$(
      _vetcoders_shell_quote "$import_root${PYTHONPATH:+:$PYTHONPATH}"
    )"
    python_prefix="PYTHONPATH=${quoted_parent} ${quoted_py}"
  else
    python_prefix="$quoted_py"
  fi
  if [[ -n "$quoted_raw" ]]; then
    printf '%s -m vibecrafted_core.agent_stream --agent %s --raw-file %s\n' \
      "$python_prefix" "$quoted_agent" "$quoted_raw"
  else
    printf '%s -m vibecrafted_core.agent_stream --agent %s\n' \
      "$python_prefix" "$quoted_agent"
  fi
}

# Path for raw streaming-json transcript (human pane sees filtered text only).
_vetcoders_resume_raw_transcript_path() {
  local agent="$1"
  local home_dir="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo now)"
  printf '%s/artifacts/resume/%s-%s.stream.jsonl\n' "$home_dir" "$agent" "$stamp"
}

# Wrap a headless agent command so streaming-json is rendered via AgentStreamParser.
# Grok always uses this path. Other agents pass through unchanged unless they emit
# streaming-json in the headless resume builders.
_vetcoders_wrap_with_agent_stream() {
  local agent="$1"
  local cmd="$2"
  local raw_file="${3:-}"
  local filter_cmd
  case "$agent" in
    grok)
      filter_cmd="$(_vetcoders_agent_stream_filter_cmd "$agent" "$raw_file")" || return 1
      # Keep raw transcript when requested (tee is inside the filter via --raw-file).
      printf 'set -o pipefail; { %s; } 2>&1 | %s\n' "$cmd" "$filter_cmd"
      ;;
    *)
      printf '%s\n' "$cmd"
      ;;
  esac
}

# Fresh provider session (no native --resume). Used when AICX fallback cannot
# pick a same-agent session in the window.
_vetcoders_fresh_session_command() {
  local tool="$1"
  local prompt="${2:-}"
  local mode="${3:-interactive}"
  local quoted_prompt=""
  if [[ -n "$prompt" ]]; then
    quoted_prompt="$(_vetcoders_shell_quote "$prompt")"
  else
    quoted_prompt="$(_vetcoders_shell_quote "Continue from the AICX multi-agent continuity pack.")"
  fi

  case "$tool" in
    claude)
      if [[ "$mode" == headless ]]; then
        printf 'claude --print --dangerously-skip-permissions %s\n' "$quoted_prompt"
      else
        printf 'claude %s\n' "$quoted_prompt"
      fi
      ;;
    codex)
      if [[ "$mode" == headless ]]; then
        printf 'codex exec --dangerously-bypass-approvals-and-sandbox %s\n' "$quoted_prompt"
      else
        printf 'codex %s\n' "$quoted_prompt"
      fi
      ;;
    agy)
      if [[ "$mode" == headless ]]; then
        printf 'agy --dangerously-skip-permissions --print %s\n' "$quoted_prompt"
      else
        printf 'agy --prompt-interactive %s\n' "$quoted_prompt"
      fi
      ;;
    junie)
      printf 'junie --task=%s --project=. --skip-update-check\n' "$quoted_prompt"
      ;;
    grok)
      # Interactive: positional PROMPT into the TUI (stays open).
      # Headless: --single is one-shot stdout (fleet / await / baton-pass only).
      if [[ "$mode" == headless ]]; then
        printf 'grok --cwd . --permission-mode bypassPermissions --no-alt-screen --output-format streaming-json --single %s\n' "$quoted_prompt"
      else
        printf 'grok --cwd . --permission-mode bypassPermissions --no-alt-screen %s\n' "$quoted_prompt"
      fi
      ;;
    *)
      echo "Unknown agent for fresh resume session: $tool" >&2
      return 1
      ;;
  esac
}

_vetcoders_launch_tracked_resume() {
  local tool="$1"
  local agent_session_id="$2"
  local prompt_text="$3"
  local model="${4:-}"
  local root_dir source_dir
  local -a core_args
  root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  source_dir="$(_vetcoders_core_source_dir)" || {
    echo "Tracked resume refused: Vibecrafted core is unavailable." >&2
    return 1
  }
  [[ -n "$prompt_text" ]] || {
    echo "Tracked resume requires explicit input or an AICX continuity pack." >&2
    return 1
  }

  if [[ -n "$agent_session_id" ]]; then
    core_args=(
      resume-session "$tool"
      --agent-session-id "$agent_session_id"
      --prompt-stdin
      --root "$root_dir"
      --source-dir "$source_dir"
    )
    [[ -n "$model" ]] && core_args+=(--model "$model")
    printf '%s' "$prompt_text" | _vetcoders_run_core_cli "${core_args[@]}"
    return $?
  fi

  core_args=(
    workflow "$tool"
    --prompt-stdin
    --runtime headless
    --root "$root_dir"
    --source-dir "$source_dir"
    --mode resume-new-session
  )
  [[ -n "$model" ]] && core_args+=(--model "$model")
  printf '%s' "$prompt_text" | _vetcoders_run_core_cli "${core_args[@]}"
}

_vetcoders_resume_agent() {
  local tool="$1"
  shift
  _vetcoders_parse_contract "$@" || return 1
  # --fork-session maps onto claude's verified `--resume … --fork-session`
  # compose (continuity capabilities kernel); other providers have no proven
  # equivalent, so anything else fails closed instead of dropping the flag.
  if [[ -n "${_vetcoders_contract_fork_session:-}" && "$tool" != claude ]]; then
    printf -- '--fork-session is only supported for claude resume (no verified equivalent for %s).\n' "$tool" >&2
    return 1
  fi
  # Positional form: `vc-resume <agent> <session_id> [prompt words...]`.
  # Without --session the shared parser routes positionals into tail/prompt.
  # Promote the first tail token only when it looks like a session id (not a
  # free-form prompt word).
  if [[ -z "$_vetcoders_contract_session" && -n "$_vetcoders_contract_tail" ]]; then
    local -a _resume_positional=()
    read -r -a _resume_positional <<<"$_vetcoders_contract_tail"
    local _maybe_session="${_resume_positional[0]:-}"
    # UUIDs / long hex / codex-style tokens; short words stay as prompt text.
    # A dash-leading token is never a session id — long flags like
    # --dangerously-skip-permissions would otherwise satisfy the length regex.
    if [[ "$_maybe_session" != -* ]] &&
      [[ "$_maybe_session" =~ ^[0-9a-fA-F-]{8,}$ || "$_maybe_session" =~ ^[0-9a-zA-Z_-]{16,}$ ]]; then
      _vetcoders_contract_session="$_maybe_session"
      local _resume_rest="${_vetcoders_contract_tail#"${_resume_positional[0]}"}"
      _resume_rest="${_resume_rest# }"
      if [[ "$_vetcoders_contract_prompt" == "$_vetcoders_contract_tail" ]]; then
        _vetcoders_contract_prompt="$_resume_rest"
      fi
      _vetcoders_contract_tail="$_resume_rest"
    fi
  fi

  # Preserve the operator's input intent before an internally-generated AICX
  # pack is attached as a file. Mode selection is based on this original
  # intent, never on the transport used for continuity context.
  local resume_explicit_input=""
  if {
    [[ -n "${_vetcoders_contract_prompt_explicit:-}" ]] ||
      [[ -n "${_vetcoders_contract_file_explicit:-}" ]] ||
      [[ -n "$_vetcoders_contract_prompt" ]] ||
      [[ -n "$_vetcoders_contract_file" ]]
  }; then
    resume_explicit_input=1
  fi

  local aicx_fallback_mode=""
  local aicx_context_file=""
  if [[ -z "$_vetcoders_contract_session" && -z "$resume_explicit_input" ]]; then
    # No session id: compose multi-agent continuity from AICX (48h default).
    local root_dir fallback_lines
    root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
    printf 'No --session: assembling AICX multi-agent continuity (last %sh)...\n' \
      "${VIBECRAFTED_RESUME_AICX_HOURS:-48}" >&2
    fallback_lines="$(_vetcoders_aicx_resume_fallback "$tool" "$root_dir")" || return 1
    local line key val
    while IFS= read -r line; do
      key="${line%%=*}"
      val="${line#*=}"
      case "$key" in
        SESSION_ID)
          # Bare Codex resume is continuity into a fresh interactive session.
          # A same-provider historical candidate is evidence, not a target.
          [[ "$tool" == codex ]] || _vetcoders_contract_session="$val"
          ;;
        CONTEXT_FILE) aicx_context_file="$val" ;;
        MODE) aicx_fallback_mode="$val" ;;
      esac
    done <<<"$fallback_lines"
    if [[ -n "$aicx_context_file" ]]; then
      # Continuity pack becomes the primary file input; operator --prompt stays.
      if [[ -n "$_vetcoders_contract_file" ]]; then
        _vetcoders_contract_prompt="$(
          printf '%s\n\nAlso see operator file: %s\n' \
            "${_vetcoders_contract_prompt:-}" \
            "$_vetcoders_contract_file"
        )"
      fi
      _vetcoders_contract_file="$aicx_context_file"
      printf '  context: %s\n' "$aicx_context_file" >&2
      if [[ -n "$_vetcoders_contract_session" ]]; then
        printf '  native resume candidate: %s\n' "$_vetcoders_contract_session" >&2
      else
        printf '  no same-agent session in window → NEW session with continuity pack\n' >&2
      fi
    fi
    [[ "$tool" != codex ]] || aicx_fallback_mode="new_session"
  fi

  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is only supported by vibecrafted marbles." >&2
    return 1
  }

  local resume_prompt
  local runtime
  local resume_cmd
  local resume_mode
  resume_prompt="$(_vetcoders_compose_input_context "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  # An explicit --prompt/--file means "continue the job", not "open me a TUI":
  # the resume must run the agent's NON-INTERACTIVE invocation even when a
  # visible operator tab hosts it, so it finishes, exits, and can be triaged.
  # Only a bare resume (no operator input) parks an interactive session in the
  # tab. An internal AICX file is continuity transport and does not count as
  # operator input for any provider.
  resume_mode="interactive"
  [[ -z "$resume_explicit_input" ]] || resume_mode="headless"
  if [[ "$resume_mode" == interactive && -z "$_vetcoders_contract_runtime" ]]; then
    # Worker dispatch defaults to headless, but a bare resume is deliberately
    # an operator TUI. Keep that path terminal-backed unless explicitly set.
    runtime="terminal"
  else
    runtime="$(_vetcoders_effective_runtime)"
  fi

  if [[ -n "$_vetcoders_contract_session" ]]; then
    resume_cmd="$(_vetcoders_resume_command "$tool" "$_vetcoders_contract_session" "$resume_prompt" "$resume_mode" "${_vetcoders_contract_fork_session:-}")" || return 1
  else
    # A fork needs a base session to branch from; a silent fresh session would
    # betray the operator's "keep the original untouched" intent.
    if [[ -n "${_vetcoders_contract_fork_session:-}" ]]; then
      echo "--fork-session needs a base session (--session <id> or an AICX same-agent candidate); none found." >&2
      return 1
    fi
    # NEW session: continuity pack only (explicitly not a native resume).
    resume_cmd="$(_vetcoders_fresh_session_command "$tool" "$resume_prompt" "$resume_mode")" || return 1
    aicx_fallback_mode="${aicx_fallback_mode:-new_session}"
  fi

  # CONTRACT (G7): non-interactive resume ALWAYS lands in the worker host
  # (right column), never the human operator seat. Interactive bare resume
  # stays on the operator surface. AgentStreamParser renders streaming-json
  # for grok so the worker pane is human-readable; raw stream is teed aside.
  local stream_raw=""

  if [[ "$resume_mode" == headless ]] && [[ "$runtime" =~ ^(terminal|visible)$ ]] && {
    _vetcoders_in_vc_frame ||
      [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]] ||
      [[ -n "${VIBECRAFTED_WORKER_SESSION:-}" ]] ||
      [[ -t 0 && -t 1 ]]
  }; then
    local worker_host
    worker_host="$(_vetcoders_effective_worker_session 2>/dev/null || true)"
    if [[ -n "$worker_host" ]]; then
      stream_raw="$(_vetcoders_resume_raw_transcript_path "$tool")"
      resume_cmd="$(
        _vetcoders_wrap_with_agent_stream "$tool" "$resume_cmd" "$stream_raw"
      )" || return 1
      export VIBECRAFTED_WORKER_SESSION="${VIBECRAFTED_WORKER_SESSION:-$worker_host}"
      _vetcoders_spawn_into_operator_session "resume-${tool}" "$resume_cmd" || return 1
      printf 'Resume launched in worker session: %s\n' "$VIBECRAFTED_WORKER_SESSION"
      printf '  agent:   %s\n' "$tool"
      printf '  mode:    headless (G7 workers column)\n'
      if [[ -n "$_vetcoders_contract_session" ]]; then
        printf '  session: %s\n' "$_vetcoders_contract_session"
      elif [[ -n "$resume_explicit_input" ]]; then
        printf '  session: (new — explicit non-interactive run)\n'
      else
        printf '  session: (new — aicx 48h multi-agent continuity)\n'
      fi
      [[ -n "$aicx_fallback_mode" ]] && printf '  aicx:    %s\n' "$aicx_fallback_mode"
      [[ -n "$aicx_context_file" ]] && printf '  pack:    %s\n' "$aicx_context_file"
      [[ -n "$stream_raw" && "$tool" == grok ]] && printf '  raw:     %s\n' "$stream_raw"
      return 0
    fi
  fi

  # Interactive resume — provider-neutral policy (adapters only change argv):
  #   bare resume → interactive → explicit or detected operator target
  #   prompt/file → tracked headless worker (handled above)
  # Prepare resolves: explicit env | in-frame | attached/current | repo-bound
  # live | single live. Multi-candidate ambiguity fails closed with a list.
  if [[ "$resume_mode" == interactive ]] && [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
      _vetcoders_spawn_into_operator_session "resume-${tool}" "$resume_cmd" || return 1
      printf 'Resume launched in operator session: %s\n' "$VIBECRAFTED_OPERATOR_SESSION"
      printf '  agent:   %s\n' "$tool"
      if [[ -n "$_vetcoders_contract_session" ]]; then
        printf '  session: %s\n' "$_vetcoders_contract_session"
      else
        printf '  session: (new — aicx 48h multi-agent continuity)\n'
      fi
      [[ -n "$aicx_fallback_mode" ]] && printf '  mode:    %s\n' "$aicx_fallback_mode"
      [[ -n "$aicx_context_file" ]] && printf '  pack:    %s\n' "$aicx_context_file"
      return 0
    fi
  fi

  if [[ "$resume_mode" == interactive ]]; then
    printf 'Interactive %s resume requires an explicit or detected operator target; refusing to downgrade to a headless run.\n' "$tool" >&2
    printf '  export VIBECRAFTED_OPERATOR_SESSION=<session>  # jawny target\n' >&2
    printf '  # or run from an attached vc-frame tab / leave exactly one live session\n' >&2
    local live_hint=""
    live_hint="$(_vetcoders_list_live_vc_frame_sessions 2>/dev/null | head -20 || true)"
    if [[ -n "$live_hint" ]]; then
      printf '  live vc-frame sessions:\n' >&2
      while IFS= read -r live_name; do
        [[ -n "$live_name" ]] || continue
        printf '    - %s\n' "$live_name" >&2
      done <<< "$live_hint"
    fi
    return 1
  fi

  # No vc-frame surface: core owns the detached lifetime, control-plane record,
  # transcript, and Guardian-visible process identity. There is deliberately no
  # raw nohup/setsid fallback when core cannot prove the launch contract.
  if [[ -n "${_vetcoders_contract_fork_session:-}" ]]; then
    # The tracked core path (resume-session / workflow launcher) has no fork
    # contract yet; dropping the flag here would silently mutate the original
    # session the operator asked to preserve.
    echo "--fork-session is not supported on the tracked core resume path yet; run inside vc-frame or use a bare (interactive) resume." >&2
    return 1
  fi
  _vetcoders_launch_tracked_resume \
    "$tool" \
    "$_vetcoders_contract_session" \
    "$resume_prompt"
}

_vetcoders_resume_command() {
  local tool="$1"
  local session_id="$2"
  local resume_prompt="${3:-}"
  # mode: "interactive" (resume into a visible operator pane) | "headless"
  # (direct eval / async-supervisor baton-pass — no tty). Per-agent resume flags
  # differ; the headless invocations were verified against each agent's --help.
  local mode="${4:-interactive}"
  # fork_session: non-empty branches the resume into a NEW provider session id,
  # leaving the base session untouched (claude-only; callers gate other agents).
  local fork_session="${5:-}"
  local quoted_session quoted_prompt
  quoted_session="$(_vetcoders_shell_quote "$session_id")"
  if [[ -n "$resume_prompt" ]]; then
    quoted_prompt="$(_vetcoders_shell_quote "$resume_prompt")"
  fi

  case "$tool" in
    claude)
      # headless resume needs --print (+ skip-permissions); plain --resume opens
      # an interactive session and would hang under eval with no tty.
      local claude_fork_flag=""
      [[ -z "$fork_session" ]] || claude_fork_flag=" --fork-session"
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'claude --print --dangerously-skip-permissions --resume %s%s %s\n' "$quoted_session" "$claude_fork_flag" "$quoted_prompt"
        else
          printf 'claude --print --dangerously-skip-permissions --resume %s%s\n' "$quoted_session" "$claude_fork_flag"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'claude --resume %s%s %s\n' "$quoted_session" "$claude_fork_flag" "$quoted_prompt"
      else
        printf 'claude --resume %s%s\n' "$quoted_session" "$claude_fork_flag"
      fi
      ;;
    codex)
      # headless = `codex exec resume` (non-interactive); `codex resume` is the
      # interactive picker and cannot run under a pipe.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'codex exec --dangerously-bypass-approvals-and-sandbox resume %s %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'codex exec --dangerously-bypass-approvals-and-sandbox resume %s\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'codex resume %s %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'codex resume %s\n' "$quoted_session"
      fi
      ;;
    gemini)
      # NOTE: gemini --resume takes an index or "latest", NOT a session UUID;
      # resuming a specific session by id is a known gap (use --session-file for
      # that). Best-effort: -p makes it headless.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'gemini --approval-mode yolo --resume %s -p %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'gemini --approval-mode yolo --resume %s -p ""\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'gemini --resume %s %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'gemini --resume %s\n' "$quoted_session"
      fi
      ;;
    agy)
      # agy resumes by --conversation <id>; headless needs --print <prompt>.
      # Since agy 1.1 --print takes the prompt as its VALUE (Go flags) and
      # print mode reads no stdin — flags first, prompt as the flag value.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'agy --dangerously-skip-permissions --conversation %s --print %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'agy --dangerously-skip-permissions --conversation %s --print "Continue."\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'agy --conversation %s --prompt-interactive %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'agy --conversation %s\n' "$quoted_session"
      fi
      ;;
    junie)
      # junie is non-interactive by construction (runs a task and exits); the
      # same command serves both modes.
      if [[ -n "$resume_prompt" ]]; then
        printf 'junie --session-id=%s --resume --task=%s --project=. --skip-update-check\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'junie --session-id=%s --resume --project=. --skip-update-check\n' "$quoted_session"
      fi
      ;;
    grok)
      # NEVER pass --restore-code: it checks out the original session's commit
      # and would clobber the working tree.
      # Interactive: --resume into TUI (optional seed prompt as positional).
      # Headless: --single + streaming-json for fleet/await transcript parse.
      if [[ "$mode" == headless ]]; then
        if [[ -n "$resume_prompt" ]]; then
          printf 'grok --resume %s --cwd . --permission-mode bypassPermissions --no-alt-screen --output-format streaming-json --single %s\n' "$quoted_session" "$quoted_prompt"
        else
          printf 'grok --resume %s --cwd . --permission-mode bypassPermissions --no-alt-screen --output-format streaming-json --single "Continue."\n' "$quoted_session"
        fi
      elif [[ -n "$resume_prompt" ]]; then
        printf 'grok --resume %s --cwd . --permission-mode bypassPermissions --no-alt-screen %s\n' "$quoted_session" "$quoted_prompt"
      else
        printf 'grok --resume %s --cwd . --permission-mode bypassPermissions --no-alt-screen\n' "$quoted_session"
      fi
      ;;
    *)
      echo "Unknown agent for resume: $tool" >&2
      return 1
      ;;
  esac
}

_vetcoders_agent_for_session() {
  local session_id="$1"
  [[ -n "$session_id" ]] || return 1
  python3 - "$session_id" "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/artifacts" <<'PY'
import json
import pathlib
import sys

session_id, artifacts_root = sys.argv[1:3]
root = pathlib.Path(artifacts_root)
if not root.is_dir():
    raise SystemExit(1)

matches = []
for meta_path in root.rglob("*.meta.json"):
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    if payload.get("session_id") != session_id:
        continue
    agent = payload.get("agent")
    if agent:
        try:
            mtime = meta_path.stat().st_mtime
        except OSError:
            mtime = 0
        matches.append((mtime, agent))

if not matches:
    raise SystemExit(1)
print(sorted(matches)[-1][1])
PY
}

# Real resume helper used by deck cmd_resume via _run_helper.
# NEVER `command vibecrafted resume` here — that re-enters Python lifecycle →
# deck → this function forever (fork bomb, 2026-07-28).
# Leading --help must not enter resume parsers (audit: accidental control runs).
vc-resume() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    command vibecrafted resume --help
    return $?
  fi
  local tool="${1:-}"
  [[ -n "$tool" ]] || {
    echo "Usage: vc-resume <claude|codex|agy|junie|grok> [<session_id>] [prompt ...] | --session <session_id> [--prompt <text>] [--file <path>]" >&2
    echo "  Without session_id: AICX multi-agent continuity pack (last ${VIBECRAFTED_RESUME_AICX_HOURS:-48}h) → native resume if a same-agent session is found, else NEW session." >&2
    return 1
  }
  if [[ "$tool" == "--session" ]]; then
    _vetcoders_parse_contract "$@" || return 1
    tool="$(_vetcoders_agent_for_session "$_vetcoders_contract_session")" || {
      echo "Could not infer agent for session: $_vetcoders_contract_session" >&2
      echo "Usage: vc-resume <claude|codex|agy|junie|grok> --session $_vetcoders_contract_session" >&2
      return 1
    }
  else
    shift || true
  fi
  _vetcoders_resume_agent "$tool" "$@"
}

codex-marbles() { _vetcoders_marbles codex "$@"; }
claude-marbles() { _vetcoders_marbles claude "$@"; }
gemini-marbles() { _vetcoders_marbles gemini "$@"; }
agy-marbles() { _vetcoders_marbles agy "$@"; }
junie-marbles() { _vetcoders_marbles junie "$@"; }
grok-marbles() { _vetcoders_marbles grok "$@"; }

# Marbles control subcommands
marbles-pause()   { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" pause "$@"; }
marbles-stop()    { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" stop "$@"; }
marbles-resume()  { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" resume "$@"; }
marbles-session() { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" session "$@"; }
marbles-inspect() { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" inspect "$@"; }
marbles-delete()  { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" delete "$@"; }
marbles-gc()      { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" gc "$@"; }
