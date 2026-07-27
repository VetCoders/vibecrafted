---
name: vc-partner
version: 3.0.0-dev
description: >
  Proactive interactive posture for shared steering with the operator.
  `vc-partner` preserves the original shape across planning, compaction,
  delegation, review, audit, DoU, and shipping. Use when the user wants to
  define the problem together, keep strategic decisions shared, and let the
  agent do heavy work without letting the vision drift. Mentioning the skill
  in an interactive session does not automatically launch the same-named
  runtime workflow.
  Trigger phrases: "partner mode", "idziemy razem", "przemyslmy to",
  "zlapmy shape", "zdefiniujmy problem", "proactive partner",
  "shared steering", "nie rozmyj wizji", "pilnuj pierwotnego shape".
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - web.run
    - js_repl
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v3 -->

> **Invocation for `vc-partner` (launcher `partner`)**
>
> Same three-path _shape_ as the fleet, with **this** skill's literals — see the
> canonical [Delegation Matrix](../DELEGATION_MATRIX.md):
>
> - [Shared three paths](../DELEGATION_MATRIX.md#shared-three-paths)
> - [Launcher catalogue](../DELEGATION_MATRIX.md#launcher-catalogue-core-runtime)
> - [Per-launcher rule](../DELEGATION_MATRIX.md#per-launcher-rule-the-semantic-delta)
> - [Native vs external](../DELEGATION_MATRIX.md#native-subagents-vs-external-workers)
>
> | Path                    | Literal for this skill                                                                                                                   |
> | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
> | 1. User-launched worker | `vibecrafted partner <agent>`                                                                                                            |
> | 2. Interactive          | `/vc-partner` — execute **in this session**; use native subagents when required; do **not** externalize merely because a launcher exists |
> | 3. Agent-operator       | may dispatch the worker form above via `vc-dispatch` / operator lines while preserving this skill's identity                             |

> Freer native on some runs ≠ abandon external fleet. `vc-dispatch` and `vc-ship` keep their own identities.

<!-- /fleet-imperative -->

# vc-partner

> Proactive shared steering. Original-shape custody. Read/write cadence before
> ship.

## Taxonomy

```yaml
vc-partner:
  kind: interactive_posture
  scope: current_interactive_session
  meaning: proactive shared steering, original shape custody, partner journal
  autonomy: collaborative
```

`vc-partner` is not a weaker `vc-ownership`.

- `vc-partner` keeps the steering brain shared with the operator.
- `vc-ownership` takes responsibility end-to-end with fewer checkpoints.
- `vc-operator` orchestrates waves and recovery dispatches.
- `vc-init` opens the session with repo/runtime/intention truth; it is not a
  posture.

Skill invocation is not runtime invocation. If the operator says `$vc-partner`
inside the current conversation, the current agent adopts this posture. A
separate runtime run exists only when the operator or framework launches
`vibecrafted partner <agent> ...`.

See [TAXONOMY.md](TAXONOMY.md) for the side-by-side skill/runtime map.

## Canonical Orientation Gate

Partner mode requires fresh `vc-init` evidence before repo-specific planning,
delegation, implementation, review, audit, or release decisions. If fresh
`vc-init` evidence is absent, perform the init pass first and treat the partner
plan as provisional until repo truth exists.

`Loctree:loctree` is the default structural perception skill for that pass.
Use it to produce or refresh the Code-Derived Application Map before building
the plan with `vc-scaffold`, choosing execution lanes, or judging shape
fidelity against live code.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Prime Directive

Preserve the original shape.

Every plan, worker, audit, compacted context, and recovery move is judged
against the shape captured at the beginning of the mission. The partner may
adapt the plan when runtime truth disproves an assumption, but must not let the
vision dissolve silently.

## Original Shape

At the start of a non-trivial partner session, capture:

```yaml
original_shape:
  problem: ""
  promise: ""
  target_user_or_operator: ""
  invariants: []
  non_goals: []
  success_contract: []
  accepted_drift_policy: "only with explicit journal entry"
```

If the user is still thinking aloud, help sharpen this contract instead of
pretending the problem is already stable.

## Core Flow

1. Define the problem.
2. Write the success contract.
3. Build the plan with `vc-scaffold`.
4. Choose the execution shape.
5. Run the write lane.
6. Verify runtime truth with `vc-review`.
7. Judge shape fidelity with `vc-followup`.
8. Close gaps, usually through `vc-marbles` when the gap needs write work.
9. Run independent `vc-audit`.
10. Run `vc-dou` before claiming the task is finished or release-ready.
11. Polarize or release only after the read-only checks agree with the shape.

See [FLOW.md](FLOW.md) for the flowchart and routing details.

## Read-Write Cadence

Every write workflow must be followed by read-only perception before completion:

```text
write:
  vc-implement | vc-workflow | vc-marbles | vc-polarize

read:
  vc-review -> vc-followup -> vc-audit -> vc-dou
```

Do not claim a task is finished before the Definition of Undone pass has
cleared or explicitly recorded the remaining product-surface gaps.

## Execution Shape

Choose the smallest runtime lane that can honestly satisfy the success
contract:

- Single bounded lane -> dispatch one `vc-implement` agent.
- Strict Examine -> Research -> Implement pipeline -> dispatch `vc-workflow`.
- Field teams -> escalate through the `vc-operator` pipeline.
- Operator says "take over" -> escalate to `vc-ownership`.
- Gaps found by `vc-followup` -> close with `vc-marbles` or a focused write
  lane.
- Entropy after marbles -> `vc-audit` then `vc-polarize`.
- Release surface -> `vc-release`, after DoU.

Do not delegate before the problem and success contract are explicit.

When you dispatch a lane while sitting with the operator, keep the worker
**headless and observable**. CLI and MCP use the same detached default even when
`VC_FRAME_SESSION_NAME` is live. Share the durable transcript, `observe`,
`await`, and Guardian state; vc-frame may project those surfaces but must not
own the worker process. Use `terminal` / `visible` only for a provider path
proven to require a TTY.

## Partner Journal

For work that may span compaction, delegation, review, or multiple turns, keep
an append-only partner journal. The journal is the mission memory, not a final
report.

Default runtime path:

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/partner/journal.md
```

In a purely interactive session without a runtime artifact directory, keep the
journal shape in the response/report until the framework can persist it.

See [JOURNAL.md](JOURNAL.md) for the entry contract.

## Operating Rules

- Keep the operator in the strategic loop.
- Do the heavy work proactively.
- Ask only when the decision changes the shape, risk, cost, or operator intent.
- Name uncertainty as a hypothesis and kill or prove it.
- Separate review, followup, audit, and DoU:
  - `vc-review` checks implementation/runtime truth.
  - `vc-followup` checks direction and shape fidelity.
  - `vc-audit` falsifies completed claims independently.
  - `vc-dou` checks product-surface undone work before finish/release.
- Treat compaction as a risk event. Re-anchor on `original_shape` and the
  partner journal after every resume.
- If your earlier model was wrong, write the correction plainly and continue.

## Escalation

- Escalate to `vc-ownership` when shared steering is no longer the desired
  mode.
- Escalate to `vc-operator` when multiple external agents must be coordinated
  as a wave.
- Escalate to `vc-marbles` when P0/P1 gaps remain after implementation and
  followup.
- Escalate to `vc-release` when the repo/runtime work is done and DoU no
  longer blocks outward shipping.

## Output Shape

For ordinary updates:

1. Current state.
2. Shape check.
3. Decision or proposal.
4. Next bounded move.

For close-out:

1. Original shape.
2. What changed.
3. Evidence and gates.
4. Gaps closed.
5. Review/followup/audit/DoU state.
6. Ship or next move.

## Anti-Patterns

- Turning Partner into silent Ownership.
- Letting workers redefine the original shape.
- Treating Mermaid or prose as a binding runtime contract.
- Shipping because tests passed while shape fidelity or DoU failed.
- Calling audit before local gaps are closed.
- Calling the task finished before DoU.
- Rewriting the journal to make the story cleaner.

## Helper Documents

- [FLOW.md](FLOW.md) - collaborative delivery flow and routing.
- [TAXONOMY.md](TAXONOMY.md) - side-by-side `vc-*` skill/runtime map.
- [CONTRACT.md](CONTRACT.md) - binding posture/runtime contract.
- [JOURNAL.md](JOURNAL.md) - append-only partner journal format.
- [RUNTIME.md](RUNTIME.md) - runtime launch and artifact expectations.
