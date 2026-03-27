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
require_symlink "$home_dir/.codex/skills/vc-agents"
require_symlink "$home_dir/.claude/skills/vc-agents"
require_symlink "$home_dir/.gemini/skills/vc-agents"
require_file "$home_dir/.codex/skills/vc-agents/scripts/codex_spawn.sh"
require_file "$home_dir/.claude/skills/vc-agents/scripts/claude_spawn.sh"
require_file "$home_dir/.gemini/skills/vc-agents/scripts/gemini_spawn.sh"
# Canonical + legacy helper locations
require_file "$config_dir/vetcoders/vc-skills.sh"
require_file "$config_dir/zsh/vc-skills.zsh"
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

require_file "$codex_report"
require_file "$claude_report"
require_file "$gemini_report"
assert_contains "$codex_report" 'Fake Codex Report'
assert_contains "$claude_report" 'Claude completed without writing a standalone report file.'
assert_contains "$gemini_report" 'fake gemini stdout'

log "helper bash smoke"
env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH" \
  bash -c 'source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"; command -v codex-implement >/dev/null && command -v claude-implement >/dev/null && command -v gemini-implement >/dev/null && command -v skills-sync >/dev/null && echo helper-ok' \
  | grep -Fq 'helper-ok' || die 'bash helper layer not loaded'

# If zsh is available, also smoke test zsh loading via legacy compat symlink
if command -v zsh >/dev/null 2>&1; then
  log "helper zsh smoke (bonus)"
  env HOME="$home_dir" XDG_CONFIG_HOME="$config_dir" PATH="$fake_bin:$PATH" \
    zsh -c 'source "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/vc-skills.zsh"; command -v codex-implement >/dev/null && command -v claude-implement >/dev/null && command -v gemini-implement >/dev/null && command -v skills-sync >/dev/null && echo helper-ok' \
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
echo "$sync_output" | grep -q "~/.vibecrafted/skills\|~/.agents/skills" || die "Sync dry-run didn't target the shared canonical skill store"

log "docs truth checks"
assert_not_contains "$repo_root/skills/vc-followup/SKILL.md" 'Use canonical Terminal spawn (`osascript`)'
assert_not_contains "$repo_root/skills/vc-workflow/SKILL.md" 'osascript preferred'
[[ ! -e "$repo_root/skills/vc-subagents/SKILL.md" ]] || die 'vc-subagents should not exist'
if [[ -e "$repo_root/docs/index.html" ]]; then
  assert_not_contains "$repo_root/docs/index.html" 'Canonical osascript Terminal spawn'
fi
[[ -e "$repo_root/skills/vc-suite-showcase.html" ]] && die 'vc-suite-showcase.html should not exist (was mv to docs/index.html)'

log "portable checks passed"
