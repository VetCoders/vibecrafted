# vibecrafted-mcp

FastMCP server for the Vibecrafted operator framework. Closes the third
sense of the cold-start contract:

```text
mcp__loctree-mcp__context()        # perception (external)
mcp__aicx-mcp__aicx_intents()      # intentions (external)
mcp__vibecrafted__vc_repo_full()   # ground truth (this server)
```

A thin synthesis layer (`vc_init`) composes the three signals plus a
small set of v0.1 stubs (live failure score, unmade decisions,
unverified claims). The full synthesis brain lands in v0.2.

## Install

From the repository root, in a fresh Python 3.10+ environment:

```bash
pip install -e ./vibecrafted-core ./vibecrafted-mcp
```

The package depends on `vibecrafted-core` as a sibling library and on
`fastmcp>=2.0`.

## Run

```bash
vibecrafted-mcp           # speaks MCP over stdio
vibecrafted-mcp --version # print the package version and exit
vibecrafted-mcp --help
```

## Wire into an agent

```jsonc
{
  "mcpServers": {
    "vibecrafted": {
      "command": "vibecrafted-mcp",
    },
  },
}
```

## Tools

| Tool                              | Purpose                                                                                                      | Default budget |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------- |
| `vc_repo_full(project=".")`       | Full git ground truth (branch, ahead/behind, dirt, recent commits, worktrees, remotes).                      | ~3-6k tokens   |
| `vc_doctor(project=None)`         | Vibecrafted runtime health summary (ok / warnings / failures).                                               | ~2-4k tokens   |
| `vc_board_status(home=None)`      | Operator control-plane snapshot (active runs, recent runs, event tail, warnings).                            | ~3-10k tokens  |
| `vc_init(project=".", slim=True)` | Cold-start synthesis: composes the three senses + insight stubs. Slim default keeps the response under ~5KB. | ~5KB slim      |

All v0.1 tools are read-only. Mutations (run launch, marbles trigger)
are reserved for v0.2 once an explicit operator-permission contract is
in place.

## Resources

| URI                                           | Returns                                                                           |
| --------------------------------------------- | --------------------------------------------------------------------------------- |
| `vibecrafted://board/runs`                    | `{generated_at, active_runs, recent_runs, warnings}` from the live control plane. |
| `vibecrafted://control-plane/events/{run_id}` | Last 50 events for `run_id` from the operator event stream.                       |

## Constraints

- v0.1 tools are read-only and never spawn agents — fleet dispatch is
  an operator decision, not an MCP one.
- Each tool response is bounded by FastMCP's 25K token cap; the
  defaults aim for ≤20K to leave a safety margin.
- The doctor surface degrades gracefully (returns `unavailable=true`)
  when the package is consumed outside a vibecrafted source checkout.

## Development

```bash
pip install -e ./vibecrafted-core ./vibecrafted-mcp
pip install pytest
pytest vibecrafted-mcp/tests/
```

## License

`𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.` with AI Agents by VetCoders (c)2024-2026 LibraxisAI
