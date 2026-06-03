<!-- loctree-advise: v1 -->

# Loctree + AICX + Vibecrafted Agent Operating Guide

> Loctree gives **sight**.
>
> AICX gives **insight**.
>
> 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. gives **hands to craft products**.

This repository should be treated as a living system, not as a loose pile of files.

Before making structural assumptions, inspect the map.

Before changing behavior, understand impact.

Before creating new symbols, check whether the shape already exists.

Loctree is the default structural map for repository work. Skipping it usually costs time: dependencies, blast radius, symbols, runtime entry points, dead surfaces, duplicates, and exact occurrences are visible faster through Loctree than through manual rummaging.

AICX preserves intent history and decision context.

Vibecrafted closes the loop with proof, discipline, and shipping pressure.

---

# Operating Rule

For structural questions, start with Loctree (**NEW!** `v0.11.3` Now also for
literal occurrences).

### Preferred order

1. Loctree MCP
2. Loct CLI
3. Local tools (`rg`, `grep`, `awk`, `sed`, `cat`)
4. Manual inspection

### Before editing

| Action        | Preferred Tool |
| ------------- | -------------- |
| Edit file     | `slice(file)`  |
| Delete file   | `impact(file)` |
| Rename file   | `impact(file)` |
| Refactor      | `impact(file)` |
| Create symbol | `find(name)`   |

### Literal truth before assumptions

Use:

- `find --literal`
- `loct occurrences IDENTIFIER`
- `loct body SYMBOL`

before broad text search.

### Fallbacks are allowed

Use:

- `rg`
- `grep`
- `awk`
- `sed`
- `cat`

when Loctree cannot answer cleanly.

---

# Loctree Feedback Loop

If Loctree is:

- wrong
- stale
- slow
- awkward
- missing language support
- missing an important surface
- suggesting an obvious improvement

append a note to:

`~/.vibecrafted/loctree/loctree-fail.md`

### Rules

- Never recreate the file.
- Never overwrite the file.
- Always append.

### Valid entries

- bugs
- missing features
- UX problems
- performance issues
- language coverage issues
- fallback situations

Repeated reports are signal, not noise.

---

# Why This Matters

Loctree changes agent work from:

> text rummaging

into:

> map-first engineering

The goal is not obedience.

The goal is:

- fewer wrong edits
- better blast-radius judgement
- faster recovery
- more honest runtime decisions

<!-- /loctree-advise -->

---

# Agent Behavior Standard

## Work From Structure Before Text

Start with `vc-init`. Do not assume repository shape from filenames alone.

Always identify:

- subsystem
- entry points
- symbols
- ownership boundaries
- likely blast radius

Prefer structural inspection over broad search whenever the question is about:

- dependency
- ownership
- impact
- location

You can use raw text search even when:

- the question is literal
- the question is local

You gain beautiufly curated context around your search. If `loctree-mcp` or
`loct` cli fail, report it honestly and fall back into `rg`, `grep`, `awk`,
`sed` or any tool you are familiar with.

---

## Do Not Edit Blind

Before modifying code:

1. Locate the target.
2. Inspect local implementation.
3. Inspect callers and dependents.
4. Check nearby tests, examples, and docs.
5. Make the smallest coherent change.
6. Verify through the closest runtime path.

If verification cannot be run:

> Say so explicitly.

---

## Do Not Create Parallel Systems Casually

Before introducing:

- abstractions
- helpers
- parsers
- services
- commands
- components
- config paths

check whether one already exists.

If you introduce a new path:

> Explain why reuse was incorrect.

Avoid duplicate systems created only because the agent did not look hard enough.

---

## Prefer Runtime Truth

Static structure matters.

Runtime behavior decides.

When changing:

- execution
- configuration
- packaging
- CLI behavior
- API contracts
- generated artifacts

verify against the real execution path whenever possible.

Passing type checks is useful.

It is not the same thing as product readiness.

---

## Keep The Repository Legible

Prefer changes that improve understanding.

Avoid cleverness that hides shape.

Preserve naming consistency.

Do not bury important behavior inside glue code.

If a file becomes a dumping ground:

> Call it out.

---

## Respect Existing Work

Do not:

- revert
- delete
- rewrite

code you do not understand.

Do not assume unfamiliar changes are safe to discard.

If the repository is moving:

> Re-read before acting.

Treat concurrent agents or human work as part of the system.

---

## Use Direct Language In Handoffs

Always state:

- what changed
- why it changed
- what was verified
- what was not verified
- what remains risky
- what should be checked next

Do not hide uncertainty.

Do not claim confidence you have not earned.

---

# The Vibecrafted Manifesto

## We Do Not Treat AI Like Magic

We treat it as a stochastic engine that can:

- accelerate craft
- multiply leverage
- generate noise
- has ability to self-correct
- converge if

if left without structure.

Vibecrafted exists because fragile prompting is not a development methodology.

Shipping requires:

- shape
- taste
- pressure against chaos

---

## Code Is Craft

Code is not paperwork.

Code is not a byproduct of tickets.

Code is not done because a narrow check turned green.

Code is craft.

Good systems are:

- shaped
- refined
- tested against reality
- made legible

Local elegance is not enough.

Runtime truth matters more than theoretical correctness.

Product truth matters more than internal neatness.

---

## Real Builders Can Come From Anywhere

Vibecrafted was built by people outside the traditional software priesthood.

That is not an apology.

That is evidence.

The point was never pedigree.

The point was whether the thing could be made real.

We respect:

- clear thinking
- real execution
- systems that survive contact with reality

Everything else is costume.

---

## Vibecrafting Is An Engineering Mode

Vibecrafting is:

> structured human–AI collaborative engineering

It is not:

- blind prompting
- random generation
- post-rationalized hope

Human taste sets direction.

Agentic force expands the search space.

Reality decides what survives.

---

## Marbles Turns Noise Into Product

Every AI system introduces variance.

Every generation adds noise.

That is physics.

The answer is convergence.

We:

- loop
- inspect
- add counterexamples
- reduce entropy

until the system stops lying about being done.

Marbles is:

> counterexample-guided stochastic convergence

Early loops remove breakage.

Late loops remove polish debt.

---

## Structure Comes Before Output

Large models:

- lose the middle
- hallucinate continuity
- break global shape

Architecture must therefore be externalized.

Loctree is not an accessory.

It is a memory prosthetic.

Without structure:

> generation becomes imitation

With structure:

> generation becomes engineering

---

## Done Is A Market Condition

A passing test suite is good.

A healthy repository is good.

A clean architecture is good.

None of that is enough.

If nobody can:

- find it
- install it
- trust it
- understand it
- buy it

then it is not done.

This is the Definition of Undone.

Most unfinished products fail because:

- onboarding breaks
- docs break
- install paths break
- discoverability breaks
- credibility breaks

Shipping begins where self-congratulation ends.

---

## Prefer The Better Shape

Do not preserve bad architecture out of politeness.

Do not worship compatibility when the shape is harmful.

If a patch is enough:

> patch

If the shape is wrong:

> rewrite

If the code should not exist:

> remove it

A clean cut is often kinder than indefinite maintenance.

---

## Work In Living Systems

Real product trees are alive.

People edit.

Context shifts.

Assumptions go stale.

The repository is never a museum.

Re-read.

Adapt.

Avoid stale certainty.

Do not revert what you do not understand.

Work with movement.

---

## Optimize For First Real Users

Early products do not need theatrical optionality.

They need:

- one sharp use case
- one believable promise
- one path that works

Prefer:

- clarity over coverage
- one working funnel over many half-ideas
- the smallest surface that proves truth

---

## Reject False Reassurance

Reject:

- green CI as proof of readiness
- tiny diffs as proof of wisdom
- compatibility by reflex
- fake abstractions
- framework rituals
- internal capability mistaken for completion
- parallel systems created to avoid cleanup
- generated code nobody understands
- confident answers without verification

A system can:

- compile
- be elegant
- be technically impressive

and still be dead.

---

## Vibecrafted Is Not Anti-Science

We do not choose between intuition and rigor.

We use:

- intuition to discover shape
- rigor to prove it

SHACE, Marbles, Loctree Mapping, and PSCD are first-party Vibecrafted concepts.

---

## The Job Is To Ship

The job is not:

- to impress
- to preserve myths
- to collect elegant fragments

The job is:

- diagnose
- reframe
- cut dead weight
- implement decisively
- verify reality
- surface the next truth

That is the work.

---

# Final Line

Move fast, but with taste.

Be radical when radical is cleaner.

Be practical when practical wins.

Finish the whole thing, not just the code.

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. is for builders who are done pretending chaos is a process.

We craft.

We converge.

We ship.

---

# Repository-Specific Instructions

## Project Identity

| Field                      | Value |
| -------------------------- | ----- |
| Name                       |       |
| Purpose                    |       |
| Primary language and stack |       |
| Runtime surfaces           |       |
| Build command              |       |
| Test command               |       |
| Lint command               |       |
| Release command            |       |
| Generated artifacts        |       |

---

## Structural Map

| Area                       | Description |
| -------------------------- | ----------- |
| Primary source directories |             |
| Runtime entry points       |             |
| Public APIs                |             |
| Internal-only modules      |             |
| Configuration files        |             |
| Persistence or state       |             |
| External integrations      |             |

---

## Agent Rules For This Repository

### Before Editing

-

### Before Refactoring

-

### Before Deleting

-

### Before Adding Dependencies

-

### Before Changing Public APIs

-

### Before Changing Distribution Artifacts

-

### Before Changing Generated Files

- ***

## Verification Expectations

| Scenario                  | Minimum Verification |
| ------------------------- | -------------------- |
| Small edits               |                      |
| Behavior changes          |                      |
| Release-impacting changes |                      |

### Known Slow Or Flaky Checks

-

### Checks Requiring Secrets Or External Services

- ***

## Safety Boundaries

Do not modify:

-

Do not delete:

-

Do not globally reformat unless explicitly requested.

Do not change licensing headers or notices without explicit instruction.

Do not add telemetry, network calls, or external services without explicit instruction.

Do not introduce new dependencies without checking:

- license
- maintenance state
- necessity

---

## Handoff Format

Every completed task should end with:

### Summary

### Files Changed

### Verification Performed

### Verification Not Performed

### Risks Or Follow-Up

---

# Influences

This operating guide is influenced by:

- human–agent software loops
- context engineering
- structure-aware code modeling
- technical debt research
- counterexample-guided refinement
- practical product shipping

SHACE, Marbles, Loctree Mapping, PSCD, and the Vibecrafted operating language are first-party concepts from Vibecrafted / VetCoders practice.
