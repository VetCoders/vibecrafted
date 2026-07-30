---
title: "Management Commands"
description: "Reference for vibecrafted management commands: init, status, doctor, receipt, settlements, update, resume, version, uninstall, help."
section: cli
order: 20
---

# Management Commands

Management commands operate on the installation, the current repository, and
past runs. They launch no workflows themselves — that is the job of the
[skill launchers](/docs/workflow-launchers/).

## Reference table

| Command                              | Purpose                                             |
| ------------------------------------ | --------------------------------------------------- |
| `vibecrafted init [agent]`           | Orient an agent in this repo                        |
| `vibecrafted status`                 | Today's agent activity                              |
| `vibecrafted doctor`                 | Installation health — pass/fail                     |
| `vibecrafted receipt [--json]`       | Delivery/runtime receipt (source ↔ installed)       |
| `vibecrafted settlements <action>`   | Read-only f/x/n ledger query                        |
| `vibecrafted update`                 | Update to the latest release                        |
| `vibecrafted resume <agent>`         | Continue a previous session                         |
| `vibecrafted resume-session <agent>` | Continue an exact provider session as a tracked run |
| `vibecrafted version`                | Print version                                       |
| `vibecrafted uninstall`              | Reverse the install                                 |
| `vibecrafted help [topic\|--all]`    | Command deck · full reference                       |

## init

```bash
vibecrafted init claude
```

The interactive first context handoff: loads repository context (history,
structural perception, verification) and opens an oriented agent session.
Run it once per repository session before dispatching work.

## status

```bash
vibecrafted status
```

Today's runs at a glance: which agents ran, which runs are live, which
delivered reports. The run — not a terminal tab — is the unit of truth.

## doctor

```bash
vibecrafted doctor
```

Installation health check with a pass/fail verdict: summary line first,
then failures and warnings. Passing checks are reported as a count. Exit
code is non-zero when a check fails.

## receipt

```bash
vibecrafted receipt --json
```

One delivery/runtime receipt for the fleet tools (vc-frame, vibecrafted,
scaffold-doctor, loct, aicx). Each row binds owner/repo → branch → checkout
SHA → dirty state → installed SHA → ahead/behind → index generation, and
labels the drift:

```text
SOURCE_AHEAD_OF_INSTALLED | INSTALLED_NOT_ON_PATH | UNPUSHED
| DIRTY_BUILD_PROVENANCE | INDEX_STALE | CLEAN
```

Receipt never uses the process working directory to identify a tool source.
When auto-discovery fails, point it explicitly with `VIBECRAFTED_SOURCE`,
`VC_FRAME_SOURCE`, `LOCTREE_SOURCE`, `AICX_SOURCE`, or `VIBECRAFTED_FLEET_ROOT`.

This is the fastest way to catch the push ≠ install trap: a git checkout can
be ahead of the staged tools your daily CLI actually executes. `git pull`
alone does not refresh the installed runtime — `vibecrafted update` does.

## settlements

Read-only query over the settlement ledger — the append-only source of
`f · x · n` (finalized / failed / needs-attention) verdicts:

```bash
vibecrafted settlements summary [--json]
vibecrafted settlements list [--bucket f|x|n] [--revalidatable] \
  [--group agent,skill,reason,root] [--limit N] [--json]
vibecrafted settlements inspect <run_id> [--json]
```

Counters come from the ledger, never from open terminal tabs or bare
control-plane completion rows.

## update

```bash
vibecrafted update
```

Pulls the latest release and reinstalls, refreshing the staged tools the
CLI executes. Verify afterwards with `vibecrafted version` and
`vibecrafted receipt`.

## resume and resume-session

```bash
vibecrafted resume claude --session <id> --prompt "Continue the fix"
```

`resume` continues a previous tracked session for an agent.

```bash
printf '%s' "continue safely" | vibecrafted resume-session codex \
  --agent-session-id <provider-session-id> --prompt-stdin
```

`resume-session` continues one exact provider-owned session as a tracked,
detached headless run. The prompt comes from `-p <text>`, `-f <path>`, or
`--prompt-stdin` (keeps the prompt out of argv). Optional flags: `--root
<path>`, `--model <name>`, `--json` for a machine-readable launch receipt.
This command is always headless; it does not pretend to be an interactive
session.

## version, uninstall, help

```bash
vibecrafted version        # print version (X.Y.Z+g<shortsha>)
vibecrafted uninstall      # reverse the install
vibecrafted help           # compact command deck
vibecrafted help --all     # full reference
vibecrafted help marbles   # per-topic help
```

The version's `+g<shortsha>` suffix identifies the exact staged build —
compare it with your source checkout when diagnosing drift.
