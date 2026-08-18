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
