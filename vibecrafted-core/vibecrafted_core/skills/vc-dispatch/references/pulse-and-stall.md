# Pulse & stall — autonomous worker liveness doctrine

A living worker gets ZERO interference. A dead one gets killed and replaced
without ceremony — in BOTH postures (vc-partner and vc-ownership). You cannot
risk the batch on an undelivered brief: later cuts usually depend on it.
Recovery is responsibility for delivery and an act of mutual trust, not an
escalation event.

## Framework automation first

vibecrafted ships the heartbeat — reach for it before hand-rolling timers:

| Need                           | Mechanism                                                                                                                                                                                                       |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| command-rank dispatcher await  | `vibecrafted loop spanko --run-id <id> --agent <a> --verify '<cmd>' --tracker <tracker.md> --cut-id <cut> --then '<next dispatch>'`                                                                             |
| lower-level await primitive    | `vibecrafted loop await-run --run-id <id> --agent <a> --then-cmd '<next dispatch>'`                                                                                                                             |
| line state machine             | `vibecrafted loop start/next/status/cancel/complete` (`--max-iterations`, `--completion-promise`, `--state-file`)                                                                                               |
| crontab heartbeat with context | `vibecrafted cron line --root <repo> --every-minutes 10 --then-cmd 'vibecrafted loop next'` (captures Loctree + AICX per tick)                                                                                  |
| resume after idle window       | `vibecrafted cron tick --after-idle-minutes 10 --then-cmd <cmd>`                                                                                                                                                |
| per-dispatch auto-await pane   | `vibecrafted-await-watch.sh --meta <meta.json>` — tails transcript, watches meta status + size delta + process liveness, self-terminates (tunables: `VIBECRAFTED_AWAIT_IDLE_TIMEOUT`, `VIBECRAFTED_AWAIT_POLL`) |

Canonical supervisor contract (see `docs/runtime/AGENT_OPS.md`): After
dispatch, arm `vibecrafted <agent> await --run-id <id>` immediately,
supervisor-side. Control-plane JSON, report files, transcripts, panes, and
scheduled wakeups are diagnostic only, not wake signals. Hedging await with
ad-hoc pollers/watchers is a Class 3 violation; fix `control_plane.await_run`,
do not normalize the hedge.

Drive the await with the dedicated command (OUR vc-loop / cron) as the
STANDARD even from an interactive session — a dispatched run HAS the CLI. A
harness-level loop (Claude `/loop 15m <watch prompt>`) is a true last-resort,
only when the vibecrafted CLI is genuinely unavailable. The manual pulse below
is the DIAGNOSTIC layer — what a tick inspects, and the forensics you run when
automation says "still running" but nothing moves.

## The pulse (every watch tick, ~15 min cadence)

Three INDEPENDENT signals — never judge on one:

```bash
# 1. Control plane: run status
grep -E '"status"|"exit_code"|"liveness"' \
  ~/.vibecrafted/control_plane/runs/<run_id>.json

# 2. Agent session file: is the model actually producing events?
#    (codex example; adjust the path per agent)
S=$(ls -t ~/.codex/sessions/<YYYY>/<MM>/<DD>/*.jsonl | head -1)
stat -f "mtime=%Sm size=%z" "$S"      # frozen mtime + static size = no events

# 3. Tree truth: is anything being written?
git log --oneline -1 && git status --short
```

Healthy patterns:

- jsonl growing by hundreds of KB between probes → recon phase, leave alone.
- WIP files matching the cut's scope in `git status` → edit phase.
- Commit landed but run still `running` → worker is writing its report
  (normal; do NOT flip yet, wait for exit).

## Stall verdict (hard rule)

**≥10 minutes of silence on ALL THREE signals** — control plane stale, agent
session file frozen (mtime + size), zero tree deltas — AND process CPU time
flat (e.g. `ps -o etime,time,%cpu -p <pid>`: minutes elapsed, seconds of CPU)
→ the run is dead-in-the-water (typically a hung first model call).

A signal matching a known failure ≠ that failure: differentiate before
acting, but once all signals agree, act without asking. Do not wait a "polite"
extra tick — the batch is the casualty.

## Recovery procedure

1. **Kill the whole launcher tree** (launcher pid + shell + agent binary +
   stream bridge): `kill <pids>`; verify with `ps`/`pgrep`.
2. **Check for orphans** — a supervisor killed mid-loop may have already
   fired a worker that DELIVERS: `pgrep -f '<agent> exec'` + `git log` +
   `git status`. If an orphan is working, treat it as the live run.
3. **Inventory leftovers**: what did the dead run leave on the tree? Usually
   nothing (clean stall) — state it explicitly either way.
4. **BATON update in the SAME prompt file** (append a dated section): what
   stalled, the evidence (elapsed vs CPU time, frozen session file, zero
   edits), what the new worker inherits ("nothing — start fresh on live
   HEAD" or exact WIP description), plus any commits that landed since.
5. **Re-dispatch** — same agent or a different one (dispatcher's call; a
   second identical stall is a strong hint to switch agents). Never
   blind-restart without the evidence written into the prompt.
6. **Ledger**: tracker evidence gets the stall + recovery trail (run ids,
   diagnosis, who killed); journal gets the full entry.

## Refire vs recovery

- **Recovery-dispatch** = the run DIED; BATON update describes the corpse.
- **Refire (mini-marbles)** = the run FINISHED but the surface needs another
  round (partial delivery, "B<n> not done" in the report, convergence
  pressure on a fragile area). Same prompt verbatim — idempotency clause in
  EXTRA makes this safe; hot substrate makes it cheap (vc-marbles: cache
  heat). vc-frame's `<ENTER> re-run` on the spawn pane is the canonical
  one-keystroke refire; the operator may refire behind your back — treat an
  unexpected fresh run of a known prompt as a refire, not an anomaly.

## Await mechanics

- Background the await (`vibecrafted <agent> await --run-id <id>`) and let
  its completion wake you; the pulse tick is the fallback heartbeat.
- Report files may appear under a `pending-report-*` name before the
  canonical one — search the reports dir by mtime, not by guessed filename.
- Artifacts may live under case-variant org dirs (APFS case-insensitive):
  one directory, two spellings — not a path divergence.
