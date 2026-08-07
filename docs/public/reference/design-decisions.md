---
title: "Design decisions"
description: "Public digest of the accepted architecture decision records: standalone justdo and one owner per truth domain."
section: reference
order: 20
---

# Design decisions

Vibecrafted records its structural choices as architecture decision
records (ADRs). This page digests the accepted, public-relevant decisions
for outside readers: what was decided, why, and what it changes for you.

## ADR-0001 — `justdo` is a posture, not an alias

**Status:** accepted.

### Context

`vc-justdo` originally shipped as a compatibility alias of `vc-implement`,
the structured WRITE-stage implementation workflow. The alias conflated
two different things: a phased pipeline stage with ceremony, and a
_posture_ — take the task and deliver it, no clarifying questions, no
best-of-n deliberation. The posture was designed as a rescue mode: when
the operator is unavailable (or asleep), a launcher that asks questions is
a launcher that stalls.

### Decision

`vc-justdo` became a standalone skill and launcher with its own identity:

- **No questions, no best-offer mode.** The worker orients itself and
  acts; when context is thin it explores proactively instead of asking.
- **The prompt defines the task type.** Implement, review, audit,
  research, fix — `justdo` is not implementation-only; it is a delivery
  stance applied to whatever the prompt says.
- **Non-pipeline.** Unlike `vc-implement`, which is a WRITE phase of the
  Read–Write cadence, `justdo` stands beside the pipeline, not inside it.
- **"Just do" is not "don't verify".** Delivery still ends with a
  verifier-confirmed done, never a done-on-someone's-word.

### Consequence

`justdo` has its own run identity and registry entry; documentation no
longer describes it as an alias. Anything wired to `justdo` expecting the
full implement pipeline gets the posture instead — a deliberate,
changelogged semantic change, not silent drift.

## ADR-0002 — one owner per truth domain

**Status:** accepted; enforced by a deterministic test gate over a machine
ownership matrix (schema `vibecrafted.ownership.v1`).

### Context

As the runtime grew — installed capsule, branded terminal, multiplexer,
server shell, messaging bus, billing — several prior plans independently
converged on the same failure mode: whenever two components both "kind of"
owned a truth (run status, session state, entitlement), the surfaces
diverged and operators learned to distrust all of them.

### Decision

Every runtime, context, structure, terminal, messaging, and billing truth
has **exactly one owner** with a named write surface. Every other surface
is a projection, and a projection never writes. Highlights:

| Truth                | Owner               | Notable non-owner                      |
| -------------------- | ------------------- | -------------------------------------- |
| Run lifecycle        | Control plane       | Server UI, chat threads, session rails |
| Installed runtime    | Generation manifest | Host shell, launchers                  |
| Session intention    | AICX                | Context views                          |
| Repository structure | Loctree             | Structure views                        |
| Session composition  | vc-frame            | Terminal emulator                      |
| A2A envelopes        | Message bus store   | Chat rendering                         |
| Plan artifacts       | The files on disk   | Editor/API clients                     |

Supporting rules that travel with the matrix:

- **Files own plans.** Every write path for plan artifacts terminates in
  files under the artifact store; any API or editor is a convenience
  client, never a required mediator. Requiring API mediation would make
  "server up" a precondition for a write to count.
- **Resume preserves lineage.** A resumed run keeps the identity and
  attempt history of the worker it resumes; silently swapping in a
  different agent persona is forbidden.
- **Installed artifacts are checkout-free.** Nothing under the installed
  runtime may resolve into a development checkout; repository paths appear
  only in development receipts.
- **Gates verify the artifact users run** (installed binary, staged tools
  home), not only source-tree tests.

### Rejected alternatives (instructive ones)

- A UI keeping "some local state for convenience" — convenience caches
  that answer user-visible questions are parallel truths by definition.
- The chat bus as run-status truth — the bus carries envelopes _about_
  runs; the control plane owns the runs.
- Two lifecycle-capable terminals — two owners of the terminal substrate.

### Consequence

A deterministic gate rejects any change that introduces a second owner for
an existing domain. New surfaces must extend the ownership matrix in the
same commit that adds them, so a split-brain can never land silently.

## Reading the originals

The full ADRs, including file-level migration notes, live in the
repository under `docs/adr/`. The machine ownership matrix ships beside
them and is exercised by the test suite on every change.
