---
title: "Skills overview"
description: "What a Vibecrafted skill is, the three ways to invoke one, and how READ and WRITE skills divide the lifecycle."
section: skills
order: 10
---

# Skills overview

A skill is a packaged workflow contract: one operator situation mapped to one
named workflow that produces one decisive outcome. Each skill ships as a
directory with a `SKILL.md` contract, examples, and optional scripts — and
most ship with a launcher, so the same contract runs identically whether a
human types a command or a supervisor dispatches a fleet.

## Anatomy

```text
skills/vc-review/
├── SKILL.md         # the contract: triggers, acceptance criteria, anti-patterns
├── README.md        # operator-facing overview
├── examples/        # realistic trigger + expected behavior pairs
├── scripts/         # optional shipped scripts
└── references/      # deeper docs the agent loads on demand
```

`SKILL.md` opens with YAML frontmatter (`name`, `description`, `version`) and
is what the launcher matches against when you type a freeform request. The
description carries the trigger phrases; the body carries the procedure,
acceptance criteria, and anti-patterns.

## Three invocation paths

Every core skill is reachable three ways; all three execute the same
contract:

1. **User-launched worker.** Skill-first grammar from any terminal:

   ```bash
   vibecrafted review claude       # run vc-review with the claude agent
   vibecrafted implement codex     # run vc-implement with the codex agent
   ```

   The launcher spawns a headless worker, records the run in the control
   plane, and writes a report plus transcript and metadata sidecars under
   `~/.vibecrafted/artifacts/<org>/<repo>/<date>/`.

2. **Interactive slash command.** Inside an agent session, `/vc-<skill>`
   (for example `/vc-review`) loads the same contract and executes it in
   session — no worker process, full conversational control.

3. **Operator dispatch.** A supervising agent or the dispatch lane
   (`vibecrafted dispatch`) launches skills as part of a planned multi-wave
   run, awaits the durable artifacts, and verifies the reports. The
   `vc-ship` umbrella chains eleven stages this way as one supervised
   lifecycle run.

Whichever path you use, the outcome is judged by the same bar: a report on
disk and a control-plane record — never terminal output alone.

## READ and WRITE skills

The lifecycle alternates perception and mutation — the Read–Write cadence:

- **READ skills** observe and judge without mutating the tree: `vc-init`
  (context bootstrap), `vc-review` (bounded findings), `vc-followup`
  (trajectory audit), `vc-audit` (per-plan falsification), `vc-dou`
  (Definition of Undone gap analysis), `vc-intents`, `vc-trust`,
  `vc-research`. Their product is evidence: findings with grades, verdicts,
  requirement matrices.
- **WRITE skills** change the repository or its packaging: `vc-scaffold`
  (plans), `vc-implement`, `vc-workflow`, `vc-marbles`, `vc-polarize`,
  `vc-prune`, `vc-decorate`, `vc-hydrate`, `vc-release`, `vc-justdo`. Their
  product is committed work plus a report proving it.

A WRITE stage is never its own judge: implementation is followed by READ
stages (review, followup, audit, DoU) before the next WRITE cut. That
alternation is what lets a fleet run long chains without drifting from the
plan.

A third, smaller class exists: **foundation skills** (structural perception,
intent retrieval) that have no worker of their own and load inside other
skills, and **meta skills** (`vc-ship`, `vc-dispatch`, `vc-operator`) that
conduct other skills rather than doing repo work directly.

## Where to go next

- [Skills catalog](/docs/skills-catalog/) — every shipped skill, grouped by
  pipeline position.
- [Authoring skills](/docs/authoring-skills/) — write and install your own.
