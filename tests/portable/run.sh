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
  "$repo_root/vc-agents/scripts/install.sh" \
  "$repo_root/vc-agents/scripts/install-shell.sh" \
  "$repo_root/vc-agents/scripts/skills_sync.sh" \
  "$repo_root/vc-agents/scripts/observe.sh" \
  "$repo_root/vc-agents/scripts/common.sh" \
  "$repo_root/vc-agents/scripts/codex_spawn.sh" \
  "$repo_root/vc-agents/scripts/claude_spawn.sh" \
  "$repo_root/vc-agents/scripts/gemini_spawn.sh"
zsh -n "$repo_root/vc-agents/shell/vetcoders.zsh"

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
home_dir="$workspace/home"
config_dir="$home_dir/.config"
work_repo="$workspace/workrepo"
fake_bin="$workspace/fake-bin"
mkdir -p "$home_dir" "$config_dir" "$work_repo" "$fake_bin"

log "install smoke into clean HOME"
HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" \
  bash "$repo_root/vc-agents/scripts/install.sh" \
  --source "$repo_root" \
  --tool codex --tool claude --tool gemini \
  --with-shell

require_file "$home_dir/.agents/skills/vc-agents/scripts/codex_spawn.sh"
require_file "$home_dir/.agents/skills/vc-agents/scripts/claude_spawn.sh"
require_file "$home_dir/.agents/skills/vc-agents/scripts/gemini_spawn.sh"
require_symlink "$home_dir/.codex/skills/vc-agents"
require_symlink "$home_dir/.claude/skills/vc-agents"
require_symlink "$home_dir/.gemini/skills/vc-agents"
require_file "$home_dir/.codex/skills/vc-agents/scripts/codex_spawn.sh"
require_file "$home_dir/.claude/skills/vc-agents/scripts/claude_spawn.sh"
require_file "$home_dir/.gemini/skills/vc-agents/scripts/gemini_spawn.sh"
require_file "$config_dir/zsh/vc-skills.zsh"
require_file "$home_dir/.zshrc"
assert_contains "$home_dir/.zshrc" 'vc-skills.zsh'

log "prepare fake repo and fake agent CLIs"
git -C "$work_repo" init -q
mkdir -p "$work_repo/.ai-agents/plans"
cat > "$work_repo/.ai-agents/plans/test.md" <<'PLAN'
# Test plan
- Prove the portable spawn runtime can create artifacts.
PLAN

cat > "$fake_bin/codex" <<'EOF_CODEX'
#!/usr/bin/env bash
set -euo pipefail
report=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-last-message)
      shift
      report="$1"
      ;;
  esac
  shift || true
done
cat >/dev/null || true
echo 'fake codex stdout'
if [[ -n "$report" ]]; then
  printf '# Fake Codex Report\n\nspawn ok\n' > "$report"
fi
EOF_CODEX

cat > "$fake_bin/claude" <<'EOF_CLAUDE'
#!/usr/bin/env bash
set -euo pipefail
echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"fake claude stream"}]}}'
EOF_CLAUDE

cat > "$fake_bin/gemini" <<'EOF_GEMINI'
#!/usr/bin/env bash
set -euo pipefail
echo 'fake gemini stdout'
EOF_GEMINI

chmod +x "$fake_bin/codex" "$fake_bin/claude" "$fake_bin/gemini"

common_env=(HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH")

log "headless spawn smoke"
env "${common_env[@]}" bash "$home_dir/.codex/skills/vc-agents/scripts/codex_spawn.sh" --mode plan --runtime headless --root "$work_repo" "$work_repo/.ai-agents/plans/test.md"
env "${common_env[@]}" bash "$home_dir/.claude/skills/vc-agents/scripts/claude_spawn.sh" --mode review --runtime headless --root "$work_repo" "$work_repo/.ai-agents/plans/test.md"
env "${common_env[@]}" bash "$home_dir/.gemini/skills/vc-agents/scripts/gemini_spawn.sh" --mode implement --runtime headless --root "$work_repo" "$work_repo/.ai-agents/plans/test.md"

codex_meta="$(find "$work_repo/.ai-agents/reports" -maxdepth 1 -type f -name '*_codex.meta.json' | sort | tail -n 1)"
claude_meta="$(find "$work_repo/.ai-agents/reports" -maxdepth 1 -type f -name '*_claude.meta.json' | sort | tail -n 1)"
gemini_meta="$(find "$work_repo/.ai-agents/reports" -maxdepth 1 -type f -name '*_gemini.meta.json' | sort | tail -n 1)"

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

require_file "$codex_report"
require_file "$claude_report"
require_file "$gemini_report"
assert_contains "$codex_report" 'Fake Codex Report'
assert_contains "$claude_report" 'Claude completed without writing a standalone report file.'
assert_contains "$gemini_report" 'fake gemini stdout'

log "helper shell smoke"
env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH" zsh -ic 'source "$HOME/.zshrc" >/dev/null 2>&1; command -v codex-implement >/dev/null && command -v claude-implement >/dev/null && command -v gemini-implement >/dev/null && command -v skills-sync >/dev/null && echo helper-ok' | grep -Fq 'helper-ok' || die 'zsh helper layer not loaded'

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

sync_output="$(env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH" bash "$repo_root/vc-agents/scripts/skills_sync.sh" fakehost --source "$repo_root" --dry-run)"
echo "$sync_output" | grep -q "Syncing skills from" || die "Sync dry-run failed to start"
echo "$sync_output" | grep -q "rsync .* --dry-run" || die "Sync dry-run didn't pass dry-run to rsync"
echo "$sync_output" | grep -q "~/.agents/skills" || die "Sync dry-run didn't target the shared canonical skill store"

log "docs truth checks"
assert_not_contains "$repo_root/vc-followup/SKILL.md" 'Use canonical Terminal spawn (`osascript`)'
assert_not_contains "$repo_root/vc-workflow/SKILL.md" 'osascript preferred'
[[ ! -e "$repo_root/vc-subagents/SKILL.md" ]] || die 'vc-subagents should not exist'
assert_not_contains "$repo_root/docs/index.html" 'Canonical osascript Terminal spawn'
[[ -e "$repo_root/vc-suite-showcase.html" ]] && die 'vc-suite-showcase.html should not exist (was mv to docs/index.html)'

log "portable checks passed"
