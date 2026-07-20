---
status: accepted
owner: codex
date: 2026-07-20
scope: vibecrafted-server scaffold artifact editor
---

# Scaffold Server Editor Design

## Current State

`vc-scaffold` Phase 6 requires the plan, cut briefs, and design docs to become editable artifacts served through `vibecrafted-server`. The runtime roadmap already fixes the invariant: Python writes control-plane run state, Rust `control-core` reads typed state, and frontends do not hand-parse JSON.

The review surface consumes canonical plan roots at
`~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan_id>/`:

- `manifest.json` is the ordered, explicit artifact inventory.
- roles come from manifest declarations, never filenames or locations.
- every editable tab maps to one physical file below the plan root.
- operator edits must persist to disk and become visible to agents through a typed endpoint.
- approvals/checkpoints must be first-class state because scaffold-doctor will gate the scaffold to implement baton on them.

## Decision

Use a Leptos-native mount with a server-rendered editor route and typed `control-core` artifact store.

The editor is mounted from `web/src/app.rs` at `/scaffold`. The actual editable HTML is served from `/scaffold/editor` by Axum so it can read and write local artifacts without client-side filesystem tricks. JSON endpoints expose the same typed contract:

- `GET /api/scaffold/plans?org=&repo=&day=`
- `GET /api/scaffold/artifacts?org=&repo=&day=&plan_id=`
- `GET /api/scaffold/changes?org=&repo=&day=&plan_id=`
- `POST /api/scaffold/artifact`
- `POST /api/scaffold/checkpoint`

## Open Forks Resolved

Leptos-native vs transplanted Studio browser app: choose Leptos-native. GlyphPulse Studio and Pensieve supply interaction grammar, not implementation substrate. Pulling Solid/Swift code into this Rust SSR server would create a parallel app and duplicate persistence.

Batch + sequential review: the surface supports both. The sidebar shows all artifacts at once for batch review; each artifact panel has its own save/checkpoint form for sequential review.

Bidirectional edit to endpoint sync: operator saves include the loaded SHA-256 content hash, update
the canonical Markdown file with an atomic sibling rename, append `.scaffold-changes.jsonl`, and
refresh the typed endpoints. A stale hash returns `409 Conflict`.

Checkpoint primitive: each artifact carries a typed checkpoint sidecar in `.scaffold-checkpoints.json`; checkpoint updates append the same change feed. This is the foundation scaffold-doctor can read later.

## Transplant Notes

Pensieve contributed the selected-document model: sidebar/workspace list, active editable Markdown buffer, dirty-save path, and resilient split/editor thinking.

GlyphPulse Studio contributed the browser shape: persistent sidebar, switchable tabs/surfaces, keyboardable navigation posture, and inspector/checkpoint sections that do not rebuild the writing surface on every keystroke.

`/brainstorming` visual-companion was not present at the expected local paths during this cut, so it was not used as implementation evidence.

## Contract

`control-core::ScaffoldArtifactStore` owns the typed artifact contract:

- discovers manifest-backed plans and requires explicit selection when a day has multiple plans;
- preserves manifest order and explicit roles;
- writes only declared, editable, non-symlinked Markdown artifacts below the selected plan root;
- appends an agent-readable change feed;
- stores checkpoint state as a sidecar next to the artifacts.

The Python control-plane writer remains untouched and remains the source of truth for run state.

## Follow-Up

`scaffold-doctor` and the server call the same `control-core` manifest loader and validator. Legacy
`operator/` workspaces remain discoverable for one compatibility window but are always read-only.
