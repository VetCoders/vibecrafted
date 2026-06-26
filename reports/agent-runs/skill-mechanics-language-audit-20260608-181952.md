# Skill Mechanics And Language Audit - 2026-06-08

## Verdict

The Vibecrafted skills are not weak. They are unevenly mechanized.

The strongest surfaces already behave like control programs:

- `vc-scaffold` defines plan state and verifier-backed completion.
- `vc-operator` has the strongest dispatch brief shape.
- `vc-audit` and `vc-review` enforce read-only falsification.
- `vc-marbles` isolates write workers and caps overgrowth.
- `vc-polarize` uses a score band to decide whether action is legal.
- `vc-release` has the clearest public-readiness gate.

The missing system-level move is a shared prompt-control grammar. Today the
agent-leading mechanics are scattered across skills and companion docs. Future
skills should not rely on author memory to copy the right parts.

Canonical upgrade:

```text
Iron Law
Gate Function
Allowed Statuses
Red Flags / Stop
Output Contract
Acceptance Criteria
```

Every `vc-*` skill should expose those blocks, even if the skill voice stays
Vibecrafted.

## Method

- Followed AGENTS.md framing: Loctree first, AICX for intent context, local
  commands only after structural orientation.
- Used `vc-ownership` as posture, `vc-agents` as hands, and `vc-research`
  methodology as the evidence shape.
- Refreshed/consumed `loct context --full --markdown`.
- Queried AICX intents for Vibecrafted workflow topology and lifecycle context.
- Read the active `vc-ownership`, `vc-agents`, and `vc-research` skill bodies.
- Read Superpowers references, especially:
  - `systematic-debugging`
  - `writing-skills`
  - `dispatching-parallel-agents`
- Measured 27 `skills/vc-*/SKILL.md` files: 7426 total lines.
- Measured 14 Superpowers `SKILL.md` files: 3207 total lines.
- Ran a literal-language candidate scan:
  - 1292 raw candidates
  - 852 high-signal candidates after dropping many purely technical hits
- Dispatched three read-only agents:
  - literal language and tone sweep
  - per-skill mechanics comparison
  - workflow prompt grammar / lifecycle comparison

This report curates actionable strings and mechanics. It does not list every
legitimate `optional`, `fallback`, or `unknown` technical occurrence, because
many of those are correct runtime policy rather than weak agent guidance.

## What The Reference Prompt Gets Right

The provided `Workflow(export const meta = ...)` reference is strong because it
turns intent into a control contract:

- named workflow
- phase list
- explicit root
- typed schemas
- parallel Map work
- one bounded Deliver worker
- adversarial Verify workers
- exact commands
- explicit out-of-scope
- hard no-push / no-commit boundaries
- temp-HOME verification
- computed `allPass`
- final headline tied to evidence

The power is not the word `Workflow`. The power is contract density. It removes
social ambiguity and makes the agent answer a finite state machine.

## Mechanics That Steer Agents

Use this as the future prompt compiler grammar.

```yaml
---
workflow_prompt_version: 1
run_id: <id>
parent_run_id: <id|null>
skill: <vc-workflow|vc-marbles|vc-audit|...>
phase: <scaffold|implement|review|workflow|followup|marbles|audit|polarize|dou|hydrate|release>
mode: <READ|WRITE|META>
agent: <codex|claude|gemini|junie|agy|grok>
project_root: <abs-path>
branch_head: <branch@sha>
artifact_root: <abs-path>
report_path: <abs-path>
upstream_artifacts: [<paths>]
downstream_consumer: <next skill/phase>
wave: <id|null>
position: <n|null>
vector: <stabilize|implement|recon|e2e|research|release>
state: <pending|running|reported|verified|blocked|recovery|stop>
depends_on: []
parallel_with: []
blocks: []
permissions:
  source_write: <true|false>
  git_commit: <true|false>
  push_pr_deploy: false
gates:
  - <exact command>
stop_buttons:
  - push
  - merge
  - deploy
  - public promise
---
```

Sections should be emitted in this order:

1. Role and mode.
2. Mission: the one thing that lands or is falsified.
3. Inputs to read, in order.
4. Baseline truth: branch, head, dirty tree, prior artifact status.
5. Scope, out-of-scope, forbidden changes.
6. Target surfaces.
7. Acceptance criteria.
8. Cadence contract: previous artifact, this output, next legal phase.
9. Tool order: `vc-init`, Loctree, AICX, gates, local fallback.
10. Execution protocol.
11. Failure and recovery.
12. Artifact contract.
13. Completion condition.
14. Imperative call to action.

Mode overlays:

- `READ`: cannot edit, cannot commit, default verdict is unknown/unverified.
- `WRITE`: must modify scoped surfaces, run gates, and emit report.
- `META`: dispatches through launcher, awaits artifacts, updates state, stops
  at operator buttons.

## Superpowers Reference Mechanics

`systematic-debugging` works because it has:

- an Iron Law: no fix before root cause
- four required phases
- explicit red flags
- common rationalization traps
- human-partner redirect rules
- a completion bar higher than "changed code"

`writing-skills` works because it treats skill creation as TDD:

- define pressure scenario
- observe baseline failure
- write skill
- test again with the skill
- refactor the skill text
- keep frontmatter description as trigger logic, not workflow summary

`dispatching-parallel-agents` works because it separates:

- independent domains
- focused tasks
- self-contained prompts
- review and integration by the main agent

The shared pattern is not style. It is process enforcement.

## Per-Skill Mechanics Comparison

| Skill             |  Strength | Main Control Present                                               | Main Gap                                  | Upgrade                                                                                               |
| ----------------- | --------: | ------------------------------------------------------------------ | ----------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `vc-agents`       |      High | plan template, acceptance, launch card, artifacts, await/observe   | parallel eligibility too soft             | add Dispatch Eligibility Gate: independent domains, no shared files, telemetry path, verifier command |
| `vc-aicx`         |   Low-Med | orientation and output structure                                   | retrieval can become narrative            | add Memory Is Claim gate: `current_true/stale/contradicted/unverified`                                |
| `vc-audit`        | Very High | default unverified, evidence taxonomy, trace, report, no-edit rule | no compact top-level gate                 | add Iron Law: no pass without task, code, tests, negative evidence                                    |
| `vc-decorate`     |    Medium | detect-first, anti-patterns, CLI guidance                          | judgment-heavy acceptance                 | add Coherence Gate: before/after evidence, token check, no new palette without evidence               |
| `vc-delegate`     |    Medium | orientation and escalation boundary                                | worker return not constrained             | add helper brief schema: goal, scope, files, status, blocker, verification                            |
| `vc-dou`          |      High | Undone matrix, severity, output format                             | pass/stop criteria not strict enough      | add JSONL matrix: plane, finding, severity, evidence, blocks_ship, next_skill                         |
| `vc-followup`     |    Medium | read-only trajectory check                                         | verdict taxonomy too soft                 | add `on_track/drifting/blocked/needs_marbles` statuses                                                |
| `vc-hydrate`      |    Medium | domain list and sprint protocol                                    | cold-path proof not per-domain            | add artifact exists, findable, usable, evidence row                                                   |
| `vc-implement`    |  Med-High | staged loop and followup/marbles expectation                       | bugfix can skip root-cause law            | add reproduce, recent-change check, hypothesis, failing test/no-test rationale before code            |
| `vc-init`         |      High | structural orientation gate                                        | output depends on context pack shape      | add `init_receipt.md` schema                                                                          |
| `vc-intents`      |      High | evidence hierarchy and classification                              | weak stop condition for memory-only truth | block `done` unless runtime/code evidence is linked                                                   |
| `vc-justdo`       |   Low-Med | strong posture                                                     | no phases, red flags, output contract     | add orient, act, verify, read-only DoU, report gate                                                   |
| `vc-loctree`      |      High | structural workflow and anti-patterns                              | fallback not shaped                       | add fallback report: MCP attempt, CLI fallback, backlog note, confidence downgrade                    |
| `vc-marbles`      |      High | one worker, one round, max targets, no self-extension              | failed-gate result not normalized         | add round result schema: pass/fail, regressions, unresolved P0/P1, next route                         |
| `vc-operator`     | Very High | brief gate, telemetry, tracker, journal, anti-patterns             | state machine spread across docs          | inline allowed state transitions                                                                      |
| `vc-ownership`    |  Med-High | end-to-end phases, buyer verification, DoU before done             | broad mandate can swallow exits           | add ownership exit contract: repo, runtime, product, install, risks                                   |
| `vc-partner`      |    Medium | collaboration cadence                                              | weaker phase acceptance                   | add decision log: question, options, choice, evidence, next gate                                      |
| `vc-polarize`     |      High | prism score bands, output contract                                 | stale prism input risk                    | add preflight receipt: prism path, snapshot freshness, band, dispatch boolean                         |
| `vc-prune`        |  Med-High | phased prune and verification                                      | deletion blast radius not always explicit | add prune ledger: candidate, cone evidence, impact, verdict, gate                                     |
| `vc-prview`       | Very High | structured artifacts, scans, P-level findings                      | final coverage gate not explicit          | parse `MERGE_GATE.json`, list skipped artifacts                                                       |
| `vc-release`      | Very High | security gate, cold-path smoke, blocked release rule               | status enum missing                       | add `blocked/risk_accepted/ready_for_operator_button/released_verified`                               |
| `vc-research`     |  Med-High | triple swarm and synthesis                                         | source quality varies                     | add evidence grading: primary/current/secondary/speculative                                           |
| `vc-review`       | Very High | read-only, default unverified, P-scale, self-attack                | slightly weaker than audit                | add audit-style acceptance checklist                                                                  |
| `vc-scaffold`     | Very High | DRIVER, state alphabet, verifier-only done, scaffold-doctor        | no explicit pressure-test loop            | add cold-operator execution test                                                                      |
| `vc-screenscribe` |    Medium | artifact expectations and investigation order                      | can skip root-cause discipline            | add reproduce, pipeline layer, diagnostic rerun, then fix                                             |
| `vc-skillaunch`   |      High | closest to writing-skills, validation, structure                   | no RED baseline                           | add baseline failure recording before skill generation                                                |
| `vc-workflow`     |      High | ERI phases, artifacts, delegation template                         | phase gates still ask too much from user  | add automatic status schema: research_required, implement_allowed, blocked_reason, next_skill         |

## Language Audit - Rewrite Targets

### Runtime Marbles Commands

| File                                                                  | Current snippet                               | Category                       | Verdict                                                                   |
| --------------------------------------------------------------------- | --------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------- |
| `runtime/vc-marbles/orchestrator/commands/codex-marbles-loop.md:11`   | "Codex does not expose that same hook..."     | apologetic platform limitation | rewrite as "Codex loop contract is interactive/session-disciplined."      |
| `runtime/vc-marbles/orchestrator/commands/help.md:90`                 | "Codex does not expose Claude's Stop hook..." | repeated apology               | rewrite same policy, without apology                                      |
| `runtime/vc-marbles/orchestrator/commands/cancel-codex-marbles.md:15` | "if the operator asks for evidence"           | weak audit posture             | always report iteration and audit path                                    |
| `runtime/vc-marbles/orchestrator/commands/marbles-loop.md:16`         | "When you try to exit..."                     | vague operational wording      | rewrite as "On attempted session exit, the stop hook repeats the prompt." |
| `runtime/vc-marbles/orchestrator/commands/cancel-marbles.md:19`       | "No active Marbles found."                    | low-risk UX wording            | keep or narrow to "No active Marbles loop found."                         |

### Marbles Doctrine

| File                              | Current snippet                                    | Category                 | Verdict                                                                   |
| --------------------------------- | -------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------- |
| `skills/vc-marbles/SKILL.md:110`  | "perhaps should not be filled"                     | hedge weakens doctrine   | rewrite as "including cracks later proven irrelevant"                     |
| `docs/runtime/MANIFESTO_EN.md:73` | "including ones that perhaps should not be filled" | repeated hedge           | rewrite same as above                                                     |
| `skills/vc-marbles/SKILL.md:341`  | "Convergence cosplay"                              | sharp anti-pattern label | keep                                                                      |
| `skills/vc-marbles/SKILL.md:347`  | "Fake omniscience"                                 | useful guardrail         | keep                                                                      |
| `skills/vc-marbles/SKILL.md:383`  | "You don't need to bother..."                      | sloppy boundary          | rewrite as "Do not chase unrelated overgrowth; report it if encountered." |

### Repeated Skill Boilerplate

| File                                                     | Current snippet                                           | Category                       | Verdict                                                           |
| -------------------------------------------------------- | --------------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------- |
| `skills/vc-agents/SKILL.md:20` and repeated skill copies | "Generic words like 'isolate'... are not enough"          | defensive duplicated clause    | centralize in `skills/LIVING_TREE_RULE.md`; keep short references |
| `skills/LIVING_TREE_RULE.md:28`                          | "too poisoned to continue safely"                         | overdramatic substrate wording | rewrite as "invalid or unsafe to continue"                        |
| repeated `skills/*/SKILL.md`                             | "missing `vc-init`/Loctree evidence is a process failure" | strong but duplicated          | keep intent, centralize as a single gate                          |
| repeated `skills/*/SKILL.md`                             | "Use rg/grep as fallback or local magnifier..."           | boilerplate noise              | keep one canonical fallback rule                                  |

### AGENTS.md / Global Voice

| File            | Current snippet                                       | Category                | Verdict                                                |
| --------------- | ----------------------------------------------------- | ----------------------- | ------------------------------------------------------ |
| `AGENTS.md:198` | "because the agent did not look hard enough"          | blamey/defensive        | rewrite as "created without checking existing systems" |
| `AGENTS.md:272` | "Do not hide uncertainty."                            | epistemic guardrail     | keep                                                   |
| `AGENTS.md:458` | "Do not preserve bad architecture out of politeness." | direct product doctrine | keep                                                   |
| `AGENTS.md:530` | "parallel systems created to avoid cleanup"           | useful anti-pattern     | keep                                                   |

### Runtime Docs

| File                                  | Current snippet                                 | Category                      | Verdict                                                                                    |
| ------------------------------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------ |
| `docs/runtime/CONTRACT_v1.5.0.md:288` | `Resume? maybe`                                 | underspecified failure policy | replace `maybe` rows with explicit states: `after_diagnosis`, `operator_decision`, or `no` |
| `docs/runtime/CONTRACT.md:250`        | "stop pretending spawn is correctly configured" | scolding                      | rewrite as "Report spawn as unconfigured until required tools are available."              |
| `skills/vc-agents/SKILL.md:231`       | repeated "stop pretending spawn..."             | duplicate scolding            | rewrite or point to runtime contract                                                       |

### Positioning / Research Prompts

| File                                      | Current snippet                                     | Category               | Verdict                                           |
| ----------------------------------------- | --------------------------------------------------- | ---------------------- | ------------------------------------------------- |
| `docs/THE_VIBE_HANGOVER.md:5`             | "Not hating on vibe coding."                        | apologetic positioning | delete/rewrite; lead with respect plus problem    |
| `skills/vc-init/SKILL.md:57`              | quote repeats "Not hating..."                       | imported apology       | rewrite with sharper positioning quote            |
| `skills/vc-research/agents/openai.yaml:4` | "might be too extensive to examine by single model" | hedge and grammar      | rewrite as "requires multiple independent angles" |
| `skills/vc-research/SKILL.md:11`          | "one agent's perspective is not enough"             | mild defensive framing | rewrite as "needs independent triangulation"      |

## Language Audit - Keep Targets

Not every defensive-looking string is bad. These should stay because they make
agents safer or more falsifiable:

- "Do not hide uncertainty."
- "Do not preserve bad architecture out of politeness."
- "parallel systems created to avoid cleanup"
- "Fake omniscience"
- "Convergence cosplay"
- "If you cannot cite..."
- "No question - take the task - just do it."
- "Language models cannot guess..."

These are not apology. They are control language.

## First Concrete Patch Landed

Added:

- `skills/references/agent-control-contract.md`

This gives the next skill edits one shared control surface:

- Iron Law
- Gate Function
- Allowed Statuses
- Red Flags / Stop
- Output Contract
- Acceptance Criteria

## Next Concrete Patch

Make one small but high-leverage follow-up pass:

1. Add a shared control-contract reference:
   `skills/references/agent-control-contract.md` - done in this pass.
2. Add the standard block to the weak/medium skills first:
   - `vc-justdo`
   - `vc-aicx`
   - `vc-delegate`
   - `vc-decorate`
   - `vc-followup`
   - `vc-screenscribe`
3. Polish the Marbles command wording listed above.
4. Replace `Resume? maybe` policy rows in runtime contracts.
5. Add a skill lint check:
   - no TODO/pending migration in plugin manifest descriptions
   - no `maybe` in policy tables without explicit status meaning
   - every `vc-*` skill has Iron Law, Gate Function, Allowed Statuses,
     Red Flags / Stop, Output Contract, Acceptance Criteria

## Summary

The reference prompt is a good target because it is executable as a contract.
Vibecrafted already has enough doctrine. The next step is not more prose. The
next step is one shared control grammar and a lintable skill contract.

## Files Changed

- `reports/agent-runs/skill-mechanics-language-audit-20260608-181952.md`
- `skills/references/agent-control-contract.md`

## Verification Performed

- Loctree context consumed.
- AICX intents consulted.
- Three read-only agents dispatched and integrated.
- 27 `vc-*` skill bodies measured and compared.
- 14 Superpowers skill bodies measured and compared.
- Literal-language scan counted 1292 raw candidates and 852 high-signal
  candidates.
- Shared agent-control contract added as the first concrete step toward
  lintable workflow prompt mechanics.

## Verification Not Performed

- No skill bodies were edited in this pass.
- No markdown lint gate was run before writing this report.
- The 852 high-signal literal candidates were not materialized into a committed
  TSV appendix.

## Risks Or Follow-Up

- Companion docs such as `PHASES.md`, `DISPATCH.md`, `FLOW.md`, templates, and
  runtime contracts strengthen some skills beyond their main `SKILL.md`.
- Line numbers may drift in the living tree.
- The next patch should change the skill mechanics directly, not produce another
  analysis artifact.
