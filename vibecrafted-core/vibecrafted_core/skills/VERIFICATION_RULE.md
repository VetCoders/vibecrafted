---
title: Verification Rule
kind: core_rule
version: 2.0.0
description: "Walk around the truck verification rule: real artifact execution over synthetic green CI."
scope: framework
status: active
---

# Verification Rule — walk around the truck

Vetcoders ship by proof, not by gates. Before any worker says "done",
"shippable", or "ready" — even for work it personally supervised — it walks
around the truck and checks every strap before it says "now you can drive".

## Hard Rule

- Run the REAL artifact the user will run. Launch the app (not just `--version`
  from a fresh build); mount the DMG and `otool -L` / launch the app inside;
  exercise the runtime path, not only the gates.
- Signed / notarized / `spctl: accepted` / green `cargo check` / passing tests
  ≠ works. Those are straps visible from the cab, not a walk-around.
- Never trust upstream verification — another agent's or a pipeline's codesign,
  notarization, or green CI — as proof of runtime. Re-verify it yourself.
- Check your own instrument. A verification command that cannot fail is a loose
  strap on the strap-checker (`grep | sed && echo` always exits 0 — it lies).
- Stopping at the operator button after a full walk-around is correct, not weak.
  "Now you can drive" is earned by the walk-around, not by the loading.

## Why

A vc_terminal release passed `codesign` + notarization + `spctl: accepted`, was
stapled and installed to `/Applications` — and `SIGABRT`'d at launch (libgit2
Team-ID, hardened runtime). Every strap visible from the cab was tight. Only
launching the binary + `otool -L` + mounting the DMG caught the loose one.

## Evidence checkpoints

Verification is not a ceremony layer. It is attribution infrastructure.

The minimum lifecycle checkpoints are:

1. **Pre-work intake** — re-read repo state, branch, `HEAD`, dirty files, and
   prior reports before acting.
2. **Pre-change baseline** — record current checks or known failures before
   claiming a regression was introduced later.
3. **Implementation** — keep scope and ownership boundaries explicit.
4. **Pre-handoff baseline** — before another agent takes over, record branch,
   `HEAD`, `git status --short`, changed files, gates, known failures, and the
   exact next instruction/report path.
5. **Handoff intake** — the receiving agent compares the baseline with the live
   tree before editing.

Do not treat these as optional process. If you skip an evidence checkpoint, you
are not saving time; you are destroying attribution.

## Loct is the instrument — literal vs semantic

Pick the lens by where the answer lives:

- **Semantic code mapping** (FIRST move on any structural question — not grep):
  `loct context`, `loct slice` / `impact`,
  `loct find --mode who-imports|where-symbol`, `loct follow dead|cycles|twins`,
  `loct health`, `loct suppressions`, `loct env-truth`; MCP `slice` / `impact` /
  `follow`. For where a symbol lives, who imports X, blast radius of editing or
  deleting Z, reachability, dead code, cycles, twins, silencers, env contracts —
  the AST / importer / dispatch graphs.
- **Literal occurrences + body analysis**: `loct find --literal <text>`,
  `loct occurrences <id>`, `loct body <symbol>`; MCP `find mode=literal`. For
  exact text/identifier hits with `occurrence_kind`
  (string_literal / reference / definition), error strings, version pins, config
  paths, comment/markdown content, and reading a function's real body.
  Identifier-boundary truth; coverage stated per query; "not found" means not
  found.

Reflex: "does the answer live in AST/importer/dispatch graphs, or in literal
text?" First → loct semantic. Second → `loct --literal`. grep only as a local
magnifier after loct, with the failed loct command logged to
`~/.vibecrafted/loctree/loctree-fail.md`.

## Applies to

- The closing rail of every WRITE skill body (Implement, Workflow, Marbles,
  Polarize, Hydrate) — verify before the handoff.
- Section 6 (Gates) and Section 9 (Loctree first) of every worker dispatch
  prompt — see `vc-operator/DISPATCH_TEMPLATE.md`.
- Any READ skill making a runtime claim (Review, Audit, Followup, DoU).

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 The LibraxisAI Team_
