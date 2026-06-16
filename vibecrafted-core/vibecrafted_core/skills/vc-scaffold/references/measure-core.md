# Measure-Core — the armor every scaffold cut carries

Scaffold plans are measurable, not optimistic. Each plan unit (cut/wave/task) is
**claim/outcome-addressable**: it carries a Vector, a four-term delta, a state marker, and a
delivery-verifier. This is what lets `vc-operator` read the plan and trigger/stop mechanically.

## The five-state alphabet

```
[ ] OPEN      intent recorded; no claim, nothing delivered
[~] CLAIMED   an actor asserts "done"; verifier has NOT run        (the optimism trap)
[?] UNKNOWN   verifier produced no verdict (no test / unreachable backend / no evidence either way)
[!] REFUTED   verifier ran; delivery contradicts claim/intent       (regression, panic, 5xx, deadlock, 0-byte, overclaim)
[x] DELIVERED verifier ran; delivery ≥ intent AND claim ≈ delivery   (the only green)
```

**INVARIANT:** only a **verifier** flips `[~]→[x]`. A claim never reaches `[x]` on its own. This
is the whole point — it separates measured outcome from asserted claim.

`[?]` (unknown) is honest ignorance and is distinct from `[!]` (known-bad). Park a `[?]` truthfully;
do not fake-investigate it into a `[x]` or a `[!]`.

### Transitions (what flips each)

```
[ ] → [~]   a CLAIM lands (agent reports / commit)
[~] → [x]   delivery-verifier passes (OUTCOME)
[~] → [!]   verifier fails / INCIDENT (claim > delivery)
[~] → [?]   verifier cannot run (no test / unreachable)
[?] → [x]|[!]   when evidence finally arrives
 *  → [!]   a new INCIDENT re-opens (regression)
```

## The Vector → delta axis

```
VECTOR: stabilize | implement | recon | e2e      (selects the gate profile = what counts as delivery)
Vector → (intent | baseline | claim | delivery) → trigger/stop
```

- **intent** = expected result · **baseline** = current state, MEASURED (never assumed)
- **claim** = what the agent reports (suspect) · **delivery** = what the verifier confirmed (+ evidence ref)
- The Vector picks the **delivery definition**: stabilize → "bleeding stopped + gate green";
  implement → "feature works + test"; recon → "map/answer with evidence"; e2e → "full path runs".

## Trigger / stop (read by vc-operator)

- `dou-index = |[x]| / total`; `delta = {[ ], [~], [?], [!]}` (everything not yet a delivered outcome).
- Any `[!]` or `[?]` → **STOP → recovery-vector**. A full `[x]` wave → **TRIGGER** the next phase.
- **STOP is never surrender.** It triggers fallback / failover / round-robin / handsoff. A "502-and-die",
  a hang, a 0-byte artifact is a pipeline bug, not an acceptable outcome.
- **Observability is part of the delivery-gate.** A blind watchdog/Sentry = delivery unverified = `[?]`.

## Process markers (for the intents/blackbox layer)

Commits are RESULT boundaries; the process between them is where chaos lives. Markers sample the
process so the run is reconstructable:

| Marker           | Heuristic                                       | Role                         |
| ---------------- | ----------------------------------------------- | ---------------------------- |
| `[REUSE_FENCE]`  | content-hash + mtime unchanged                  | reuse snapshot, skip rescan  |
| `[DRIFT]`        | working-tree diverged >N without commit         | between-commit chaos record  |
| `[BASELINE]`     | gate green on clean tree                        | the `baseline` term          |
| `[CLAIM]`        | agent reports done / commit                     | `[~]`                        |
| `[OUTCOME]`      | delivery-verifier green                         | `[x]`                        |
| `[INCIDENT]`     | panic / 5xx / exit≠0 / 0-byte / hang / deadlock | `[!]` (git never sees these) |
| `[INTENT_SHIFT]` | operator review changes the Vector              | switches the gate profile    |

GFM task-list `- [ ]`/`- [x]` is one artifact with two readers: it renders for a human and parses
for tooling. The `state` column is the bridge between the human-facing plan and machine trigger/stop.
