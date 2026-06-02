# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_research_file_body() {
  local file_path="$1"

  python3 - "$file_path" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

if lines and lines[0].strip() == "---":
    body_start = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = idx + 1
            break
    if body_start is not None:
        text = "".join(lines[body_start:]).lstrip("\n")

print(text, end="")
PY
}

_vetcoders_compose_research_worker_prompt() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local combined="$prompt_text"

  if [[ -n "$file_path" ]]; then
    _vetcoders_require_file "$file_path" || return 1
    local abs_file
    abs_file="$(cd "$(dirname "$file_path")" && pwd)/$(basename "$file_path")"
    local file_body
    file_body="$(_vetcoders_research_file_body "$file_path")" || return 1
    if [[ -n "$combined" ]]; then
      combined+=$'\n\n'
    fi
    combined+="Research plan file: $abs_file"
    combined+=$'\n\n'
    combined+="$file_body"
  fi

  printf '%s\n' "$combined"
}

