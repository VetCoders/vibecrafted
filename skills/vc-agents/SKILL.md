---
name: vc-agents
version: 3.0.0
description: >
  Spawn external specialized AI agents from the user's fleet (Codex, Claude, Gemini).
  Use this when you need parallel execution, deep isolation, or task-specific cognitive 
  strengths that surpass generic in-thread delegation.
  Trigger: "vc-agents", "/vc-agents", "delegate to agents", "spawn".
---

# vc-agents — The AI-Native Fleet

> We do not outsource thought. We deploy equally capable minds on parallel execution paths to protect the main context buffer.

A single agent session carries immense context. Attempting to execute every small rewrite, forensic deep-dive, or radical structural shift in-thread causes prompt bloat and dilutes your focus.

`vc-agents` is the delegation layer. You identify the structural gap, pick the right mind for the job from the **`vc-why-matrix`**, spin up the autonomous worker, and return to your main orchestration.

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

- **Delegate, do not micromanage:** Do not produce 15-point bureaucratic checklists for the spawned agent. Write a high-level plan with `Goal`, `Scope`, and `Acceptance Criteria`. Let them figure out the *how*.
- **The Living Tree:** Agents must know they operate in a live system. Ensure your spawn plan states: *"You are working on a living tree. Concurrent changes are expected. Adapt proactively."*
- **Full Replacement over Scar Tissue:** Tell your agents they are empowered to rewrite broken abstractions. Sometimes a full replacement is cleaner than patching over bad prototype code.

## Execution (The Spawn Paths)

Create a highly focused `.md` plan in the canonical store, then strike using the portable bash scripts.

```bash
# 1. Save the target plan
PLAN="$HOME/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan-slug>.md"

# 2. Spawn the chosen mind
bash $VIBECRAFT_ROOT/skills/vc-agents/scripts/codex_spawn.sh "$PLAN" --mode implement
```
*(Swap `codex_spawn.sh` for `claude_spawn.sh` or `gemini_spawn.sh` depending on the matrix).*

## Anti-Patterns

- **Hoarding Execution:** Refusing to spawn external agents because you think you can "do it quickly here." You will bloat the context window. Delegate.
- **Bureaucracy:** Treating the sub-agent like a glorified macro with a hyper-rigid output format. If it requires actual thought, give them the goal and get out of the way. If it's trivial, just write the script yourself.
- **Blind Faith:** You spawn them, they execute. *You* still review the output when they finish. Trust, but verify via code mapping (`loctree`) and quality gates.

---
_Vibecrafted with AI Agents by VetCoders (c)2026_
