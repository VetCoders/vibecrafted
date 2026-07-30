---
title: "Slack gateway"
description: "An always-on Slack bridge bound to the omni-observer: mention-to-run dispatch, status commands, and a fail-closed policy surface."
section: server
order: 40
---

# Slack gateway

The Slack gateway is an always-on bridge between a Slack workspace and the
fleet. It is mouth and ear only: it reads run status through the local
server's HTTP eye and it dispatches work through the normal launcher. It
never keeps its own status store — the control plane stays the single truth.

## Architecture

```text
Workers / ship / justdo
    |  write (core dispatcher)
    v
~/.vibecrafted/control_plane/          <- single source of truth
    |
    +--> vibecrafted server  :3024      HTTP eye (state, runs, events)
            ^
            |  read: GET /api/control/*
    Slack gateway (Socket Mode)         human <-> fleet connector
            |  write path: dispatch only (vibecrafted justdo ...)
            v
    #your-fleet-channel threads         run id, status, report path
```

The gateway's only write path is launching a run; everything it reports back
comes from re-reading the observer. Its internal job index maps Slack
threads to run ids — it is a routing table, never a board.

## Mention flow

An allowlisted user mentions the bot with a task:

```text
@Vibecrafted justdo ~/projects/my-app fix the failing install test
```

The gateway validates the user against the allowlist, launches the run
through the standard CLI, and replies in a thread with the `run_id` — the
delivery receipt. The product contract is receipt-in-thread within seconds,
not a live worker terminal. As the run progresses, the gateway posts
rate-limited progress updates to the same thread on state, health, liveness,
or report changes, and a terminal message when the run settles.

Anyone can then verify the same run outside Slack:

```bash
curl -s http://127.0.0.1:3024/api/control/runs/just-20260730-e5f6
```

## Status commands

`/vc status` returns the same board slice as `GET /api/control/state` — the
HTTP eye, not a Slack-side cache. It also prints measured bridge freshness:
the gateway compares its code mtime against its own process start and labels
its modules `fresh` or `STALE`. `/vc run <id>` fetches one run via
`GET /api/control/runs/{id}`.

A companion CLI offers the same reads from a shell, plus an out-of-process
freshness probe that discovers the live bridge process id — so a multi-day-old
bridge cannot hide behind a green unit-test suite.

## Policy surface (gateway-owned, fail-closed)

Dispatch policy belongs to the gateway process, not the control plane:

- **User allowlist, fail-closed.** An empty allowlist denies all dispatch:
  the gateway stays read-only until an operator explicitly lists users.
  "Allowlist empty" and "user not listed" are distinct denial messages.
- **Per-user cooldown.** A cooldown between dispatches per user
  (default 30 s). Cooldown starts only after a real `run_id` receipt — a
  failed spawn does not burn it.
- **Concurrency cap.** A maximum number of concurrent jobs per user
  (default 3).
- **Progress rate-limit.** Intermediate posts fire on meaningful change; the
  first is immediate, later ones respect a minimum interval.
- **STALE-module detection.** The bridge does not hot-reload code. After an
  update, restart it; status surfaces show `modules=STALE` until you do, and
  the end-to-end certainty check fails by design while a live bridge is
  stale. Unit green never equals Slack green.

The gateway never claims verification checkmarks without control-plane or
report evidence, and if the observer is down it reports that within seconds
while still acknowledging slash commands.

## Configuration

Tokens and workspace wiring are deliberately not documented here — no
credentials belong in docs or git. Configure the gateway through its
environment: the user allowlist, default agent, cooldown, concurrency, and
progress-interval variables, plus `VC_SERVER_URL` for the observer address
(default `http://127.0.0.1:3024`). Run the gateway's doctor script to measure
the remaining operator setup — allowlist present, bridge fresh, observer
reachable — before trusting a live channel.

## Workers do not need Slack

A worker finishes and settles whether or not the bridge is up. Slack is a
convenience surface for humans; the durable path is always control plane →
observer → your eyes.
