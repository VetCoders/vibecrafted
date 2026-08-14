---
title: "Agent-agnostic worktree runtime migration"
description: "Move active fleets from provider-specific worktrees and shared Cargo outputs to the canonical Vibecrafted runtime geometry."
section: dispatch
order: 25
---

# Agent-agnostic worktree runtime migration

New dispatches use only these planes:

```text
workers    ~/.vibecrafted/worktrees/<org>/<repo>/YYYY_MMDD/<cut-id>
artifacts  ~/.vibecrafted/artifacts/<org>/<repo>/YYYY_MMDD/{plans,reports,...}
runtime    ~/.vibecrafted/control_plane/...
```

Do not move a live legacy checkout behind its worker. Let it finish or recover
it from its existing receipt, then start new cuts in canonical worktrees.
Legacy `.claude/worktrees`, `.codex`, `.gemini`, and repo-local
`.vibecrafted` locations are read-only recovery inputs and are never created by
the new dispatcher.

Before enabling `concurrency > 1`:

1. Unset any fleet-wide `CARGO_TARGET_DIR`.
2. Run `vibecrafted dispatch <plan> --doctor`.
3. Add explicit `depends_on` edges and a named `integrator = true` join for
   non-linear branch tips.
4. Start the plan and inspect its runtime ledger with
   `dispatch-doctor <plan> --run-id <run-id>`.
5. After integration settles, run
   `vibecrafted dispatch <plan> --cleanup-settled <run-id>`.

The exact hard-failure remediation for an old shared target is:

```text
unset CARGO_TARGET_DIR — Vibecrafted assigns $PWD/target per worker
```

Cleanup removes settled linked checkouts and their local targets. It retains
branches and durable evidence. Runtime receipts remain on the control plane for
reconciliation and retention policy; active runs are never cleaned.

The repository smoke command exercises two concurrent workers plus an
exclusive join using real linked checkouts and local subprocesses:

```bash
python3 scripts/smoke-dispatch-worktrees.py
```

It prints the durable JSON receipt path.
