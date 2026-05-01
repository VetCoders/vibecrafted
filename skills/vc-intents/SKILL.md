---
name: vc-intents
version: 1.0.1
description: >
  Operator-side intention-to-runtime truth audit. Use when the team needs to
  know which planned implementations actually landed in code, which are only
  partially present, which never materialized, and what the highest remaining
  truth is. This skill pulls intentions from aicx, reduces them to a bounded
  implementation checklist, then verifies each item against the live repo.
  Trigger phrases: "intents", "co z planu siedzi", "which planned items exist",
  "what from the plan is in code", "check intent coverage", "planned vs code",
  "highest truth", "checklist from intents".
---

# vc-intents — Intention To Runtime Truth

## Operator Entry

Standard launcher (`vibecrafted start` / `vc-start`, then `vc-<workflow> <agent> [--prompt|--file ...]`).
Prefer `--prompt` for a fresh audit and `--file` when an existing plan, report,
or extracted intent bundle should be compared against the tree.

```bash
vibecrafted intents codex --prompt 'Check which planned implementations actually landed in CodeScribe'
vc-intents claude --prompt 'Build a 20-item checklist from intents and mark done/partial/missing'
vibecrafted intents gemini --file ~/.vibecrafted/artifacts/VetCoders/CodeScribe/2026_0419/plans/research-plan.md
```

Foundation deps: `vc-aicx` (intention retrieval, source chunks, recent decision
memory), `vc-loctree` (live repo perception, structural verification).

> Plans are cheap.
> The truth is whether the plan actually landed in runtime.

## Core doctrine

`vc-intents` is not a review skill and not a planning skill. It is the
reconciliation layer between:

- what the team meant to build
- what the sessions said was next
- what the codebase actually contains now

This skill exists because the other surfaces stop too early:

- `vc-init` restores context but does not reconcile completion
- `vc-review` judges a diff, not the original intention
- `vc-scaffold` creates future shape, not present truth
- `vc-marbles` hardens what exists but does not first normalize which promises are real

It answers the operator's narrower question: what from the plan is really in
the code, what is half-landed, what never happened, what was replaced by a
better shape, and what is the highest remaining truth.

## Why this works

Agent sessions are rich in intent but noisy in form. `aicx intents` extracts
structured intention signals from prior work — but raw intent output is still
not the truth. It is desire, momentum, unfinished conversation, sometimes
hallucinated certainty.

The second half is what matters: reduce the raw intent stream to implementation
candidates, inspect the live repo, refuse to overclaim, classify every candidate
against present runtime truth. This is how we stop treating plans, changelogs,
and session summaries as if they were the product.

## What this skill does

One invocation = one bounded intention-to-truth audit:

1. retrieve recent project intents from `aicx`
2. open referenced `source_chunk` files for shortlisted items
3. reduce the noisy stream into a bounded checklist of implementation candidates
4. verify each candidate against the live tree
5. classify each candidate
6. emit checklist + highest remaining truth
7. stop

Default checklist target: **20 meaningful implementation items**. If fewer real
candidates exist, report fewer. Do not pad with fluff or duplicate promises.

## Retrieval protocol

### Quick operator lane

```bash
aicx intents -p <ProjectName> --emit json 2>&1 | tail -200
```

Triage surface, not final evidence.

### Truth lane

Before classifying, open the referenced `source_chunk` files and recover the
actual plan context around shortlisted intents. Discipline:

1. pull `aicx intents`
2. shortlist implementation candidates
3. open the backing chunks
4. only then normalize into checklist items

Do not classify from a one-line summary alone when the source chunk is
available.

## Verification protocol

After extracting the checklist, verify each item against the live repo.
Preferred order:

1. `vc-loctree` / loctree MCP — repo shape, scope, hot files
2. targeted symbol or path checks
3. `rg` / shell reads for local detail
4. docs only as supporting evidence

The repository is the primary court. Docs are supporting witnesses.

### Evidence hierarchy

1. **Runtime code path** — live implementation reachable from current code
2. **Test-bearing path** — tests prove the path exists or contract is exercised
3. **UI / CLI / config surface** — user/operator-visible surface exists
4. **Docs / CHANGELOG / plans** — supporting only, never enough alone for `done`

If all you have is docs or a changelog, that item is not `done`.

## Classification contract

Every checklist item must end in exactly one state: `done`, `partial`,
`missing`, `superseded`, `non-code`.

- **`done`** — intended implementation is materially present. Real code path,
  config surface, or runtime contract. Not merely mentioned in docs.
- **`partial`** — shape exists but the original promise is not fully landed
  (config without UI, UI wording without runtime, core logic without delivery
  path or operator surface).
- **`missing`** — plan is real and specific but no meaningful implementation
  surface in the live tree. Requires good-faith search, not a shrug.
- **`superseded`** — the original intent no longer makes sense because a
  different shape replaced it. Name the replacing shape explicitly. Do not use
  to hide failure.
- **`non-code`** — real plan item but belongs primarily to distribution,
  operations, release choreography, customer/product surface. Still matters;
  simply does not belong in a "sits in code" verdict.

## Highest truth

Every run must end with a section named **Highest truth**. Not a summary — the
single most important unresolved reality the operator should act on next.

Good:

- "The UI says qube-daemon autostarts, but no runtime path actually starts it."
- "Silence discriminator exists in core, but the operator has no settings surface to steer it."
- "App bundle is signed and notarizable, but the update path is still manual."

Bad:

- "Some items are partial."
- "There is more work to do."
- "We should continue improving."

The highest truth should hurt a little. If it does not create leverage, it is
too soft.

## Output contract

1. **Intent source** — project, retrieval window or source files, shortlist method
2. **Checklist** — up to 20 items, each with `status`, `item`, `why`, `evidence`
3. **Highest truth** — one paragraph
4. **Next leverage** — 1-3 most valuable follow-up moves

### Evidence format

Prefer concise repo references: file path, symbol name, command used to verify.
Do not dump huge logs or bury the verdict under grep spam.

## Scope discipline

Unit of analysis is not "all thoughts ever had about the project." Prefer
recent, relevant intent windows; implementation-shaped items; one current
branch / workspace truth.

Filter out: pure ideology · tooling philosophy without implementation
consequence · duplicate phrasings · operator chatter that never hardened into
a concrete candidate.

## What this skill does not do

- Turn `aicx intents` into a blind backlog generator
- Mark items `done` from docs alone
- Confuse a branch name with shipped implementation
- Count a TODO comment as a landed feature
- Pad the checklist to 20 with low-signal noise
- Drift into line-level PR review
- Rewrite the plan into a new roadmap (unless the operator asked)
- Treat "present in code" and "working end-to-end" as automatically identical

If the operator wants diff quality → `vc-review`. New architecture →
`vc-scaffold` or `vc-partner`. Gaps closed → `vc-ownership` or `vc-marbles`.

## Relation to other skills

- **After `vc-init`** — much stronger because the worker already knows the
  structural shape and intention surface.
- **Before `vc-marbles`** — when operator asks "what from the plan actually
  landed?" / "which promises are fake-complete?", run `vc-intents` first, then
  send the sharpest remaining lie into `vc-marbles`.
- **Before `vc-ownership`** — define the truth surface so ownership mode acts
  on reality, not drift.

## Operator heuristics

- Fewer, sharper items over a bloated list
- Explicit evidence over confidence theater
- Runtime truth over plan loyalty
- Naming the lie over cosmetically softening it

The goal is not to prove progress was made. The goal is to know exactly what
shape progress actually took.

## Final reminder

This skill is not about preserving the dignity of the plan. It is about
preserving the dignity of reality.

When plan and repo disagree, trust the repo first. When repo and runtime
disagree, trust runtime first. When all three disagree, name the fracture
clearly and call it the highest truth.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
