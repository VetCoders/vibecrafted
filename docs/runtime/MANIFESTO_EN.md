---
name: what_is_vibecrafted
version: 2.0.0
description: >
  A convergence framework for AI-native software development.
  Convergence through counterexample. READ-ONLY perception alternating
  with WRITE action. Marbles over-apply fixes in deliberate excess;
  audit verifies what landed; polarize cuts back to one truth. Carve
  from marble pattern at the heart of the quality cycle. Architecture
  and philosophy manifesto.
---

# Vibecrafted. — Architecture Manifesto

## Definition

**Vibecrafted.** is a convergence framework for AI-assisted software development, engineered by VetCoders.
It does not merely write code for you. It provides a **system** in which code produced by AI agents is systematically driven to production quality — through alternating steps of **perception** and **action**, structural analytical tooling, and multi-agent orchestration.

## Philosophical Core

The ultimate bottleneck in AI-assisted coding is not a lack of innate "intelligence," but the unbounded accumulation of entropy and hallucinations in complex systems over time.

Rather than expecting zero-shot coding miracles, the Vibecrafted. architecture is grounded in **process**. It relentlessly enforces the single question: _"What is still wrong?!"_ — forcing agents back into iterative verification loops based on counterexamples (counterexample convergence), narrowing the margin of error until absolute truth is established.

Counterexample convergence is not a single step or a single tool. It is an **emergent property** of the entire pipeline — tools arranged in a rhythm: perceive, act, perceive, act. No WRITE step happens without a preceding READ-ONLY step. No READ-ONLY step ends without handing a verdict to the next WRITE step. That is the core.

## Origin Story

It began with two veterinarians from Poland attending a Harvard Medical School course ("AI in Health Care: From Strategies to Implementation"). They decided to build an ultrasound enhancement application to support practitioners in their daily work, despite possessing zero prior software engineering background. They aggressively delegated the implementation to AI agents.

As the codebase grew exponentially, those agents lost the ability to keep the bigger picture in mind. Instead of building the product forward, they started hallucinating — rewriting hundreds of lines just to patch simple functionalities. In absolute frustration, pure perseverance necessitated a new, unforgivingly strict methodology.

Once this strict system of continual re-verification was paired with increasingly capable LLMs, it broke the boundaries of a raw automation script. It birthed a true framework.

**A framework so closely integrated that it successfully managed to extend, rebuild, and continuously rewrite itself.**

## Pipeline (Sculpting Pattern)

Vibecrafted. operates like a sculptor working stone: first the rough block is roughed out, then the chisel is laid against it again and again, the angle checked after every strike. Each chisel stroke is **action** (WRITE). Each pause to look at the block is **perception** (READ-ONLY). Without both, no sculpture appears — strokes without looking produce rubble, looking without strokes leaves the block untouched.

```
[scaffold]            WRITE    build the frame and project documentation
    ↓
[workflow / implement] WRITE    implement (workflow = orchestrated;
                                implement = daily-driver, one-agent jack-of-all-trades)
    ↓
[followup]            READ      assess trajectory — is direction healthy
    ↓
[review]              READ      assess each implementation — findings-max,
                                no code modification
    ↓
[marbles]             WRITE     meta-implementation by swarm — plaster every
                                crack in total excess, deliberate over-write
    ↓
[audit]               READ      verify the chosen truth actually landed
                                — falsification, default UNVERIFIED, PASS earned
    ↓
[polarize]            WRITE     choose one truth, reject the rest — decisive cut
                                shakes off the marbles excess, one axis remains
    ↓
[dou]                 READ      measure distance to shippable state
    ↓
[hydrate]             WRITE     polish surfaces
    ↓
[decorate]            WRITE     paint — brand visual layer
    ↓
[release]             WRITE     pack the stall and head to market to sell
```

**Rhythm rule:** every WRITE is bracketed by READ-ONLY steps before and after. Agents do not write blind. Agents do not look without acting. Breaking the rhythm (skipping READ before WRITE, skipping WRITE after READ) breaks the core.

**Carve-from-marble pattern at the centre of the pipeline:** marbles deliberately over-apply fixes (excess plaster in every crack, including ones that perhaps should not be filled); audit verifies what landed; polarize decisively cuts the excess back to one truth. The marbles excess **is intentional** — it exists so there is something to shake off.

## Tooling Ontology

| Layer                       | Tool                                   | Mode      | Mechanism                                                                                                                                                       |
| --------------------------- | -------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Senses**                  | Loctree                                | READ      | Structural codebase analysis — dead weight, cyclical dependencies, blast radius tracking. Agents read the architecture, rather than guessing it.                |
| **Orientation**             | vc-init                                | READ      | Three foundational bases before action: intentions (what happened previously), vision (current code state), and truth (operational sanity checks).              |
| **Creation**                | vc-scaffold, vc-workflow, vc-implement | WRITE     | Project frame, orchestrated implementation pipeline, and the daily-driver one-agent implementer.                                                                |
| **Perception (Quality)**    | vc-followup, vc-review                 | READ-ONLY | Followup assesses the trajectory of the whole line. Review assesses each individual implementation — findings-max, zero code modification.                      |
| **Completion**              | vc-marbles                             | WRITE     | Meta-implementation by swarm. Plaster on every crack in **total excess**. The excess is deliberate — it exists so there is something for polarize to shake off. |
| **Falsification (Quality)** | vc-audit                               | READ-ONLY | Per-task verdict matrix after marbles. Default UNVERIFIED, PASS earned by evidence. Verifies whether the chosen truth actually landed in code.                  |
| **Convergence**             | vc-polarize                            | WRITE     | Decisive cut. Shakes off the marbles excess, picks one axis of truth, rejects competing surfaces. Emits DoU/release handoff.                                    |
| **Readiness Measurement**   | vc-dou                                 | READ-ONLY | Definition of Undone — measures the distance separating the project from production. Shipping readiness audit.                                                  |
| **Distribution**            | vc-hydrate, vc-decorate, vc-release    | WRITE     | Surface polishing, brand visual layer, packaging and shipping to market.                                                                                        |
| **Orchestration**           | vc-agents, vc-operator                 | meta      | Background agent invocation (vc-agents) or fleet conduct in operator mode (vc-operator), with rigorous reporting, transcripts, and `aicx` context.              |
| **Safety**                  | rust-ai-locker                         | infra     | Advisory resource locking — guaranteeing that simultaneous asynchronous agents never collide or fatally overlap on heavy compilation builds.                    |

**The Quality layer is split into perception (review + followup, READ) and falsification (audit, READ).** All three are READ-ONLY. All three produce verdict + findings + report. None of them modify code. Code modification is reserved for marbles (over-write) and polarize (decisive cut).

## The Proof of Concept

Vibecrafted. acts as its own irrefutable proof. This exact framework fully constructed its own skills matrix, its background mechanisms, its CI pipeline, the local installer, and its promotional page. Every interaction demands an evidence chain — the agent acts solely on objective counterexamples until validation is achieved.

Framework version 2.0.0 itself went through its own pipeline: marbles dumped an excess of ideas into the skill taxonomy, audit verified what really landed, polarize chose one axis (READ-ONLY vs WRITE) and rejected the competing framings. The manifesto you are reading is the output of that cycle.

_Produced with ⚒🅅·🄸·🄱·🄴·🄲·🅡·🄰·🄵·🅃·🄴·🄳·_
