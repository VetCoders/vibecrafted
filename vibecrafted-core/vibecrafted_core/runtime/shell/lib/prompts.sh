# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_prompt_file() {
  local agent="$1"
  shift
  if [[ $# -eq 0 ]]; then
    echo "Usage: ${agent}-prompt <prompt>" >&2
    return 1
  fi

  local root ts prompt_text slug prompt_file
  root="$(_vetcoders_repo_root)"
  ts="$(date +%Y%m%d_%H%M)"
  prompt_text="$*"
  slug="$(printf '%s' "$prompt_text" | tr '\n' ' ' | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48)"
  [[ -n "$slug" ]] || slug="adhoc-prompt"

  mkdir -p "$root/.vibecrafted/tmp"
  prompt_file="$root/.vibecrafted/tmp/${ts}_${slug}_${agent}_prompt.md"
  printf '%s\n' "$prompt_text" > "$prompt_file"
  printf '%s\n' "$prompt_file"
}

_vetcoders_contract_reset() {
  _vetcoders_contract_prompt=""
  _vetcoders_contract_prompt_explicit=""
  _vetcoders_contract_file=""
  _vetcoders_contract_file_explicit=""
  _vetcoders_contract_task=""
  _vetcoders_contract_session=""
  _vetcoders_contract_count=""
  _vetcoders_contract_depth=""
  _vetcoders_contract_runtime=""
  _vetcoders_contract_root=""
  _vetcoders_contract_tail=""
  _vetcoders_contract_dry_run=""
  _vetcoders_contract_no_aicx=""
  _vetcoders_contract_no_context_corpus=""
}

_vetcoders_append_tail() {
  local piece="${1:-}"
  [[ -n "$piece" ]] || return 0
  if [[ -n "$_vetcoders_contract_tail" ]]; then
    _vetcoders_contract_tail+=" "
  fi
  _vetcoders_contract_tail+="$piece"
}

_vetcoders_parse_contract() {
  _vetcoders_contract_reset
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -p|--prompt)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --prompt" >&2; return 1; }
        _vetcoders_contract_prompt_explicit=1
        # Greedy: everything after --prompt is the prompt text.
        # Flags must come BEFORE --prompt.
        _vetcoders_contract_prompt="$*"
        break
        ;;
      -f|--file)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --file" >&2; return 1; }
        _vetcoders_contract_file_explicit=1
        _vetcoders_contract_file="$1"
        ;;
      --task)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --task" >&2; return 1; }
        _vetcoders_contract_task="$1"
        ;;
      --no-aicx)
        _vetcoders_contract_no_aicx=1
        ;;
      --no-context-corpus)
        _vetcoders_contract_no_context_corpus=1
        ;;
      --dry-run)
        _vetcoders_contract_dry_run=1
        ;;
      --session)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --session" >&2; return 1; }
        _vetcoders_contract_session="$1"
        ;;
      --count)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --count" >&2; return 1; }
        _vetcoders_contract_count="$1"
        ;;
      --depth)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --depth" >&2; return 1; }
        _vetcoders_contract_depth="$1"
        ;;
      --runtime)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --runtime" >&2; return 1; }
        _vetcoders_contract_runtime="$1"
        ;;
      --root)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --root" >&2; return 1; }
        _vetcoders_contract_root="$1"
        ;;
      --)
        shift
        while [[ $# -gt 0 ]]; do
          _vetcoders_append_tail "$1"
          shift
        done
        break
        ;;
      *)
        _vetcoders_append_tail "$1"
        ;;
    esac
    shift
  done

  if [[ -z "$_vetcoders_contract_prompt" && -n "$_vetcoders_contract_tail" ]]; then
    _vetcoders_contract_prompt="$_vetcoders_contract_tail"
  fi
}

_vetcoders_effective_runtime() {
  if [[ -n "$_vetcoders_contract_runtime" ]]; then
    printf '%s\n' "$_vetcoders_contract_runtime"
  else
    _vetcoders_default_runtime
  fi
}

_vetcoders_require_positive_int() {
  local value="${1:-}"
  local flag_name="${2:-value}"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
    echo "${flag_name} must be a positive integer." >&2
    return 1
  }
}

_vetcoders_require_file() {
  local file_path="${1:-}"
  [[ -n "$file_path" ]] || {
    echo "Missing file path." >&2
    return 1
  }
  [[ -f "$file_path" ]] || {
    echo "Input file not found: $file_path" >&2
    return 1
  }
}

_vetcoders_compose_input_context() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local combined="$prompt_text"

  if [[ -n "$file_path" ]]; then
    _vetcoders_require_file "$file_path" || return 1
    local abs_file
    abs_file="$(cd "$(dirname "$file_path")" && pwd)/$(basename "$file_path")"
    local file_body
    file_body="$(cat "$file_path")"
    if [[ -n "$combined" ]]; then
      combined+=$'\n\n'
    fi
    combined+="Primary input file: $abs_file"
    combined+=$'\n\n```md\n'
    combined+="$file_body"
    combined+=$'\n```'
  fi

  printf '%s' "$combined"
}

_vetcoders_compose_skill_prompt() {
  local skill="$1"
  local prompt_text="${2:-}"
  local file_path="${3:-}"
  local base="Perform the vc-${skill} skill on this repository."
  local extra
  extra="$(_vetcoders_compose_input_context "$prompt_text" "$file_path")" || return 1
  if [[ -n "$extra" ]]; then
    base+=$'\n\n'
    base+="$extra"
  fi
  printf '%s\n' "$base"
}
