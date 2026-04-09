# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Runtime Contract

This document defines the execution engine, session contracts, telemetry structures,
plan conventions, and spawn mechanics of the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework.

For the delegation doctrine and the `vc-why-matrix`, see
[`skills/vc-agents/SKILL.md`](../../skills/vc-agents/SKILL.md).
For the framework overview and pillar descriptions, see
[`docs/runtime/README.md`](./README.md).

---

## Under the Hood

**𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.** is a framework designed by VetCoders and **`vc-agents`**
is a part of it. It provides telemetry, canonical store with durable artifacts,
portable spawn helpers, telemetry driven context and intentions retrieval
for straightforward, robust and measurable work in the AI-human teams.

As the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙. methodology is **strict**, spawning through the
𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. method requires a **strict** execution pattern. The framework
provides all the necessary tools to follow this pattern.

### The Four Pillars

1. **Foundations:**
   - [loctree](https://loct.io) — Codebase mapping and architectural perception.
   - [aicx](https://github.com/VetCoders/aicx) — Context boundaries and intentions retrieval.
   - [prview](https://github.com/VetCoders/prview) — Continuous review pipelines.
   - [ScreenScribe](https://github.com/VetCoders/ScreenScribe) — Voice-to-text context ingestion.

   The main VetCoders native framework drivers, designed to make non-programmers
   capable of production-grade implementation of complex development tasks.

2. **`vc-workflows`** (technically `skills`) are the specialized instructions
   based on the VetCoders team experience and are used to optimize the
   delegation of work to the AI agents.

3. **`vc-runtime`:**
   - `vibecrafted` — Ultimate shell helper and the entry point for `vc-workflows`.
     Used as the main framework launcher.
   - `vc-term` — A custom alacritty implementation providing a terminal emulator.
   - `vc-panes` — A zellij-powered operator panel for `vc-term`. Compatible with
     standard terminal emulators.
   - `vc-metrics` — A full frontmatter and `aicx` metadata-driven session tracker
     using the `session_id`+`run_id` as the primary key.

4. **`vc-agents`:**
   The skill that spawns external specialized AI agents from the user's fleet
   (Codex, Claude, Gemini) using the `vc-why-matrix` picker, `vibecrafted` helper
   and (if applied) the magic of zellij panes that keeps the track, measurability,
   telemetry and auditability of the delegated work.

---

## Runtime Contract

- Session ownership is repo-bound. The operator session name is derived from
  the current repo root, not a global shared session.
- In the `vc-panes` mode, the operator pane reserves the upper `3/5`
  for the operator's tab and the spawn surfaces belong in the lower `2/5`.
- If you are outside the `vc-panes` mode, open a new tab in the repo session
  instead of mutating the currently focused operator tab.
- There's a fallback strategy if no usable repo session routing exists,
  and is described in further section.
- `.vibecrafted/plans` and `.vibecrafted/reports` inside the repo are
  convenience links only. The canonical store remains
  `$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/`.

---

## Mandatory Plan Rules

Every subagent plan should:

- be high level, decisive, and test-gated
- include reason and context
- include a clear checkbox todo list
- include acceptance criteria
- include required checks
- end with a short call to action

---

## Living Tree Rule

Always include this exact preamble in every subagent plan or prompt:

```text
You work on a living tree with 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙 methodology, so concurrent changes are expected.
Adapt proactively and continue, but this is never permission to skip quality, security, or test gates.
Run required checks. If something is blocked, report the exact blocker and run the closest safe equivalent.
```

Keep this preamble repo-agnostic.

Add this living-tree coordination note below the preamble whenever the plan
needs it:

- State explicitly whether the agent is working solo at that stage or alongside
  other agents in parallel.
- The agent needs to know whether the stage is solo or shared, but does not
  need to read other agents' plan files unless the plan explicitly requires it.
- If the original plan clearly calls for a stabilization checkpoint, the agent
  must preserve its tranche of work with a local commit, without push.
- During active `decorate` rounds, prefer incremental local commits over one
  giant end-of-task snapshot. Use numbered subjects in the form
  `decorate 1: ...`, `decorate 2: ...`, and continue upward as the round
  hardens distinct seams.
- Never change branches during active work. The intent is to stay on the
  current working branch and keep building inside that living tree.
- Plans may explicitly instruct the agent to finish and harden one seam, spawn
  another `vc-agents` worker for the next plan, commit locally for
  preservation, and continue.

---

## Artifact Contract & Frontmatter Telemetry

Central Store Axiom: **NO ORPHANED ARTIFACTS.**
All artifacts (plans, reports, context docs, research) MUST be written to the central store:
`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/{plans,reports,tmp}/`

Frontmatter Rule: **To be measurable, it must be steerable.**
Every Markdown artifact generated by ANY skill (`vc-agents`, `vc-scaffold`, `vc-workflow`, `vc-review`, `vc-research`, `vc-dou`, `vc-marbles`, etc.) MUST include a YAML frontmatter block for `aicx steer` indexing.

### Mandatory Frontmatter Template

```yaml
---
run_id: <generated-unique-id>
agent: <claude|codex|gemini|system>
skill: <vc-skill-name>
project: <repo-name>
status: <pending|in-progress|completed|failed>
created: <ISO-8601 timestamp>
---
```

## Plan Template

Use this structure for execution plans:

```text
---
run_id: <generated-unique-id>
agent: <agent-name>
skill: <vc-skill-name>
project: <repo-name>
status: <pending|completed>
---

# Task: <short title>

Goal:
- <1-3 bullets>

Scope:
- In scope: <files/areas> as high-level suggestions
- Out of scope: <explicit>

Constraints:
- No --no-verify
- Follow repo conventions

Acceptance:
- [ ] <objective outcome>
- [ ] <objective outcome>

Test gate:
- <command(s)>

Context:
- <very short summary>

Living tree note:
- You work on a living tree with 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙 methodology, so concurrent changes are expected.
- Adapt proactively and continue, but this is never permission to skip quality, security, or test gates.
- Run required checks. If something is blocked, report the exact blocker and run the closest safe equivalent.
- Coordination mode: <solo on this stage / parallel with other agents on this stage>
- You do not need to inspect other agents' plans unless this plan explicitly tells you to.
- If this plan explicitly calls for a stabilization checkpoint, commit your own changes locally without push and continue on the current branch.
```

---

## Spawn Commands

The canonical launch path for agent-to-agent delegation is through the portable spawn scripts.

If the environment has optional shell aliases (like `codex-implement`), those are just convenience wrappers around these
exact same scripts. Always use the portable scripts to ensure maximum compatibility.

### Codex

```bash
PLAN="$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/codex_spawn.sh "$PLAN" --mode implement
```

### Claude

```bash
PLAN="$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/claude_spawn.sh "$PLAN" --mode implement
```

### Gemini

```bash
PLAN="$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/gemini_spawn.sh "$PLAN" --mode implement
```

If these tools are unavailable, stop pretending spawn is correctly configured and say so explicitly.

---

## Output Convention

- Plans: `$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<timestamp>_<slug>.md` or another stable per-task
  filename
- Reports: `$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.md`
- Transcripts: `$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.transcript.log`
- Metadata: `$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.meta.json`

---

## Observation

Observe progress through durable artifacts in `$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/`.

If your environment exposes the observer helper, the standard check is:

```bash
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/observe.sh codex --last
```

Use the equivalent agent observer when needed.

---

## Quality Gate Expectations

Keep the standard 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. quality bar:

- loctree-mcp as first-choice exploration and search tool with fail-fast if inaccessible
- semgrep as first-choice security guard when available
- Rust repos: `cargo clippy -- -D warnings`
- Non-Rust repos: choose the closest equivalent lint/type/test gate
- Tests: run if reviewing; write if implementing new behavior; prefer real e2e coverage for the actual pipeline
- If a gate is blocked, report the exact blocker and run the closest safe equivalent

---

## Safety Rules

- Do not log secrets or commit `.env` files.
- Never use `--no-verify` for `commit` or `push`.
- Do not rewrite git history unless the user explicitly asks.
- Treat concurrent edits as normal, but still verify before overwriting.
- If a repo has a strict command such as `make check`, run it or explain why not.

---

## 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Doctrine

- Do not treat agents like couriers or report printers. Treat them like artists and implementers.
- Do not over-restrict them into tiny bureaucratic slices when the task wants a real rewrite.
- Sometimes a full replacement is cleaner than patching scar tissue.
- 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. builders ship real products through vibeguiding. Agents should be trusted to do the same.

Fleet is not for outsourcing thought.
Fleet is for deploying equally capable front-line agents through a strict, canonical launch path.
Use them to implement, not merely to comment on implementation.
