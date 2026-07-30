---
title: "Dispatch Overview"
description: "Deterministic dispatch lines: what vibecrafted dispatch does, when to use it instead of ship, and the doctor, dry-run, and resume flags."
section: dispatch
order: 10
---

# Dispatch Overview

`vibecrafted dispatch` runs a `vibecrafted.dispatch.v1` TOML plan through a
deterministic supervisor: a serial loop that executes a predefined line of
cuts, launches one worker per cut, runs machine-checkable verifiers after
each, and applies explicit repair and failure policies. Where the
[lifecycle](/docs/lifecycle-overview/) relays one mission through eleven
generic stages, dispatch executes a plan you already decomposed — every cut
named, every success condition written down before anything launches.

## Running a dispatch line

```bash
vibecrafted dispatch plan.dispatch.toml
vibecrafted dispatch plan.dispatch.toml --doctor
vibecrafted dispatch plan.dispatch.toml --dry-run --json
vibecrafted dispatch plan.dispatch.toml --resume <run-id>
```

| Flag                | Effect                                                                   |
| ------------------- | ------------------------------------------------------------------------ |
| `--doctor`          | Validate only; exit non-zero on dispatch-doctor errors                   |
| `--dry-run`         | Render every worker prompt under `reports_dir/dry-run` without launching |
| `--json`            | Machine-readable output                                                  |
| `--resume <run-id>` | Continue a previous dispatch run                                         |

Run `--doctor` before every real launch: it parses the plan, checks the
schema, and enforces the policy rules (for example, READ cuts must declare a
`mutation` policy, and verifier commands must not contain hard-stop commands
like `git push`). `--dry-run` then shows you the exact prompt each worker
would receive — placeholders rendered, briefs inlined, baton attached.

## What the supervisor does per cut

For each `[[cut]]` in order, the supervisor:

1. Renders the cut's prompt: shared `[common]` text, then the cut's brief
   file or inline prompt, then `extra`, then the current baton state as JSON.
2. Launches the cut's agent through the named workflow as a tracked run.
3. Awaits the worker (poll and timeout from `[policy.await]`).
4. Runs the cut's verifiers and matches their output against the declared
   expectations (`contains`, `equals`, `matches`, `not_contains`,
   `exit_code`).
5. Records a verdict with verifier evidence, appends it to the baton, and
   applies policy: repair rounds on failure, `recovery` jumps when declared,
   and `on_critical_fail` / `on_timeout` behavior.

The baton accumulates one state per cut (`[x]` verified, `[!]` failed,
`[~]` worker done but unverified, `[ ]` pending) — later cuts see the full
history in their prompt, so an audit cut can read what actually happened.

## Artifacts

A full dispatch writes its evidence next to the plan's `reports_dir`:

```text
tracker.md              # per-cut state line
journal.md              # supervisor journal
handoff.md              # operator handoff
dispatch-result.json    # machine-readable result
```

Exit codes: the supervisor exits with the worker's exit code when a worker
fails, and with `2` when the worker exited cleanly but the artifact contract
failed (for example, no report was delivered).

## Dispatch vs ship

| Question                                                                | Use                    |
| ----------------------------------------------------------------------- | ---------------------- |
| The mission is one goal and stages should shape themselves              | `vibecrafted ship`     |
| The work is already a list of bounded cuts with known success commands  | `vibecrafted dispatch` |
| You want workers to steer transitions via report frontmatter            | `ship`                 |
| You want the supervisor to enforce written verifiers, deterministically | `dispatch`             |

Both produce the same run records per worker; dispatch adds the verifier
layer and removes stage-level improvisation.

## Single-worker async supervision

The same command also owns one-worker async lifecycle supervision:

```bash
vibecrafted dispatch run --run-id <id> --root . \
  --report .vibecrafted/report.md --transcript .vibecrafted/trace.log \
  -- <command> [args]
```

`dispatch run` owns process spawn, transcript capture, artifact validation,
and exit status for a single supervised worker process. It is plumbing for
runtimes and scripts; the TOML plan form is the operator surface.

Next: the full TOML reference in [Dispatch schema](/docs/dispatch-schema/)
and the worker-side contract in
[Briefs and reports](/docs/briefs-and-reports/).
