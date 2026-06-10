# Marbles Orchestrator Persistent Audit - 2026-06-08

Generated: 2026-06-08 05:09:47 MDT  
Branch: `feat/runtime-integration`  
Mode: living-tree audit, no push

## Current State

- Working tree is dirty with orchestrator-only edits from this pass.
- Branch is ahead of `origin/feat/runtime-integration`.
- The large app/mux/tui rewrite is already in local commits, especially `b534103 [claude/interactive] feat(vibecrafted-app): land voc overlay + Mission Control dashboard`.
- The user push failed after local pre-push gates passed because GitHub rejected the ref update for workflow permission scope.
- `vc-audit --help` failed in the user's shell with `command not found`, so audit output cannot depend on the installed `vc-audit` launcher being available.
- Claude plugin loading was broken by invalid `skills/vc-*/.claude-plugin/plugin.json` names and two missing manifests.

## Evidence Captured

User-provided push evidence:

```text
pre-push: shellcheck full, ruff full, prettier full, semgrep full passed
remote rejected: refusing to allow an OAuth App to create or update workflow `.github/workflows/portable.yml` without `workflow` scope
```

Fresh local evidence from this pass:

```text
git diff --name-status: 8 modified orchestrator files
git diff origin/feat/runtime-integration..HEAD -- .github/workflows: no current diff output
loctree focus runtime/vc-marbles/orchestrator: 10 files, 1128 LOC, no external consumers
loct slice hooks/hooks.json: missing from snapshot even though file exists on disk
claude plugin validate ~/.claude/skills/vc-*: passed after manifest repair
```

Loctree miss was appended to `~/.vibecrafted/loctree/loctree-fail.md`.

## Armed Surface

The Marbles orchestrator now has persistent audit behavior across both runtimes:

- Codex interactive loop:
  - state: `.codex/marbles.local.md`
  - audit: `.codex/marbles.audit.jsonl`
  - records activation, status, next iteration, completion, cancellation, max-iteration stop, inactive stop, and promise mismatch
- Claude Stop-hook loop:
  - state: `.claude/marbles.local.md`
  - audit: `.claude/marbles.audit.jsonl`
  - records activation, continuation, completion, max-iteration stop, state corruption, transcript failures, jq parse failures, and missing prompt failures

## Files Updated

- `runtime/vc-marbles/orchestrator/scripts/codex-loop-step.sh`
- `runtime/vc-marbles/orchestrator/scripts/setup-codex-loop.sh`
- `runtime/vc-marbles/orchestrator/scripts/setup-marbles-loop.sh`
- `runtime/vc-marbles/orchestrator/hooks/stop-hook.sh`
- `runtime/vc-marbles/orchestrator/hooks/hooks.json`
- `runtime/vc-marbles/orchestrator/commands/help.md`
- `runtime/vc-marbles/orchestrator/commands/cancel-codex-marbles.md`
- `runtime/vc-marbles/orchestrator/commands/codex-marbles-loop.md`
- `runtime/vc-marbles/orchestrator/commands/marbles-loop.md`
- `runtime/vc-marbles/orchestrator/commands/cancel-marbles.md`

Note: the two Codex script files were already audit-armed in the current local HEAD before this working-tree pass; this audit verifies and documents them as part of the armed surface.

## Findings

1. Push blocker is not a local quality-gate failure.

   - Local pre-push checks passed in the user's run.
   - The blocker is remote authorization: OAuth credential lacks `workflow` scope for a ref update GitHub believes touches `.github/workflows/portable.yml`.
   - Fresh local diff against `origin/feat/runtime-integration` did not show a current workflow diff, so treat this as a credential/ref-history blocker until reproduced with current auth.

2. `vc-audit` cannot be assumed available.

   - The user's shell returned `zsh: command not found: vc-audit`.
   - Persistent audit must therefore live in repo artifacts and loop JSONL ledgers, not only in a launcher command.

3. Orchestrator state previously was too ephemeral.

   - Claude had state and a Stop hook, but no durable JSONL ledger.
   - Codex had a state file and manual step discipline, but the commands did not present audit as a first-class handoff artifact.
   - Cancellation docs did not preserve cancellation in a durable ledger.

4. Command wiring had stale names.

   - `/marbles-loop` referenced `setup-marbles.sh`, while the actual script is `setup-marbles-loop.sh`.
   - Help text still mentioned `.claude/.marbles.local.md` in one place.

5. Claude-side executable bits were not armed.

   - `setup-marbles-loop.sh` and `hooks/stop-hook.sh` were not executable during smoke testing.
   - Slash-command and hook surfaces invoke those files as commands, so mode bits are runtime behavior, not cosmetic metadata.

6. Claude plugin manifests were invalid as installed.
   - 25 `vc-*` manifests used display names such as `VC Init`, `VC Audit`, or `AICX Extract` in the required `name` field.
   - Claude Code requires kebab-case plugin names, so those are now normalized to the folder names: `vc-init`, `vc-audit`, `vc-aicx`, etc.
   - `vc-operator` and `vc-skillaunch` had no `.claude-plugin/plugin.json`; both now have manifests in repo source and staged install.
   - The active `~/.claude/skills/vc-*` paths are symlinks into `~/.local/share/vibecrafted/tools/vibecrafted-current/skills`, so the staged copy was repaired immediately as well as the repo source.

## Remaining Risk

- The branch still cannot be pushed with an OAuth token lacking workflow scope if GitHub's ref update path includes workflow changes.
- The current report does not audit the full app/mux/tui runtime rewrite for correctness; it only records that the living tree is materially larger than the previous substrate handoff and arms the loop audit mechanism.
- `vc-audit` launcher availability remains an installer/PATH issue outside this orchestrator patch.
- Claude plugin manifest validation is now green for 27 `vc-*` plugins, but the fix must be committed so the next staged install does not reintroduce display-name manifests.

## Next Checks

Run before committing this pass:

```bash
bash -n runtime/vc-marbles/orchestrator/scripts/codex-loop-step.sh \
  runtime/vc-marbles/orchestrator/scripts/setup-codex-loop.sh \
  runtime/vc-marbles/orchestrator/scripts/setup-marbles-loop.sh \
  runtime/vc-marbles/orchestrator/hooks/stop-hook.sh

shellcheck -S error runtime/vc-marbles/orchestrator/scripts/codex-loop-step.sh \
  runtime/vc-marbles/orchestrator/scripts/setup-codex-loop.sh \
  runtime/vc-marbles/orchestrator/scripts/setup-marbles-loop.sh \
  runtime/vc-marbles/orchestrator/hooks/stop-hook.sh

tmp=$(mktemp -d)
runtime/vc-marbles/orchestrator/scripts/setup-codex-loop.sh \
  --state-file "$tmp/codex.md" \
  --audit-file "$tmp/codex.audit.jsonl" \
  --max-iterations 2 \
  --completion-promise DONE \
  "audit smoke"
runtime/vc-marbles/orchestrator/scripts/codex-loop-step.sh --state-file "$tmp/codex.md" status
runtime/vc-marbles/orchestrator/scripts/codex-loop-step.sh --state-file "$tmp/codex.md" next
runtime/vc-marbles/orchestrator/scripts/codex-loop-step.sh --state-file "$tmp/codex.md" complete --promise DONE
test -s "$tmp/codex.audit.jsonl"
```

Additional smoke performed in this pass:

```bash
# Claude Stop-hook runtime
setup-marbles-loop.sh --audit-file "$tmp/claude.audit.jsonl" --max-iterations 2 --completion-promise DONE "audit smoke"
printf '{"session_id":"","transcript_path":"..."}' | stop-hook.sh
test -s "$tmp/claude.audit.jsonl"
```
