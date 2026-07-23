---
title: Delegation Matrix
kind: doctrine_matrix
version: 3.0.0
description: "Canonical invocation, execution, and delegation model for the Vibecrafted fleet."
scope: framework
status: active
---

# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Delegation Matrix

> Invocation, execution, and delegation model for the Vibecrafted fleet.

<!-- fleet-imperative: v3 -->

## Invocation, Execution, and Delegation Model

A `vibecrafted` skill or workflow may be invoked through three distinct paths:

### 1. User-Launched Worker

The user may invoke `vibecrafted workflow <agent>` through the launcher CLI. This creates a separate, non-interactive worker run responsible for executing the complete pipeline.

### 2. Interactive Skill Invocation

The user may invoke `/vc-workflow` or load the skill inside an existing agent session. In this case, the current agent must load and execute the complete skill within that same session. It must not externalize the workflow itself to a separate `vibecrafted` worker merely because delegation is available. It may, and when required must, use its native in-process subagent fleet to complete the workflow thoroughly.

### 3. Agent-Operator Delegation

While conducting broader orchestration, an agent operator may use `vibecrafted workflow <agent>` as a `vc-dispatch` agent, just as the user can. This launches a separate workflow session through the `vibecrafted` runtime and delegates the full pipeline to the external fleet agent.

---

## Execution Mandate and Lifecycles

While under a workflow through an interactive or non-interactive invocation, the agent has the same mandate: execute the pipeline instructions from the skill comprehensively and use available native subagents when necessary.

The difference is only:

- **where** the workflow executes
- **whose attention** it occupies

Nonetheless:

- A **headless worker** retains authority to spawn and coordinate its own native subagents — being a worker constrains the scope and lifecycle of its run, but does not remove its delegation authority.
- An **agent that receives the skill interactively** must execute it locally within the current session using its native subagents when appropriate.

---

## Native Subagents vs External Workflow

A subagent that is running as part of the agent's native fleet may appear similar to a separate worker, but is distinct in its integration and context lifecycle:

- **Native Subagents**: live within the same process as the orchestrating agent. They share memory, configuration, and execution context.
- **External Workers**: launched as separate `vibecrafted` processes. They communicate with the orchestrator through defined interfaces and have independent lifecycles.

The decision to use native subagents or delegate to an external worker depends on the use case, but the fundamental principle remains: **workflow execution authority is retained by the agent unless explicitly delegated through defined channels.**

---

## Exceptions and References

- **Native Subagent Exceptions**: Defined with specific constraints in [`vc-delegate`](vc-delegate/SKILL.md).
- **External Fleet Dispatch**: Defined in [`vc-dispatch`](vc-dispatch/SKILL.md).
- **Operator Multi-Wave Orchestration**: Defined in [`vc-operator`](vc-operator/SKILL.md).

<!-- /fleet-imperative -->
