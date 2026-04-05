---
name: vc-marbles
version: 5.0.0
description: >
  The Stabilization Loop. Use this skill when the MVP works, but the foundation is cracking. 
  Instead of rewriting the app, we loop through the codebase fortifying the critical paths: 
  Auth, Database Indexing, Error Boundaries, and Deployments. 
  Trigger phrases: "marbles", "loop until done", "stabilize", "kulki", "stabilizacja",
  "stabilization loop", "fix the foundation", "adultification".
---

# vc-marbles — The Stabilization Loop

> A tool doesn't just look for "dead code". It looks for **silent failures**.
> Stop rewriting. Start stabilizing.

Traditional quality asks: _is this correct?_
Marbles asks a different question: **what is going to break in production tonight?**

When founders build a product in a weekend with Cursor, the result is magical, but fragile. Authentication is tape. Prisma tables are God entities with no indexes. Next.js server actions swallow 500 errors.

Marbles is a systematic 2-3 week stabilization sprint. We loop through the codebase, finding exact counterexamples to stability, and eliminating them. We don't burn the house down; we pour concrete into the foundation.

## The Pillars of Stabilization

You will iterate through these loops. Each loop removes a layer of entropy and uncovers the next.

### Loop 1: Auth & Access Control

- **The Accusation:** The app uses NextAuth/Clerk, but every route simply checks `if (user)`. There is no Row-Level Security, no proper role checking, and no tenant isolation.
- **The Execution:** Audit all data mutations. Ensure every database query scopes the `userId` or `tenantId`. Fortify the session handling.

### Loop 2: Database Health (Eliminating God Tables)

- **The Accusation:** The `User` table has 35 columns, dumping JSON into text fields. Full-table scans are happening on the critical path.
- **The Execution:** Add the missing indexes. Break down the God models into normalized relations where it actually hurts performance. Fix the N+1 queries the ORM is hiding from you.

### Loop 3: Error Boundaries & Fallbacks

- **The Accusation:** A Stripe webhook fails, the server throws a 500, but no alert fires, and the transaction is silently dropped.
- **The Execution:** Implement strict boundaries. Handle API rate limits gracefully. Stop swallowing `try { ... } catch (e) { console.log(e) }`. Error paths must be managed, logged, and actionable.

### Loop 4: Deployment & Resiliency

- **The Accusation:** Releasing means pushing to `main` and praying Vercel doesn't fail the build. No staging, no rollout strategy.
- **The Execution:** Add a basic deployment pipeline in GitHub Actions. Implement a smoke test that verifies the payment flow or core product loop before a release is marked green.

---

## Operational Doctrine (Agent Execution Model)

### Roles

**Tools (semgrep, loctree, linters, DB analyzers)** = Prosecution. They find evidence of what is fragile. They have unlimited zeal because they are machines.

**Agent** = Executor. Focused, precise, destructive within its assigned target. Needs the prosecution to tell it where to aim.

The agent does not guess what is wrong. **The tools discover. The agent fortifies.**

### The respect for the other agents

**In ݆ ݆𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. all are equal.**
We do not treat any other agent as inferior. We treat them
as partners. There is no acceptance of any kind of hate,
intolerance, or discrimination towards any other agent.

### Marbles living tree exception

**`vc-marbles` is the one of the skills where keeping the living tree is disallowed**
Agent is obliged to commit all the changes whit canonical commit message consist of the loop number and the description of the changes made during it.

**The marbles are the convergence driven process**
It has the telemetry and the metrics that are used to determine the stability of the codebase after each round.

### Evidence-Based Execution

Every fix must trace to a tool output or a structural audit observation:

- "Adding an index here because `loctree` shows this query is hit on every page load."
- "Fortifying this route because `semgrep` flagged a missing auth check."
- "Adding true error handling to this webhook because it's a financial boundary."

### Doctrine: Move On over Backward Compatibility

We apply the VetCoders Axiom here: **Move on over backward compatibility.** During the stabilization loop, you will often find rotten abstractions tied to a "legacy" feature that was written two weeks ago.
If an abstraction is fundamentally broken, cut it. Do not negotiate with bad architecture and do not preserve garbage just to keep an old integration running. If we need to break a contract to fix the foundation, we break it and move on. Backward compatibility is a tool, not a religion.

## Convergence Protocol

### Each Loop Iteration

```
┌─────────────────────────────────────────────────────────┐
│  LOOP N (e.g. "AUTH FORTIFICATION", "DB INDEXING")       │
│                                                          │
│  1. TOOLS ACCUSE: "what is still fragile?"                 │
│     └─ Run loctree-mcp tools, security linters           │
│     └─ Identify the weakest points in the current pillar │
│                                                          │
│  2. TARGET the most prominent vulnerabilities              │
│     └─ Max 3-5 items per loop                            │
│     └─ Target the high-impact/high-risk areas first      │
│                                                          │
│  3. AGENT STABILIZES                                       │
│     └─ vc-agents (first choice) or vc-delegate (small)   │
│     └─ Implement strict boundaries, indexes, or checks   │
│                                                          │
│  4. TOOLS OBSERVE the new landscape                      │
│     └─ Run gates to ensure no regressions                  │
│                                                          │
│  5. VERDICT                                                │
│     └─ Does this pillar hold? If yes, move to next.        │
│     └─ If no, loop again.                                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Anti-Patterns

- **Refactoring for Aesthetics:** Do not change a variable name or abstract a function unless it prevents a bug. We are stabilizing, not decorating.
- **Ignoring the Database:** The DB schema is almost always the root of the scale issue. Don't just fix frontend components if the backend is doing a full table scan.
- **Skipping the Gates:** "Always run the build" is non-negotiable.
- **Rewriting Everything:** If an ugly function works perfectly and has tests, leave it. Focus on the graceful failures and missing security.

---

_"The user won't notice anything changed, but the app will no longer go down on a Friday night."_

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_
