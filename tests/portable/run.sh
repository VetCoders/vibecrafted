#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log() {
  printf '[portable] %s\n' "$*"
}

die() {
  printf '[portable] FAIL: %s\n' "$*" >&2
  exit 1
}

require_file() {
  [[ -f "$1" ]] || die "Missing file: $1"
}

require_symlink() {
  [[ -L "$1" ]] || die "Missing symlink: $1"
}

wait_for_meta() {
  local meta_path="$1"
  local attempts="${2:-80}"
  local delay="${3:-0.25}"
  local status=""
  local i
  for ((i=0; i<attempts; i++)); do
    if [[ -f "$meta_path" ]]; then
      status="$(python3 - "$meta_path" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    payload = json.load(fh)
print(payload.get('status') or '')
PY
)"
      case "$status" in
        completed|failed)
          printf '%s\n' "$status"
          return 0
          ;;
      esac
    fi
    sleep "$delay"
  done
  die "Timed out waiting for $meta_path"
}

assert_contains() {
  local file="$1"
  local pattern="$2"
  grep -Fq "$pattern" "$file" || die "Expected '$pattern' in $file"
}

assert_matches() {
  local file="$1"
  local pattern="$2"
  grep -Eq "$pattern" "$file" || die "Expected regex '$pattern' in $file"
}

assert_not_contains() {
  local file="$1"
  local pattern="$2"
  [[ -f "$file" ]] || die "assert_not_contains: file not found: $file"
  if grep -Fq "$pattern" "$file"; then
    die "Did not expect '$pattern' in $file"
  fi
}

log "syntax checks"
bash -n \
  "$repo_root/install.sh" \
  "$repo_root/skills/vc-agents/scripts/install.sh" \
  "$repo_root/skills/vc-agents/scripts/install-shell.sh" \
  "$repo_root/skills/vc-agents/scripts/skills_sync.sh" \
  "$repo_root/skills/vc-agents/scripts/observe.sh" \
  "$repo_root/skills/vc-agents/scripts/common.sh" \
  "$repo_root/skills/vc-agents/scripts/codex_spawn.sh" \
  "$repo_root/skills/vc-agents/scripts/claude_spawn.sh" \
  "$repo_root/skills/vc-agents/scripts/gemini_spawn.sh"
# Shell helpers are bash-compatible; verify with bash -n
bash -n "$repo_root/skills/vc-agents/shell/vetcoders.sh"
# If zsh is available, also verify zsh syntax
if command -v zsh >/dev/null 2>&1; then
  zsh -n "$repo_root/skills/vc-agents/shell/vetcoders.sh"
fi

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
bootstrap_home="$workspace/bootstrap-home"
bootstrap_config_dir="$bootstrap_home/.config"
home_dir="$workspace/home"
config_dir="$home_dir/.config"
work_repo="$workspace/workrepo"
fake_bin="$workspace/fake-bin"
bootstrap_archive="$workspace/vibecrafted-bootstrap.tar.gz"
mkdir -p "$bootstrap_home" "$bootstrap_config_dir" "$home_dir" "$config_dir" "$work_repo" "$fake_bin"

log "bootstrap smoke via root install.sh"
tar -czf "$bootstrap_archive" \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='output' \
  --exclude='*.png' \
  -C "$repo_root" .
HOME="$bootstrap_home" XDG_CONFIG_HOME="$bootstrap_config_dir" VIBECRAFTED_HOME="$bootstrap_home/.vibecrafted" \
  bash "$repo_root/install.sh" --archive-file "$bootstrap_archive"

require_symlink "$bootstrap_home/.vibecrafted/tools/vibecrafted-current"
require_file "$bootstrap_home/.vibecrafted/tools/vibecrafted-current/Makefile"
require_file "$bootstrap_home/.vibecrafted/skills/vc-agents/scripts/codex_spawn.sh"
# Helper file lives at canonical location; legacy symlink also exists
require_file "$bootstrap_config_dir/vetcoders/vc-skills.sh"
require_file "$bootstrap_config_dir/zsh/vc-skills.zsh"

log "install smoke into clean HOME"
HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" \
  bash "$repo_root/skills/vc-agents/scripts/install.sh" \
  --source "$repo_root" \
  --tool codex --tool claude --tool gemini \
  --with-shell

require_file "$home_dir/.vibecrafted/skills/vc-agents/scripts/codex_spawn.sh"
require_file "$home_dir/.vibecrafted/skills/vc-agents/scripts/claude_spawn.sh"
require_file "$home_dir/.vibecrafted/skills/vc-agents/scripts/gemini_spawn.sh"
require_file "$home_dir/.vibecrafted/bin/vibecrafted"
require_symlink "$home_dir/.vibecrafted/bin/vc-help"
require_symlink "$home_dir/.vibecrafted/bin/vc-marbles"
require_symlink "$home_dir/.codex/skills/vc-agents"
require_symlink "$home_dir/.claude/skills/vc-agents"
require_symlink "$home_dir/.gemini/skills/vc-agents"
require_file "$home_dir/.codex/skills/vc-agents/scripts/codex_spawn.sh"
require_file "$home_dir/.claude/skills/vc-agents/scripts/claude_spawn.sh"
require_file "$home_dir/.gemini/skills/vc-agents/scripts/gemini_spawn.sh"
# Canonical + legacy helper locations
require_file "$config_dir/vetcoders/vc-skills.sh"
require_file "$config_dir/zsh/vc-skills.zsh"
assert_contains "$config_dir/vetcoders/vc-skills.sh" '𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. helper shim'
bad_helper_candidate="\${VIBECRAFTED_ROOT:-}/skills/vc-agents/shell/vetcoders.sh"
assert_not_contains "$config_dir/vetcoders/vc-skills.sh" "$bad_helper_candidate"
# At least one rcfile must have the source line (depends on SHELL/platform)
rc_found=0
for rcfile in "$home_dir/.zshrc" "$home_dir/.bashrc"; do
  [[ -f "$rcfile" ]] && grep -Fq 'vc-skills.sh' "$rcfile" && rc_found=1
done
(( rc_found )) || die "No rcfile sources vc-skills.sh"

log "prepare fake repo and fake agent CLIs"
git -C "$work_repo" init -q
mkdir -p "$work_repo/.vibecrafted/plans"
cat > "$work_repo/.vibecrafted/plans/test.md" <<'PLAN'
# Test plan
- Prove the portable spawn runtime can create artifacts.
PLAN

cat > "$fake_bin/codex" <<'EOF_CODEX'
#!/usr/bin/env bash
set -euo pipefail
report=""
json_mode=0
if [[ -n "${FAKE_CODEX_CAPTURE:-}" ]]; then
  printf "%s\n" "$@" > "$FAKE_CODEX_CAPTURE"
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-last-message)
      shift
      report="$1"
      ;;
    --json)
      json_mode=1
      ;;
  esac
  shift || true
done
cat >/dev/null || true
if (( json_mode )); then
  printf '{"type":"thread.started","thread_id":"fake-session-001"}\n'
  printf '{"type":"item.started","item":{"type":"command_execution","command":"ls"}}\n'
  printf '{"type":"item.completed","item":{"type":"command_execution","output":"alpha\\nbeta\\n"}}\n'
  printf '{"type":"turn.started"}\n'
  printf '{"type":"item.completed","item":{"type":"agent_message","text":"Fake Codex Report: spawn ok"}}\n'
  printf '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":10}}\n'
else
  echo 'fake codex stdout'
fi
if [[ -n "$report" ]]; then
  cat > "$report" <<EOF_REPORT
---
agent: codex
run_id: ${SPAWN_RUN_ID:-missing-run-id}
prompt_id: ${SPAWN_PROMPT_ID:-missing-prompt-id}
started_at: 2026-03-27T17:47:00Z
model: fake-codex
---

# Fake Codex Report

spawn ok
EOF_REPORT
fi
EOF_CODEX

cat > "$fake_bin/claude" <<'EOF_CLAUDE'
#!/usr/bin/env bash
set -euo pipefail
echo '{"type":"system","subtype":"init","session_id":"fake-claude-001"}'
echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Read"},{"type":"text","text":"fake claude stream"}]}}'
echo '{"type":"result","result":"done"}'
EOF_CLAUDE

cat > "$fake_bin/gemini" <<'EOF_GEMINI'
#!/usr/bin/env bash
set -euo pipefail
output_format="text"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output-format) shift; output_format="${1:-text}" ;;
  esac
  shift || true
done
if [[ "$output_format" == "stream-json" ]]; then
  printf '{"type":"init","session_id":"fake-gemini-001","model":"fake-model"}\n'
  printf '{"type":"tool_use","tool_name":"Read","tool_id":"read_1"}\n'
  printf '{"type":"tool_result","tool_id":"read_1","status":"success","output":"file content"}\n'
  printf '{"type":"message","role":"assistant","content":"fake gemini stdout","delta":true}\n'
  printf '{"type":"result","status":"success","stats":{"input_tokens":50,"output_tokens":5,"duration_ms":100,"tool_calls":1}}\n'
else
  echo 'fake gemini stdout'
fi
EOF_GEMINI

chmod +x "$fake_bin/codex" "$fake_bin/claude" "$fake_bin/gemini"

common_env=(HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH")

log "headless spawn smoke"
env "${common_env[@]}" bash "$home_dir/.codex/skills/vc-agents/scripts/codex_spawn.sh" --mode plan --runtime headless --root "$work_repo" "$work_repo/.vibecrafted/plans/test.md"
env "${common_env[@]}" bash "$home_dir/.claude/skills/vc-agents/scripts/claude_spawn.sh" --mode review --runtime headless --root "$work_repo" "$work_repo/.vibecrafted/plans/test.md"
env "${common_env[@]}" bash "$home_dir/.gemini/skills/vc-agents/scripts/gemini_spawn.sh" --mode implement --runtime headless --root "$work_repo" "$work_repo/.vibecrafted/plans/test.md"

codex_meta="$(find "$work_repo/.vibecrafted/reports" -maxdepth 1 -type f -name '*_codex.meta.json' | sort | tail -n 1)"
claude_meta="$(find "$work_repo/.vibecrafted/reports" -maxdepth 1 -type f -name '*_claude.meta.json' | sort | tail -n 1)"
gemini_meta="$(find "$work_repo/.vibecrafted/reports" -maxdepth 1 -type f -name '*_gemini.meta.json' | sort | tail -n 1)"

require_file "$codex_meta"
require_file "$claude_meta"
require_file "$gemini_meta"

[[ "$(wait_for_meta "$codex_meta")" == "completed" ]] || die "codex spawn did not complete"
[[ "$(wait_for_meta "$claude_meta")" == "completed" ]] || die "claude spawn did not complete"
[[ "$(wait_for_meta "$gemini_meta")" == "completed" ]] || die "gemini spawn did not complete"

codex_report="$(python3 - "$codex_meta" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    print(json.load(fh)['report'])
PY
)"
claude_report="$(python3 - "$claude_meta" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    print(json.load(fh)['report'])
PY
)"
gemini_report="$(python3 - "$gemini_meta" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    print(json.load(fh)['report'])
PY
)"
codex_transcript="$(python3 - "$codex_meta" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    print(json.load(fh)['transcript'])
PY
)"
claude_transcript="$(python3 - "$claude_meta" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    print(json.load(fh)['transcript'])
PY
)"
gemini_transcript="$(python3 - "$gemini_meta" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    print(json.load(fh)['transcript'])
PY
)"

require_file "$codex_report"
require_file "$claude_report"
require_file "$gemini_report"
require_file "$codex_transcript"
require_file "$claude_transcript"
require_file "$gemini_transcript"
assert_contains "$codex_report" 'Fake Codex Report'
assert_matches "$codex_report" 'run_id: plan-[0-9]{6}'
assert_contains "$codex_report" 'prompt_id: test_'
assert_contains "$claude_report" 'Claude completed without writing a standalone report file.'
assert_contains "$gemini_report" 'fake gemini'
assert_matches "$codex_transcript" '\[[0-9]{2}:[0-9]{2}:[0-9]{2} \$ ls\]'
assert_matches "$codex_transcript" '\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] tokens: 100 in / 10 out'
assert_matches "$claude_transcript" '\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] session: fake-claude-001'
assert_matches "$claude_transcript" '\[[0-9]{2}:[0-9]{2}:[0-9]{2} Read\]'
assert_matches "$gemini_transcript" '\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] session: fake-gemini-001'
assert_matches "$gemini_transcript" '\[[0-9]{2}:[0-9]{2}:[0-9]{2} Read\]'

jq -e '.prompt_id != null and (.prompt_id | startswith("test_"))' "$codex_meta" >/dev/null || die "codex meta missing prompt_id"
jq -e '.run_id | test("^plan-[0-9]{6}$")' "$codex_meta" >/dev/null || die "codex meta missing plan run_id"
jq -e '.run_id | test("^rvew-[0-9]{6}$")' "$claude_meta" >/dev/null || die "claude meta missing review run_id"
jq -e '.run_id | test("^impl-[0-9]{6}$")' "$gemini_meta" >/dev/null || die "gemini meta missing implement run_id"
jq -e '.loop_nr == 0' "$codex_meta" >/dev/null || die "codex meta missing loop_nr"
jq -e '.framework_version != null and .framework_version != ""' "$codex_meta" >/dev/null || die "codex meta missing framework_version"
jq -e '.completed_at != null and .duration_s != null' "$codex_meta" >/dev/null || die "codex meta missing completion telemetry"

log "launcher resume smoke"
resume_capture="$workspace/resume-codex.txt"
env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH" FAKE_CODEX_CAPTURE="$resume_capture" \
  "$home_dir/.vibecrafted/bin/vibecrafted" resume codex --session fake-session-001 --prompt "resume smoke"
require_file "$resume_capture"
assert_contains "$resume_capture" 'resume'
assert_contains "$resume_capture" 'fake-session-001'
assert_contains "$resume_capture" 'resume smoke'

log "helper bash smoke"
# shellcheck disable=SC2016
env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$home_dir/.vibecrafted/bin:$fake_bin:$PATH" \
  bash -c 'source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"; command -v codex-implement >/dev/null && command -v claude-implement >/dev/null && command -v gemini-implement >/dev/null && command -v vc-marbles >/dev/null && command -v skills-sync >/dev/null && echo helper-ok' \
  | grep -Fq 'helper-ok' || die 'bash helper layer not loaded'
log "skill helper telemetry smoke"
# shellcheck disable=SC2016
skill_output="$(
  env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH" VETCODERS_SPAWN_RUNTIME=headless \
    bash -c 'cd "$1"; source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"; codex-marbles --prompt "telemetry smoke" --count 1' _ "$work_repo"
)"
skill_report="$(printf '%s\n' "$skill_output" | sed -n 's/^Agent launched\. Report will land at: //p' | tail -n 1)"
[[ -n "$skill_report" ]] || die "skill helper did not report output path"
skill_meta="${skill_report%.md}.meta.json"
require_file "$skill_meta"
[[ "$(wait_for_meta "$skill_meta")" == "completed" ]] || die "skill helper spawn did not complete"
jq -e '.skill_code == "marb"' "$skill_meta" >/dev/null || die "skill helper did not wire skill_code"
jq -e '.run_id | startswith("marb-")' "$skill_meta" >/dev/null || die "skill helper did not wire run_id"

# If zsh is available, also smoke test zsh loading via legacy compat symlink
if command -v zsh >/dev/null 2>&1; then
  log "helper zsh smoke (bonus)"
  # shellcheck disable=SC2016
  env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$home_dir/.vibecrafted/bin:$fake_bin:$PATH" \
    zsh -c 'source "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh"; command -v codex-implement >/dev/null && command -v claude-implement >/dev/null && command -v gemini-implement >/dev/null && command -v vc-marbles >/dev/null && command -v skills-sync >/dev/null && echo helper-ok' \
    | grep -Fq 'helper-ok' || die 'zsh helper layer not loaded'
fi

log "sync dry-run smoke"
cat > "$fake_bin/ssh" <<'EOF_SSH'
#!/usr/bin/env bash
# mock ssh just echoes the command
shift
echo "$@"
EOF_SSH
chmod +x "$fake_bin/ssh"

cat > "$fake_bin/rsync" <<'EOF_RSYNC'
#!/usr/bin/env bash
# mock rsync just echoes args
echo rsync "$@"
EOF_RSYNC
chmod +x "$fake_bin/rsync"

sync_output="$(env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH" bash "$repo_root/skills/vc-agents/scripts/skills_sync.sh" fakehost --source "$repo_root" --dry-run)"
echo "$sync_output" | grep -q "Syncing skills from" || die "Sync dry-run failed to start"
echo "$sync_output" | grep -q "rsync .* --dry-run" || die "Sync dry-run didn't pass dry-run to rsync"
# shellcheck disable=SC2016 # matching literal $HOME in sync output, not expanding
echo "$sync_output" | grep -q '\$HOME/.vibecrafted/skills\|\$HOME/.agents/skills' || die "Sync dry-run didn't target the shared canonical skill store"

log "docs truth checks"
# shellcheck disable=SC2016 # backticks are literal content we're matching, not command substitution
assert_not_contains "$repo_root/skills/vc-followup/SKILL.md" 'Use canonical Terminal spawn (`osascript`)'
assert_not_contains "$repo_root/skills/vc-workflow/SKILL.md" 'osascript preferred'
assert_not_contains "$repo_root/docs/FRONTIER.md" 'vetcoders.zsh'
assert_not_contains "$repo_root/docs/FAQ-ANSWERED.md" 'truth as of March 2026'
[[ ! -e "$repo_root/skills/vc-subagents/SKILL.md" ]] || die 'vc-subagents should not exist'
if [[ -e "$repo_root/docs/index.html" ]]; then
  assert_not_contains "$repo_root/docs/index.html" 'Canonical osascript Terminal spawn'
  assert_contains "$repo_root/docs/index.html" 'vibecrafted init claude'
  assert_contains "$repo_root/docs/index.html" 'vibecrafted workflow claude --prompt "Plan and implement auth module"'
  assert_contains "$repo_root/docs/index.html" 'vibecrafted marbles codex --count 3 --depth 3'
  assert_not_contains "$repo_root/docs/index.html" 'vc-init claude'
fi
assert_contains "$repo_root/docs/QUICK_START.md" 'vibecrafted init claude'
assert_contains "$repo_root/docs/QUICK_START.md" 'vibecrafted justdo codex --prompt "Add user authentication with JWT"'
assert_contains "$repo_root/docs/presence/quickstart.html" 'vibecrafted init claude'
assert_contains "$repo_root/docs/presence/quickstart.html" 'vibecrafted workflow claude --prompt "Plan and implement auth module"'
assert_not_contains "$repo_root/docs/presence/quickstart.html" 'vc-init claude'
[[ -e "$repo_root/skills/vc-suite-showcase.html" ]] && die 'vc-suite-showcase.html should not exist (was mv to docs/index.html)'

log "portable checks passed"
log "portable checks passed"
