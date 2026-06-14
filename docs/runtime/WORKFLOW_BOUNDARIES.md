# Workflow Boundaries

Vibecrafted has three related surfaces that must stay separate:

- `skills/<workflow>/` is interactive doctrine. It tells a human-loaded or
  agent-loaded skill how to think and behave.
- `runtime/workflows/<workflow>/` is executable workflow truth. It owns default
  prompts, runtime assets, and workflow-specific runner material.
- `vibecrafted_core.workflows.registry` is the Python index over executable
  workflow truth. It gives launch code a stable way to ask for input policy,
  default agent, runtime kind, lifecycle order, and read/write cadence.

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

This is the runtime-side substrate for a future `vc-ship`/operator lifecycle:
distinct workflow nodes, distinct agent runs, and an async supervisor that can
move the baton forward or backward based on observed truth.
