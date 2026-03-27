# VetCoders shell helpers (bash/zsh compatible)
# Source this from your ~/.bashrc or ~/.zshrc to get consistent wrapper commands
# for the VibeCraft framework installed under your local repository path.

_vetcoders_spawn_home() {
  local tool="$1"
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  local crafted_store="$crafted_home/skills/vc-agents"
  if [[ -d "$crafted_store" ]]; then
    printf '%s' "$crafted_store"
    return 0
  fi

  local repo_root
  repo_root="${VIBECRAFT_ROOT:-$(_vetcoders_repo_root)}"
  if [[ -d "$repo_root/skills/vc-agents" ]]; then
    printf '%s/skills/vc-agents' "$repo_root"
    return 0
  fi

  local legacy_store="$HOME/.agents/skills/vc-agents"
  if [[ -d "$legacy_store" ]]; then
    printf '%s' "$legacy_store"
    return 0
  fi

  printf '%s' "$crafted_store"
}

_vetcoders_spawn_script() {
  local tool="$1"
  local script_name="$2"
  local base
  base="$(_vetcoders_spawn_home "$tool")"
  [[ -f "$base/scripts/$script_name" ]] || {
    echo "VetCoders spawn script not found: $base/scripts/$script_name" >&2
    return 1
  }
  printf '%s/scripts/%s' "$base" "$script_name"
}

_vetcoders_repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

_vetcoders_default_runtime() {
  printf '%s\n' "${VETCODERS_SPAWN_RUNTIME:-terminal}"
}

_vetcoders_frontier_root() {
  local root
  root="${VIBECRAFT_ROOT:-}"
  if [[ -n "$root" && -d "$root/config/atuin" && -d "$root/config/zellij" && -f "$root/config/starship.toml" ]]; then
    printf '%s/config' "$root"
    return 0
  fi

  local repo_root
  repo_root="$(_vetcoders_repo_root)"
  if [[ -d "$repo_root/config/atuin" && -d "$repo_root/config/zellij" && -f "$repo_root/config/starship.toml" ]]; then
    printf '%s/config' "$repo_root"
    return 0
  fi

  local crafted_sidecar="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tools/vibecrafted-current/config"
  if [[ -d "$crafted_sidecar/atuin" && -d "$crafted_sidecar/zellij" && -f "$crafted_sidecar/starship.toml" ]]; then
    printf '%s' "$crafted_sidecar"
    return 0
  fi

  local sidecar="${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/frontier"
  if [[ -d "$sidecar/atuin" && -d "$sidecar/zellij" && -f "$sidecar/starship.toml" ]]; then
    printf '%s' "$sidecar"
    return 0
  fi

  echo "VetCoders frontier config not found. Run vc-frontier-install from the repo checkout." >&2
  return 1
}

_vetcoders_load_frontier_sidecars() {
  local root
  root="$(_vetcoders_frontier_root 2>/dev/null)" || return 0

  if [[ -z "${STARSHIP_CONFIG:-}" ]] && command -v starship >/dev/null 2>&1 && [[ -f "$root/starship.toml" ]]; then
    export STARSHIP_CONFIG="$root/starship.toml"
  fi

  if [[ -z "${ZELLIJ_CONFIG_DIR:-}" ]] && command -v zellij >/dev/null 2>&1 && [[ -d "$root/zellij" ]]; then
    export ZELLIJ_CONFIG_DIR="$root/zellij"
  fi
}

_vetcoders_load_frontier_sidecars

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

_vetcoders_spawn_plan() {
  local tool="$1"
  local mode="$2"
  local plan_file="$3"
  shift 3
  local script
  script="$(_vetcoders_spawn_script "$tool" "${tool}_spawn.sh")" || return 1
  bash "$script" --mode "$mode" "$plan_file" "$@"
}

_vetcoders_prompt() {
  local tool="$1"
  local mode="$2"
  shift 2
  local prompt_file
  prompt_file="$(_vetcoders_prompt_file "$tool" "$@")" || return 1
  _vetcoders_spawn_plan "$tool" "$mode" "$prompt_file" --runtime "$(_vetcoders_default_runtime)"
}

_vetcoders_observe() {
  local tool="$1"
  shift
  local script
  script="$(_vetcoders_spawn_script "$tool" "observe.sh")" || return 1
  bash "$script" "$tool" "$@"
}

codex-review() {
  _vetcoders_spawn_plan codex review "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-plan() {
  _vetcoders_spawn_plan codex plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-implement() {
  _vetcoders_spawn_plan codex implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-review() {
  _vetcoders_spawn_plan claude review "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-plan() {
  _vetcoders_spawn_plan claude plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-implement() {
  _vetcoders_spawn_plan claude implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-review() {
  _vetcoders_spawn_plan gemini review "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-plan() {
  _vetcoders_spawn_plan gemini plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-implement() {
  _vetcoders_spawn_plan gemini implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-research() {
  _vetcoders_spawn_plan codex research "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-research() {
  _vetcoders_spawn_plan claude research "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-research() {
  _vetcoders_spawn_plan gemini research "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-prompt() {
  _vetcoders_prompt codex implement "$@"
}

claude-prompt() {
  _vetcoders_prompt claude implement "$@"
}

gemini-prompt() {
  _vetcoders_prompt gemini implement "$@"
}

codex-observe() {
  _vetcoders_observe codex "$@"
}

claude-observe() {
  _vetcoders_observe claude "$@"
}

gemini-observe() {
  _vetcoders_observe gemini "$@"
}

_vetcoders_skill() {
  local tool="$1"
  local skill="$2"
  shift 2
  local extra="$*"
  local prompt="Perform the vc-${skill} skill on this repository.${extra:+ }${extra}"
  _vetcoders_prompt "$tool" implement "$prompt"
}

codex-dou() { _vetcoders_skill codex dou "$@"; }
claude-dou() { _vetcoders_skill claude dou "$@"; }
gemini-dou() { _vetcoders_skill gemini dou "$@"; }

codex-hydrate() { _vetcoders_skill codex hydrate "$@"; }
claude-hydrate() { _vetcoders_skill claude hydrate "$@"; }
gemini-hydrate() { _vetcoders_skill gemini hydrate "$@"; }

codex-marbles() { _vetcoders_skill codex marbles "$@"; }
claude-marbles() { _vetcoders_skill claude marbles "$@"; }
gemini-marbles() { _vetcoders_skill gemini marbles "$@"; }

codex-decorate() { _vetcoders_skill codex decorate "$@"; }
claude-decorate() { _vetcoders_skill claude decorate "$@"; }
gemini-decorate() { _vetcoders_skill gemini decorate "$@"; }

codex-followup() { _vetcoders_skill codex followup "$@"; }
claude-followup() { _vetcoders_skill claude followup "$@"; }
gemini-followup() { _vetcoders_skill gemini followup "$@"; }

codex-prune() { _vetcoders_skill codex prune "$@"; }
claude-prune() { _vetcoders_skill claude prune "$@"; }
gemini-prune() { _vetcoders_skill gemini prune "$@"; }

codex-scaffold() { _vetcoders_skill codex scaffold "$@"; }
claude-scaffold() { _vetcoders_skill claude scaffold "$@"; }
gemini-scaffold() { _vetcoders_skill gemini scaffold "$@"; }

codex-release() { _vetcoders_skill codex release "$@"; }
claude-release() { _vetcoders_skill claude release "$@"; }
gemini-release() { _vetcoders_skill gemini release "$@"; }

codex-justdo() { _vetcoders_skill codex justdo "$@"; }
claude-justdo() { _vetcoders_skill claude justdo "$@"; }
gemini-justdo() { _vetcoders_skill gemini justdo "$@"; }

codex-partner() { _vetcoders_skill codex partner "$@"; }
claude-partner() { _vetcoders_skill claude partner "$@"; }
gemini-partner() { _vetcoders_skill gemini partner "$@"; }

vc-help() {
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  cat <<'HELP'
VibeCraft Framework — Skills & Helpers

Pipeline:  scaffold → init → workflow → followup → marbles → dou → decorate → hydrate → release
Modes:     partner (collaborative) | justdo (autonomous)
Research:  research (triple-agent) | delegate (in-session)
Quality:   review | prune | screenscribe

Spawn helpers (× claude, codex, gemini):
  <agent>-implement <plan.md>    Full implementation from plan
  <agent>-research <plan.md>     Research swarm
  <agent>-review <plan.md>       PR review
  <agent>-plan <plan.md>         Planning only
  <agent>-prompt "text"          Quick one-shot prompt
  <agent>-scaffold                Architecture planning
  <agent>-followup               Post-implementation audit
  <agent>-dou                    Definition of Undone audit
  <agent>-hydrate                Market packaging
  <agent>-marbles                Convergence loop
  <agent>-decorate               Visual polish
  <agent>-release                Ship to market
  <agent>-prune                  Repo pruning
  <agent>-justdo                 Autonomous e2e implementation
  <agent>-partner                Collaborative partner mode
  <agent>-observe --last         Check last report

Utilities:
  repo-full                      Full git context dump
  skills-sync                    Sync skills to agents
  vc-frontier-paths              Show frontier config paths
  vc-frontier-install            Install starship/atuin/zellij presets
  vc-help                        This help

Frontier docs:  docs/FRONTIER.md (mise, zellij, starship, atuin quickstart)
HELP
  printf '\nInbox:     %s/inbox/\n' "$crafted_home"
  printf 'Artifacts: %s/artifacts/<org>/<repo>/<YYYY_MMDD>/\n' "$crafted_home"
  printf 'Skills:    %s/skills/ (17 installed)\n' "$crafted_home"
}

skills-sync() {
  local script
  script="$(_vetcoders_spawn_script codex skills_sync.sh)" || return 1
  bash "$script" "$@"
}

repo-full() {
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

  if git rev-parse '@{u}' >/dev/null 2>&1; then
    read upstream_ahead upstream_behind <<< "$(git rev-list --left-right --count HEAD...@{u} 2>/dev/null)"
  else
    upstream_ahead="-"
    upstream_behind="-"
  fi

  _repo_full_compare_ref() {
    local ref="$1"
    git rev-parse --verify "$ref" >/dev/null 2>&1 || return 0
    local ahead behind sha
    read ahead behind <<< "$(git rev-list --left-right --count HEAD..."$ref" 2>/dev/null)"
    sha="$(git rev-parse --short "$ref" 2>/dev/null)"
    printf "%-24s ahead:%-4s behind:%-4s sha:%s\n" "$ref" "$ahead" "$behind" "$sha"
  }

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

vc-frontier-paths() {
  local root
  root="$(_vetcoders_frontier_root)" || return 1
  printf 'STARSHIP_CONFIG=%s/starship.toml\n' "$root"
  printf 'ATUIN_CONFIG=%s/atuin/config.toml\n' "$root"
  printf 'ZELLIJ_CONFIG_DIR=%s/zellij\n' "$root"
}

vc-frontier-install() {
  local repo_root script
  repo_root="$(_vetcoders_repo_root)"
  script="$repo_root/skills/vc-agents/scripts/install-frontier-config.sh"
  [[ -f "$script" ]] || {
    echo "Frontier installer not found in current repo checkout: $script" >&2
    return 1
  }
  bash "$script" --source "$repo_root" "$@"
}
