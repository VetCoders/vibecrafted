# Workflow Boundaries

Vibecrafted has three related surfaces that must stay separate:

- `skills/<workflow>/` is interactive doctrine. It tells a human-loaded or
  agent-loaded skill how to think and behave.
- `runtime/workflows/<workflow>/` is executable workflow truth. It owns default
  prompts, runtime assets, and workflow-specific runner material.
- `vibecrafted_core.workflows.registry` is the Python index over executable
  workflow truth. It gives launch code a stable way to ask for input policy,
  default agent, runtime kind, lifecycle order, read/write cadence, and umbrella
  lifecycle manifests such as `vc-ship`.
- `vibecrafted_core.lifecycle_runner` is the umbrella runtime. It reads the
  registry manifest, loads Context Atlas, launches each stage through
  `vibecrafted_core.workflow`, records state, and writes a lifecycle report.
- `vibecrafted_core.lifecycle_runner.LifecycleSupervisor` is the async MVP
  facade for server/app observability. It starts the same runner, reads state,
  and projects a compact status view; it is not a second lifecycle owner.

`vibecrafted_core.workflow` remains a compatibility launcher facade. It should
not become the place where workflow semantics accumulate.

## Lifecycle Cadence

The registry models the current read/write cadence:

| Workflow    | Cadence | Role                                |
| ----------- | ------- | ----------------------------------- |
| `scaffold`  | read    | discovery and plan shape            |
| `implement` | write   | delivery through operator/agents    |
| `review`    | read    | test-heavy review and falsification |
| `workflow`  | write   | examine/research/implement lane     |
| `followup`  | read    | intent and direction check          |
| `marbles`   | write   | entropy-up convergence runtime      |
| `audit`     | read    | independent falsification           |
| `polarize`  | write   | entropy-down simplification         |
| `dou`       | read    | Definition of Undone before release |
| `hydrate`   | write   | preflight product surface work      |
| `release`   | write   | outward shipping work               |

This is the runtime-side substrate for `vc-ship`: distinct workflow nodes,
distinct agent runs, and an async supervisor that can move the baton forward or
backward based on observed truth. `vc-marbles` has an explicit `audit_after`
edge to `audit`; READ stages carry `can_modify_code=false`, WRITE stages carry
`can_modify_code=true`. Manifest payloads also expose `allowed_artifacts`,
`transition_conditions`, and `human_controls` so READ/WRITE behavior and human
intervention are explicit machine-readable contract, not prose-only doctrine.

Each lifecycle stage also exposes explicit transition conditions and allowed
artifact classes. READ stages allow reports, cache, transcripts, and run state;
WRITE stages additionally allow code, docs, and generated files. Manifest-level
`human_controls` model the operator actions the workflow understands: approving
transitions, interrupting runs, forcing audits, accepting DoU findings, and
choosing fallback stages.
