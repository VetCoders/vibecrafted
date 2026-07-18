# Foundation Rule

Verification proves that a delivered change matches its claim. Foundation proves that the claim and executable plan were formed from the right repository authority, normative data, and falsified premises before a worker may mutate anything.

## Non-negotiable contract

- A write workflow starts only from a `vibecrafted.foundation.v1` receipt whose terminal state is `SEALED`.
- Repository authority is explicit and attributable: repository config, operator input, or an attributable PR base. Remote ordering and a feature-branch upstream are evidence, never authority selection.
- Unknown and error values remain typed unknown/error. They never become zero commits, a clean tree, synchronized state, or safety.
- Authority fetch, immutable SHA, merge base, both commit directions, missing commits, dirty/detached/shallow/submodule/worktree state, and relation are receipt evidence.
- Normative sources are declared and hashed. Synthetic data cannot satisfy a requirement for live provenance, and discovered live sources cannot remain silently unbound.
- Every critical premise has a bounded falsifying probe, expected and actual evidence, drift policy, expiry, and status.
- Authority-only capability loss remains visible even when implementation and tests disappeared together. Missing or unknown classification blocks.
- Every receipt is schema-complete and carries a supervisor issuer proof. Rehashing a hand-written artifact is not authority and must fail before process creation.
- Executable plans bind canonical plan path/content hash as well as the receipt hash, authority ref/SHA, and premise-set hash. Read-only drafts may remain `UNSEALED`; write dispatch may not.
- Destructive work requires an immutable operator-approved lease signed inside the receipt, recovery checkpoint, dirty-state receipt, staged-diff validation, and exact delivery-commit validation including deleted symbols.
- Revalidate before the first worker, destructive cuts, handoffs, wave boundaries, delivery acceptance, and completion claims. Drift emits durable evidence and stops the run.

## Terminal states

- `SEALED`: all critical evidence is known, current, and acceptable for the bound action.
- `BLOCKED`: deterministic refusal. No worker process is launched.
- `OPERATOR_WAIVER_REQUIRED`: a scoped human decision is required. This state is not permission to launch.

The control plane must project Foundation separately from verification, live-tree drift, worker delivery, and release readiness. One green status may not hide another red status.
