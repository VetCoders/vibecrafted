# `vc-justdo` Flow — legacy alias of `vc-implement`

> Canonical flow lives in [`../vc-implement/FLOW.md`](../vc-implement/FLOW.md).
> This file is a redirect kept for backwards compatibility.

## TL;DR

```bash
vibecrafted implement codex --prompt 'Ship the feature'   # canonical
vibecrafted justdo    codex --prompt 'Ship the feature'   # legacy alias, same dispatch
```

Both paths land on the same internal skill (id: `justdo`, run-id prefix:
`just-`). All session artifacts, locks, and per-agent helpers
(`<agent>-justdo`, `<agent>-skill-justdo`, plus the new
`<agent>-skill-implement`) point to the same flow.

For the full mermaid graph, route table, escalation edges and artifact
contract, read the canonical document.
