# Skills

This index documents the live framework inventory in `skills/` and the routes
currently exposed by `scripts/vibecrafted`.

`CI mode` means the skill can run headless from the launcher without requiring a
zellij-attached operator tab. `Stand-alone` means the operator has a direct
command-deck entry instead of reaching the surface only through another mode or
workflow.

| Skill          | Purpose                                                                         | Primary entry                                                                   | CI mode | Stand-alone | Docs                                                                              |
| -------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------- | ----------- | --------------------------------------------------------------------------------- |
| `vc-agents`    | External execution fleet and agent-mode dispatch contract.                      | `vibecrafted <agent> implement\|research\|review\|plan\|prompt\|observe\|await` | Yes     | No          | [SKILL](../skills/vc-agents/SKILL.md) · [FLOW](../skills/vc-agents/FLOW.md)       |
| `vc-decorate`  | Late-stage visual finishing and coherence pass.                                 | `vibecrafted decorate <agent>`                                                  | Yes     | Yes         | [SKILL](../skills/vc-decorate/SKILL.md) · [FLOW](../skills/vc-decorate/FLOW.md)   |
| `vc-delegate`  | Native in-session delegation for small bounded cuts.                            | `vibecrafted delegate <agent>`                                                  | Yes     | Yes         | [SKILL](../skills/vc-delegate/SKILL.md) · [FLOW](../skills/vc-delegate/FLOW.md)   |
| `vc-dou`       | Definition of Undone audit across repo, runtime, packaging, and market surface. | `vibecrafted dou <agent>`                                                       | Yes     | Yes         | [SKILL](../skills/vc-dou/SKILL.md) · [FLOW](../skills/vc-dou/FLOW.md)             |
| `vc-followup`  | Post-implementation audit for gaps, regressions, and next leverage.             | `vibecrafted followup <agent>`                                                  | Yes     | Yes         | [SKILL](../skills/vc-followup/SKILL.md) · [FLOW](../skills/vc-followup/FLOW.md)   |
| `vc-hydrate`   | Packaging, SEO, onboarding, and go-to-market hydration.                         | `vibecrafted hydrate <agent>`                                                   | Yes     | Yes         | [SKILL](../skills/vc-hydrate/SKILL.md) · [FLOW](../skills/vc-hydrate/FLOW.md)     |
| `vc-implement` | Autonomous end-to-end implementation with followup and marbles built in.        | `vibecrafted implement <agent>`                                                 | Yes     | Yes         | [SKILL](../skills/vc-implement/SKILL.md) · [FLOW](../skills/vc-implement/FLOW.md) |
| `vc-init`      | Context bootstrap: history, structure, gates, and operator-session handoff.     | `vibecrafted init <agent>`                                                      | No      | Yes         | [SKILL](../skills/vc-init/SKILL.md) · [FLOW](../skills/vc-init/FLOW.md)           |
| `vc-intents`   | Intention-to-runtime truth audit across plans, sessions, and code.              | `vibecrafted intents <agent>`                                                   | Yes     | Yes         | [SKILL](../skills/vc-intents/SKILL.md) · [FLOW](../skills/vc-intents/FLOW.md)     |
| `vc-justdo`    | Legacy alias of `vc-implement` kept for agents already wired to this name.      | `vibecrafted justdo <agent>`                                                    | Yes     | Yes         | [SKILL](../skills/vc-justdo/SKILL.md) · [FLOW](../skills/vc-justdo/FLOW.md)       |
| `vc-marbles`   | Truth-convergence loop for fixing what is still wrong.                          | `vibecrafted marbles <agent>`                                                   | Yes     | Yes         | [SKILL](../skills/vc-marbles/SKILL.md) · [FLOW](../skills/vc-marbles/FLOW.md)     |
| `vc-ownership` | Full-spectrum take-the-wheel mode across code, UX, docs, and packaging.         | `vibecrafted ownership <agent>`                                                 | Yes     | Yes         | [SKILL](../skills/vc-ownership/SKILL.md) · [FLOW](../skills/vc-ownership/FLOW.md) |
| `vc-partner`   | Shared executive reasoning, debugging, and collaborative planning.              | `vibecrafted partner <agent>`                                                   | Yes     | Yes         | [SKILL](../skills/vc-partner/SKILL.md) · [FLOW](../skills/vc-partner/FLOW.md)     |
| `vc-prune`     | Runtime-cone cleanup and dead-surface removal.                                  | `vibecrafted prune <agent>`                                                     | Yes     | Yes         | [SKILL](../skills/vc-prune/SKILL.md) · [FLOW](../skills/vc-prune/FLOW.md)         |
| `vc-release`   | Release prep, deployment truth, and outward ship checks.                        | `vibecrafted release <agent>`                                                   | Yes     | Yes         | [SKILL](../skills/vc-release/SKILL.md) · [FLOW](../skills/vc-release/FLOW.md)     |
| `vc-research`  | Triple-agent research swarm.                                                    | `vibecrafted research --prompt\|--file`                                         | Yes     | Yes         | [SKILL](../skills/vc-research/SKILL.md) · [FLOW](../skills/vc-research/FLOW.md)   |
| `vc-review`    | Findings-first review pipeline over PR or branch artifacts.                     | `vibecrafted review <agent>`                                                    | Yes     | Yes         | [SKILL](../skills/vc-review/SKILL.md) · [FLOW](../skills/vc-review/FLOW.md)       |
| `vc-scaffold`  | Founder-first architecture planning from vague intent.                          | `vibecrafted scaffold <agent>`                                                  | Yes     | Yes         | [SKILL](../skills/vc-scaffold/SKILL.md) · [FLOW](../skills/vc-scaffold/FLOW.md)   |
| `vc-workflow`  | Examine -> Research -> Implement pipeline.                                      | `vibecrafted workflow <agent>`                                                  | Yes     | Yes         | [SKILL](../skills/vc-workflow/SKILL.md) · [FLOW](../skills/vc-workflow/FLOW.md)   |

## Route notes

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock path: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Generic spawned skills write `reports/<timestamp>_<slug>_<agent>.md` with matching
  `.transcript.log` and `.meta.json` sidecars under the date root.
- `vc-marbles` uses the same root but nests loop artifacts under `marbles/`.
- `vc-init` is interactive-only and prepares the operator session; it does not
  guarantee a report on its own.

The framework-level chaining map lives in [WORKFLOWS](./WORKFLOWS.md).
