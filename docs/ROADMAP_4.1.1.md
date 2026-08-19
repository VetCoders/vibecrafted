# Vibecrafted 4.1.1 roadmap — one `vc-init` pack

Status: planned. This is not part of the 4.1.0 release contract.

## Product thesis

Every provider agent should begin from the same compact, evidence-backed
repository packet. The framework owns assembly and ordering; Codex, Claude,
Grok and other providers own only the final launch adapter. Agents must not each
invent a different orientation ritual.

Operator-facing working name: `vc-init pack`.

## One packet, two renderings

The assembler emits one typed payload and two deterministic projections:

- JSON for runtime/provider adapters and contract tests;
- bounded Markdown for a human or an agent prompt.

Both projections carry the same packet ID, schema version, assembled time,
source fingerprints and content digest.

## Required evidence lanes

1. Repository identity: canonical root, remote identity, branch, HEAD, dirty
   summary and every worktree from `vc-git`.
2. Runtime identity: active generation receipt, installed/source drift and the
   relevant `doctor` statuses.
3. Structural map: bounded Loctree entry points, ownership boundaries and
   explicit map degradations.
4. Intent continuity: AICX decisions, tasks and peers selected with exact
   cross-organization `-p /repo`, preserving renamed organizations without
   fuzzy sibling-repo leakage.
5. Operator contract: current ask, scope boundary, protected surfaces, known
   failures and the exact next verification obligation.

## Digestibility contract

- fixed section order and explicit per-section budgets;
- facts before narrative, with source and freshness attached;
- no full transcripts, broad source dumps, secrets or ambient home-directory
  inventory;
- degradations stay visible and never silently widen the query to all projects;
- stale or unavailable evidence is labeled, not guessed;
- a short pack remains useful when Loctree, AICX or the runtime is unavailable.

## Reuse instead of another system

The existing AICX resume fallback becomes one consumer of the shared assembler.
Resume and fresh `vc-init` must not maintain separate project identity, session
selection or Markdown-formatting logic. Provider-specific launchers receive the
same immutable pack path and digest.

## Acceptance contract

- organization rename history is retained by `/repo` selection;
- similarly named repositories such as `codescribe` and `codescribe-rs` never
  cross-contaminate;
- dirty-tree and multi-worktree truth matches live Git porcelain;
- installed runtime drift is visible without mutating the host;
- identical inputs produce byte-identical JSON and Markdown;
- every provider adapter records the exact packet digest it received;
- fixture coverage includes missing AICX, stale Loctree, absent runtime receipt,
  renamed organization and ambiguous bare-name regressions;
- a real cold-start smoke proves two different providers receive the same pack.

## Explicit non-goals for 4.1.1

- automatic code edits during packet assembly;
- a second durable control plane;
- provider-specific summaries that fork repository truth;
- replacing native provider resume when an exact resumable session exists.

## Backlog for the next scaffold (not 4.1.1 scope) — scaffolded as ROADMAP_4.2.0

Items surfaced by ground truth on 2026-08-18; each is a small scaffold cut,
none is a release blocker.

1. **Dirty donors are a release feature, not an operator ritual.** `make release`
   refuses dirty donors (`../vc-terminal`, `../vc-frame`); the operator hand-rolls
   `git worktree add --detach` snapshots to get past it, and the ghost entry
   `snapshot2` (2026-08-11, pointing at a deleted `$TMPDIR/.tmpQUEtCY/snapshot`)
   was the residue — no script in either repo ever created a worktree
   (`git log --all -S'worktree add' -- scripts Makefile` → docs only). Add
   `--snapshot-donors` to `scripts/build-vibecrafted-release.sh`: create detached
   worktrees at donor HEADs inside the build work dir, record the SHAs in the
   receipt, reap with `git worktree remove --force` + `prune` in the trap, and a
   contract test that a run leaves `git worktree list` at exactly one entry.
   Superseded by ROADMAP_4.2.0 cut W1-b.
2. **Symlink-free distribution payload as a gate, not a hope.** The 3.7.0
   tarball shipped 4 symlink entries (`vetcoders.zsh -> vetcoders.sh`,
   `docs/install.sh -> ../install.sh`, a stray `.antigravitycli/<uuid>.json`
   pointing into an operator `$HOME`), which breaks Windows extraction and
   `core.symlinks=false` clones. The portable channel now builds outside the
   tree; verify on 4.x that the payload carries zero symlinks and add a
   `find <payload> -type l` gate beside the env-secret gate. Fold the
   in-repo aliases (`runtime`, `skills`, `docs/install.sh`,
   `vibecrafted_core/config/vc-frame -> ../../../config/vc-frame`) into that
   cut: a package must not depend on repo layout above itself.
3. **Import direction around `vibecrafted_core/__init__.py`.** Loctree audit
   (health 93) shows every non-breaking cycle (1 structural, 3 diamond,
   17 lazy) rooted in the package barrel re-exporting from modules that
   import back from the package. One deliberate cut on the hub (188 external
   importers) clears roughly 40% of the audit list; needs its own wave with
   the full Python gates, not a drive-by.
