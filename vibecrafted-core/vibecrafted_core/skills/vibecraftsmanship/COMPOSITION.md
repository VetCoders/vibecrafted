# Vibecraftsmanship — Composition with Other Skills

Vibecraftsmanship is the meta-doctrine. It does not replace any skill —
it tells you which skill to invoke and why. The skill bundle stratifies
into 4 layers, vibecraftsmanship cross-cuts only one of them.

---

## Skill stratification

### Layer 1 — Foundations (pre-charter)

Run before any tactical charter. Provide perception, intent, and
ground truth.

- `vc-init` — perception + intentions + ground truth triad
- `vc-scaffold` — founder-first architecture planning when scope is fuzzy

**Relation to vibecraftsmanship**: foundations supply the substrate
that gust/siła/rzeczywistość operate on. You can't pick a posture
without knowing the repo truth.

### Layer 2 — Postures (the 3 tactical charters)

How the operator-agent sits relative to the work. vibecraftsmanship is
the meta-decision **among** these three.

- `vc-ownership` — solo end-to-end delivery, agent drives full slice
- `vc-operator` — multi-wave fleet conduct, agent conducts other agents
- `vc-partner` — shared executive steering, operator + agent co-decide

**Relation to vibecraftsmanship**: vibecraftsmanship's routing table
picks one of these three at session start (and reroutes when drift
detected mid-flight). See routing table below.

### Layer 3 — Techniques (orthogonal to posture)

Workflow patterns available WITHIN any posture. Marbles can be used
inside ownership, operator, or partner. So can research, audit,
review, polarize, prune.

- `vc-marbles` — loop convergence on existing code
- `vc-research` — triple-agent gap-free research
- `vc-audit` — per-plan spec falsification
- `vc-review` — per-implementation diff perception
- `vc-followup` — trajectory direction checking
- `vc-polarize` — decisive one-axis cut after marbles
- `vc-prune` — repo curation + silencer strip
- `vc-intents` — intention-vs-runtime truth audit
- `vc-delegate` — native subagent delegation
- `vc-agents` — external fleet spawn

**Relation to vibecraftsmanship**: techniques are tools, not postures.
vibecraftsmanship does NOT pick among techniques — the active posture
does, based on what the current step needs. Treat techniques as
orthogonal pool.

### Layer 4 — Late-stage (product surface)

For when code is done but product isn't yet shipped, found, sold.

- `vc-dou` — Definition of Undone audit
- `vc-decorate` — late-stage visual finishing
- `vc-hydrate` — packaging + go-to-market
- `vc-release` — final outward ship

**Relation to vibecraftsmanship**: late-stage runs the rzeczywistość
axis hardest — does the product survive contact with **customer**
reality, not just developer reality. vibecraftsmanship may invoke
late-stage when survival check reveals product is "done in repo" but
not yet shipped to anyone.

---

## Routing table — which posture for which moment

| Moment                                                             | Posture      | Tactical charter |
| ------------------------------------------------------------------ | ------------ | ---------------- |
| One bounded feature, one branch, full slice owned end-to-end       | Ownership    | `vc-ownership`   |
| Multi-wave dispatch plan, multi-agent by design, multiple branches | Operator     | `vc-operator`    |
| Triage before plan exists, shared problem definition needed        | Partner      | `vc-partner`     |
| Convergence loop on existing code (within any posture)             | (technique)  | `vc-marbles`     |
| Pre-implementation research with 3 perspectives                    | (technique)  | `vc-research`    |
| Post-completion spec falsification                                 | (technique)  | `vc-audit`       |
| Per-PR or per-branch code review                                   | (technique)  | `vc-review`      |
| Trajectory check ("are we going right direction?")                 | (technique)  | `vc-followup`    |
| One-axis decisive cut after marbles excess                         | (technique)  | `vc-polarize`    |
| Dead-code curation + silencer strip                                | (technique)  | `vc-prune`       |
| Repo orientation before any work                                   | (foundation) | `vc-init`        |
| Idea-to-plan when scope fuzzy                                      | (foundation) | `vc-scaffold`    |
| Product-surface readiness audit                                    | (late-stage) | `vc-dou`         |
| Visual coherence polish pass                                       | (late-stage) | `vc-decorate`    |
| Packaging + listing + onboarding                                   | (late-stage) | `vc-hydrate`     |
| Final ship + DNS + verification                                    | (late-stage) | `vc-release`     |

---

## When to escalate posture mid-flight

Drift detection signals (vibecraftsmanship's job to call):

### Ownership → Operator escalation

Trigger: "this slice has grown into N parallel cuts, none of which
the original agent can hold in working memory simultaneously."

Action: invoke vc-operator, write master-dispatch, wave-shape the
remaining work.

### Operator → Partner escalation

Trigger: "the dispatch plan keeps requiring operator-side decisions
that aren't documented and operator isn't responding mid-wave."

Action: pause dispatch, invoke vc-partner, co-decide pending
ambiguities, then resume.

### Partner → Ownership/Operator escalation

Trigger: "co-decision phase converged on clear plan, time to execute."

Action: explicit posture handoff. Partner mode ends; ownership or
operator begins. Declare it.

### Any → Vibecraftsmanship recalibration

Trigger: any of:

- operator names a framing correction (rescheduled-not-retired,
  equal-intensity-not-ranked, brief-brevity-rule)
- empirical compression ratio reveals estimate was wrong order of
  magnitude
- substrate-failure pattern repeats across multiple agents (signal
  that substrate strategy itself needs rethink)
- silence from operator for >10 min on a question that needs answer

Action: invoke vibecraftsmanship to name which axis is broken (gust /
siła / rzeczywistość), realign, then re-enter appropriate tactical
charter.

---

## Anti-pattern: invoking vibecraftsmanship when tactical charter suffices

Vibecraftsmanship is the **5th charter**, meant for meta-moments. Do
NOT invoke it for:

- "implement feature X" (use vc-ownership or vc-implement)
- "dispatch 3 waves of work" (use vc-operator)
- "debug this issue with me" (use vc-partner)
- "run tests" (use the technique directly)
- "review this PR" (use vc-review)

Invoke vibecraftsmanship when the question is **about the posture
itself**, not about the work.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
