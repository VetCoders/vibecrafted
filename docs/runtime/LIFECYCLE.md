# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Lifecycle — Read-Write Cadence

> Canon source: operator-dictated, 2026-06-08 (doc_id `intents_2026_0506`),
> persisted into the repo by cut `VC-vbcr-canon-034`. The phase table below is
> substantively 1:1 with the dictated canon; only linguistic redaction was
> applied. Status is earned by the runtime, not announced by the spawner.

This document is the canonical description of the full 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. product
lifecycle: the read/write cadence of the `vc-ship` pipeline, the component
architecture it runs on, and the async supervision model that closes the loop.
For the execution engine and spawn mechanics see
[`CONTRACT.md`](./CONTRACT.md); for the parked implementation follow-ups see
[`READ_WRITE_CADENCE_TODO.md`](./READ_WRITE_CADENCE_TODO.md).

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
  commits and completions; automatically triggers Audit after Marble.
- **Audit agent** — has its own lifecycle and helper; connects to the next
  agent after the audit; fires the "baton" to the next agent.
- **Umbrella mode** — processes can move backwards or forwards.

## Summary

The project closes within the Lifecycle — complete automation from A to Z;
all components wired into one system with agents and an async supervisor;
simplicity in UX, flexibility in the backend (code, servers, VM).

---

## Runtime truth hooks (where the cadence is enforced today)

- Run state lifecycle: `launching → running → completed|failed|ghost`,
  written by the run owner (spawner writes `launching`, the generated
  launcher earns `running`, `spawn_finish_meta` / `spawn_reap_dead_run`
  close it) — see `runtime/scripts/lib/meta.sh` and
  `runtime/scripts/lib/launcher.sh`.
- Artifact truth: the path announced at spawn stays valid after the
  artifact-contract rename (compat symlinks in `spawn_finalize_artifacts`).
- The async supervisor, MCP control surface, and umbrella mode described
  above are ROADMAP from the canon — documented here, implemented
  incrementally (see `READ_WRITE_CADENCE_TODO.md` and
  `RUNTIME_INTEGRATION_ROADMAP.md`).
