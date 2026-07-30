# Omni-observer + Slack gateway

**control_plane** is the only durable status truth.  
**vc-server** is the eye (HTTP read model).  
**vibecrafted-mcp** is the same board for IDE agents (stdio).  
**Slack bot** is mouth/ear.  
**Workers** are hands — they announce by running (dispatcher writes control_plane).

Plan: `vc-server-mcp-slack-gateway` (2026-07-28 scaffold · implement 2026-07-30).

## Architecture

```
Workers / ship / justdo
    │  write (vibecrafted_core dispatcher)
    ▼
~/.vibecrafted/control_plane/     ← single source of truth
    │
    ├─► vc-server (HTTP read + SSE)     omni-observer UI + API  :3024
    ├─► vibecrafted-mcp (stdio MCP)     same board for agents
    │
    └─► Slack gateway (Socket Mode)     human ↔ fleet connector
            │  read: GET /api/control/*
            │  write (dispatch only): vibecrafted justdo …
            ▼
        #agents-room threads (run_id, status, report path)
```

## Measured curls (operator host)

```bash
# health (constant-time readiness)
curl -s http://127.0.0.1:3024/api/health
# → {"schema":"vibecrafted.health.v1","status":"ok"}

# board slice used by /vc status and MCP vc_board_status
curl -s http://127.0.0.1:3024/api/control/state | python3 -m json.tool | head

# one run
curl -s http://127.0.0.1:3024/api/control/runs/<run_id> | python3 -m json.tool | head

# lifecycle list
curl -s http://127.0.0.1:3024/api/control/lifecycle | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count"),"lifecycle runs")'
```

Env override: `VC_SERVER_URL` (default `http://127.0.0.1:3024`).  
Home override: `$VIBECRAFTED_HOME` (default `~/.vibecrafted`).

## Bot surfaces (vibecrafted-slack-agent)

| Surface                               | Backend                                                                                         |
| ------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `/vc status` · `vc-slack status`      | `GET /api/health` + `GET /api/control/state`                                                    |
| `/vc run <id>` · `vc-slack run <id>`  | `GET /api/control/runs/{id}`                                                                    |
| `@Vibecrafted justdo <root> <prompt>` | allowlist → `vibecrafted justdo <agent> --json …` → thread `run_id` → progress posts → terminal |
| `vc-slack signal` / lifecycle hook    | Slack post only (does not invent control_plane state)                                           |

Allowlist: `SLACK_ALLOW_USERS`. Default agent: `VC_DEFAULT_AGENT=grok`.

Dispatch policy (gateway, not control_plane):

- empty allowlist ⇒ fail-closed (read-only)
- per-user cooldown (`VC_DISPATCH_COOLDOWN_MS`, default 30s)
- max concurrent jobs per user (`VC_DISPATCH_MAX_CONCURRENT`, default 3)
- intermediate `*progress*` posts on state/health/liveness/report key change (first always; then `VC_PROGRESS_MIN_MS`)
- ≤5s product SLA = receipt-in-thread (`run_id`), not worker terminal

Workers do **not** need Slack. Example visibility path:

1. Worker finishes → control_plane meta/report written by dispatcher
2. Operator (or bot) reads `GET /api/control/runs/{id}` or `/vc run {id}`
3. Optional human bus: `scripts/vc-slack-hook.sh` / `vc-slack signal` from hook policy

## MCP dual-run (W6 decision)

HTTP is sufficient for the Node gateway. Prefer:

- always-on: `vibecrafted server start` (or equivalent) on `:3024`
- IDE: stdio `vibecrafted-mcp` with existing tools (`vc_board_status`, `vc_launch`, …)

Do **not** merge packages unless a single MCP-HTTP binary is explicitly required. Mutating MCP tools stay permissioned; Slack gateway uses shell launch for allowlisted humans.

## Always-on

- vc-server: first-class `vibecrafted server start|status|stop`
- Slack bridge: `npm start` in `vibecrafted-slack-agent` or LaunchAgent example  
  `deploy/com.vetcoders.vibecrafted-slack-bridge.plist.example` in that repo
- Certainty script: `vibecrafted-slack-agent/scripts/e2e-certainty.sh` (full `npm test` + live board)
- **Restart the Socket Mode bridge after every pull** — Node does not hot-reload
  `dispatch.js`; a stale process can green unit tests while Slack still lacks
  intermediate `*progress*` / rate-limit behavior. Operator smoke:
  set `SLACK_ALLOW_USERS` → restart bridge → `@Vibecrafted justdo …` → `curl /api/control/runs/{id}`

## Invariants

1. No secrets in git; tokens only `~/.keys` / `.env`.
2. Bot never claims verifier `[x]` without control_plane / report evidence.
3. Offline observer → `ObserverOffline` within a few seconds; slash still acks.
4. Empty `SLACK_ALLOW_USERS` ⇒ fail-closed dispatch (read-only gateway).

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
