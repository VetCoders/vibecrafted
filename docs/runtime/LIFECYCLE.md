# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Lifecycle — Read-Write Cadence

> Canon source: operator-dictated, 2026-06-08 (doc_id `intents_2026_0506`),
> persisted into the repo by cut `VC-vbcr-canon-034`. The phase table below is
> substantively 1:1 with the dictated canon; only linguistic redaction was
> applied. Status is earned by the runtime, not announced by the spawner.

This document is the canonical description of the full 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. product
lifecycle: the read/write cadence of the `vc-ship` pipeline, the component
architecture it runs on, and the async supervision model that closes the loop.
The executable truth lives in `vibecrafted_core.workflows.registry` and
`vibecrafted_core.lifecycle_runner`. This document explains the operator
contract; the Python manifest is the runtime source of truth.

---

## vc-ship — the meta-skill

`vc-ship` is a meta-skill, usually launched in the `vc-operator` formula.
The pipeline alternates READ and WRITE phases — perception before mutation,
proof after pressure.

## Phase cadence (vc-ship pipeline order)

| #   | Phase        | Cadence | Tooling                                                                                             | Notes                                                              |
| --- | ------------ | ------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| 1   | VC Scaffold  | READ    | `vc-init`, `vc-loctree`, `vc-research`                                                              |                                                                    |
| 2   | VC Implement | WRITE   | `vc-init`, `vc-operator`, `vc-agents`                                                               |                                                                    |
| 3   | VC Review    | READ    | `vc-init`, `vc-loctree`, `vc-review`, `vc-screenscribe`, `vc-prview`                                | Deviation from "tests always last" — Review is test-heavy          |
| 4   | VC Workflow  | WRITE   | `vc-init`, `vc-research`, `vc-implement`                                                            |                                                                    |
| 5   | Follow-up    | READ    | `vc-init`, `vc-intents` (main intention engine), `vc-loctree`, TDD                                  | Tests always at the end                                            |
| 6   | VC Marbles   | WRITE   | `vc-init` + `vc-marbles` (unique runtime)                                                           | ⬆ entropy — we fill every crack                                    |
| 7   | VC Audit     | READ    | `vc-init`, `vc-loctree`, `vc-aicx`, `vc-research`                                                   |                                                                    |
| 8   | VC Polarize  | WRITE   | `vc-init` + `vc-polarize` (marbles runtime)                                                         | ⬇ entropy — we cut the excess, choose one truth — without scruples |
| 9   | VC DoU       | READ    | `vc-init`, `vc-intents`, `vc-loctree`; TDD irrelevant (assumed green)                               | Detects gaps before the release procedure                          |
| 10  | VC Hydrate   | WRITE   | Preflight Hard Job — `vc-init`, `vc-operator`, `vc-decorate`                                        |                                                                    |
| 11  | VC Release   | WRITE   | SEO, deployment, Docker, publishing, codesigning and everything else agents can't do _totallissimo_ |                                                                    |
| +   | **Fanfary**  | —       | —                                                                                                   | At the very end                                                    |

## Invocation

`vibecrafted <phase> <agent>` is the public command grammar; `vc-<phase>`
wrappers remain installed shell shortcuts. The agent starts after the Context
Atlas is loaded (`loct context`). Separate runtime, separate agent. Target
state: every workflow launchable the same way.

`vc-ship <agent> --prompt ...` starts the umbrella lifecycle runner. By default
it launches the first stage (`scaffold`) and writes lifecycle state under
`$VIBECRAFTED_HOME/control_plane/lifecycle_runs/<run_id>/`. Passing
`--await-stages` lets the MVP supervisor wait for each stage and hand the baton
to the next one. `--start-stage <stage>` or `--checkpoint <stage>` can resume
from a specific stage.

Single-stage lifecycle commands such as `vc-dou <agent>`, `vc-audit <agent>`,
`vc-marbles <agent>`, `vc-polarize <agent>`, and `vc-hydrate <agent>` launch
through `vibecrafted_core.lifecycle_runner` as one-stage manifests. The runner
loads Context Atlas once, writes lifecycle run state, prepares the stage prompt,
then delegates the actual agent process to `vibecrafted_core.workflow`.
`vibecrafted <skill> <agent>` remains the compatibility direct launcher for
ordinary skill dispatch.

## READ and WRITE semantics

READ phases may create reports, cache, transcripts, and run-state artifacts.
They must not mutate project code unless the operator explicitly changes the
stage contract.

WRITE phases may modify code, remove legacy, refactor, integrate, and generate
missing runtime pieces. The lifecycle runner records changed files after an
awaited stage so the handoff shows what moved.

## Human participation

The operator is part of the lifecycle, but operator actions must leave a trace.
The runtime should make the project feel steerable without turning manual
intervention into invisible state mutation.

Allowed operator moves:

- approve transition to the next lifecycle stage;
- interrupt a workflow and leave the run in a terminal or recoverable state;
- force an audit when the current evidence feels weak;
- mark a DoU finding as consciously accepted for this release;
- choose a fallback or earlier stage when audit evidence says the run should
  move backwards.

Boundaries:

- do not edit `state.json` by hand without recording why in the report or
  transcript;
- do not mix READ and WRITE behavior silently; if a READ stage needs to mutate
  code, change the phase contract explicitly first;
- do not treat a passing stage as product truth when install, docs, runtime, or
  release surfaces remain unverified;
- prefer baton handoff through lifecycle state and reports over side-channel
  chat instructions.

## Notes (operator)

- It must be clearly defined what the human can and cannot do.
- Human involvement in the process is crucial — to "feel" the project.
- Final goal: a big win and **ZERO DoU index**.

## Lifecycle — Architecture (components, all in this repo)

| Component     | Role                                                                                        |
| ------------- | ------------------------------------------------------------------------------------------- |
| Core (Engine) | Execution engine                                                                            |
| MCP           | The agent's eyes and hands (invokes agents, observes the environment)                       |
| VM            | Docker, isolated working environment                                                        |
| Server        | Remote observability + future control                                                       |
| App           | Full Swift application (branch `longtime/integration`)                                      |
| TUI           | Terminal agent `vc-tui` (separate from vc-frame, but launched INSIDE vc_frame / `vc-frame`) |

## Lifecycle — Operation

- **Marble** — launched with or without a prompt.
- **Async supervisor (Python)** — dispatches consecutive runs; observes
  commits, process completion, reports, and changed files; automatically
  triggers Audit after Marble when running a supervised lifecycle.
- **Audit agent** — has its own lifecycle and helper; connects to the next
  agent after the audit; fires the "baton" to the next agent.
- **Umbrella mode** — processes can move backwards or forwards.

## Summary

The project closes within the Lifecycle — complete automation from A to Z;
all components wired into one system with agents and an async supervisor;
simplicity in UX, flexibility in the backend (code, servers, VM).

---

## Runtime truth hooks (where the cadence is enforced today)

- Workflow manifest: `vibecrafted_core.workflows.registry.WORKFLOW_MANIFESTS`.
- Single-stage launcher: `vibecrafted_core.workflow.launch_workflow`.
- Umbrella runner: `vibecrafted_core.lifecycle_runner.LifecycleRunner`.
- Run state: `$VIBECRAFTED_HOME/control_plane/lifecycle_runs/<run_id>/state.json`.
- Final lifecycle report:
  `$VIBECRAFTED_HOME/control_plane/lifecycle_runs/<run_id>/report.md`.
- Agent run truth still comes from the existing control plane runtime runs,
  reports, transcripts, and metadata written by `launch_workflow` and the async
  dispatcher.
