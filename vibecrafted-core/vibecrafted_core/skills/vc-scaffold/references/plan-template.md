# SCAFFOLD.md Template

Use this template for planning output. Strip out the comments in your actual output.

```markdown
---
run_id: <generated-unique-id>
agent: <claude|codex|gemini>
skill: <vc-scaffold|vc-workflow|vc-implement>
project: <repo-name>
status: pending
vector: <stabilize|implement|recon|e2e> # selects the gate profile = what counts as delivery
created: <ISO-8601 timestamp>
---

# Architecture Plan: [Project Name]

## OPERATOR_CHOSEN_BASELINE

Record the absolute Git root, operator-selected branch, full 40-character SHA,
exact status, `git fetch --all --prune` result with UTC timestamp, upstream ref
and relation, and selection source. This record is immutable provenance.

Before acting, every receiver re-checks root/branch/HEAD/status. Exact SHA passes.
A descendant on the same root and branch passes only after
`git merge-base --is-ancestor <baseline_sha> HEAD`, reviewed drift, and re-reading
affected files. Any other relation is DIVERGED-STOP; never checkout/reset/rebase/
stash to manufacture agreement.

## Problem Statement

[1-2 sentences. What problem are we solving? Why does it matter?]

Example: "The monolith is becoming unmaintainable. We need to extract the payment service into its own service so teams can ship independently without coordinating deploys."

## Key Architectural Decisions

### Decision 1: [Name]

**Choice:** [What we're doing]
**Trade-off:** [What we're giving up]
**Why:** [Why this is better than the alternative]

### Decision 2: [Name]

**Choice:** [What we're doing]
**Trade-off:** [What we're giving up]
**Why:** [Why this is better than the alternative]

(Keep to 3-5 decisions. Not every technical detail.)

## Scope Boundaries

### Phase 1: MVP (This Sprint/Cycle)

**In scope:**

- Feature/component A
- Feature/component B
- Test infrastructure

**Out of scope:**

- Feature X (nice to have, ships phase 2)
- Optimization Y (not blocking MVP)

**Explicitly out of scope:**

- Rewrite of the old system (not happening)
- Migrate to language Z (out of bounds)

## Architecture Overview

[ASCII diagram or brief description]

Example:
```

User → API Gateway → Auth Service → Payment Service → Stripe
↓
Cache Layer
↓
Database

```

## Task Breakdown

Each task is agent-ready. Agents execute in parallel when dependencies allow. Each task carries a
`state` marker `[ ] [~] [?] [!] [x]` (see references/measure-core.md); only a delivery-verifier flips
`[~]→[x]`. vc-operator reads the `state` column to trigger/stop.

### Task 1: [Imperative title]   `state: [ ]`
**Vector:** [stabilize|implement|recon|e2e]
**Produces:** [What code/config/tests get created]
**Depends on:** [Task X, infrastructure ready]
**Owner:** [Agent skill or human role]
**Delivery-verifier:** [the non-fakeable test that flips [~]→[x]; without it the task ships as [?]]
**Acceptance:** [intent vs baseline — what proves delivery ≈ claim, not just "agent said so"]
**Pre-handoff baseline:** [immutable OPERATOR_CHOSEN_BASELINE + current descendant HEAD/status + reviewed drift + gates/known failures + exact next instruction; mismatch = DIVERGED-STOP]

Example:
```

Task: Build authentication middleware state: [ ]
Vector: implement
Produces: /middleware/auth.ts, /tests/auth.test.ts
Depends on: Infrastructure up, database schema
Owner: Core backend agent
Delivery-verifier: `pnpm test auth` green — rejects invalid tokens, passes valid; flips [~]→[x]
Acceptance: intent (auth enforced on all routes) vs baseline (routes open); delivery proven by the verifier, not "agent said so"
Pre-handoff baseline: immutable OPERATOR_CHOSEN_BASELINE, current descendant HEAD/status, reviewed drift, verifier output, known failures, next instruction; mismatch = DIVERGED-STOP

```

## Test Gates (per Vector profile)

Each phase has a delivery-gate selected by its `Vector` (see references/measure-core.md) — the gate
defines what counts as delivery, so it differs by Vector. Don't advance a phase until its gate flips
every cut `[~]→[x]`.

- **implement** → feature works + tests green on core paths
- **stabilize** → the bleeding stops + a regression/canary gate green (busy ≠ dead)
- **recon** → map/answer delivered with evidence refs
- **e2e** → the full path runs end-to-end
- **always** → no exposed secrets; security gate not skipped (`--no-verify` forbidden)

## Living Tree Note

This plan is alive. It changes as we learn. When you change the plan:

1. **Date** the change
2. **Explain why** (new constraint, discovered dependency, market shift)
3. **Re-run task breakdown** if scope changed
4. **Update acceptance criteria** if definitions shifted

Document the reasoning. Future engineers will thank you.

---

## Running This Plan

1. Read this document top-to-bottom
2. For each task, spin up an agent or assign to a human
3. Each task produces artifacts (code, tests, docs)
4. Validate against acceptance criteria
5. Capture the pre-handoff baseline before assigning the next owner
6. When all phase 1 tasks pass gates, move to phase 2

No handwaving. Clear work. Clear criteria. That's how founders ship.
```
