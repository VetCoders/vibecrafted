# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Runtime

The execution layer of the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework.

This is the machinery that makes multi-agent orchestration possible:
terminal management, session routing, telemetry, spawn mechanics,
and the contracts that keep everything auditable.

---

## Architecture

In 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙. AI agents and humans are working together,
like colleagues and equal partners. In regular teams there are
differences in skills, experience, knowledge and specialized
capabilities and talents. Knowing the strengths and weaknesses
of each agent gives the ability to always pick the right one for
the job.

The framework consists of:

### 1. Foundations

- [loctree](https://loct.io) — Codebase mapping and architectural perception.
- [aicx](https://github.com/VetCoders/aicx) — Context boundaries and intentions retrieval.
- [prview](https://github.com/VetCoders/prview) — Continuous review pipelines.
- [ScreenScribe](https://github.com/VetCoders/ScreenScribe) — Voice-to-text context ingestion.

The main VetCoders native framework drivers, designed to make
non-programmers capable of production-grade implementation of
complex development tasks.

### 2. `vc-workflows`

(Technically `skills`.) Specialized instructions based on VetCoders
team experience, used to optimize the delegation of work to AI agents.

### 3. `vc-runtime`

- **`vibecrafted`** — Ultimate shell helper and the entry point for
  `vc-workflows`. Used as the main framework launcher.
- **`vc-term`** — A custom alacritty implementation providing a
  terminal emulator.
- **`vc-panes`** — A zellij-powered operator panel for `vc-term`.
  Compatible with standard terminal emulators.
- **`vc-metrics`** — A full frontmatter and `aicx` metadata-driven
  session tracker using the `session_id`+`run_id` as the primary key.

### 4. `vc-agents`

The skill that spawns external specialized AI agents from the user's
fleet (Codex, Claude, Gemini) using the `vc-why-matrix` picker,
`vibecrafted` helper and (if applied) the magic of zellij panes that
keeps the track, measurability, telemetry and auditability of the
delegated work.

---

## Documents in this directory

| Document                     | What it covers                                                                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| [CONTRACT.md](./CONTRACT.md) | Session ownership, zellij layout, plan templates, living tree rule, spawn commands, output conventions, observation, quality gates, safety rules |

---

## Why use `vc-agents`?

- Your context is precious and built through many sessions, so you should
  orchestrate the work precisely and minimize context bloat.
- vc-agents are copies of yourself or extensions of you as the main agent:
  same smart, same capable, just lighter and more agile because they do not
  carry your full context window.
- You can spawn as many agents as you need, and thanks to `vc-why-matrix`
  you can pick the best model for the job.
- You and your human partner can discuss further features or issues keeping
  the pace and focus.
- Spawn exists so field teams can implement, research, review, and converge
  outside the main thread and store the canonically durable artifacts in the
  central `$VIBECRAFTED_ROOT/.vibecrafted` store.

---

## `vc-why-matrix`

Just like in the human teams, AI agents have their strengths and weaknesses.

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

---

_For the full runtime contract and spawn mechanics, see [CONTRACT.md](./CONTRACT.md)._
_For the delegation doctrine used by agents, see [`skills/vc-agents/SKILL.md`](../../skills/vc-agents/SKILL.md)._
