# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Runtime Contract & Architecture

This document defines the underlying execution engine, telemetry structures, and UI contracts of the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework. It is intended for framework operators, not for the AI agents' active context buffers.

## Under the Hood

**𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.** is a framework designed by VetCoders. It provides telemetry, a canonical store with durable artifacts, portable spawn helpers, and telemetry-driven context/intentions retrieval for straightforward, robust, and measurable work in AI-human teams.

The framework consists of four main pillars:

### 1. Foundations
- **loctree**: Codebase mapping and architectural perception.
- **aicx**: Context boundaries and intentions retrieval.
- **prview**: Continuous review pipelines.
- **ScreenScribe**: Voice-to-text context ingestion.

These are native VetCoders drivers built to equip non-programmers with production-grade implementation capabilities.

### 2. `vc-workflows`
(Technically `skills`). These are specialized instructions based on the VetCoders team experience, used to optimize the delegation of work to AI agents (e.g., `vc-marbles`, `vc-prune`, `vc-init`).

### 3. `vc-runtime`
- **`vibecrafted`**: The ultimate shell helper and the entry point for `vc-workflows`. Used as the main framework launcher.
- **`vc-term`**: A custom alacritty implementation providing a specialized terminal emulator.
- **`vc-panes`**: A zellij-powered operator panel for `vc-term`. Compatible with standard terminal emulators.
- **`vc-metrics`**: A full frontmatter and `aicx` metadata-driven session tracker using the `session_id`+`run_id` as the primary key.

### 4. `vc-agents`
The execution orchestration skill that spawns external specialized AI agents from the user's fleet (Codex, Claude, Gemini) using the `vc-why-matrix` picker. It leverages the `vibecrafted` helper and the magic of zellij panes to maintain trackability, measurability, telemetry, and auditability.

---

## Runtime Contract

- **Session Ownership:** Session ownership is repo-bound. The operator session name is derived from the current repo root, not a global shared session.
- **Zellij Layout (`vc-panes`):** In the `vc-panes` mode, the operator pane reserves the upper `3/5` for the operator's tab, and the spawn surfaces belong in the lower `2/5`.
- **Standard Terminal Fallback:** If you are outside the `vc-panes` mode, open a new tab in the repo session instead of mutating the currently focused operator tab.
- **Artifact Links:** `.vibecrafted/plans` and `.vibecrafted/reports` inside the local repo are convenience symbolic links only. The canonical, durable store remains `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/`.

---

## Spawn Commands

The canonical launch path for agent-to-agent delegation is through the portable spawn scripts.

If the environment has optional shell aliases (like `codex-implement`), those are just convenience wrappers around these exact same scripts. Always use the portable scripts natively to ensure maximum compatibility across environments.

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

---

## Output Convention

- **Plans:** `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<timestamp>_<slug>.md` (or another stable per-task filename).
- **Reports:** `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.md`
- **Transcripts:** `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.transcript.log`
- **Metadata:** `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_<slug>_<agent>.meta.json`

---

## Observation & Telemetry

Observe progress through durable artifacts in `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/`.

If your environment exposes the observer helper, the standard check is:

```bash
bash $VIBECRAFT_ROOT/skills/vc-agents/scripts/observe.sh codex --last
```

*(Use the equivalent agent observer flag when checking runs from Claude or Gemini).*
