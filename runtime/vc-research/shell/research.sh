# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_research_launcher_path() {
  local tool="$1"
  local prompt_file="$2"
  local root="$3"
  local run_id="$4"
  local run_lock="$5"
  local runtime="$6"
  local run_dir="$7"
  local script output launcher

  script="$(_vetcoders_spawn_script "$tool" "${tool}_spawn.sh")" || return 1
  output="$(
    env \
      VIBECRAFTED_RUN_ID="$run_id" \
      VIBECRAFTED_RUN_LOCK="$run_lock" \
      VIBECRAFTED_SKILL_CODE="rsch" \
      VIBECRAFTED_SKILL_NAME="research" \
      VIBECRAFTED_RESEARCH_MODE="1" \
      VIBECRAFTED_STORE_DIR="$run_dir" \
      VIBECRAFTED_STORE_ROOT="$root" \
      VIBECRAFTED_RESEARCH_RUN_DIR="$run_dir" \
      bash "$script" --dry-run --mode research --runtime "$runtime" --root "$root" "$prompt_file" 2>&1
  )" || {
    printf '%s\n' "$output" >&2
    return 1
  }

  launcher="$(printf '%s\n' "$output" | awk -F': ' '/Dry run mode: launcher generated only:/ {print $NF}' | tail -1)"
  [[ -n "$launcher" && -f "$launcher" ]] || {
    printf 'Could not resolve %s research launcher.\n' "$tool" >&2
    printf '%s\n' "$output" >&2
    return 1
  }
  printf '%s\n' "$launcher"
}

_vetcoders_runtime_manifest_path() {
  local candidate
  for candidate in \
    "${VIBECRAFTED_ROOT:-}" \
    "$(_vetcoders_repo_root)" \
    "${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}/vibecrafted-current"
  do
    [[ -n "$candidate" && -f "$candidate/install.toml" ]] || continue
    printf '%s/install.toml\n' "$candidate"
    return 0
  done
  return 1
}

_vetcoders_user_config_path() {
  local config_home config_path
  config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
  config_path="$config_home/vibecrafted/config.toml"
  [[ -f "$config_path" ]] || return 1
  printf '%s\n' "$config_path"
}

_vetcoders_research_config_paths() {
  local config_path manifest

  config_path="$(_vetcoders_user_config_path 2>/dev/null || true)"
  [[ -n "$config_path" ]] && printf '%s\n' "$config_path"

  manifest="$(_vetcoders_runtime_manifest_path 2>/dev/null || true)"
  [[ -n "$manifest" ]] && printf '%s\n' "$manifest"
}

_vetcoders_python311_bin() {
  local candidate bin
  for candidate in \
    "${VIBECRAFTED_PYTHON:-}" \
    python3.14 \
    python3.13 \
    python3.12 \
    python3.11 \
    python3
  do
    [[ -n "$candidate" ]] || continue
    bin="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$bin" ]] || continue
    "$bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1 || continue
    printf '%s\n' "$bin"
    return 0
  done

  printf 'Vibecrafted requires Python >=3.11 on PATH; Python 3.10/3.9 launchers are unsupported because runtime TOML parsing uses tomllib.\n' >&2
  return 1
}

_vetcoders_research_agents_from_config() {
  local config_path="$1"
  local python_bin output parse_status

  python_bin="$(_vetcoders_python311_bin)" || return 2

  output="$("$python_bin" -c '
import sys
import tomllib

path = sys.argv[1]
with open(path, "rb") as handle:
    data = tomllib.load(handle)

agents = (
    data.get("runtime", {})
    .get("picking", {})
    .get("research", {})
    .get("default_agents", [])
)

printed = False
for agent in agents:
    if isinstance(agent, str) and agent.strip():
        print(agent.strip())
        printed = True

sys.exit(0 if printed else 3)
' "$config_path")"
  parse_status=$?
  if (( parse_status == 0 )); then
    printf '%s\n' "$output"
    return 0
  fi
  if (( parse_status == 3 )); then
    return 1
  fi
  printf 'Failed to read research agent config: %s\n' "$config_path" >&2
  return "$parse_status"
}

_vetcoders_research_agents() {
  local config_path
  local parse_status

  if [[ -n "${VIBECRAFTED_RESEARCH_AGENTS:-}" ]]; then
    printf '%s\n' "${VIBECRAFTED_RESEARCH_AGENTS}" | tr ', ' '\n' | awk 'NF'
    return 0
  fi

  while IFS= read -r config_path; do
    [[ -n "$config_path" ]] || continue
    _vetcoders_research_agents_from_config "$config_path" && return 0
    parse_status=$?
    if (( parse_status != 1 )); then
      return "$parse_status"
    fi
  done < <(_vetcoders_research_config_paths)

  printf '%s\n' claude codex gemini
}

_vetcoders_write_research_layout() {
  local layout_file="$1"
  shift
  local entry agent script

  cat > "$layout_file" <<EOF
layout {
    default_tab_template {
        pane size=1 borderless=true {
            plugin location="compact-bar"
        }
        children
        pane size=1 borderless=true {
            plugin location="status-bar"
        }
    }

    tab name="𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Research" {
        pane split_direction="vertical" {
            pane name="synthesis" size="55%" focus=true command="zsh"
            pane split_direction="horizontal" size="45%" {
EOF

  for entry in "$@"; do
    agent="${entry%%=*}"
    script="${entry#*=}"
    [[ -n "$agent" && "$agent" != "$entry" ]] || continue
    cat >> "$layout_file" <<EOF
                pane name="$agent" command="bash" {
                    args "$script"
                }
EOF
  done

  cat >> "$layout_file" <<EOF
            }
        }
    }
}
EOF
}

_vetcoders_research_session_ready() {
  # Non-blocking session discovery for research. The general
  # _vetcoders_prepare_operator_runtime may run a BLOCKING zellij client
  # (attach / --new-session-with-layout) inside the calling terminal — the
  # operator's shell gets swallowed and the research flow freezes until the
  # client exits. Research only ever needs an EXISTING live session to hang
  # its tab on; when none exists we degrade to headless instead.
  _vetcoders_zellij_bin >/dev/null 2>&1 || return 1
  if _vetcoders_in_zellij; then
    VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_zellij_session_name)"
    export VIBECRAFTED_OPERATOR_SESSION
    return 0
  fi
  if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]] \
    && [[ "$(_vetcoders_zellij_session_state "$VIBECRAFTED_OPERATOR_SESSION")" == "live" ]]; then
    return 0
  fi
  local guessed_session
  guessed_session="$(_vetcoders_guess_active_zellij_session 2>/dev/null || true)"
  if [[ -n "$guessed_session" ]]; then
    export VIBECRAFTED_OPERATOR_SESSION="$guessed_session"
    return 0
  fi
  return 1
}

_vetcoders_research_help() {
  cat <<'HELP'
⚒  research
─────────────────────────────────────────
Configurable triple-agent research swarm launcher.

Usage:
  vc-research --prompt "Question to research"
  vc-research --file /path/to/plan.md
  vc-research uno <claude|codex|gemini|agy|junie|grok> --prompt "Question to research"
  vc-research uno <claude|codex|gemini|agy|junie|grok> --file /path/to/plan.md

Common flags:
  -p, --prompt <text>            Inline prompt
  -f, --file <path.md>           Input file as prompt context
  --runtime <runtime>             Runtime backend (terminal|headless|visible)
  --root <path>                   Root workspace for this research run

Examples:
  vc-research --prompt "Compare API alternatives for oauth libraries"
  vc-research uno codex --prompt "Probe just one research lane"
  vc-research --file /path/to/research-plan.md
  vibecrafted research --prompt "State of the art for MCP streaming"

Do not pass an agent directly to vc-research.
Use `vc-research uno <agent> ...` if you intentionally need single-agent mode.
HELP
}

_vetcoders_research() {
  local first_arg="${1:-}"
  local inherited_run_id inherited_run_lock
  local prompt root run_id run_lock runtime run_dir prompt_file layout_file summary_file
  local session_name agent launcher cmd_file research_mode requested_research_agent lock_actor launch_label
  local -a research_agents launchers launcher_entries command_entries

  for _arg in "$@"; do
    case "$_arg" in
      help|-h|--help)
        _vetcoders_research_help
        return 0
        ;;
    esac
  done

  research_mode="swarm"
  requested_research_agent=""
  if [[ "$first_arg" == "uno" ]]; then
    shift || true
    requested_research_agent="${1:-}"
    _vetcoders_has_agent "$requested_research_agent" || {
      printf 'vc-research uno expects <claude|codex|gemini|agy|junie|grok> as the next argument.\n' >&2
      printf 'Usage: vc-research uno <agent> --prompt "..." or --file /path/to/plan.md.\n' >&2
      return 1
    }
    shift || true
    research_mode="uno"
    first_arg="${1:-}"
  fi

  case "$first_arg" in
    claude|codex|gemini|agy|junie|grok)
    printf 'vc-research is a triple-agent swarm launcher. Do not pass %s.\n' "$first_arg" >&2
    printf 'Use vc-research --prompt "..." or vc-research --file /path/to/plan.md.\n' >&2
    printf 'If you intentionally want one researcher, use vc-research uno %s --prompt "...".\n' "$first_arg" >&2
    return 1
      ;;
  esac

  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is only supported by vibecrafted resume." >&2
    return 1
  }
  [[ -n "$_vetcoders_contract_prompt" || -n "$_vetcoders_contract_file" ]] || {
    echo "vc-research requires --prompt or --file." >&2
    return 1
  }

  prompt="$(_vetcoders_compose_research_worker_prompt "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  root="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  runtime="$(_vetcoders_effective_runtime)"

  if [[ "$runtime" =~ ^(terminal|visible)$ ]] && ! _vetcoders_research_session_ready; then
    printf 'vc-research: no live zellij operator session to attach the research tab to.\n' >&2
    printf 'Degrading to headless so your terminal stays yours (start one with vc-start for the shared tab).\n' >&2
    runtime="headless"
  fi

  inherited_run_id="$(_vetcoders_effective_run_id 2>/dev/null || true)"
  inherited_run_lock="$(_vetcoders_effective_run_lock 2>/dev/null || true)"
  run_id="$inherited_run_id"
  [[ -n "$run_id" ]] || run_id="$(_vetcoders_generate_run_id "rsch")"
  run_lock="$inherited_run_lock"
  if [[ -z "$run_lock" || ! -f "$run_lock" ]]; then
    lock_actor="swarm"
    [[ "$research_mode" == "uno" ]] && lock_actor="$requested_research_agent"
    run_lock="$(_vetcoders_create_run_lock "$run_id" "$lock_actor" "research" "$root")" || return 1
  fi

  run_dir="$(_vetcoders_research_run_dir "$root" "$run_id")"
  mkdir -p "$run_dir/plans" "$run_dir/reports" "$run_dir/logs" "$run_dir/tmp"
  prompt_file="$(_vetcoders_research_prompt_file "$run_dir" "$prompt")" || return 1

  research_agents=()
  if [[ "$research_mode" == "uno" ]]; then
    research_agents=("$requested_research_agent")
  else
    local agents_output
    agents_output="$(_vetcoders_research_agents)" || return 1
    while IFS= read -r agent; do
      case "$agent" in
        claude|codex|gemini|agy|junie|grok) research_agents+=("$agent") ;;
        "") ;;
        *) printf 'Ignoring unsupported research agent from runtime picking config: %s\n' "$agent" >&2 ;;
      esac
    done <<< "$agents_output"
    if (( ${#research_agents[@]} == 0 )); then
      printf 'vc-research: no supported research agents configured.\n' >&2
      return 1
    fi
  fi

  launchers=()
  launcher_entries=()
  for agent in "${research_agents[@]}"; do
    launcher="$(_vetcoders_research_launcher_path "$agent" "$prompt_file" "$root" "$run_id" "$run_lock" "$runtime" "$run_dir")" || return 1
    launchers+=("$launcher")
    launcher_entries+=("$agent=$launcher")
  done

  summary_file="$(_vetcoders_write_research_summary "$run_dir" "$run_id" "$root" "$prompt_file" "${launcher_entries[@]}")" || return 1

  if [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    # Session readiness was proven non-blockingly above; never call the
    # blocking operator-runtime preparer from the research dispatch path.
    local zellij_bin=""
    zellij_bin="$(_vetcoders_zellij_bin)" || return 1
    session_name="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
    [[ -n "$session_name" ]] || {
      echo "Could not determine the operator zellij session." >&2
      return 1
    }

    layout_file="$run_dir/tmp/research.kdl"

    command_entries=()
    for entry in "${launcher_entries[@]}"; do
      agent="${entry%%=*}"
      launcher="${entry#*=}"
      cmd_file="$run_dir/tmp/${agent}_cmd.sh"
      _vetcoders_write_command_script "$cmd_file" "bash $(_vetcoders_shell_quote "$launcher")" || return 1
      command_entries+=("$agent=$cmd_file")
    done
    _vetcoders_write_research_layout "$layout_file" "${command_entries[@]}"

    # Intended exports to env for the zellij child process — false-positive SC2031.
    # shellcheck disable=SC2031
    export VIBECRAFTED_RUN_ID="$run_id"
    # shellcheck disable=SC2031
    export VIBECRAFTED_RUN_LOCK="$run_lock"
    # shellcheck disable=SC2031
    export VIBECRAFTED_SKILL_CODE="rsch"
    # shellcheck disable=SC2031
    export VIBECRAFTED_SKILL_NAME="research"
    # shellcheck disable=SC2031
    export VIBECRAFTED_RESEARCH_MODE="1"
    # shellcheck disable=SC2031
    export VIBECRAFTED_STORE_DIR="$run_dir"
    # shellcheck disable=SC2031
    export VIBECRAFTED_STORE_ROOT="$root"
    # shellcheck disable=SC2031
    export VIBECRAFTED_RESEARCH_RUN_DIR="$run_dir"
    "$zellij_bin" --session "$session_name" action new-tab --layout "$layout_file" >/dev/null
    launch_label="Research swarm"
    [[ "$research_mode" == "uno" ]] && launch_label="Research uno ($requested_research_agent)"
    printf '%s launched in shared tab (run_id=%s).\n' "$launch_label" "$run_id"
    printf '  run dir: %s\n' "$run_dir"
    printf '  reports: %s\n' "$run_dir/reports"
    printf '  summary: %s\n' "$summary_file"
    _vetcoders_await "" --describe "${launchers[@]}" || true
    printf '\nAwait:\n\n'
    printf 'vc-research-await --run-id %s\n' "$run_id"
    return 0
  fi

  launch_label="Research swarm"
  [[ "$research_mode" == "uno" ]] && launch_label="Research uno ($requested_research_agent)"
  printf '%s prepared (run_id=%s), but runtime %s does not use the shared zellij layout.\n' "$launch_label" "$run_id" "$runtime"
  printf 'Run directory: %s\n' "$run_dir"
  printf 'Reports: %s\n' "$run_dir/reports"
  printf 'Summary: %s\n' "$summary_file"
  printf 'Launchers:\n'
  for entry in "${launcher_entries[@]}"; do
    agent="${entry%%=*}"
    launcher="${entry#*=}"
    printf '  %s: %s\n' "$agent" "$launcher"
  done
  printf '\nAwait:\n\n'
  printf 'vc-research-await --run-id %s\n' "$run_id"
}
