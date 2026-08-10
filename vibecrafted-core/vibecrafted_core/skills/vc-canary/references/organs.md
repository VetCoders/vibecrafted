# Loctree organs for canary

## Three organs, one `loct auto`

| Organ     | On disk (cache) | CLI projection                                    | Canary phase        |
| --------- | --------------- | ------------------------------------------------- | ------------------- |
| Sense     | `agent.json`    | `loct repo-view --json`                           | planes / scopes     |
| Inventory | `snapshot.json` | stream → `inventory.jsonl` via `canary_cli atlas` | unit budgets        |
| Signals   | `findings.json` | `atlas/signals.json`                              | post-fleet findings |

## Never

- `loct context --full` → `structural.files` as full inventory (hub ranking)
- Hardcoded `~/Library/Caches/loctree/projects/<id>/...` in prompts
- Loading entire `snapshot.json` into the LLM

## Resolve cache without hardcode

```bash
canary_cli snapshot-path --root "$PWD"
# uses agent.json project field match + prefers pack named latest
```

## Coverage receipt

`atlas/coverage.json` must show `snapshot_load_ratio >= 0.95` (full snapshot load)
and document inventory filters (tests/generated/lang). Fail closed on load ratio.
