# SCAFFOLD.md Template

Use this template for planning output. Strip out the comments in your actual output.

```markdown
---
run_id: <generated-unique-id>
agent: <claude|codex|gemini>
skill: <vc-scaffold|vc-workflow|vc-implement>
project: <repo-name>
status: pending
created: <ISO-8601 timestamp>
---

# Architecture Plan: [Project Name]

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

- Legacy system rewrite (not happening)
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

Each task is agent-ready. Agents will execute in parallel when dependencies allow.

### Task 1: [Imperative title]
**Produces:** [What code/config/tests get created]
**Depends on:** [Task X, infrastructure ready]
**Owner:** [Agent skill or human role]
**Acceptance:** [How we test it]

Example:
```

Task: Build authentication middleware
Produces: /middleware/auth.ts, /tests/auth.test.ts
Depends on: Infrastructure up, database schema
Owner: Core backend agent
Acceptance: Middleware rejects invalid tokens, passes valid tokens, tests at 85%+ coverage

```

## Test Gates

Each phase has gates. Don't move to the next phase unless gates pass.

- **Unit tests:** 80%+ coverage on core paths
- **Integration tests:** Services talk to each other correctly
- **Performance:** P95 latency under [threshold]
- **Security:** No exposed secrets, auth enforced

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
5. When all phase 1 tasks pass gates, move to phase 2

No handwaving. Clear work. Clear criteria. That's how founders ship.
```
