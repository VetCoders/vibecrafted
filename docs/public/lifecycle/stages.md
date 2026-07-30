---
title: "The Eleven Stages"
description: "Reference for the eleven lifecycle stages: order, READ/WRITE phase, purpose, tooling, and what each stage report must show."
section: lifecycle
order: 20
---

# The Eleven Stages

The lifecycle manifest defines eleven stages in a fixed order. Each stage is
a distinct agent run with an explicit phase (`read` or `write`), allowed
artifact classes, transition conditions, and expected tooling. This page is
the per-stage contract; the relay mechanics live in
[Lifecycle overview](/docs/lifecycle-overview/).

## Stage table

| #   | Stage       | Phase | Purpose                             |
| --- | ----------- | ----- | ----------------------------------- |
| 1   | `scaffold`  | READ  | Discovery and plan shape            |
| 2   | `implement` | WRITE | Delivery through operator/agents    |
| 3   | `review`    | READ  | Test-heavy review and falsification |
| 4   | `workflow`  | WRITE | Examine → research → implement lane |
| 5   | `followup`  | READ  | Intent and direction check          |
| 6   | `marbles`   | WRITE | Entropy-up convergence runtime      |
| 7   | `audit`     | READ  | Independent falsification           |
| 8   | `polarize`  | WRITE | Entropy-down simplification         |
| 9   | `dou`       | READ  | Definition of Undone before release |
| 10  | `hydrate`   | WRITE | Preflight product surface work      |
| 11  | `release`   | WRITE | Outward shipping work               |

READ stages carry `can_modify_code: false` and allow reports, cache,
transcripts, and run state. WRITE stages add code, docs, and generated files.
Every stage report must carry the standard frontmatter
(see [Briefs and reports](/docs/briefs-and-reports/)); READ-stage reports
must additionally declare `code_mutation: false` — declaring `true`, or an
invalid value, is a hard READ-phase violation.

## 1. scaffold (READ)

Entry: a mission — even a vague one. Exit: a measurable plan with scope,
acceptance criteria, and test gates. The report must show the plan itself and
the evidence it rests on (repository perception, prior intent), not just a
summary of the idea.

## 2. implement (WRITE)

Entry: the scaffold plan. Exit: the delivery landed on the current branch
with commits. The report must show what changed, which gates ran, and what
remains unverified.

## 3. review (READ)

Entry: an implementation to falsify. This stage is deliberately test-heavy
for a READ stage — it runs gates without changing code. Exit: graded
findings. The report must show evidence per finding, not opinions.

## 4. workflow (WRITE)

Entry: remaining scoped work. The examine → research → implement lane:
structure first, ground truth second, code third. Exit: the lane's delivery
committed. The report must show all three phases fed each other.

## 5. followup (READ)

Entry: the work in motion. Exit: a direction verdict — gaps, drift, and the
next highest-leverage move. The report must name what still feels unfinished
and where the implementation diverged from intent.

## 6. marbles (WRITE)

Entry: an implementation that exists but has not converged. Bounded
correction rounds flood every remaining crack — entropy deliberately goes up.
Exit: rounds complete with one commit per round. The report must show
per-round evidence. The manifest gives marbles an explicit `audit_after`
edge: audit follows automatically in a supervised lifecycle.

## 7. audit (READ)

Entry: completion claims from the WRITE stages. Independent plan-vs-code
falsification with a requirements matrix. Exit: each claim proved, refused,
or marked unverified. The report must carry the matrix — a pass is earned
per requirement, never assumed.

## 8. polarize (WRITE)

Entry: the marbles excess. Chooses one axis and cuts competing truths so
runtime, tests, docs, and promises agree — entropy deliberately goes down.
Exit: the decisive cut committed. The report must state which axis won and
what was rejected.

## 9. dou (READ)

Entry: a supposedly finished product. The Definition of Undone audit scans
the whole product surface for gaps between internal capability and external
readiness. Exit: an enumerated findings list. The report must emit
`dou_index: <n>` in its frontmatter — the count of open findings, where `0`
is the launch-ready target. Absent or invalid values read as unknown, never
as a fake zero.

## 10. hydrate (WRITE)

Entry: the DoU findings. Executes the non-code work that closes them:
packaging, onboarding, listings, distribution artifacts. Exit: findings
closed or consciously accepted by the operator. The report must map each
finding to a closure or an acceptance.

## 11. release (WRITE)

Entry: a hydrated product with a zero (or accepted) DoU index. Outward
shipping: deployment, publishing, signing, DNS — the work that makes the
release real. Exit: the release is live and verified from the outside. The
report must contain security gate evidence, the exposed surface inventory,
the deployment mode decision, and a post-release install smoke from the
published artifact — not from the working tree.

## Steering between stages

Stage order is the manifest default. A stage report can override it with
`next_stage` (forward or backward), hand the baton with `next_agent`, or —
for audit-shaped evidence — the operator can force transitions with the
[supervision verbs](/docs/supervision/).
