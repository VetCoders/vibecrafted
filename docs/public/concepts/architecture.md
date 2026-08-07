---
title: "Architecture"
description: "The Vibecrafted runtime topology: one control plane owns run truth, every other surface is a projection."
section: concepts
order: 10
---

# Architecture

Vibecrafted is organized around a single durable source of run truth — the
local control plane — with every user-facing surface acting as a projection
of it. No dashboard, terminal pane, or chat bridge is allowed to invent its
own parallel state. This page maps the parts and the rule that binds them.

## The body model

A useful shorthand for the topology:

| Role          | Component                                      | What it does                                                                                         |
| ------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Memory        | Control plane (`~/.vibecrafted/control_plane`) | The single durable truth for run lifecycle: events, run state, settlement ledger                     |
| Eye           | Local server (read model)                      | Renders NOW / CONTEXT / STRUCTURE / FLEET / METRICS through typed routes; reads, never owns          |
| Mouth and ear | Messaging gateway (e.g. Slack bus)             | Carries agent-to-agent envelopes with persistence, ACK, and dedup; transport, never run-status truth |
| Hands         | Workers                                        | Headless agent processes that do the actual work and write durable artifacts                         |
| Senses        | Loctree, AICX                                  | Repository structure and session-intention retrieval for agents                                      |

## The control plane is the truth

Run lifecycle state lives on your machine under `~/.vibecrafted/control_plane`:

```text
~/.vibecrafted/control_plane/
  events.jsonl              # append-only control-plane events
  runs/                     # active run tracking
  settlement_ledger.jsonl   # immutable, hash-chained settlement history
```

Only the core dispatcher and its typed control-plane routes write here.
Everything else — the server UI, MCP board tools, chat threads, terminal
session views — reads projections of the same records.

Durable work products land in the artifact store, not in terminal
scrollback:

```text
~/.vibecrafted/artifacts/<org>/<repo>/<date>/{plans,reports,tmp}/
```

## One owner per truth domain

The ownership doctrine (see [Design decisions](/docs/design-decisions/)) is:
every truth domain has exactly one owner with a named write surface; every
other surface is a read projection, and a projection never writes.

| Truth domain             | Sole owner                  | Everyone else                                        |
| ------------------------ | --------------------------- | ---------------------------------------------------- |
| Installed runtime        | Runtime generation manifest | Reads via launcher, `doctor`                         |
| Run lifecycle            | Control plane               | Server views, MCP tools, chat threads, session rails |
| Session intention        | AICX                        | Context views, overlays                              |
| Repository structure     | Loctree                     | Structure views, report links                        |
| Session composition      | vc-frame                    | Terminal windows, fleet links                        |
| Agent-to-agent envelopes | Message bus store           | Chat threads, handoff evidence                       |
| Plan artifacts           | The files on disk           | Editor/API clients, derived ledgers                  |

Two consequences worth internalizing:

- **No UI invents state.** A visible control either performs a real,
  authorized backend transition or it is absent. The server does not crawl
  arbitrary files or reconstruct liveness heuristically.
- **Plan files are owned by the filesystem.** Agents write plans and reports
  directly under the artifact store; any editor or API on top is a
  convenience client, never a required mediator.

## Runtime surfaces

You interact with the same truth through several surfaces:

```bash
vibecrafted dashboard    # vc-frame cockpit — the primary operator experience
vibecrafted tui          # experimental Rust operator console
vibecrafted help         # plain CLI — headless and scripting fallback
```

The vc-frame dashboard organizes sessions into tabs and rails so background
agents never "disappear". The CLI works everywhere and is what workers and
CI use. All of them poll or render control-plane state; closing any of them
changes nothing about a running worker.

## Workers are independent of viewers

Workers launch as detached headless processes by default, regardless of
whether a terminal is attached. You observe them through durable artifacts
— receipts, control-plane state, transcripts, reports — not by keeping a
window open. Losing a viewer tab, an SSH session, or the whole terminal
does not kill or orphan a run. See [Agents](/docs/agents/).

## Verify it yourself

```bash
# Where is the truth?
ls ~/.vibecrafted/control_plane

# What does the board say?
vibecrafted settlements summary

# Is the installed runtime consistent?
vibecrafted doctor
```

If two surfaces ever disagree, the control plane wins — that is the point
of the design.
