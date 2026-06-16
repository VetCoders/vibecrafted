# `vc-operator` Journal

The operator journal is an append-only mission diary for orchestration.

It records why waves were fired, paused, recovered, escalated, or stopped. It
complements the wave tracker.

## Path

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/operator/journal.md
```

Related artifact:

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/operator/tracker.md
```

## Journal vs Tracker

| Artifact     | Purpose                                                             |
| ------------ | ------------------------------------------------------------------- |
| `tracker.md` | current wave status, checkboxes, run IDs, branches, SHAs, gates     |
| `journal.md` | decisions, role shifts, stalls, recovery logic, close-out reasoning |

The tracker answers "what landed?".
The journal answers "why did the operator do that next?".

## Rules

- Append only.
- First entry declares operator posture and plan.
- Every fire, await, notify, stall, recovery, escalation, close-out, and stop
  point gets an entry.
- Every plan mutation and security guardrail incident gets an entry.
- Corrections are written as new entries.
- Worker-facing closing rails do not appear in operator journal entries.
- Do not collapse separate worker states into a vague wave status.

## First Entry

````md
## <timestamp> - operator mode active

```yaml
operator_run:
  plan_name: ""
  artifact_root: ""
  source_plan: ""
  init_evidence: ""
  stop_point: "operator button"
```

- State:
- Wave atlas:
- Next:
````

## Dispatch Entry

```md
## <timestamp> - fire wave <n>

- Wave:
- Briefs:
- Agents:
- Run IDs:
- Dependency state:
- Await path:
```

## Await Entry

```md
## <timestamp> - await wave <n>

- Completed:
- Running:
- Stalled:
- Reports:
- Gates:
- Next:
```

## Recovery Entry

```md
## <timestamp> - recovery dispatch

- Stalled run:
- Failure class:
- Evidence:
- Recovery brief:
- Recovery agent:
- Expected close condition:
```

## Plan Mutation Entry

```md
## <timestamp> - plan mutation

- Changed:
- Why:
- Final goal unchanged because:
- Evidence:
- Next:
```

## Security Guardrail Entry

```md
## <timestamp> - security guardrail

- Surface: prompt | commit
- Detected:
- Action taken:
- Recommit SHA, if applicable:
- Next:
```

## Close-Out Entry

```md
## <timestamp> - wave <n> close-out

- Landed:
- Branches:
- SHAs:
- Gates:
- Risks:
- Next wave or stop reason:
```

## Stop-Point Entry

```md
## <timestamp> - stop at operator button

- Completed waves:
- Remaining human button:
- Evidence:
- Risks:
- Recommended next action:
```
