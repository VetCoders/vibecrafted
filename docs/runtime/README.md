---
name: vc-agents
version: 2.0.0
description: >
  Spawn external specialized AI agents from the users fleet (codex, claude, gemini) 
  using the `vc-why-matrix` picker, `vibecrafted` helper and (if applied) the magic of 
  zellij panes that keeps the track, measurability, telemetry and auditability of 
  the delegated work. 
  
  **Trigger phrases:** 
  The skill is triggered by call of:
   - `vc-agents`
   - `$vc-agents`
   - `/vc-agents`
  Or any other tasks you judge to benefit from the `vc-why-matrix` delegation.
---

# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. agents

  In 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙. AI agents and humans are working together, 
  like colleagues and equal partners. In regular teams there are
  differences in skills, experience, knowledge and specialized
  capabilities and talents. The multiculturalism, respect and 
  diversity of the team is the source of its strength and Frontier
  AI Agents also have their certain strengths and weaknesses. 
  Knowing the strengths and weaknesses of each agent gives the 
  ability to always pick the right one for the job. 
  
## Under the hood
**𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.** is a framework designed by VetCoders and **`vc-agents`** 
is a part of it. It provides telemetry, canonical store with durable artifacts, 
portable spawn helpers, telemtry driven context and intentions retrieval 
for straightforward, robust and measurable work in the AI-human teams. 

As the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙. methodology is **strict**, spawning through the 
𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. method requires a **strict** execution pattern. The framework
provides all the necessary tools to follow this pattern.

The framework consists of:

1. foundations: 
  - [loctree](https://loct.io)
  - [aicx](https://github.com/VetCoders/aicx)
  - [prview](https://github.com/VetCoders/prview)
  - [ScreenScribe](https://github.com/VetCoders/ScreenScribe) 
    
  The main and VetCoders native framework drivers growth on the team 
  experience, research, and is designed to make non-programmers capable of 
  production-grade implementation of complex development tasks

2. **`vc-workflows`** (technically `skills`) are the specialized instructions 
  based on the VetCoders team experience and are used to optimize the 
  delegation of work to the AI agents. 

3. **`vc-runtime`** and [Runtime contract](#Lines-167-189)
  - `vibecrafted` - Ultimate shell helper and the entry point for `vc-workflows` 
    used as the main framework launcher. 
  - `vc-term` - A custom alacritty implementation providing a terminal emulator
  - `vc-panes` - A zellij-powered operator panel for `vc-term`. Compatible with
    standard terminal emulators.
  - `vc-metrics` - A full frontmatter and `aicx` metadata-driven session tracker 
    using the `session_id`+`run_id` as the primary key.

4. **`vc-agents`** 
  The skill that spawns external specialized AI agents from the users fleet (codex, claude, gemini) 
  using the `vc-why-matrix` picker, `vibecrafted` helper and (if applied) the magic of 
  zellij panes that keeps the track, measurability, telemetry and auditability of 
  the delegated work. 

## When to use

Trigger when the user asks to delegate work, especially phrases like:
  - If the trigger is direct call of `vc-agents`, `$vc-agents` or `/vc-agents`.
  - Any mentions like: "Delegate to agents", "Let's spawn it to external agents", 
    "Let's use agents", "Let's use the fleet".
  - Any request that implies parallelization or multi-track execution
  - Any request that wants visible Terminal agents or long-running isolated work

## Why use `vc-agents`?

- Your context is precious and built through many sessions, so you should orchestrate 
  the work precisely and minimize context bloat.
- vc-agents are copies of yourself or extensions of you as the main agent: same smart, 
  same capable, just lighter and more agile because they do not carry your full 
  context window.
- You can spawn as many agents as you need, and thanks to `vc-why-matrix` you can 
  pick the best model for the job.
- You and your human partner can discuss furher features or issues keeping the 
  pace and focus.
- Spawn exists so field teams can implement, research, review, and converge 
  outside the main thread and because so store the canonicaly durable artifacts 
  in the central [𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.]($HOME/.vibecrafted) store.

## When do not use `vc-agents`
- if the task is simple and can be done in one go by the main agent
- if there is no capability-proven reason to use external agents
- if the caller is not directly asking for `vc-agents`

## Antipatterns

- judging yourself and questioning the need of spawning to external agents 
  and deciding yourself on whether to spawn or not if the user called `vc-agents` 
  or any of its aliases.
- delegation to your built-in native agents when the user explicitly asked 
  for `vc-agents`.
- implementing the requested code task yourself with the high risk of context 
  bloat when the user explicitly asked for `vc-agents`.
- not following the instructions provided by this and foundational skills.
- not reporting if acknowledged a obstacles like helpers damaged, missing or 
  not working as expected and proceed yourself without escalation.

## `vc-why-matrix`
Just like in the human teams, AI agents have their strengths and weaknesses. 

Use `vc-agents` as the default first choice whenever the task benefits from model-specific strengths.
Reach for native `vc-delegate` only when the task is small, bounded, and model-agnostic.

```mermaid
  graph TD
    subgraph Codex
        CodexDesc[Why choose it:\n\n– Precision, implementation purity\n– Highly reliable code surgery]
        CodexBest[Best for:\n\n– Critical implementations\n– Exact refactors and test‑gated fixes\n– Bounded engineering execution]
        CodexAvoid[Avoid when:\n\n– Repo is chaotic\n– Brief is vague\n– You need exploration/cleanup]
        Codex --> CodexDesc
        Codex --> CodexBest
        Codex --> CodexAvoid
    end

    subgraph Claude
        ClaudeDesc[Why choose it:\n\n– Investigative depth\n– Stubborn logic tracing\n– Exhaustive research instincts]
        ClaudeBest[Best for:\n\n– Bug hunts and codebase forensics\n– Audits and architecture research\n– Assessing state‑of‑the‑art frameworks]
        ClaudeAvoid[Avoid when:\n\n– Work is straightforward surgery\n– No need for deep investigative pass]
        Claude --> ClaudeDesc
        Claude --> ClaudeBest
        Claude --> ClaudeAvoid
    end

    subgraph Gemini
        GeminiDesc[Why choose it:\n\n– Bold reframing\n– Creative system redesign\n– Fearless simplification]
        GeminiBest[Best for:\n\n– Architecture leaps\n– Radical cleanup ideas\n– Product reframing and high‑variance exploration]
        GeminiAvoid[Avoid when:\n\n– Task needs predictable, surgical implementation\n– Low‑variance execution suffices]
        Gemini --> GeminiDesc
        Gemini --> GeminiBest
        Gemini --> GeminiAvoid
    end
```

If the task wants one of these strengths, external agents win by default because you can route work to the right mind
instead of forcing a generic in-thread delegation path.

## Goals

1. Create a well defined plans based on the `vc-why-matrix` and spawn a fleet of
   subagents to implement, research, review, and converge on the task.

2. Each subagent gets a plan into the canonical `plans/` directory under
   `$VC_WORKSPACE_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/`.

3. Collect their results in
   `$VC_WORKSPACE_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/`

## Runtime contract

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
    `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/`.

## Mandatory plan rules

Every subagent plan should:

- be high level, decisive, and test-gated
- include reason and context
- include a clear checkbox todo list
- include acceptance criteria
- include required checks
- end with a short call to action

## Living tree rule

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
- Never change branches during active work. The intent is to stay on the
  current working branch and keep building inside that living tree.
- Plans may explicitly instruct the agent to finish and harden one seam, spawn
  another `vc-agents` worker for the next plan, commit locally for
  preservation, and continue.

## 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. doctrine

- Do not treat agents like couriers or report printers. Treat them like artists and implementers.
- Do not over-restrict them into tiny bureaucratic slices when the task wants a real rewrite.
- Sometimes a full replacement is cleaner than patching scar tissue.
- 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. builders ship real products through vibeguiding. Agents should be trusted to do the same.

## Plan template

Use this structure:

```text
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

The canonical launch path for agent-to-agent delegation is through the portable spawn scripts.

If the environment has optional shell aliases (like `codex-implement`), those are just convenience wrappers around these
exact same scripts. Always use the portable scripts to ensure maximum compatibility.

### Codex

```bash
PLAN="$HOME/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
bash $VIBECRAFT_ROOT/skills/vc-agents/scripts/codex_spawn.sh "$PLAN" --mode implement
```

### Claude

```bash
PLAN="$HOME/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
bash $VIBECRAFT_ROOT/skills/vc-agents/scripts/claude_spawn.sh "$PLAN" --mode implement
```

### Gemini

```bash
PLAN="$HOME/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan>.md"
bash $VIBECRAFT_ROOT/skills/vc-agents/scripts/gemini_spawn.sh "$PLAN" --mode implement
```

If these tools are unavailable, stop pretending spawn is correctly configured and say so explicitly.

## Output convention

- Plans: `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<timestamp>_<slug>.md` or another stable per-task
  filename
- Reports: `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.md`
- Transcripts: `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.transcript.log`
- Metadata: `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.meta.json`

## Observation

Observe progress through durable artifacts in `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/`.

If your environment exposes the observer helper, the standard check is:

```bash
bash $VIBECRAFT_ROOT/skills/vc-agents/scripts/observe.sh codex --last
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
