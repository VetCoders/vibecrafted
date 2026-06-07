# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_init_runtime() {
  local runtime="${1:-terminal}"
  case "$runtime" in
    terminal|visible)
      printf '%s\n' "$runtime"
      ;;
    *)
      echo "vc-init is interactive-only: use --runtime terminal or visible." >&2
      return 1
      ;;
  esac
}

_vetcoders_compose_init_prompt() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local init_prompt="/vc-init"
  local extra

  extra="$(_vetcoders_compose_input_context "$prompt_text" "$file_path")" || return 1
  if [[ -n "$extra" ]]; then
    init_prompt+=$'\n\n'
    init_prompt+="$extra"
  fi

  printf '%s' "$init_prompt"
}

_vetcoders_init_command_text() {
  local tool="$1"
  local init_prompt="$2"
  local quoted_prompt
  quoted_prompt="$(_vetcoders_shell_quote "$init_prompt")"

  case "$tool" in
    claude)
      printf 'claude --verbose --dangerously-skip-permissions %s' "$quoted_prompt"
      ;;
    codex)
      printf 'codex --dangerously-bypass-approvals-and-sandbox %s' "$quoted_prompt"
      ;;
    gemini)
      printf 'gemini -y -i %s' "$quoted_prompt"
      ;;
    agy)
      printf 'agy --prompt-interactive --dangerously-skip-permissions --add-dir . %s' "$quoted_prompt"
      ;;
    junie)
      printf 'junie --task=%s --project=. --skip-update-check --use-local-cache' "$quoted_prompt"
      ;;
    grok)
      printf 'grok --cwd . --permission-mode bypassPermissions --no-alt-screen --single %s' "$quoted_prompt"
      ;;
    *)
      echo "Unsupported init agent: $tool" >&2
      return 1
      ;;
  esac
}

# Operator-mode launcher helpers — parallel to init helpers above.
# vc-operator is NOT a dispatchable Iter-3 worker mode; it is an
# interactive session entry point per the vc-init pattern. Invocation
# opens the operator's primary tab in zellij with the agent of choice
# preloaded with the /vc-operator skill prompt.

_vetcoders_operator_runtime() {
  local runtime="${1:-terminal}"
  case "$runtime" in
    terminal|visible)
      printf '%s\n' "$runtime"
      ;;
    *)
      echo "vc-operator is interactive-only: use --runtime terminal or visible." >&2
      return 1
      ;;
  esac
}

_vetcoders_compose_operator_prompt() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local operator_prompt="/vc-operator"
  local extra

  extra="$(_vetcoders_compose_input_context "$prompt_text" "$file_path")" || return 1
  if [[ -n "$extra" ]]; then
    operator_prompt+=$'\n\n'
    operator_prompt+="$extra"
  fi

  printf '%s' "$operator_prompt"
}

_vetcoders_operator_command_text() {
  local tool="$1"
  local operator_prompt="$2"
  local quoted_prompt
  quoted_prompt="$(_vetcoders_shell_quote "$operator_prompt")"

  case "$tool" in
    claude)
      printf 'claude --verbose --dangerously-skip-permissions %s' "$quoted_prompt"
      ;;
    codex)
      printf 'codex --dangerously-bypass-approvals-and-sandbox %s' "$quoted_prompt"
      ;;
    gemini)
      printf 'gemini -y -i %s' "$quoted_prompt"
      ;;
    agy)
      printf 'agy --prompt-interactive --dangerously-skip-permissions --add-dir . %s' "$quoted_prompt"
      ;;
    junie)
      printf 'junie --task=%s --project=. --skip-update-check --use-local-cache' "$quoted_prompt"
      ;;
    grok)
      printf 'grok --cwd . --permission-mode bypassPermissions --no-alt-screen --single %s' "$quoted_prompt"
      ;;
    *)
      echo "Unsupported operator agent: $tool" >&2
      return 1
      ;;
  esac
}

