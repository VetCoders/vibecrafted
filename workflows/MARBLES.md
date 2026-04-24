---
name: marbles
version: 1.0.0
description: >
  1st Row Agent Operator Almanach for marbles convergence loops.
  Canonical workflow reference derived from battle-tested session 2026-04-06
  (unicode-puzzles-portal, 5 parallel agents, 8 convergence reports, 10 bugs found).
  Covers: fleet orchestration, zellij routing, plan authoring, spawn mechanics,
  watcher lifecycle, convergence protocol, branch safety, and failure recovery.
trigger_phrases:
  - "marbles workflow"
  - "how to run marbles"
  - "convergence loop"
  - "fleet orchestration"
  - "marbles almanach"
  - "jak odpalić marbles"
  - "workflow marbles"
---

# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Marbles — 1st Row Agent Operator Almanach

> Derived from battle session 2026-04-06: unicode-puzzles-portal, 5 parallel agents
> (3× Codex, 1× Gemini, 1× Claude), 8 convergence reports, 25 loop reports,
> 3 framework bugs found and fixed in real-time.

---

## 1. Prerequisites

Before running marbles, the operator MUST have completed:

| Step              | Skill                               | What it delivers                             |
| ----------------- | ----------------------------------- | -------------------------------------------- |
| Due diligence     | `vc-init`                           | Repo perception, intentions, ground truth    |
| Architecture spec | `vc-scaffold` or manual             | File ownership matrix with zero collisions   |
| Plans             | `docs/superpowers/plans/` or inline | One plan per track, clear scope + acceptance |

Without these, marbles agents fly blind. Init is not optional.

---

## 2. The Command

One command. One canonical form.

```bash
vc-marbles <agent> --count <N> --prompt "<task description>"
vc-marbles <agent> --count <N> --file <plan.md>
```

Aliases: `vibecrafted marbles <agent> ...` is identical.

### Parameters

| Flag              | Required | Default  | Description                                         |
| ----------------- | -------- | -------- | --------------------------------------------------- |
| `<agent>`         | yes      | —        | `codex`, `claude`, or `gemini`                      |
| `--count <N>`     | no       | 3        | Number of convergence loops                         |
| `--prompt <text>` | one of   | —        | Inline task description                             |
| `--file <path>`   | one of   | —        | Plan file as input                                  |
| `--depth <N>`     | no       | 3        | Auto-crawl last N plans (when no prompt/file given) |
| `--runtime <rt>`  | no       | terminal | `terminal` or `headless`                            |

### Agent Selection — `vc-why-matrix`

| Agent      | Cognitive Profile    | Use When                                                       |
| ---------- | -------------------- | -------------------------------------------------------------- |
| **Codex**  | Precision surgery    | Bounded implementation, exact refactors, test-gated fixes      |
| **Claude** | Forensics & research | Bug hunts, architecture audits, design system analysis         |
| **Gemini** | Radical reframing    | Architecture leaps, product narrative, fearless simplification |

---

## 3. What Happens When You Run It

```
vc-marbles codex --count 4 --prompt "fix the stego round-trips"
    │
    ├── marbles_spawn.sh
    │     ├── Generates plan file in marbles store
    │     ├── Creates session lock
    │     ├── Spawns L1 agent (codex_spawn.sh) with direction=right
    │     └── Starts marbles_watcher.sh (foreground, temporal guardian)
    │
    ├── Zellij Layout
    │     ┌─────────────────┬─────────────────┐
    │     │  Watcher (left)  │  Agent (right)   │
    │     │  ◉───○───○───○   │  codex working   │
    │     │  chain visual    │  session: abc123  │
    │     └─────────────────┴─────────────────┘
    │
    ├── On L1 completion → marbles_next.sh (success hook)
    │     ├── Launch verification (fire-and-forget, resumes agent session)
    │     ├── Copy plan → L2
    │     ├── Spawn L2 agent (direction=right → reuses right pane)
    │     └── Recursive: L2 success hook → marbles_next.sh → L3...
    │
    └── On all loops done → CONVERGENCE.md
          ├── Final verification (convergence assessment)
          ├── Release session lock
          └── Trajectory: 65 → 78 → 92 → 100
```

### Watcher Lifecycle (per loop)

```
promise    → Agent spawned, waiting for session ID
confirmed  → Session ID captured from transcript
report ✓   → Report file landed, metrics extracted
```

### Control Plane

```bash
marbles_ctl.sh session              # List active sessions
marbles_ctl.sh inspect <run_id>     # Full state + trajectory
marbles_ctl.sh pause <run_id>       # Pause after current loop
marbles_ctl.sh stop <run_id>        # Stop immediately
marbles_ctl.sh resume <run_id>      # Resume paused session
```

---

## 4. Plan Authoring

### Zero File Collision Rule

When running parallel agents, each track MUST own exclusive files.
No two tracks touch the same file. Verify with a collision matrix before spawning.

```
Track A: unicode_styles.js/ts, Stylizer.tsx
Track B: EmotionEngine.tsx, TransformLab.tsx, emotionize_v2.ts
Track E: advanced_techniques.js/ts, manager.js, StegoLab.tsx
                    ↑ ZERO OVERLAP ↑
```

### Inline Prompt Pattern

For direct execution without a plan file:

```bash
vc-marbles codex --count 3 --prompt "wykonaj ten plan: docs/superpowers/plans/layer-1-art/track-a.md"
```

The plan file is read by the agent, not by marbles_spawn. The prompt is the directive;
the file is the context. The agent reads the file, understands scope, and executes.

### Prompt Discipline

Good marbles prompts contain:

- **What to do** — specific deliverables
- **Scope** — which files to touch, which to leave alone
- **Branch guard** — "NIE zmieniaj brancha. Pracujesz na living tree."
- **Commit convention** — `marble(N): <summary>`
- **Test gate** — exact commands to run

Bad prompts: vague goals, no scope, no gate, no branch guard.

---

## 5. Parallel Fleet Operations

### Spawning Multiple Agents

Launch one at a time. Verify zellij placement before spawning next.

```bash
# Track A — Codex (bounded surgery)
vc-marbles codex --count 4 --prompt "wykonaj ten plan: docs/plans/track-a.md"

# Track B — Codex
vc-marbles codex --count 4 --prompt "wykonaj ten plan: docs/plans/track-b.md"

# Track D — Claude (investigative)
vc-marbles claude --count 3 --prompt "wykonaj ten plan: docs/plans/track-d.md"

# Track I — Gemini (reframing)
vc-marbles gemini --count 4 --prompt "wykonaj ten plan: docs/plans/track-i.md"
```

### Fleet Monitoring

```bash
marbles_ctl.sh session --json        # All active as JSON
vibecrafted status                   # Today's activity summary
vibecrafted codex observe --last     # Last codex report
```

### Convergence Flow

Each agent independently converges. Watcher checks P0/P1/P2 metrics.
Early convergence: if P0=0, P1=0, P2=0 → loop stops before count exhausted.

---

## 6. Branch Safety

### HARD RULE

```
NEVER change branches during marbles.
NEVER create branches in the user's repo-root.
```

The branch is the operator's decision. If the agent believes the branch is wrong,
it stops and returns control to the operator/runtime layer with a substrate
failure. Parallel agents depend on branch stability, and a worker must not solve
substrate invalidity by moving sideways.

**Violation consequences:** Concurrent agents on the same living tree lose coherence.
Commits land on wrong branches. Merge conflicts proliferate. The operator loses trust.

### What Happened (2026-04-06)

Gemini (Track I) changed branch from `feat/forge-and-others` to `feat/track-i-docs`
during a marbles run. Other agents' work was disrupted. Guard was added to
`skills/vc-marbles/SKILL.md` as a hard rule.

---

## 7. Failure Recovery

### Known Failure Modes (battle-tested)

| Failure                     | Symptom                             | Root Cause                                           | Recovery                                                          |
| --------------------------- | ----------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------- |
| Agent lands in Terminal.app | New window opens outside zellij     | `ZELLIJ=0` treated as false                          | Fix: `spawn_in_zellij_context()` checks `${ZELLIJ+set}` not value |
| Watcher crashes on init     | `JSONDecodeError` in state.json     | `watcher_pid: $` instead of `$$`                     | Fix: `_init_state()` heredoc                                      |
| L2+ opens new pane          | Pane proliferation in watcher tab   | Missing `SPAWN_DIRECTION=right` in `marbles_next.sh` | Fix: add direction env var                                        |
| Agent hijacks stale tab     | Agent unresponsive, watcher timeout | Operator didn't close old tabs                       | Fix: always `new-pane`, never reuse; cleanup after convergence    |
| Count overflow              | 4 agents on 3-count run             | Timeout counted as iteration                         | Fix: `_wait_for_loop_report()` guard — no report = no advance     |
| Branch switch mid-run       | Living tree disrupted               | No branch guard in skill                             | Fix: hard rule in SKILL.md + substrate failure handoff            |

### Operator Hygiene

After convergence:

1. Close completed marbles tabs in zellij
2. Review convergence reports
3. Commit or cherry-pick agent work
4. Clean stale locks: `rm ~/.vibecrafted/locks/<org>/<repo>/*.lock`

---

## 8. Commit Convention

Marbles agents commit after each round (Living Tree Exception):

```
marble(<N>): <one-line summary of what was fortified>

- <file>: <what changed and why>
- <file>: <what changed and why>

Gate: <pass|fail> | Tests: <count> | Regressions: <count>
```

If gate fails, commit message says `Gate: fail` and next round starts with the regression.

---

## 9. Telemetry & Artifacts

### Store Layout

```
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/
├── plans/                    # Original task plans
├── reports/                  # implement/workflow reports (legacy: justdo/workflow)
├── marbles/
│   ├── plans/                # Per-loop plan copies (L1, L2, ...)
│   └── reports/              # Per-loop reports + CONVERGENCE.md
│       ├── *_L1_codex.md
│       ├── *_L1_codex.transcript.log
│       ├── *_L1_codex.meta.json
│       ├── *_L2_codex.md
│       ├── *_CONVERGENCE.md
│       └── *_L1_codex_verified.md
└── tmp/                      # Runtime prompt files
```

### State Files

```
$VIBECRAFTED_HOME/marbles/<run_id>/state.json     # Watcher state
$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock # Session lock
```

### Frontmatter Contract

Every report MUST include:

```yaml
---
run_id: <id>
agent: <claude|codex|gemini>
skill: vc-marbles
project: <repo-name>
status: <pending|in-progress|completed|failed>
created: <ISO-8601>
---
```

---

## 10. The CronCreate Layer (Experimental)

Claude Code's `CronCreate` can serve as a fleet-level heartbeat above individual
marbles runs. This is the missing conductor that:

1. Wakes up every N minutes
2. Calls `marbles_ctl.sh session --json` → reads fleet state
3. Calls `marbles_ctl.sh inspect <run_id>` → reads trajectory per run
4. Decides: converged? → spawn next phase. Stuck? → pause + escalate. All done? → self-cancel.

This layer sits ABOVE marbles — it does not replace the watcher, it orchestrates
multiple watchers. The cron prompt IS the conductor's brain.

```
CronCreate (heartbeat)
  ├── vc-marbles codex (track A) → watcher → agent
  ├── vc-marbles codex (track B) → watcher → agent
  ├── vc-marbles claude (track D) → watcher → agent
  └── vc-marbles gemini (track I) → watcher → agent
```

Status: conceptually validated in session 2026-04-06, not yet implemented as
a reusable skill. The `marbles_watcher.sh` + `marbles_ctl.sh` infrastructure
supports this pattern — the missing piece is the cron-based decision loop.

---

## 11. Session Timeline Reference

This almanach was derived from session `90aaab61-62f9-4045-af06-64e30a2b2f13`
(2026-04-06, unicode-puzzles-portal).

Full timeline: 181 entries, 5 hours, 1 session.

### Key Moments

| Time  | Event                                                                                         |
| ----- | --------------------------------------------------------------------------------------------- |
| 07:01 | `/vc-init` — due diligence, repo perception                                                   |
| 07:15 | Steganography decode — `wszechswiat-krzyczy.md` (10,729 chars, combining marks + ZW overflow) |
| 07:20 | `re-ply.txt` decoded — inverted polarity binary, API safety filter discovery                  |
| 07:30 | 3 plans authored: engine round-trip, studio decode UI, MCP boost                              |
| 07:30 | `vibecrafted justdo codex` × 3 — first fleet deployment                                       |
| 07:45 | Justdo agents completed — +1,893/-477 lines, 100/100 tests                                    |
| 08:00 | `vibecrafted marbles codex` × 2 — hardening loops on engine + MCP                             |
| 08:21 | Watcher crash — `$$` bug discovered and fixed                                                 |
| 08:28 | Both marbles converged                                                                        |
| 08:30 | Discussion: CronCreate vs marbles watcher vs marbles orchestrator plugin                      |
| 08:40 | Deep reading: vibecrafted docs (CONTRACT, PERCEPTION, FOUNDATION, VIBE_HANGOVER)              |
| 08:50 | `ZELLIJ=0` bug discovered — `spawn_in_zellij_context()` fixed                                 |
| 09:04 | Phase 2 fleet: 4 parallel marbles (A, B, D, I) — all in zellij                                |
| 09:10 | `marbles_next.sh` direction fix — L2+ pane reuse                                              |
| 09:17 | Gemini branch violation — guard added to SKILL.md                                             |
| 09:51 | Claude marbles launched — design system + UX decorate                                         |
| 10:30 | 7 convergence reports — all tracks delivered                                                  |
| 10:37 | Codex launched on vibecrafted framework bugs                                                  |
| 10:56 | Framework self-healing marbles running                                                        |

### Session Metrics

| Metric                                 | Value                     |
| -------------------------------------- | ------------------------- |
| Total agents spawned                   | 12+                       |
| Convergence reports                    | 8                         |
| Loop reports                           | 25+                       |
| Framework bugs found                   | 10                        |
| Framework bugs fixed (same session)    | 6                         |
| Lines changed (unicode-puzzles-portal) | +1,893 / -477             |
| New test files                         | 2                         |
| Tests passing                          | 127 (studio) + 100 (root) |

---

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_
