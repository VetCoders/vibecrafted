# VetCoders Partner

Executive-brain partner skill for hard debugging, architecture triage, and
feature framing where:

- user + Codex stay the managing brain
- spawned agents do the field research, planning, review, and bounded
  implementation work

This skill is for sessions where we do not want to outsource strategy. We keep
the problem definition, chronology, contract rules, and final decisions in the
main thread, then use external agents as comparative field teams.

## What It Is Good For

Use `vc-partner` when:

- runtime truth matters more than static code reading
- a failure has to be reconstructed step by step
- one agent opinion is not enough
- the team wants comparative planner swarms before implementation
- implementation should continue on the same research threads via `*-resume`

Typical examples:

- entitlement or billing flows with hidden state
- multimodal/runtime contract bugs
- architecture forks where the wrong early assumption would waste days
- product failures where chronology matters as much as code

## Core Operating Model

The default loop is:

1. define the exact failure or feature surface together
2. split it into `2-3` clean research tracks
3. write precise exploratory plans
4. run the same plans through:
   - `codex-plan`
   - `claude-plan`
   - `gemini-plan` when available
5. synthesize agreements and disagreements
6. continue the same sessions through `*-resume`
7. converge with `vc-marbles`

This is not “ask agents and wait.” It is command-and-control with shared
reasoning in the center.

## Key Rules

- runtime truth beats theoretical correctness
- one hypothesis at a time; prove or kill it
- preserve an append-only findings log during the crisis
- keep the user and Codex as the executive brain
- agents do not own strategy

## Spawn and Resume

`vc-partner` is designed to pair naturally with
`vc-agents`:

- planner swarms go out through the portable spawn scripts with `--mode plan`
- chosen tracks continue via `*-resume` helpers or fresh implementation agents

> **Note**: `codex-plan`, `claude-plan`, `gemini-plan`, `*-resume` are
> convenience aliases from private dotfiles. The canonical, machine-portable
> equivalent is the repo-owned spawn scripts:
> `bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/codex_spawn.sh <plan>.md --mode plan`
> See `vc-partner/SKILL.md` Spawn Playbook for full details.

During resumed implementation, one important rule now applies:

- a resumed implementation agent may spawn **exactly one** extra helper agent,
  but only for a real, bounded blocker
- the parent agent still owns the implementation track and final synthesis

That keeps the method sharp without turning it into uncontrolled fleet sprawl.

## Files

- `SKILL.md` — canonical instructions for the partner workflow

## Relationship To The Rest Of The Stack

`vc-partner` sits above the lower-level tools:

- `vc-agents` for external agent execution
- `vc-workflow` for structured examine/research/implement flows
- `vc-marbles` for convergence once the shape is chosen

If `vc-workflow` is the pipeline, `vc-partner` is the
executive operating mode for the hardest sessions.
