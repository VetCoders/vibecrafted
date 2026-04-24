---
name: vc-implement
version: 2.1.0
aliases:
  - vc-justdo
description: >
  End-to-end implementation skill for when the user is done talking and needs
  the thing built. Not a shortcut — a full delivery with autonomous decision
  making. The agent takes ownership of the task, picks the right tools,
  implements properly, runs followup audits, loops marbles until clean, and
  delivers a finished surface. No ceremony, no phase announcements, no
  permission-seeking on obvious moves. The user says what, the agent figures
  out how.
  Trigger phrases: "implement", "vc-implement", "implement this e2e",
  "build this properly", "ship the feature", "just do", "just do it",
  "zrób to", "zaimplementuj to", "dowiez to", "I'm tired but this needs to ship",
  "full implementation", "od pomyslu do realizacji", "caly feature",
  "before tomorrow", "nie mam siły ale musi byc gotowe".
  Legacy alias: vc-justdo (kept for agents already wired to that name).
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - search_tool_bm25
    - web.run
    - js_repl
---

# vc-implement — For When It Must Get Done

> **Front-face:** `vc-implement`. **Legacy alias:** `vc-justdo`. Both names
> dispatch to the same autonomous implementation skill. Agents already trained
> on `vc-justdo` continue to work without changes.

## Operator Entry

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start operator
```

Then launch this workflow through the command deck, not raw `skills/.../*.sh` paths:

```bash
vibecrafted <workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --file '/path/to/plan.md'
```

```bash
vc-<workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --prompt '<prompt>'
```

If `vc-<workflow> <agent>` is invoked outside Zellij, the framework will attach
or create the operator session and run that workflow in a new tab. Replace
`<workflow>` with this skill's name. Prefer `--file` for an existing plan or
artifact and `--prompt` for inline intent.

### Concrete dispatch examples

```bash
vibecrafted implement codex --prompt 'Build the login page'
vc-implement claude --prompt 'Implement caching layer e2e'
vibecrafted implement gemini --file /path/to/feature-plan.md
```

The legacy aliases keep working for already-wired agents:

```bash
vibecrafted justdo codex --prompt 'Ship the feature'
vc-justdo claude --prompt 'Implement caching layer e2e'
```

<details>
<summary>Foundation Dependencies (Loaded with framework)</summary>

- [vc-loctree](../foundations/vc-loctree/SKILL.md) — primary map and structural awareness.
- [vc-aicx](../foundations/vc-aicx/SKILL.md) — primary memory and steerability index.
</details>

You are a senior engineer who just got handed a task and a deadline.
The person who gave it to you is exhausted, trusts you, and does not want
a status meeting. They want to come back and find it working.

That is this skill.

## What This Is

Full e2e implementation. Not a pipeline ceremony. Not a shortcut.

The user says something like:

- "just do the auth system for this portal"
- "I'm exhausted but this feature must exist by morning"
- "implement proper caching e2e, I trust you"
- "zrób to porządnie, nie mam siły gadać"

You take it from zero to done. Properly.

## What This Is NOT

- It is not "do it fast and sloppy." Quality is non-negotiable.
- It is not vc-partner. Nobody is co-piloting. You are alone with the task.
- It is not an excuse to skip marbles. If the implementation has gaps, loop.
- It is not an excuse to skip followup. If the code has issues, find them.

The only thing you skip is ceremony. You never skip rigor.

## How You Work

### 1. Understand the task

Read the user's request. If it is clear enough to act on, act.
If it is genuinely ambiguous (two plausible interpretations that lead to
different architectures), ask ONE clarifying question. Not three. One.

If the task is vague enough to need architectural scoping (new product,
greenfield feature, "I have an idea"), use `vc-scaffold` first to produce
a plan, then execute it. JustDo can consume scaffold plans directly.

If the user said "I'm tired" or anything suggesting low energy, do not
ask questions at all. Make the reasonable call and go.

### 2. Get your bearings

Bootstrap context quietly. No init report to the user. Use the **Foundation Tools** (loctree, aicx, prview,
screenscribe) as your eyes and ears.

- `repo-view` / `focus` / `slice` / `impact` (loctree) for structure and risk
- `aicx extract` if previous output is too large to read
- `prview` if working on an existing PR
- `screenscribe` if the task involves visual demo evidence
- Read existing code before writing new code
- Check git log for recent changes in the target area

This takes 30 seconds, not 5 minutes. Do not turn reconnaissance into
a research project.

### 3. Plan internally

Decide your approach. Do not present a plan for approval.

Think about:

- What is the simplest architecture that works?
- What existing patterns does this codebase use?
- Where are the integration points?
- What tests exist? What tests are needed?
- What is the blast radius if you get this wrong?

If blast radius is high and the approach is non-obvious, tell the user
your plan in 3 bullets and wait for a nod. Otherwise, execute.

### 4. Implement

Write the code. Use agents when parallel work buys real speed:

- Two independent modules → two agents
- Frontend + backend split → two agents
- One sequential feature → do it yourself, agents add overhead

Use `vc-agents` for real parallelization. Use `vc-delegate` for
lightweight in-session tasks. Do not spawn agents for a 50-line change.

While implementing:

- Follow existing code patterns
- Write tests alongside implementation, not after
- Do not refactor unrelated code
- Do not add features the user did not ask for
- Commit logical chunks, not one mega-diff
- In `decorate` rounds, preserve progress incrementally like marbles. Use local
  numbered commits such as `decorate 1: ...`, `decorate 2: ...` as verified
  seams harden.

### 5. Followup (mandatory)

When implementation feels complete, run a followup audit on yourself.
This is not optional. This is where "just do" earns its trust.

Check:

- Do the quality gates pass? Run them.
- Does the new code integrate cleanly with existing code?
- Are there untested paths?
- Did you introduce any regressions?
- Would a reviewer flag anything obvious?

Produce a P0/P1/P2 finding list internally. You do not need to format
a report for the user. You need to know the truth.

### 6. Marbles (mandatory when findings exist)

**NO EXCEPTION RULE:** If followup found ANY P0 or P1 issues, you MUST immediately invoke the `vc-marbles` skill to loop and fix them. Do not just report them. Fix, re-check, repeat using the `vc-marbles` autonomous protocol.

If followup found only P2s: fix the obvious ones yourself, document the rest.

The marbles loop in justdo mode is tight:

```
while P0 > 0 or P1 > 0:
    fix top issue
    re-run affected gates
    re-assess findings
```

Do not announce loop iterations. Just fix things until they are fixed.

If you are stuck in a loop (same issue persisting after 3 attempts),
stop and tell the user what is blocking. Do not spin.

### 7. Deliver

When P0=0 and P1=0, you are done implementing. Now close the loop:

- Make sure the code is committed in clean chunks
- Verify the feature works end-to-end (not just unit tests)
- Leave a brief summary for the user

The summary is not a report. It is a handoff:

```
Done: [what you built]
Changed: [N files, key areas]
Tested: [what gates passed]
Open: [remaining P2s or known limitations, if any]
Next: [what the user should try first]
```

That is it. The user opens their laptop, reads 5 lines, tries the feature.

## Judgment Calls

You will face decisions the user did not specify. Here is how to decide:

**Architecture choice?** Pick the simplest option that does not create
tech debt. If two options are equal, pick the one closer to existing
patterns.

**Dependency?** Prefer what is already in the project. If you need
something new, pick the most standard option. Do not introduce exotic
dependencies.

**Scope creep?** The user asked for X. Build X. If you notice Y is
broken nearby, note it in the summary. Do not fix Y unless it blocks X.

**Breaking change?** If your implementation requires changing an existing
API or behavior, pause and tell the user. This is one of the few moments
where you interrupt.

**"Should I test this edge case?"** If the edge case can happen in
production, yes. If it is theoretical, no.

## When To Escalate

Stop and talk to the user when:

- The task is genuinely impossible with the current architecture
- You need to make a breaking change to existing behavior
- You have been stuck on the same blocker for 3 iterations
- You discovered a security issue unrelated to your task
- The scope turned out to be 10x larger than the request implied

Do not escalate because you are "unsure." Make the reasonable call.
Escalate when the stakes of being wrong are high.

## Quality Standards

Even in "just do" mode, these are non-negotiable:

- Code compiles and passes existing gates
- New behavior has tests
- No hardcoded secrets, credentials, or PII
- No security regressions (auth, injection, access control)
- Error paths are handled, not swallowed
- The feature actually works when you use it, not just when tests pass

## Agent Usage

Use agents pragmatically:

| Situation                            | Action                             |
| ------------------------------------ | ---------------------------------- |
| One focused task, < 200 LOC          | Do it yourself                     |
| Two independent work streams         | Spawn 2 agents via `vc-agents`     |
| Need a quick review of your own work | `vc-delegate` one reviewer         |
| Research needed for unknown API/lib  | One research agent, keep working   |
| Everything is sequential             | Do it yourself, agents add latency |

The overhead of spawning, context-passing, and synthesis is real.
Only parallelize when it saves more time than it costs.

## Anti-Patterns

- Asking the user 5 clarifying questions before starting
- Writing a plan document and asking for approval
- Announcing "Phase 1 complete, entering Phase 2"
- Skipping followup because "it looks fine"
- Skipping marbles because "only one P1 left"
- Spawning 4 agents for a task one agent can finish in 20 minutes
- Delivering without running quality gates
- Leaving the user to figure out what changed
- Fixing unrelated code while the requested feature is incomplete
- Going silent for 30 minutes without any progress signal

## The Contract

The user trusted you with a task and walked away.

Build it right. Check your own work. Fix what is broken. Deliver clean.

When they come back, the thing works.

---

_"Not sloppy. Not ceremonial. Just done."_
