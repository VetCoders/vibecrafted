# `vc-justdo` Flow — posture, compatibility runtime

> Posture is standalone. Runtime remains compatibility-wired to `vc-implement`
> until the de-alias migration in `docs/adr/0001-vc-justdo-standalone.md` lands.
> „Nie pierdol, po prostu zrób proszę" — take the task, just do it, regardless of task type.

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted justdo claude --prompt '<task>'  ·  $vc-justdo in chat] --> G[Canonical Orientation Gate: vc-init + loctree — no-question ≠ no-orientation]
    G --> T{Task type — defined by PROMPT, not by the skill}
    T --> X[Take the task — no questions, no best-of-n]
    X --> Ex[Proactively explore if context is thin — exploration replaces questioning]
    Ex --> D[Deliver — carry the vc-ownership posture]
    D --> V[Verify: measure-core — finish [x] via verifier, never [~] on word]
```

## Posture (not a pipeline phase)

vc-justdo stands **beside** the VC-ship read/write cadence — it is **not** a WRITE phase (that is
`vc-implement`). It is the daily-rescue escape-hatch: no question, take the task, just do it. The task
type (implement / review / audit / research / fix / anything) comes from the prompt, not the skill.

## Routes

| Entry                                     | Args                   | Produces                                           | Exit            |
| ----------------------------------------- | ---------------------- | -------------------------------------------------- | --------------- |
| `vibecrafted implement <agent>`           | `--prompt` or `--file` | canonical autonomous implementation runtime        | `0` on dispatch |
| `vibecrafted justdo <agent>`              | same                   | compatibility alias until de-alias migration lands | `0` on dispatch |
| `vc-justdo <agent>`                       | same                   | shell shortcut / compatibility alias               | `0` on dispatch |
| `$vc-justdo` / `/vc-justdo` (interactive) | —                      | agent adopts the "just do" posture in-session      | —               |

### Boundaries (carried from `../vc-ownership/SKILL.md`)

- Move immediately: edits, tests, docs, scoped refactor, local smoke, recovery-commit.
- Pause + realign before irreversible: destructive git, push/merge/deploy/publish, spend, secrets/auth, prod data.

### Runtime migration status (honest)

The **posture/skill** is standalone (this file + `SKILL.md` v3.0.0 agree). The **runtime de-alias** —
splitting the run-id prefix (`just-`) and the installer/registry so `justdo` no longer collapses onto
`implement` — is the pending migration scoped in `../../docs/adr/0001-vc-justdo-standalone.md` (status:
Proposed). Until ratified, the launcher may still share run-id wiring with `implement`.

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: `reports/<timestamp>_<slug>_<agent>.md` with matching `.transcript.log` and `.meta.json`
