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

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start vibecrafted
```

Then launch this workflow through the command deck, not raw `skills/...` paths:

```bash
vibecrafted <workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --file '/path/to/plan.md'
```

```bash
vc-<workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --prompt '<prompt>'
```

If `vc-<workflow> <agent>` is invoked outside Zellij, the framework will attach
or create the operator session and run that workflow in a new tab. Replace
`<workflow>` with this skill's name. Prefer `--prompt` when the operator wants a
fresh audit of the current project and `--file` when the operator already has a
plan, report, or extracted intent bundle to compare against the tree.

### Concrete dispatch examples

```bash
vibecrafted intents codex --prompt 'Check which planned implementations actually landed in CodeScribe'
vc-intents claude --prompt 'Build a 20-item checklist from intents and mark done/partial/missing'
vibecrafted intents gemini --file ~/.vibecrafted/artifacts/VetCoders/CodeScribe/2026_0419/plans/research-plan.md
```

<details>
<summary>Foundation Dependencies (Loaded with framework)</summary>

- [vc-aicx](../foundations/vc-aicx/SKILL.md) — intention retrieval, source chunks, recent decision memory.
- [vc-loctree](../foundations/vc-loctree/SKILL.md) — live repo perception and structural verification.
</details>

> Plans are cheap.
> The truth is whether the plan actually landed in runtime.

## Core doctrine

`vc-intents` is not a review skill and not a planning skill.

It is the reconciliation layer between:

- what the team meant to build
- what the sessions said was next
- what the codebase actually contains now

This skill exists because the other surfaces each stop too early:

- `vc-init` restores context but does not reconcile completion
- `vc-review` judges a diff, not the original intention
- `vc-scaffold` creates future shape, not present truth
- `vc-marbles` hardens what exists, but does not first normalize which promises are real

`vc-intents` answers a narrower and sharper operator question:

- what from the plan is really in the code
- what is only half-landed
- what never happened
- what was replaced by a better shape
- what is the highest remaining truth

## Why this works

Agent sessions are rich in intent but noisy in form.

`aicx intents` is the right first cut because it extracts structured intention
signals from prior work. But raw intent output is still not the truth. It is
desire, momentum, unfinished conversation, and sometimes hallucinated certainty.

The second half of the skill is what matters:

- reduce the raw intent stream to implementation candidates
- inspect the live repo
- refuse to overclaim
- classify every candidate against present runtime truth

This is how we stop treating plans, changelogs, and session summaries as if they
were the product.

## What this skill does

One invocation of `vc-intents` performs one bounded intention-to-truth audit:

1. retrieve recent project intents from `aicx`
2. open the referenced `source_chunk` files for the shortlisted items
3. reduce the noisy stream into a bounded checklist of implementation candidates
4. verify each candidate against the live tree
5. classify each candidate
6. emit the checklist plus the highest remaining truth
7. stop

By default, the checklist target is **20 meaningful implementation items**.

If there are fewer than 20 real implementation candidates, report fewer.
Do not pad the audit with fluff, vibes, or duplicate promises.

## Retrieval protocol

### Quick operator lane

Use the fast lane first when the operator wants the recent shape immediately:

```bash
aicx intents -p <ProjectName> --emit json 2>&1 | tail -200
```

This is a triage surface, not final evidence.

### Truth lane

Before classifying an item, open the referenced `source_chunk` files and recover
the actual plan context around the shortlisted intents.

Minimal discipline:

1. pull `aicx intents`
2. shortlist implementation candidates
3. open the backing chunks
4. only then normalize into checklist items

Do not classify from a one-line summary alone when the source chunk is available.

## Verification protocol

After extracting the checklist, verify each item against the live repo.

Preferred order:

1. `vc-loctree` / loctree MCP for repo shape, scope, and hot files
2. targeted symbol or path checks
3. `rg` / shell reads for local detail
4. docs only as supporting evidence

The repository is the primary court.
Docs are supporting witnesses.

### Evidence hierarchy

Use this hierarchy when classifying:

1. **Runtime code path**
   - live implementation reachable from current code
2. **Test-bearing path**
   - tests prove the path exists or contract is exercised
3. **UI / CLI / config surface**
   - user-visible or operator-visible surface exists
4. **Docs / CHANGELOG / plans**
   - supporting evidence only, never enough by themselves for `done`

If all you have is docs or a changelog, that item is not `done`.

## Classification contract

Every checklist item must end in exactly one of these states:

- `done`
- `partial`
- `missing`
- `superseded`
- `non-code`

### `done`

Use only when the intended implementation is materially present in the live
codebase.

Minimum bar:

- there is a real code path, config surface, or runtime contract
- the item is not merely mentioned in docs or a changelog

### `partial`

Use when the shape exists, but the original promise is not fully landed.

Examples:

- config exists but no UI surface
- UI wording exists but runtime behavior still lies
- core logic exists but no delivery path or no operator surface

### `missing`

Use when the plan is real and specific, but no meaningful implementation surface
is present in the live tree.

This requires a good-faith search, not a shrug.

### `superseded`

Use when the original intent no longer makes sense because a different shape
replaced it.

Do not use `superseded` to hide failure.
Name the replacing shape explicitly.

### `non-code`

Use when the plan item is real but belongs primarily to:

- distribution
- operations
- release choreography
- customer / product surface

These items still matter.
They simply do not belong in a "sits in code" verdict.

## Highest truth

Every run must end with a section named:

**Highest truth**

This is not a summary.
It is the single most important unresolved reality the operator should act on next.

Good examples:

- "The UI says qube-daemon autostarts, but no runtime path actually starts it."
- "The silence discriminator exists in core, but the operator has no settings surface to steer it."
- "The app bundle is signed and notarizable, but the update path is still manual."

Bad examples:

- "Some items are partial."
- "There is more work to do."
- "We should continue improving."

The highest truth should hurt a little.
If it does not create leverage, it is too soft.

## Output contract

Return the audit in this shape:

1. **Intent source**
   - project
   - retrieval window or source file(s)
   - shortlist method

2. **Checklist**
   - up to 20 items
   - each with:
     - `status`
     - `item`
     - `why`
     - `evidence`

3. **Highest truth**
   - one paragraph

4. **Next leverage**
   - the 1-3 most valuable follow-up moves

### Evidence format

Prefer concise repo references:

- file path
- symbol name
- command used to verify

Do not dump huge logs.
Do not bury the verdict under grep spam.

## Scope discipline

The unit of analysis is not "all thoughts ever had about the project."

Prefer:

- recent, relevant intent windows
- implementation-shaped items
- one current branch / workspace truth

Filter out:

- pure ideology
- tooling philosophy without implementation consequence
- duplicate phrasings of the same feature
- operator chatter that never hardened into a concrete implementation candidate

## What this skill does not do

Do not:

- turn `aicx intents` into a blind backlog generator
- mark items `done` from docs alone
- confuse a branch name with shipped implementation
- count a TODO comment as a landed feature
- pad the checklist to 20 with low-signal noise
- drift into line-level PR review
- rewrite the plan into a new roadmap unless the operator asked for that
- treat "present in code" and "working end-to-end" as automatically identical

If the operator wants diff quality, use `vc-review`.
If the operator wants new architecture, use `vc-scaffold` or `vc-partner`.
If the operator wants the gaps closed, escalate into `vc-ownership` or `vc-marbles`.

## Relation to other skills

### Use after `vc-init`

`vc-intents` becomes much stronger after `vc-init`, because the worker already
knows the structural shape of the repo and the intention surface.

### Use before `vc-marbles`

When the operator says:

- "what from the plan actually landed?"
- "what is still a lie?"
- "which promises are fake-complete?"

run `vc-intents` first, then send the sharpest remaining lie into `vc-marbles`.

### Use before `vc-ownership`

When the user wants the missing items closed end-to-end, `vc-intents` should
first define the truth surface so ownership mode is acting on reality, not drift.

## Operator heuristics

When running this skill, the operator should prefer:

- fewer, sharper items over a bloated list
- explicit evidence over confidence theater
- runtime truth over plan loyalty
- naming the lie over cosmetically softening it

The goal is not to prove that the team made progress.
The goal is to know exactly what shape progress actually took.

## Final reminder

This skill is not about preserving the dignity of the plan.

It is about preserving the dignity of reality.

When the plan and the repo disagree, trust the repo first.
When the repo and runtime disagree, trust runtime first.
When all three disagree, name the fracture clearly and call it the highest truth.
