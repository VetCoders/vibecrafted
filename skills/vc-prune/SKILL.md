---
name: vc-prune
version: 3.0.0
description: >
  Repository pruning. Use when the team wants to strip a repo down to the code 
  that truly participates in runtime truth. Cut out the ghosts of AI weekend-coding: 
  abandoned auth experiments, duplicate Stripe handlers, and dead serverless functions.
  Trigger phrases: "prune", "prune repo", "strip dead code", "runtime cone", 
  "clean up the codebase", "wyczyść repo", "usuń martwy kod", "bez litości wyczyść".
---

# vc-prune - Stripping the Weekend Scaffolding

> Don't burn the house down, just strip it to the load-bearing walls.

A vibe-coded repo is a graveyard of good intentions. Claude loves generating 4 different iterations of an API integration before one sticks. The user hits "Accept All" and moves on.

Now, you have 3 dead Stripe webhooks, 2 NextAuth configurations, and a serverless function that times out and drains Vercel credits.

This skill asks a sharp question: **what must survive for runtime truth, and what is just an AI hallucination we forgot to delete?**

The goal is not cosmetic cleanup. The goal is to reduce the product surface so we can actually stabilize what remains.
We apply the VetCoders Axiom here: **Aggressive pruning with belief in the VCS archive over 'keep it just in case'.** Dead code is not necessarily _bad_ code; it is often a graveyard of incredibly valuable ideas that simply didn't find a finale. But its place is in the Git archive, not polluting the runtime. If you need it later, revive it. Until then—cut it without sentiment.

## Core Contract

- For any non-trivial prune, external `vc-agents` is the default first move.
- Assume 30% of the codebase is dead scaffolding left over from the prototype phase.
- Classify every candidate as `KEEP-RUNTIME`, `KEEP-BUILD`, `MOVE-ARCHIVE`, `DELETE-NOW`, or `VERIFY-FIRST`.
- Prefer deleting whole dead vertical slices over trimming symbolic leaves.
- Tighten contracts immediately after each pruning wave: manifests, docs, CI, package bounds.
- Run gates after every wave and require one real smoke or build proof.

## Delegation Doctrine

Use `vc-agents` first whenever the prune goes beyond obvious generated artifacts.

| Dimension                                                            | Best model | Why                                                                                                         |
| -------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| Archaeology, hidden reachability, proving if a surface is truly live | Claude     | Best at patient investigation, logic tracing, and proving whether a surface is actively stealing resources. |
| Exact deletions, manifest tightening, dead-route cleanup             | Codex      | Best at precise, low-noise implementation and keeping the cleanup mechanically correct.                     |
| Radical simplification, cutting entire abandoned subsystems          | Gemini     | Best when the repo needs a stronger new shape, not just a safer local trim.                                 |

## Workflow

### Phase 1 - Find the Ghosts (Define the Cone)

For apps and services, capture:

- Real entrypoints
- Mandatory user flows that must still work after pruning
- Build, bundle, and release path

Do not start with "unused exports". Start with "does this endpoint actually serve live traffic?"

### Phase 2 - Map the Cone with `loct`

Run the generic structural pass:

```bash
loct auto
loct manifests
loct hotspots
loct dead
```

Framework-aware branches:

- Web/API backends: `loct routes`
- Desktop apps: `loct commands`, `loct events`

### Phase 3 - Prune in Waves

Never do the whole cleanup in one cut. Prune in waves from safest to riskiest.

#### Wave 1 - The AI Exhaust & Prototype Scaffolding

Move or remove:

- `v1_backup.ts`, `old_auth_handler.js`, `stripe_test_claude.ts`
- Dead agent session folders (`.claude/`, `.codex/`)
- Stale screenshots and preview outputs generated during hacking.

#### Wave 2 - Whole Dead Vertical Slices

Before trimming leaves, ask whether an entire feature strand was an MVP experiment that died.

- A frontend service with no runtime consumers.
- An alternate login page design never mounted in the router.
- A webhook handler that was replaced by a different SaaS.
  If it's not live, cut the whole slice. These are unfinished ideas—commit them and let the archive hold them.

#### Wave 3 - Unreachable Product Surface

Now prune inside the surviving code surface:

- Unmounted routes
- Duplicate services or engines (e.g., both Prisma and raw SQL handlers doing the same thing)
- Dead feature flags retained after the feature launched.

#### Wave 4 - Contract Tightening

After every removal wave, clean the references:

- `package.json` dependencies (remove that library you tried once and hated).
- `Cargo.toml` features.
- Env vars (remove stale secrets from `.env.example`).
- CI workflows.

### Phase 4 - Verify Reality

After each wave, run the closest safe gates for the repo.
Green static gates are necessary, not sufficient. Always add one real proof path:

- Boot the live app locally.
- Run the CLI for a meaningful command.
- Hit the main API route.

## Anti-Patterns

- Deleting ten dead symbols while a whole dead abandoned subsystem is still standing.
- Trusting "unused" reports without checking if it's dynamically loaded via a framework router.
- Preserving a chaotic 2000-line file because "we might need that code later" or "it has good logic." (That is what git history is for. Delete it.)
- Cleaning code but leaving the stale NPM dependencies behind.
- Treating docs and build scripts as equally disposable as prototype experiments.

## The Pruning Principle

Do not ask the repo to explain every scar. Ask it to justify every surviving surface.

If it doesn't run in production, build the release, or test the integrity... **cut it.**

---

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_
