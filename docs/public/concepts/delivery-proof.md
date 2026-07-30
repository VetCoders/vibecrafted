---
title: "Delivery proof"
description: "Evidence discipline: report frontmatter, claims versus settlement, the f/x/n ledger, and why a process exit never finalizes anything."
section: concepts
order: 50
---

# Delivery proof

Vibecrafted treats "the agent said it finished" as a claim, not a fact.
A run becomes settled only when independent evidence agrees with the
claim. This page explains the evidence chain: structured reports, the
separation of execution from proof from delivery, and the settlement
ledger you can query.

## The core inequality

```text
the process exited
≠ the verifier actually examined the product
≠ the declared effect was achieved
≠ the change was delivered where it was promised
≠ the proof of delivery was sealed
```

The runtime represents these facts separately and never derives one from
another automatically. A bare exit code 0 finalizes nothing.

## Reports carry a machine contract

Every Markdown artifact a worker produces — plan, report, research doc —
must open with a YAML frontmatter block (contract id
`vibecrafted.report-frontmatter.v1`):

```yaml
---
run_id: impl-<timestamp>-<id>
agent: codex
skill: vc-implement
project: my-app
status: completed
claim_status: completed # the agent's own claim
date: 2026-07-30T12:00:00+00:00
---
```

Required keys are `run_id`, `agent`, `skill`, and `status`. A missing block
or missing required key is an artifact contract error
(`report_frontmatter_*`) — the run is not Finalized, regardless of how
confident the prose below sounds.

**A claim is not a self-seal.** `claim_status: completed` is triangulated
against the process exit code, the report and transcript, and the delivery
kernel's own axes. Contradictions do not resolve in the agent's favor —
they land the run in Needs attention.

## Three orthogonal axes

The delivery-proof kernel keeps three states that may not be collapsed
into each other:

| Axis      | Question it answers                                    | Example values                                      |
| --------- | ------------------------------------------------------ | --------------------------------------------------- |
| Execution | Did the process run and how did it end?                | running, exited, interrupted, launch_failed         |
| Proof     | Did a qualified verifier examine the product and pass? | undeclared, running, passed, failed, invalid, stale |
| Delivery  | Does the proven effect exist where it was promised?    | unverified, delivered, sealed                       |

Each arrow on the success path requires its own evidence:

```text
execution.exited(0) → proof.passed → delivery.delivered → delivery.sealed
```

A report that exists and has bytes proves only that a report exists
(`artifact_ok` — a transport fact). An `interrupted` or `partial` run can
never be promoted to delivered by a compatibility projection. And a proof
is `invalid` — not the product, the proof — when the verifier cannot
demonstrate it would detect a controlled falsehood.

Only the shipping authority (`vc-ship`) issues a delivery seal. A direct
worker run can honestly end as `execution.exited / proof.passed /
delivery.unverified` — that is not failure; it is precision.

## The settlement ledger: f / x / n

Run-level settlement truth lives in an immutable, append-only,
hash-chained ledger at
`~/.vibecrafted/control_plane/settlement_ledger.jsonl`. Every finished run
settles into one of three buckets:

| Bucket | Meaning                                                                |
| ------ | ---------------------------------------------------------------------- |
| `f`    | Finalized — claim and evidence agree                                   |
| `x`    | Failed — the run demonstrably failed                                   |
| `n`    | Needs attention — contradiction, missing evidence, or an unsettled end |

Zero on this rail is a verdict, not a default. UI counters, boards, and
chat surfaces must derive f/x/n from this ledger; none of them may invent
an `f` locally.

## Querying settlements

The read-only query surface (schema `vibecrafted.settlements-query.v1`)
never mutates the ledger:

```bash
vibecrafted settlements summary          # f/x/n counts over the ledger
vibecrafted settlements list             # filtered run rows
vibecrafted settlements inspect <run_id> # one run, full settlement view
vibecrafted settlements revalidatable    # runs whose evidence is still on disk
```

`revalidatable` means the report and transcript still exist for a
deliberate re-verification campaign — not that anything will resume
automatically.

## Why this discipline exists

Autonomous agents are rewarded, by default, for telling a good story about
finishing. The proof discipline removes that reward: the runtime stops
trusting well-narrated endings and starts requiring contact with reality —
a verifier that ran the actual product, an assertion that consumed its
actual output, and a ledger entry that cannot be rewritten afterwards.
That is what makes it safe to give agents real autonomy.
