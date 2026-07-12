# vc-ship

The lifecycle umbrella: one mission flown through all eleven Read-Write
cadence stages (scaffold → … → release) as a single supervised run. The
invoking agent becomes the run's supervising operator — verifying every stage
report, steering with the human-controls verbs (approve / interrupt /
fallback / force-audit / accept-dou), and carrying the baton with its report
cargo to release. Reach for it when a product cut deserves the full cadence;
you get back a traced lifecycle run, per-stage reports, and an honest final
flight report with the DoU trail.

## Quick reference

| Field            | Value                      |
| ---------------- | -------------------------- |
| Name             | `vc-ship`                  |
| Version          | `1.0.0`                    |
| Operator command | `vibecrafted ship <agent>` |
| Shell shortcut   | `vc-ship <agent>`          |
| Canonical doc    | [`SKILL.md`](SKILL.md)     |

## Related canon

- [`docs/runtime/LIFECYCLE.md`](../../docs/runtime/LIFECYCLE.md) — the
  Read-Write cadence, component architecture, and supervision model.
- [`docs/runtime/AGENT_OPS.md`](../../docs/runtime/AGENT_OPS.md) — failure
  classes every supervisor must know (gate-nap, report-on-death) and the
  battle-tested watcher patterns.
