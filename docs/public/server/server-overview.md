---
title: "Server overview"
description: "The local control-plane server: one read model over ~/.vibecrafted/control_plane, served as a dashboard, HTTP API, and SSE stream."
section: server
order: 10
---

# Server overview

`vibecrafted server` runs a local omni-observer: a single read model over the
control plane on disk, exposed as a browser dashboard, a JSON HTTP API, and a
Server-Sent Events stream. It observes what the runtime already produced — it
never invents state.

## One truth, many eyes

Everything the fleet does — launches, progress events, reports, settlement —
is written to `~/.vibecrafted/control_plane/` (override with
`$VIBECRAFTED_HOME`) by the dispatcher. The server is a projection of that
directory, alongside the other read surfaces:

```text
Workers / ship / justdo
    |  write (core dispatcher)
    v
~/.vibecrafted/control_plane/        <- single source of truth
    |
    +--> vibecrafted server (HTTP + SSE)   dashboard + API on :3024
    +--> vibecrafted-mcp (stdio)           same logical board for agents
    +--> Slack gateway                     human <-> fleet connector
```

Three rules follow from this shape:

- **Board truth lives on disk.** Runs, events, warnings, and the settlement
  ledger (f/x/n) exist only under the control plane. Chat messages, unit
  logs, and agent transcripts are never status sources.
- **The server is an eye.** Every HTTP route is a read. When two projections
  disagree, you re-read the control plane — you never reconcile them by
  writing to a third store.
- **Workers do not need the server.** A run completes and settles whether or
  not the observer is up. Starting the server later shows the full history.

## Start and stop

```bash
vibecrafted server start          # bind the observer (default port 3024)
vibecrafted server status         # is it up, where, and since when
vibecrafted server open           # open the dashboard in a browser
vibecrafted server stop           # shut it down
vibecrafted server doctor         # diagnose the server install
```

To keep the observer always on, install it as a supervised service:

```bash
vibecrafted server service install --port 3024
vibecrafted server service start
vibecrafted server service status
```

The default bind is local-only:

```bash
curl -s http://127.0.0.1:3024/api/health
# {"schema":"vibecrafted.health.v1","status":"ok"}
```

Consumers that need to reach the server (the Slack gateway, custom scripts)
read the base URL from `VC_SERVER_URL`, defaulting to
`http://127.0.0.1:3024`.

## The installer GUI

`vibecrafted gui` serves the installer and setup surface — a separate,
short-lived local web process, not the control-plane observer:

```bash
vibecrafted gui                       # start and open in a browser
vibecrafted gui --no-open --port 4173 # headless, custom port
```

Use `gui` when installing or reconfiguring; use `server` for day-to-day
observation of the fleet.

## What the dashboard shows

The dashboard renders the same state envelope the JSON API returns: active
runs, recent runs, warnings, the event tail, and settlement counts. There is
no dashboard-only data. Anything you see in the browser you can also fetch
with `curl` — see the [HTTP API reference](/docs/http-api/).

## Where to go next

- [HTTP API](/docs/http-api/) — every endpoint, with example requests.
- [MCP server](/docs/mcp/) — the same board as typed tools for agents.
- [Slack gateway](/docs/slack-gateway/) — mention-to-run bridge for humans.
