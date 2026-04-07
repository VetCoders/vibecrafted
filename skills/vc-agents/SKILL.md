---
name: vc-agents
version: 3.0.0
description: >
  Spawn external specialized AI agents from the user's fleet (Codex, Claude, Gemini).
  Use this when you need parallel execution, deep isolation, or task-specific cognitive 
  strengths that surpass generic in-thread delegation.
  Trigger: "vc-agents", "/vc-agents", "delegate to agents", "spawn".
---

# vc-agents — The Unified Execution Fleet

## Operator Entry

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start vibecrafted
```

`vc-agents` is the delegation contract behind active workflows, not the primary
operator command a founder types first. The operator-facing entrypoint stays:

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
or create the operator session and run that workflow in a new tab. `vc-agents`
defines how that workflow fans out into external workers.

### Concrete dispatch examples

```bash
vibecrafted codex implement /path/to/plan.md
vibecrafted claude implement /path/to/plan.md
vibecrafted gemini implement /path/to/plan.md
```

> We do not outsource thought. We deploy equally capable minds on parallel execution paths to protect the main context buffer.

A single agent session carries immense context. Attempting to execute every small rewrite, forensic deep-dive, or radical structural shift in-thread causes prompt bloat and dilutes your focus.

`vc-agents` is the unified delegation layer. You identify the structural gap, pick the right mind for the job from the **`vc-why-matrix`**, choose the appropriate execution mode (Terminal vs Native Task), spin up the autonomous worker, and return to your main orchestration.

## Execution Modes (Terminal vs Native)

| Capability      | Native Task Delegation (Fallback)   | Terminal Agent Swarm (Default)               |
| --------------- | ----------------------------------- | -------------------------------------------- |
| **Execution**   | Claude Task tool (in-process)       | Portable scripts (out-of-process)            |
| **Agents**      | Claude subagents only               | Claude + Codex + Gemini                      |
| **Parallelism** | Multiple Task calls in one message  | Multiple Terminal windows                    |
| **Robustness**  | Limited by context window           | Full agent session per task                  |
| **Environment** | Inherits parent env                 | Clean Terminal env                           |
| **Best for**    | Small bounded work, native fallback | Default choice; large or model-specific work |

**Rule of Thumb:**

1. Default to **Terminal Agent Swarms** for robustness and cognitive-specific choices.
2. Fallback to **Native Task Delegation** for very small tasks, quick in-thread verification, or when external Terminal processes are unavailable.

## The `vc-why-matrix`

You do not spawn agents blindly. You pick the cognitive profile required for the cut.

```mermaid
  graph TD
    subgraph Codex
        CodexDesc[Precision & Surgery]
        CodexBest[Best for:\n\n– Critical implementations\n– Exact refactors\n– Contract-gated execution]
        Codex --> CodexDesc
        Codex --> CodexBest
    end

    subgraph Claude
        ClaudeDesc[Forensics & Research]
        ClaudeBest[Best for:\n\n– Bug hunts across deep layers\n– Architecture audits\n– Assessing unknown paths]
        Claude --> ClaudeDesc
        Claude --> ClaudeBest
    end

    subgraph Gemini
        GeminiDesc[Radical Reframing]
        GeminiBest[Best for:\n\n– Architecture leaps\n– Fearless simplification\n– Stripping dead scaffolding]
        Gemini --> GeminiDesc
        Gemini --> GeminiBest
    end
```

## Delegation Doctrine

- **Delegate, do not micromanage:** Do not produce 15-point bureaucratic checklists for the spawned agent. Write a high-level plan with `Goal`, `Scope`, and `Acceptance Criteria`. Let them figure out the _how_.
- **The Living Tree:** Agents must know they operate in a live system. Ensure your spawn plan states: _"You are working on a living tree. Concurrent changes are expected. Adapt proactively."_
- **Full Replacement over Scar Tissue:** Tell your agents they are empowered to rewrite broken abstractions. Sometimes a full replacement is cleaner than patching over bad prototype code.

## Plan template

```markdown
---
run_id: <generated-unique-id>
agent: <claude|codex|gemini>
skill: vc-agents
project: <repo-name>
status: <pending|in-progress|completed|failed>
loops_completed: <number>
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

## Spawn commands

The launch path depends on your chosen Execution Mode.

### Mode 1: Terminal Agent Swarm (Default)

The operator-facing launch path for out-of-process delegation goes through the
`vibecrafted` command deck or the `vc-<workflow>` helper. The repo-owned spawn
scripts remain the internal engine behind that path.

### Codex

```bash
PLAN="$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan-slug>.md"
vibecrafted codex implement "$PLAN"
```

### Claude

```bash
PLAN="$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
vibecrafted claude implement "$PLAN"
```

### Gemini

```bash
PLAN="$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
vibecrafted gemini implement "$PLAN"
```

If these tools are unavailable, stop pretending spawn is correctly configured and say so explicitly.

### Mode 2: Native Task Delegation (Fallback)

If you chose native delegation for a small or constrained task, invoke the `Task` tool directly rather than calling a shell script.

```
Task(
  subagent_type: "general-purpose",
  description: "<3-5 word summary>",
  prompt: "<full plan content from plan file>"
)
```

Wait for the subagent to report its findings directly back into your chat context.

## Output convention

- Plans: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<timestamp>_<slug>.md` or another stable per-task
  filename
- Reports: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.md`
- Transcripts: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.transcript.log`
- Metadata: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.meta.json`

## Observation

Observe progress through durable artifacts in `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/`.

If your environment exposes the observer helper, the standard check is:

```bash
vibecrafted codex observe --last
```

Use the equivalent agent observer when needed.

## Quality gate expectations

Keep the standard 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. quality bar:

- loctree-mcp as first-choice exploration and search tool with fail-fast if inaccessible
- semgrep as first-choice security guard when available
- Rust repos: `cargo clippy -- -D warnings`
- Non-Rust repos: choose the closest equivalent lint/type/test gate
- Tests: run if reviewing; write if implementing new behavior; prefer real e2e coverage for the actual pipeline
- If a gate is blocked, report the exact blocker and run the closest safe equivalent

## Safety rules

- Do not log secrets or commit `.env` files.
- Never use `--no-verify` for `commit` or `push`.
- Do not rewrite git history unless the user explicitly asks.
- Treat concurrent edits as normal, but still verify before overwriting.
- If a repo has a strict command such as `make check`, run it or explain why not.

## Final principle

Fleet is not for outsourcing thought.
Fleet is for deploying equally capable front-line agents through a strict, canonical launch path.
Use them to implement, not merely to comment on implementation.
