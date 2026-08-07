---
title: "Lifecycle Overview"
description: "The vc-ship umbrella: one mission through eleven supervised stages, the baton relay, stage reports as cargo, and launch forms."
section: lifecycle
order: 10
---

# Lifecycle Overview

`vc-ship` is the umbrella that runs one mission through the full eleven-stage
lifecycle as a single supervised run. Instead of you launching eleven skills
by hand and carrying context between them, the lifecycle runner launches each
stage as its own agent run, records what moved, and hands a baton — with the
previous stage's report as cargo — to the next stage.

## The Read–Write cadence

The pipeline alternates READ and WRITE phases: perception before mutation,
proof after pressure.

```text
scaffold → implement → review → workflow → followup → marbles
        → audit → polarize → dou → hydrate → release
  READ      WRITE     READ     WRITE      READ      WRITE
          → READ    → WRITE  → READ    → WRITE   → WRITE
```

READ stages may produce reports, caches, transcripts, and run state — they
must not modify project code. WRITE stages may modify code, remove legacy,
refactor, and generate missing pieces. In awaited runs the runner
fingerprints the worktree before and after every stage; a READ stage that
changes code is marked a lifecycle failure. The per-stage detail lives in
[Stages](/docs/stages/).

## Launch forms

```bash
vibecrafted ship <agent> --file mission.md        # mission from a file
vibecrafted ship <agent> --prompt "Run the full lifecycle for <goal>"
vibecrafted ship <agent> --file mission.md --start-stage audit
vibecrafted ship <agent> --file mission.md --await-stages
vc-ship <agent> --checkpoint <stage> --file mission.md   # shell shortcut
```

- A bare `vc-ship <agent>` is valid: it uses a default full-lifecycle
  repository prompt after the context atlas loads.
- `--start-stage <stage>` (or `--checkpoint <stage>`) resumes from a specific
  stage instead of `scaffold`.
- `--await-stages` makes the supervisor wait on each stage, observe exit
  truth, record commits and changed files, and hand the baton automatically.
  Without it, stages launch-and-return and you drive transitions with
  `approve` — see [Supervision](/docs/supervision/).

## Baton and cargo

The baton is the relay token: it names the pending `next_stage` and the
agent holding it. The cargo is the stage report — one stage's report is the
next stage's input. The operator (human or supervising agent) reads reports
between stages, not transcripts during them.

Workers steer the baton through their report frontmatter: `next_stage` moves
the umbrella forward or backward, `next_agent` hands the baton to another
agent, and `dou_index` reports how many Definition-of-Undone findings remain
(zero is the launch-ready target). Unknown stages or agents are ignored —
steering is manifest-validated.

## Where lifecycle state lives

Each lifecycle run writes its state under the control plane:

```text
~/.vibecrafted/control_plane/lifecycle_runs/<run_id>/state.json
~/.vibecrafted/control_plane/lifecycle_runs/<run_id>/report.md
```

Run ids look like `life-ship-<timestamp>-<id>`. `state.json` is a versioned
external contract (`"schema": "vibecrafted.lifecycle.v1"`); within v1,
changes are additive only. It carries run identity, the manifest, the baton,
per-stage records, operator actions, and DoU state. The single writer is the
lifecycle runtime — consumers (dashboards, servers, MCP clients) are readers
and must mutate only through the operator verbs.

Each stage still launches through the same core runtime as
`vibecrafted <skill> <agent>`, so ordinary run truth (reports, transcripts,
run meta) applies unchanged — see
[Observe and await](/docs/observe-await/).

## Single-stage lifecycle commands

Some skills also run as one-stage lifecycle manifests, giving you the same
state tracking and operator verbs for a single pass:

```bash
vibecrafted dou claude --prompt "Audit launch readiness"
vibecrafted audit claude --file plan.md
vibecrafted marbles codex --count 3
```

## When to use the lifecycle

Use `ship` when the mission is "take this from idea to release" and you want
one supervised relay with recorded evidence at every handoff. Use individual
[workflow launchers](/docs/workflow-launchers/) when you need one pass of one
stage. Use [dispatch](/docs/dispatch-overview/) when the work is already
decomposed into a deterministic list of cuts with machine-checkable
verifiers.
