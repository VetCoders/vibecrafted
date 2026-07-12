# vc-ship — example trigger

## Trigger phrase

> "lecisz z taskiem vc-ship dla vibecrafted-server adaptation — dopilnuj tego
> aż do release z właściwymi korektami po drodze"

## Expected agent behavior

1. vc-init pass in the target repo: Loctree context atlas read to the end,
   AICX intents recovered, git/risk truth graded.
2. Compose the mission as a durable file under
   `~/.vibecrafted/artifacts/<org>/<repo>/<date>/plans/…_prompt.md` —
   deliverables, hard constraints, named gates — and launch:
   `vibecrafted ship codex --file <mission.md>`.
3. Supervise the baton relay stage by stage: watcher on the stage report +
   `ship status --json` liveness; verify commits/gates before every
   `approve`; recover dead workers with `interrupt → fallback → approve`;
   trace conscious gaps with `accept-dou`.
4. Deliver the final flight report: stages flown, corrections, commits, gate
   colours, `dou_index`, and what release honestly did NOT verify.

## Acceptance evidence

What the operator should see in the final agent report:

- Lifecycle run id (`life-ship-…`) with 11/11 stages traced in
  `operator_actions` (or an operator-decided stop, stated as such).
- Per-stage report paths + WRITE-stage commit hashes + gate results
  (e.g. core suite green, `make server-test` green).
- `dou_index: 0` — or each remaining gap as an explicit `accept-dou` entry
  with its follow-up named.

## Notes

- Real precedent: flights `life-ship-260702-123238-24000` (v3.3.0) and
  `life-ship-260702-202338-58000` (lifecycle.schema.v1) — both supervised
  end-to-end with every verb used in anger.
