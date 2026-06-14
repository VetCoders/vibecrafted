# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

codex-decorate() { _vetcoders_skill codex decorate "$@"; }
claude-decorate() { _vetcoders_skill claude decorate "$@"; }
gemini-decorate() { _vetcoders_skill gemini decorate "$@"; }
agy-decorate() { _vetcoders_skill agy decorate "$@"; }
junie-decorate() { _vetcoders_skill junie decorate "$@"; }
grok-decorate() { _vetcoders_skill grok decorate "$@"; }

codex-followup() { _vetcoders_skill codex followup "$@"; }
claude-followup() { _vetcoders_skill claude followup "$@"; }
gemini-followup() { _vetcoders_skill gemini followup "$@"; }
agy-followup() { _vetcoders_skill agy followup "$@"; }
junie-followup() { _vetcoders_skill junie followup "$@"; }
grok-followup() { _vetcoders_skill grok followup "$@"; }

codex-prune() { _vetcoders_skill codex prune "$@"; }
claude-prune() { _vetcoders_skill claude prune "$@"; }
gemini-prune() { _vetcoders_skill gemini prune "$@"; }
agy-prune() { _vetcoders_skill agy prune "$@"; }
junie-prune() { _vetcoders_skill junie prune "$@"; }
grok-prune() { _vetcoders_skill grok prune "$@"; }

codex-scaffold() { _vetcoders_skill codex scaffold "$@"; }
claude-scaffold() { _vetcoders_skill claude scaffold "$@"; }
gemini-scaffold() { _vetcoders_skill gemini scaffold "$@"; }
agy-scaffold() { _vetcoders_skill agy scaffold "$@"; }
junie-scaffold() { _vetcoders_skill junie scaffold "$@"; }
grok-scaffold() { _vetcoders_skill grok scaffold "$@"; }

codex-release() { _vetcoders_skill codex release "$@"; }
claude-release() { _vetcoders_skill claude release "$@"; }
gemini-release() { _vetcoders_skill gemini release "$@"; }
agy-release() { _vetcoders_skill agy release "$@"; }
junie-release() { _vetcoders_skill junie release "$@"; }
grok-release() { _vetcoders_skill grok release "$@"; }

codex-justdo() { _vetcoders_skill codex justdo "$@"; }
claude-justdo() { _vetcoders_skill claude justdo "$@"; }
gemini-justdo() { _vetcoders_skill gemini justdo "$@"; }
agy-justdo() { _vetcoders_skill agy justdo "$@"; }
junie-justdo() { _vetcoders_skill junie justdo "$@"; }
grok-justdo() { _vetcoders_skill grok justdo "$@"; }

codex-partner() { _vetcoders_skill codex partner "$@"; }
claude-partner() { _vetcoders_skill claude partner "$@"; }
gemini-partner() { _vetcoders_skill gemini partner "$@"; }
agy-partner() { _vetcoders_skill agy partner "$@"; }
junie-partner() { _vetcoders_skill junie partner "$@"; }
grok-partner() { _vetcoders_skill grok partner "$@"; }

codex-skill-agents() { _vetcoders_skill_entry codex agents "$@"; }
claude-skill-agents() { _vetcoders_skill_entry claude agents "$@"; }
gemini-skill-agents() { _vetcoders_skill_entry gemini agents "$@"; }

codex-skill-audit() { _vetcoders_skill_entry codex audit "$@"; }
claude-skill-audit() { _vetcoders_skill_entry claude audit "$@"; }
gemini-skill-audit() { _vetcoders_skill_entry gemini audit "$@"; }

codex-skill-decorate() { _vetcoders_skill_entry codex decorate "$@"; }
claude-skill-decorate() { _vetcoders_skill_entry claude decorate "$@"; }
gemini-skill-decorate() { _vetcoders_skill_entry gemini decorate "$@"; }

codex-skill-delegate() { _vetcoders_skill_entry codex delegate "$@"; }
claude-skill-delegate() { _vetcoders_skill_entry claude delegate "$@"; }
gemini-skill-delegate() { _vetcoders_skill_entry gemini delegate "$@"; }

codex-skill-dou() { _vetcoders_skill_entry codex dou "$@"; }
claude-skill-dou() { _vetcoders_skill_entry claude dou "$@"; }
gemini-skill-dou() { _vetcoders_skill_entry gemini dou "$@"; }

codex-skill-followup() { _vetcoders_skill_entry codex followup "$@"; }
claude-skill-followup() { _vetcoders_skill_entry claude followup "$@"; }
gemini-skill-followup() { _vetcoders_skill_entry gemini followup "$@"; }

codex-skill-hydrate() { _vetcoders_skill_entry codex hydrate "$@"; }
claude-skill-hydrate() { _vetcoders_skill_entry claude hydrate "$@"; }
gemini-skill-hydrate() { _vetcoders_skill_entry gemini hydrate "$@"; }

codex-skill-init() { _vetcoders_skill_init codex "$@"; }
claude-skill-init() { _vetcoders_skill_init claude "$@"; }
gemini-skill-init() { _vetcoders_skill_init gemini "$@"; }

codex-skill-justdo() { _vetcoders_skill_entry codex justdo "$@"; }
claude-skill-justdo() { _vetcoders_skill_entry claude justdo "$@"; }
gemini-skill-justdo() { _vetcoders_skill_entry gemini justdo "$@"; }

# vc-implement is the front-face brand for vc-justdo. Both helper families hit
# the same dispatcher (skill id stays "justdo" so run_id prefix, locks, and
# already-trained agents keep working unchanged).
codex-skill-implement() { _vetcoders_skill_entry codex justdo "$@"; }
claude-skill-implement() { _vetcoders_skill_entry claude justdo "$@"; }
gemini-skill-implement() { _vetcoders_skill_entry gemini justdo "$@"; }

codex-skill-marbles() { _vetcoders_marbles codex "$@"; }
claude-skill-marbles() { _vetcoders_marbles claude "$@"; }
gemini-skill-marbles() { _vetcoders_marbles gemini "$@"; }

codex-skill-partner() { _vetcoders_skill_entry codex partner "$@"; }
claude-skill-partner() { _vetcoders_skill_entry claude partner "$@"; }
gemini-skill-partner() { _vetcoders_skill_entry gemini partner "$@"; }

codex-skill-polarize() { _vetcoders_skill_entry codex polarize "$@"; }
claude-skill-polarize() { _vetcoders_skill_entry claude polarize "$@"; }
gemini-skill-polarize() { _vetcoders_skill_entry gemini polarize "$@"; }

codex-skill-prune() { _vetcoders_skill_entry codex prune "$@"; }
claude-skill-prune() { _vetcoders_skill_entry claude prune "$@"; }
gemini-skill-prune() { _vetcoders_skill_entry gemini prune "$@"; }

codex-skill-release() { _vetcoders_skill_entry codex release "$@"; }
claude-skill-release() { _vetcoders_skill_entry claude release "$@"; }
gemini-skill-release() { _vetcoders_skill_entry gemini release "$@"; }

codex-skill-research() { _vetcoders_skill_entry codex research "$@"; }
claude-skill-research() { _vetcoders_skill_entry claude research "$@"; }
gemini-skill-research() { _vetcoders_skill_entry gemini research "$@"; }
vc-research() { _vetcoders_research "$@"; }
vc-research-await() { _vetcoders_await "" --research "$@"; }

codex-skill-review() { _vetcoders_skill_entry codex review "$@"; }
claude-skill-review() { _vetcoders_skill_entry claude review "$@"; }
gemini-skill-review() { _vetcoders_skill_entry gemini review "$@"; }

codex-skill-scaffold() { _vetcoders_skill_entry codex scaffold "$@"; }
claude-skill-scaffold() { _vetcoders_skill_entry claude scaffold "$@"; }
gemini-skill-scaffold() { _vetcoders_skill_entry gemini scaffold "$@"; }

codex-skill-workflow() { _vetcoders_skill_entry codex workflow "$@"; }
claude-skill-workflow() { _vetcoders_skill_entry claude workflow "$@"; }
gemini-skill-workflow() { _vetcoders_skill_entry gemini workflow "$@"; }

_vetcoders_skill_wrapper_usage() {
  local skill="$1"
  case "$skill" in
    init)
      printf 'Usage: vc-init <claude|codex|gemini|agy|junie|grok> [--prompt <text>] [--file <path>]\n' >&2
      ;;
    marbles)
      printf 'Usage: vc-marbles <claude|codex|gemini|agy|junie|grok> [--prompt <text>|--file <path>|--depth <n>] [--count <n>]\n' >&2
      printf '       vc-marbles <pause|stop|resume|session|inspect|delete|gc> [args]\n' >&2
      ;;
    polarize)
      printf 'Usage: vc-polarize <claude|codex|gemini|agy|junie|grok> --task <text> [--prompt <text>] [--file <path>] [--no-aicx] [--no-context-corpus]\n' >&2
      printf '       vc-polarize <claude|codex|gemini|agy|junie|grok> [--count <n>] [--prompt <text>] [--file <path>]\n' >&2
      ;;
    *)
      printf 'Usage: vc-%s <claude|codex|gemini|agy|junie|grok> [--prompt <text>] [--file <path>]\n' "$skill" >&2
      ;;
  esac
}

_vetcoders_has_agent() {
  local candidate="${1:-}"
  case "$candidate" in
    claude|codex|gemini|agy|junie|grok) return 0 ;;
    *) return 1 ;;
  esac
}

_vetcoders_is_help_flag() {
  local candidate="${1:-}"
  [[ "$candidate" == "help" || "$candidate" == "-h" || "$candidate" == "--help" ]]
}

_vetcoders_skill_wrapper() {
  local skill="$1"
  shift || true

  local tool="${1:-}"
  if [[ "$skill" == "marbles" ]]; then
    case "$tool" in
      pause|stop|resume|session|inspect|delete|gc)
        shift || true
        "marbles-$tool" "$@"
        return
        ;;
    esac
  fi

  [[ -n "$tool" ]] || {
    _vetcoders_skill_wrapper_usage "$skill"
    return 1
  }
  _vetcoders_has_agent "$tool" || {
    printf 'vc-%s expects <claude|codex|gemini|agy|junie|grok> as the first argument.\n' "$skill" >&2
    _vetcoders_skill_wrapper_usage "$skill"
    return 1
  }
  shift || true

  if _vetcoders_is_help_flag "${1:-}"; then
    _vetcoders_skill_wrapper_usage "$skill"
    return 0
  fi

  case "$skill" in
    init) _vetcoders_skill_init "$tool" "$@" ;;
    operator) _vetcoders_skill_operator "$tool" "$@" ;;
    marbles) _vetcoders_marbles "$tool" "$@" ;;
    *) _vetcoders_skill_entry "$tool" "$skill" "$@" ;;
  esac
}

_vetcoders_skill_dispatch() {
  # Graceful degradation for headless / partially-loaded shells: when the
  # helper layer is incomplete (version skew, stale snapshot, interrupted
  # source), fall back to the standalone command deck instead of dying with
  # "command not found: _vetcoders_skill_wrapper" (exit 127, zero run, zero
  # failure-card). Headless is a first-class environment.
  local skill="$1"
  shift || true
  if typeset -f _vetcoders_skill_wrapper >/dev/null 2>&1; then
    _vetcoders_skill_wrapper "$skill" "$@"
    return
  fi
  if command -v vibecrafted >/dev/null 2>&1; then
    command vibecrafted "$skill" "$@"
    return
  fi
  printf 'vc-%s: vibecrafted helper layer is not loaded and no "vibecrafted" deck is on PATH.\n' "$skill" >&2
  printf 'Run scripts/install-foundations.sh or add the repo bin/ to PATH.\n' >&2
  return 127
}

vc-agents() { _vetcoders_skill_dispatch agents "$@"; }
vc-audit() { _vetcoders_skill_dispatch audit "$@"; }
vc-decorate() { _vetcoders_skill_dispatch decorate "$@"; }
vc-delegate() { _vetcoders_skill_dispatch delegate "$@"; }
vc-dou() { _vetcoders_skill_dispatch dou "$@"; }
vc-followup() { _vetcoders_skill_dispatch followup "$@"; }
vc-hydrate() { _vetcoders_skill_dispatch hydrate "$@"; }
vc-init() { _vetcoders_skill_dispatch init "$@"; }
vc-intents() { _vetcoders_skill_dispatch intents "$@"; }
vc-justdo() { _vetcoders_skill_dispatch justdo "$@"; }
vc-implement() { _vetcoders_skill_dispatch justdo "$@"; }
vc-loop() { _vetcoders_loop "$@"; }
vc-cron() { command vibecrafted cron "$@"; }
vc-ship() { command vibecrafted ship "$@"; }
vc-marbles() { _vetcoders_skill_dispatch marbles "$@"; }
vc-operator() { _vetcoders_skill_dispatch operator "$@"; }
vc-ownership() { _vetcoders_skill_dispatch ownership "$@"; }
vc-partner() { _vetcoders_skill_dispatch partner "$@"; }
vc-polarize() { _vetcoders_skill_dispatch polarize "$@"; }
vc-prune() { _vetcoders_skill_dispatch prune "$@"; }
vc-release() { _vetcoders_skill_dispatch release "$@"; }
vc-review() { _vetcoders_skill_dispatch review "$@"; }
vc-scaffold() { _vetcoders_skill_dispatch scaffold "$@"; }
vc-workflow() { _vetcoders_skill_dispatch workflow "$@"; }

vc-help() {
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  cat <<'HELP'
𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Framework — Skills & Helpers

Pipeline:  scaffold → init → workflow → implement → followup → marbles → audit → dou → decorate → hydrate → release
Modes:     partner (shared steering) | ownership (take the wheel)
Research:  research (triple-agent) | delegate (in-session)
Quality:   audit (plan falsification) | review (bounded diff/PR/commit) | followup (post-implementation direction) | prune
Video:     screenscribe (foundation)

Spawn helpers (per agent):
  <agent>-implement <plan.md>    Full implementation from plan
  <agent>-review <plan.md>       Bounded PR, branch, commit-range, or artifact review
  <agent>-plan <plan.md>         Planning only
  <agent>-prompt "text"          Quick one-shot prompt
  <agent>-scaffold                Architecture planning
  <agent>-followup               Post-implementation direction audit
  <agent>-skill-audit            Plan-vs-code falsification
  <agent>-dou                    Definition of Undone audit
  <agent>-hydrate                Market packaging
  <agent>-marbles                Convergence loop
  <agent>-decorate               Visual polish
  <agent>-release                Ship to market
  <agent>-prune                  Repo pruning
  <agent>-skill-implement        Autonomous e2e implementation (vc-implement)
  <agent>-justdo                 Alias for autonomous e2e implementation
  <agent>-partner                Collaborative partner mode with the user in the loop
  <agent>-observe --last         Check last report
  <agent>-await --last           Wait for metadata completion + summary

Swarm launchers:
  vc-research --prompt "text"    Triple-agent research swarm
  vc-research-await --last       Wait for the latest research swarm

Command deck:
  vibecrafted help               Main command surface
  vibecrafted <skill> <agent>    Run a repo skill via the launcher
  vibecrafted resume <agent>     Resume a previous session
  vibecrafted loop start --file plan.md --completion-promise READY
  vibecrafted cron line --root "$(pwd)" --every-minutes 10
  vibecrafted workflow claude -p "Plan and implement auth"
  vibecrafted marbles codex --count 3 --depth 3
  vibecrafted init claude        First-context entrypoint

Uniform skill flags:
  -p, --prompt <text>            Inline prompt; captures the rest of the command line
  -f, --file <path.md>           Input file as prompt context
  --count <n>                    Marbles / Polarize loop count (default: 3)
  --depth <n>                    Marbles plan crawl depth (default: 3)
  --session <id>                 Resume session id

Utilities:
  repo-full                      Full git context dump
  skills-sync                    Sync skills to agents
  vc-frontier-paths              Show frontier config paths
  vc-frontier-install            Install frontier presets (starship/atuin/zellij)
  vc-help                        This help

Frontier docs:  docs/FRONTIER.md (starship, atuin, optional zellij)
HELP
  printf '\nInbox:     %s/inbox/\n' "$crafted_home"
  printf 'Artifacts: %s/artifacts/<org>/<repo>/<YYYY_MMDD>/\n' "$crafted_home"
  printf 'Skills:    %s/skills/ (16 installed)\n' "$crafted_home"
}

skills-sync() {
  local script
  script="$(_vetcoders_spawn_script codex skills_sync.sh)" || return 1
  bash "$script" "$@"
}

_repo_full_rescue_emit_txt() {
  local file="$1"
  awk '
    /^REPO:/ || /^REMOTE:/ || /^BRANCH:/ || /^HEAD:/ || /^UPSTREAM:/ { print }
    /^===== STATUS =====/ { p=1; print; next }
    /^===== LOCAL DIFF FILES =====/ { p=1; print; next }
    /^===== LOCAL DIFF MATCHES ONLY =====/ { p=1; print; next }
    /^===== RELEASE\/WATCH\/LSP\/MCP COMMIT MSG MATCHES SINCE MAY 1 =====/ { p=1; print; next }
    /^===== STASHES =====/ { p=1; print; next }
    /^===== STASH MATCHES =====/ { p=1; print; next }
    /^===== CURRENT TREE MATCHES/ { p=0; next }
    /^===== RECENT COMMITS SINCE MAY 1/ { p=0; next }
    /^===== / && p { p=0 }
    p { print }
  ' "$file" | sed '/^$/N;/^\n$/D'
}

_repo_full_rescue_emit_patch() {
  local file="$1"
  local max_matches="${REPO_RESCUE_MAX_MATCHES:-120}"
  local pattern='release|publish|homebrew|npm|watch|lsp|mcp|install|aicx|fallback|sign|notary|formula|loctree-mcp|loctree-lsp|artifact|prebuilt|postinstall'

  echo "----- PATCH STAT -----"
  git apply --stat "$file" 2>/dev/null || awk '
    /^diff --git / {
      old=$3; new=$4;
      sub(/^a\//, "", old);
      sub(/^b\//, "", new);
      print old " -> " new;
    }
  ' "$file" | awk 'NF && !seen[$0]++'

  echo
  echo "----- MATCHED SIGNALS (bounded) -----"
  if command -v rg >/dev/null 2>&1; then
    rg -n -i "$pattern" "$file" | head -n "$max_matches"
  else
    awk -v pat="$pattern" -v max="$max_matches" '
      BEGIN { IGNORECASE=1 }
      $0 ~ pat {
        print FNR ":" $0;
        count++;
        if (count >= max) exit;
      }
    ' "$file"
  fi
}

_repo_full_rescue_emit_plain() {
  local file="$1"
  local max_lines="${REPO_RESCUE_MAX_LINES:-120}"
  local pattern='repo|remote|branch|head|upstream|status|stash|diff|release|publish|homebrew|npm|watch|lsp|mcp|install|aicx|fallback'
  if command -v rg >/dev/null 2>&1; then
    rg -n -i "$pattern" "$file" | head -n "$max_lines"
  else
    awk -v pat="$pattern" -v max="$max_lines" '
      BEGIN { IGNORECASE=1 }
      $0 ~ pat {
        print FNR ":" $0;
        count++;
        if (count >= max) exit;
      }
    ' "$file"
  fi
}

_repo_full_rescue_emit_file() {
  local file="$1"
  local bytes lines
  bytes="$(wc -c < "$file" | tr -d ' ')"
  lines="$(wc -l < "$file" | tr -d ' ')"

  echo
  echo "================================================================================"
  echo "### $(basename "$file")"
  echo "Path:  $file"
  echo "Size:  $bytes bytes"
  echo "Lines: $lines"
  echo

  case "$file" in
    *.patch|*.diff) _repo_full_rescue_emit_patch "$file" ;;
    *.txt) _repo_full_rescue_emit_txt "$file" ;;
    *.md|*.markdown) _repo_full_rescue_emit_plain "$file" ;;
    *) echo "Skipped: unsupported rescue evidence type." ;;
  esac
}

_repo_full_rescue() {
  local rescue_dir="${1:-${REPO_RESCUE_DIR:-$HOME/Desktop/loctree-release-rescue}}"
  local pattern="${2:-*}"
  local root branch head files_found=0 file

  if [[ ! -d "$rescue_dir" ]]; then
    echo "Rescue directory not found: $rescue_dir"
    echo "Usage: repo-full --rescue [evidence-dir] [glob]"
    return 1
  fi

  root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  branch="$(git symbolic-ref --short -q HEAD 2>/dev/null || echo "DETACHED_OR_NO_GIT")"
  head="$(git rev-parse --short HEAD 2>/dev/null || echo "no-git")"

  echo "==================== REPO RESCUE ===================="
  echo "Working dir:       $(pwd)"
  echo "Root:              $root"
  echo "Branch:            $branch"
  echo "HEAD short:        $head"
  echo "Evidence dir:      $rescue_dir"
  echo "Evidence glob:     $pattern"
  echo "Generated at:      $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo

  while IFS= read -r file; do
    files_found=1
    _repo_full_rescue_emit_file "$file"
  done < <(find "$rescue_dir" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort)

  [[ "$files_found" != "0" ]] || echo "No rescue evidence files matched."
  echo
  echo "==================== RESCUE DONE ===================="
}

repo-full() {
  if [[ "${1:-}" == "--rescue" ]]; then
    shift
    _repo_full_rescue "$@"
    return
  fi

  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "Not a git repository."
    return 1
  }

  local cwd root repo branch head_short head_full upstream origin_url default_remote default_branch
  local last_tag stash_count staged_count unstaged_count untracked_count worktree_count
  local upstream_ahead upstream_behind

  cwd="$(pwd)"
  root="$(git rev-parse --show-toplevel 2>/dev/null)"
  repo="$(basename "$root")"
  branch="$(git symbolic-ref --short -q HEAD 2>/dev/null || echo "DETACHED_HEAD")"
  head_short="$(git rev-parse --short HEAD 2>/dev/null)"
  head_full="$(git rev-parse HEAD 2>/dev/null)"
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "no upstream")"
  origin_url="$(git remote get-url origin 2>/dev/null || echo "no origin")"
  last_tag="$(git describe --tags --abbrev=0 2>/dev/null || echo "no tags")"
  stash_count="$(git stash list 2>/dev/null | wc -l | tr -d ' ')"
  staged_count="$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')"
  unstaged_count="$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')"
  untracked_count="$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')"
  worktree_count="$(git worktree list 2>/dev/null | wc -l | tr -d ' ')"

  default_remote="$(git remote | awk 'NR==1{print; exit}')"
  [[ -z "$default_remote" ]] && default_remote="origin"

  default_branch="$(git symbolic-ref --quiet --short "refs/remotes/${default_remote}/HEAD" 2>/dev/null | sed "s#^${default_remote}/##")"
  [[ -z "$default_branch" ]] && default_branch="$(git remote show "$default_remote" 2>/dev/null | sed -n '/HEAD branch/s/.*: //p' | head -n 1)"
  [[ -z "$default_branch" ]] && default_branch="unknown"

  # shellcheck disable=SC1083 # @{u} is git upstream ref syntax, not shell braces
  if git rev-parse '@{u}' >/dev/null 2>&1; then
    read -r upstream_ahead upstream_behind <<< "$(git rev-list --left-right --count HEAD...'@{u}' 2>/dev/null)"
  else
    upstream_ahead="-"
    upstream_behind="-"
  fi

  _repo_full_compare_ref() {
    local ref="$1"
    git rev-parse --verify "$ref" >/dev/null 2>&1 || return 0
    local ahead behind sha
    read -r ahead behind <<< "$(git rev-list --left-right --count HEAD..."$ref" 2>/dev/null)"
    sha="$(git rev-parse --short "$ref" 2>/dev/null)"
    printf "%-24s ahead:%-4s behind:%-4s sha:%s\n" "$ref" "$ahead" "$behind" "$sha"
  }

  # shellcheck disable=SC2016 # expressions in awk are intentional
  _repo_full_human_awk='
    function human(x) {
      split("B KB MB GB TB", u, " ");
      i=1;
      while (x >= 1024 && i < 5) { x /= 1024; i++ }
      return sprintf("%.1f %s", x, u[i]);
    }
    {
      size=$1;
      $1="";
      sub(/^\t/, "", $0);
      printf "%10s  %s\n", human(size), $0;
    }
  '

  echo "==================== REPO FULL ===================="
  echo "Repo:              $repo"
  echo "Working dir:       $cwd"
  echo "Root:              $root"
  echo "Branch:            $branch"
  echo "Default remote:    $default_remote"
  echo "Default branch:    $default_branch"
  echo "Upstream:          $upstream"
  echo "Ahead / Behind:    $upstream_ahead / $upstream_behind"
  echo "Origin:            $origin_url"
  echo "HEAD short:        $head_short"
  echo "HEAD full:         $head_full"
  echo "Last tag:          $last_tag"
  echo "Stashes:           $stash_count"
  echo "Worktrees:         $worktree_count"
  echo "Staged changes:    $staged_count"
  echo "Unstaged changes:  $unstaged_count"
  echo "Untracked files:   $untracked_count"
  echo

  echo "==================== HEAD COMMIT ===================="
  git show -s --format="Commit: %H%nAuthor: %an <%ae>%nDate:   %ad%nTitle:  %s" --date=iso HEAD
  echo

  echo "==================== STATUS ===================="
  git status -sb
  echo

  echo "==================== WORKTREE ===================="
  git status --short
  echo

  echo "==================== COMPARE TO IMPORTANT REFS ===================="
  {
    [[ "$upstream" != "no upstream" ]] && echo "$upstream"
    [[ "$default_branch" != "unknown" ]] && echo "${default_remote}/${default_branch}"
    echo "origin/develop"
    echo "origin/main"
  } | awk 'NF && !seen[$0]++' | while IFS= read -r ref; do
    _repo_full_compare_ref "$ref"
  done
  echo

  echo "==================== REMOTES ===================="
  git remote -v
  echo

  echo "==================== LOCAL BRANCHES (RECENT FIRST) ===================="
  git for-each-ref \
    --sort=-committerdate \
    refs/heads \
    --format='%(HEAD) %(refname:short) | upstream=%(upstream:short) | %(committerdate:short) | %(objectname:short) | %(subject)'
  echo

  echo "==================== LAST 20 COMMITS ===================="
  git log --oneline --decorate --graph -n 20
  echo

  echo "==================== STAGED DIFF STAT ===================="
  git diff --cached --stat
  echo

  echo "==================== UNSTAGED DIFF STAT ===================="
  git diff --stat
  echo

  echo "==================== STASH LIST ===================="
  git stash list 2>/dev/null
  echo

  echo "==================== WORKTREES ===================="
  git worktree list 2>/dev/null
  echo

  echo "==================== SUBMODULES ===================="
  if [[ -f "$root/.gitmodules" ]]; then
    git submodule status
  else
    echo "No submodules."
  fi
  echo

  echo "==================== TOP 10 LARGEST TRACKED FILES ===================="
  if git ls-files -z | grep -q . 2>/dev/null; then
    { git ls-files -z | xargs -0 stat -f "%z\t%N" 2>/dev/null ||
      git ls-files -z | xargs -0 stat -c "%s\t%n" 2>/dev/null; } \
      | sort -nr \
      | head -n 10 \
      | awk "$_repo_full_human_awk"
  else
    echo "No tracked files."
  fi
  echo

  echo "==================== GIT CONFIG ===================="
  echo "user.name:         $(git config --get user.name 2>/dev/null || echo "not set")"
  echo "user.email:        $(git config --get user.email 2>/dev/null || echo "not set")"
  echo "pull.rebase:       $(git config --get pull.rebase 2>/dev/null || echo "not set")"
  echo "init.defaultBranch:$(git config --get init.defaultBranch 2>/dev/null || echo "not set")"
  echo

  echo "==================== DONE ===================="
}

vc-start() {
  if [[ "${1:-}" == "resume" ]]; then
    shift || true
    _vetcoders_resume_operator_session "$@"
    return
  fi
  if [[ "${1:-}" == "operator" || "${1:-}" == "vibecrafted" ]]; then
    shift || true
  fi
  _vetcoders_launch_dashboard operator "$@"
}

vc-frontier-paths() {
  local starship_config atuin_config zellij_config
  starship_config="$(_vetcoders_frontier_file "starship.toml")" || return 1
  atuin_config="$(_vetcoders_frontier_file "atuin/config.toml" 2>/dev/null || true)"
  zellij_config="$(_vetcoders_frontier_file "zellij/config.kdl" 2>/dev/null || true)"

  printf 'STARSHIP_CONFIG=%s\n' "$starship_config"
  [[ -n "$atuin_config" ]] && printf 'ATUIN_CONFIG=%s\n' "$atuin_config"
  [[ -n "$zellij_config" ]] && printf 'VC_FRAME_CONFIG_DIR=%s\n' "$(dirname "$zellij_config")"
  return 0
}

vc-dashboard() {
  _vetcoders_launch_dashboard "$@"
}

vc-frontier-install() {
  local repo_root script base
  repo_root="$(_vetcoders_frontier_source_root)" || {
    echo "Repo-owned frontier source not found." >&2
    return 1
  }
  base="$(_vetcoders_spawn_home "vc-agents")"
  script="$base/scripts/install-frontier-config.sh"
  
  [[ -f "$script" ]] || {
    echo "Frontier installer not found: $script" >&2
    return 1
  }
  bash "$script" --source "$repo_root" "$@"
}
