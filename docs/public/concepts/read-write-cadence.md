---
title: "Read–Write cadence"
description: "Why the lifecycle alternates read-only perception with write action, and how the runtime enforces the split."
section: concepts
order: 30
---

# Read–Write cadence

The Vibecrafted lifecycle alternates two kinds of stages. WRITE stages
change code and must prove it with commits and green gates. READ stages
perceive — they assess, verify, and falsify — and must not mutate code at
all. The alternation is the core of the framework: no write happens without
a preceding read, and no read ends without handing a verdict to the next
write.

## The pipeline

| #   | Stage     | Phase | What it does                                                   |
| --- | --------- | ----- | -------------------------------------------------------------- |
| 1   | scaffold  | READ  | Map the ground truth and write the plan                        |
| 2   | implement | WRITE | Build the frame of the change                                  |
| 3   | review    | READ  | Findings-max assessment of each implementation                 |
| 4   | workflow  | WRITE | Orchestrated implementation passes                             |
| 5   | followup  | READ  | Assess trajectory — is the direction healthy                   |
| 6   | marbles   | WRITE | Swarm over-correction — flood every crack in deliberate excess |
| 7   | audit     | READ  | Falsification — verify the claimed truth actually landed       |
| 8   | polarize  | WRITE | Decisive cut — one truth remains, the excess is shaken off     |
| 9   | dou       | READ  | Definition of Undone — measure distance to shippable           |
| 10  | hydrate   | WRITE | Polish surfaces, packaging, onboarding                         |
| 11  | release   | —     | Deployment, publishing, signing — the operator-plane stage     |

The rhythm rule: every WRITE is bracketed by READ stages before and after.
Strokes without looking produce rubble; looking without strokes leaves the
block untouched.

## How the split is enforced

This is not an honor system. The runtime enforces the READ/WRITE contract
mechanically.

### READ stages declare `code_mutation`

Every READ-stage worker receives its phase contract in the stage prompt and
must declare in its report frontmatter whether it mutated code:

```yaml
---
run_id: dou-<timestamp>-<id>
agent: codex
skill: vc-dou
status: completed
code_mutation: false
---
```

The declaration is checked against evidence, not taken on faith. The
lifecycle runner attributes changes using the worker's own claim plus the
observed tree delta — a global delta caused by a concurrent Living Tree
writer is not automatically blamed on the READ worker.

### Violations are traced, not hidden

When a READ-stage worker did mutate code, the stage record carries a
`read_phase_violation` flag in the lifecycle state. The supervisor sees it
in `vibecrafted ship status <run_id> --json` and must resolve it before
moving the baton — typically by forcing an audit or rewinding the stage.

### WRITE stages must show receipts

A WRITE stage is not accepted on narrative. Before approving the baton to
the next stage, the supervisor confirms that:

- the promised commits actually exist on the working branch, and
- the declared quality gates (tests, lint, security scan) actually ran
  green.

```bash
vibecrafted ship status <run_id> --json   # truth before any button
vibecrafted ship approve <run_id>         # baton moves only with cargo
```

## Why the alternation exists

The bottleneck in AI-assisted coding is not intelligence — it is unbounded
accumulation of entropy and hallucination in a growing system. A model that
only writes will happily rewrite hundreds of lines to patch a small defect,
and each blind write compounds the drift.

The cadence converts that failure mode into a controlled loop:

1. **Perception before action.** A READ stage establishes what is actually
   there, so the next WRITE cuts with sight, not memory.
2. **Falsification after action.** A READ stage after each WRITE asks the
   only question that matters: _what is still wrong?_ Verdicts are earned
   by evidence; the default is UNVERIFIED, never PASS.
3. **Deliberate excess, then a decisive cut.** The marbles stage
   over-applies fixes on purpose; audit verifies what landed; polarize
   strips the excess back to one axis of truth. The excess exists so there
   is something to shake off.

Convergence through counterexample is not one tool — it is an emergent
property of this rhythm. Breaking the rhythm (writing without a prior read,
or reading without handing a verdict forward) breaks the core.

## Related pages

- [Delivery proof](/docs/delivery-proof/) — how claims become settled facts.
- [Living Tree](/docs/living-tree/) — the shared checkout the cadence runs on.
