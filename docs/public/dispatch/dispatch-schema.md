---
title: "Dispatch Schema (vibecrafted.dispatch.v1)"
description: "TOML reference for dispatch plans: meta, policy, phases, cuts, verify matchers, recovery, and placeholder rendering."
section: dispatch
order: 20
---

# Dispatch Schema (vibecrafted.dispatch.v1)

A dispatch plan is a TOML file with `schema = "vibecrafted.dispatch.v1"` at
the top level. The parser fails closed: schema violations refuse the whole
plan with a list of errors. Validate with
`vibecrafted dispatch <plan> --doctor` before launching.

## Minimal plan

```toml
schema = "vibecrafted.dispatch.v1"

[meta]
name = "my-line"
repo = "~/projects/my-app"
reports_dir = "~/projects/my-app/reports"

[common]
text = """
Repo: {repo}
Report: {reports_dir}/{id}_report.md
Baton: {baton}
"""

[[cuts]]
id = "c1-first-cut"
agent = "codex"
workflow = "implement"
prompt = "Implement cut {id} in {repo}."

  [[cuts.verify]]
  run = "cd {repo} && make test"
  expect = { contains = "passed", exit_code = 0 }
```

## Top-level fields

| Field            | Required | Meaning                                                                                |
| ---------------- | -------- | -------------------------------------------------------------------------------------- |
| `schema`         | yes      | Must be exactly `"vibecrafted.dispatch.v1"`                                            |
| `[meta]`         | yes      | Plan identity and paths                                                                |
| `[policy]`       | no       | Supervisor behavior (defaults below)                                                   |
| `[common]`       | no       | Text prepended to every cut prompt                                                     |
| `[workflow_map]` | no       | Alias → supported workflow mapping (`[workflows]` accepted)                            |
| `[[phases]]`     | no       | Named phase groups for cuts                                                            |
| `[[cuts]]`       | yes      | At least one cut                                                                       |
| `[execution]`    | no       | Typed execution envelope; fails closed on unknown fields (advanced, subject to change) |
| `[proof]`        | no       | Opaque payload passed to workers verbatim; dispatch never interprets it                |

## `[meta]`

| Key           | Required | Meaning                                           |
| ------------- | -------- | ------------------------------------------------- |
| `name`        | no       | Plan name                                         |
| `repo`        | yes      | Repository path, rendered into `{repo}`           |
| `description` | no       | Free text                                         |
| `baseline`    | no       | Table, e.g. `{ branch = "main", head = "<sha>" }` |
| `reports_dir` | no       | Rendered into `{reports_dir}`                     |
| `tracker`     | no       | Tracker path, rendered into `{tracker}`           |

## `[policy]`

| Key                         | Default        | Values / meaning                                        |
| --------------------------- | -------------- | ------------------------------------------------------- |
| `repair_rounds`             | `0`            | Repair attempts after a failed cut                      |
| `on_critical_fail`          | `"break"`      | `break` \| `continue`                                   |
| `on_timeout`                | `"fail"`       | `repair` \| `fail` \| `continue`                        |
| `concurrency`               | `1`            | `> 1` requires `allow_concurrency = true`               |
| `allow_concurrency`         | `false`        | Also accepted: `enable_concurrency`, `parallel_enabled` |
| `verify_executor`           | `"supervisor"` | Who runs verifiers                                      |
| `require_commit`            | `false`        | Require a commit from the worker                        |
| `allow_idempotent_existing` | `true`         | Accept already-satisfied cuts                           |

### `[policy.await]`

```toml
[policy]
await = { poll_s = 90, timeout_min = 90 }
```

| Key           | Default | Meaning                                   |
| ------------- | ------- | ----------------------------------------- |
| `poll_s`      | `90`    | Seconds between worker polls              |
| `timeout_min` | `90`    | Minutes before the timeout policy applies |

## `[[phases]]`

Optional named groups. `title` is required and must be unique; `detail` is
free text. When any phases are declared, a cut's `phase` must match one of
the titles.

## `[[cuts]]`

| Key                | Required     | Meaning                                                                                                     |
| ------------------ | ------------ | ----------------------------------------------------------------------------------------------------------- |
| `id`               | yes          | Unique cut id, rendered into `{id}`                                                                         |
| `agent`            | no           | Fleet agent (`claude`, `codex`, `agy`, `junie`, `grok`)                                                     |
| `workflow`         | yes          | Must resolve (via `workflow_map`) to a supported workflow                                                   |
| `phase`            | no           | Phase title, when phases are declared                                                                       |
| `prompt` / `brief` | one required | Inline prompt, or a brief file path (resolved relative to the plan file; must exist)                        |
| `extra`            | no           | Text appended after the brief/prompt                                                                        |
| `mode`             | no           | `"write"` (default) or `"read"`                                                                             |
| `mutation`         | READ cuts    | `forbid` \| `allow-report-only` \| `allow` — doctor requires it on every READ cut                           |
| `observational`    | no           | `true` marks an observational READ cut (`observe` accepted); the only case where `verify` may be omitted    |
| `critical`         | no           | `true` makes failure subject to `on_critical_fail`                                                          |
| `model`            | no           | Model pin for the cut's agent                                                                               |
| `verify`           | usually      | Array of verifier tables (below)                                                                            |
| `recovery`         | no           | `{ on = "[!]", goto = "<cut-id-or-phase>", max_loops = <int> }` — `goto` must name an existing cut or phase |

## `[[cuts.verify]]`

Each verifier runs a shell command and matches its output:

```toml
[[cuts.verify]]
run = "cd {repo} && make test"
expect = { contains = "passed", not_contains = "FAILED", matches = "[0-9]+ passed", exit_code = 0 }
```

| Matcher        | Type    | Meaning                                            |
| -------------- | ------- | -------------------------------------------------- |
| `contains`     | string  | Output contains the substring                      |
| `equals`       | string  | Trimmed output equals the string                   |
| `matches`      | string  | Output matches the regex (validated at parse time) |
| `not_contains` | string  | Output does not contain the substring              |
| `exit_code`    | integer | Command exit code equals the value                 |

`run` is required and must not contain hard-stop commands — the parser
refuses `--no-verify`, `git reset --hard`, `git clean`, `git push`, `rm -rf /`,
and release invocations. Outward-facing actions belong to the operator, not
to a verifier shell.

## Placeholder rendering

Prompts (`common.text`, `prompt`/brief body, `extra`) and verifier `run`
commands render these placeholders:

| Placeholder                          | Value                                                                   |
| ------------------------------------ | ----------------------------------------------------------------------- |
| `{repo}`                             | `meta.repo`                                                             |
| `{id}`                               | Cut id                                                                  |
| `{agent}`                            | Cut agent                                                               |
| `{workflow}` / `{resolved_workflow}` | Declared / mapped workflow                                              |
| `{reports_dir}`                      | `meta.reports_dir`                                                      |
| `{tracker}`                          | `meta.tracker`                                                          |
| `{baton}`                            | Accumulated baton state as JSON — prompts only, never verifier commands |

Anything not listed in these tables is not part of the v1 schema. When in
doubt, `--doctor` is the authority: it reports every unknown or invalid
field by path (for example `cuts[2].verify[0].expect.exit_code`).
