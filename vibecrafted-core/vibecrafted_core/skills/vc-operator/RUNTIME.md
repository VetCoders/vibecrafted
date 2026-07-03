# `vc-operator` Runtime

`vc-operator` as an interactive skill does not automatically launch runtime.

Runtime begins only when the operator chooses a live supervisor or workflow
lane:

```bash
vibecrafted dispatch plan.dispatch.toml --doctor
vibecrafted dispatch plan.dispatch.toml --dry-run --json
vibecrafted dispatch run --run-id <id> --root . --report report.md --transcript trace.log -- <worker>
vibecrafted workflow claude --file /path/to/plan.md
vibecrafted implement codex --prompt '<bounded slice>'
```

## Runtime Responsibilities

The operator posture creates or consumes durable state for fleet orchestration:

- run metadata
- transcript
- wave tracker
- append-only journal
- worker briefs
- launch cards and run IDs
- per-wave close-outs
- final stop-point handoff
- plan mutation and security guardrail entries in the operator journal

## Artifact Layout

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/
  plans/
  reports/
  tmp/
  dispatch-result.json or run-specific result files
  <timestamp>_<slug>.transcript.log
  <timestamp>_<slug>.meta.json
```

An operator-mode session may also keep `tracker.md`, `journal.md`, and
`briefs/` for a multi-wave plan, but those artifacts are posture discipline, not
proof that a public `vibecrafted operator` command exists.

## Runtime Lanes

| Need                        | Runtime lane                       |
| --------------------------- | ---------------------------------- |
| Plan is fuzzy               | `vibecrafted scaffold <agent>`     |
| One worker slice            | `vibecrafted implement <agent>`    |
| Strict ERi slice            | `vibecrafted workflow <agent>`     |
| Truth-drift convergence     | `vibecrafted marbles <agent>`      |
| A to Z polish for one slice | `vibecrafted ownership <agent>`    |
| Shared strategy pause       | `vibecrafted partner <agent>`      |
| Independent verification    | `vibecrafted audit <agent>`        |
| Deterministic supervisor    | `vibecrafted dispatch <file.toml>` |
| Outward ship                | `vibecrafted release <agent>`      |

## Visible runtime (vc-frame) is the attended default

Runtime mode is `headless | terminal | visible` (`SUPPORTED_RUNTIMES`). The
selector resolves like this:

- When a vc-frame operator session is live — `VC_FRAME_SESSION_NAME` is set —
  `terminal`/`visible` opens the worker in a **new vc-frame tab** the operator
  watches in real time.
- With no session, `terminal` **degrades to headless** rather than stranding a
  worker in a tab that cannot exist (degrade-not-die).
- `headless` runs the dispatcher directly with no tab — correct for cron and
  no-session hosts, wrong for attended work.

The CLI (`vibecrafted <skill> <agent> --file <brief>`) auto-selects `terminal`
when the session exists, so attended dispatch is visible by default. The MCP
launch tools (`vc_run_launch` / `vc_launch`) do NOT: they default
`runtime="headless"` and ignore `VC_FRAME_SESSION_NAME`. When you dispatch
through MCP while a session is live, pass `runtime="visible"` explicitly — or use
the CLI. A headless dispatch into a live operator session is an invisible orphan,
not a quiet success: the operator cannot see it, and the conductor is reduced to
relaying status by hand. Visible-by-default is what keeps the operator in the
loop instead of asking "is it running?".

## Terminal States

```yaml
terminal_state:
  stopped_at_operator_button:
    requires:
      - wave tracker updated
      - journal updated
      - reports and SHAs named
      - remaining unpermitted human action named
  completed_with_plan_permission:
    requires:
      - permission source named
      - tracker updated
      - journal updated
      - reports and SHAs named
  blocked_with_evidence:
    requires:
      - blocker classification
      - attempted recovery
      - nearest safe next action
  escalated:
    requires:
      - target skill
      - reason
      - handoff state
```

## Non-Goals

- Do not use runtime to hide decisions from the operator.
- Do not run unwatchable dispatch.
- Do not bypass launch telemetry.
- Do not turn stop-point handoff into push/merge/deploy unless the written
  plan or current session explicitly permitted that action.
