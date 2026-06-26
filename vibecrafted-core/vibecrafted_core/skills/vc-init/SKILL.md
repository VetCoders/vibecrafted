---
name: vc-init
version: 5.0.0
description: >
  Technical due diligence at the start of every repo session — the entrypoint
  to all repo work, like reading CLAUDE.md. Before touching anything, see the
  asset as it IS: materialize the Loctree context atlas and READ IT TO THE END,
  recover intent (AICX), verify ground truth (git/security), and grade the risk.
  Non-pipeline; runs every session. Trigger: "init", "initialize", "bootstrap",
  "daj kontekst", "zainicjuj", "przygotuj agenta", "start fresh with context".
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v2 -->

> **Operator CLI / slash-command layer:** invoking `/vc-<workflow>` or
> `vibecrafted <workflow> <agent>` means dispatching the external Vibecrafted
> fleet through the launcher. In that layer, the invocation is an imperative to
> act, not a no-op, and not native in-process subagents.
>
> **Skill-loading / chat layer:** loading this `SKILL.md` inside Codex, Claude,
> Gemini, or another local agent does not mean self-dispatch. Read and apply the
> skill in the current thread; do not spawn another agent unless the operator
> explicitly asks you to launch, dispatch, run the fleet, or gives a concrete
> command such as `vc-init codex` / `vibecrafted init claude`.
>
> The sole native in-process carve-out is `vc-delegate`.

<!-- /fleet-imperative -->

# vc-init — Technical Due Diligence

Due diligence is the investor's move: before you commit capital to an asset, you
investigate it on evidence — surface hidden liabilities, verify the pitch, grade
the risk — so the decision is priced, not hoped. Here the pitch is the README and
the founder's belief that it works; the asset is the live code. `vc-init` is that
investigation at session entry: see what the code IS now, recover why it became
that, find what is taped together, and grade the risk — so every later move is
priced. It is **read-only orientation**, the entrypoint to all repo work.

`vc-init` (DD on the asset, at entry) and `vc-dou` (DD on the product, at exit,
from the buyer's frame) are the same discipline at the two ends.

## [HARD GATE] — materialize the atlas and READ IT TO THE END

The cheapest, fastest recon that exists is the Loctree context atlas read whole —
empirically far cheaper than a recon agent and instant. Agents under-read; this
gate exists because reading cannot be skipped.

1. **Materialize** the atlas: MCP `context()` (or `loct context`). It writes
   `.loctree/context-atlas/` — a `manifest.md` plus cards.
2. **Read `manifest.md`** — it is the reading path (per-card `why` +
   `saves-you-from`) and the completeness rule.
3. **Read the cards to the end, along the path.** The manifest's own bar:
   a repo-level answer is INCOMPLETE until `00-core-map.md` (synthesis: identity,
   risk, authority, safe commands), `01-structural-map.md` (files/symbols/
   imports/consumers), and `02-runtime-map.md` (runtime/env/reachability) are
   read. Also read `05-risk-register.md` (hotspots/fan-in/health). Cards are
   separate files precisely so none overflows — read each whole.

Do NOT stop at the first card or the first screen. The synthesis and the risk
register are distinct cards; a partial read is a blind start. You have not run
init until the completeness bar is met.

CLI fallback when MCP is unavailable: `loct context --full --markdown` and read
the WHOLE pack (its synthesis is at the end — read past the tables).

## Scope drill-down — same budget, concentrated

The whole-repo atlas is recency-weighted on a fixed ~800-line budget, so stale or
peripheral subsystems get cut. Before working inside a specific subsystem X, read
its scoped pack — this is not narrowing, it is _deeper_ coverage of X at the same
cost:

```bash
loct context --scope 'path:<X>' --task '<what you are doing>' --markdown
# pre-baked shelf, when present:
cat .loctree/context/scopes/path/<X>/context-compact.md
```

Reading the right scoped pill recovers exactly the surfaces the whole-repo atlas
dropped — at ~12s and near-zero tokens, instead of dispatching a recon agent.

## The Triad of Diligence

### Perception — over memory

The atlas is primary perception. Read authority labels before trusting a claim:
`repo_verified` (snapshot fact) > `loctree_derived` (analyzer inference) >
`aicx_operator` / `aicx_agent` (prior intent/outcome) > `aicx_failure` (a path
that already failed — don't repeat) > `semantic_guess` (heuristic — verify) >
`stale_or_unknown` (re-check). Drill with `slice` (before edit), `impact`
(before delete), `find --literal` / `occurrences` / `body` (reference truth),
`follow` (dead/cycles/twins/hotspots). Pass `project=` explicitly per repo — the
MCP default is not your cwd.

### Intentions — retrieval, not RAG

`aicx intents -p <project>` + `aicx_search`/`aicx_steer`: recover _why_ the
architecture is shaped this way and what duct-tape was applied late at night.
Retrieve the decision context, then verify its current truth against perception.

### Ground truth — over intuition

- Git history: `zsh -ic repo-full` (or `git log --graph -n 15` + `git status -sb`).
- Read `.claude/CLAUDE.md` / `.codex/AGENTS.md` / `AGENTS.md`; if a config
  contradicts the code, trust the code.
- Due-diligence red flags: god tables with no indexes; auth where everyone is
  admin/user with no row-level security; `.env` tracked in git; silent failures.

### Output — grade the risk

Init's deliverable is a priced picture: what is load-bearing (hubs/fan-in), what
is fragile, what is a landmine — so the next action is taken with eyes open.

## `.env` policy

Never commit `.env*` (gitignored; pre-commit blocks it). Report leaks → revoke
fast. Work with `.env` locally without anxiety — hesitating to use it locally is
itself a future vulnerability.

## Anti-Patterns

- Acting before the atlas is read to the completeness bar (blind start).
- Stopping at the first card/screen — the risk register is a later card.
- Trusting the MCP default `project` instead of passing it (silent wrong-repo).
- Reflex `grep`/`find` before `context()`/`find` — you lose authority labels and
  reverse deps.
- Dispatching a recon agent for what a scoped `context --scope` answers for free.
- Claiming "production-ready" off a green test on an unexamined architecture.
- Writing "ran the tests" without running them.

## Living Tree

Run in the operator's current checkout and branch; no worktree unless asked.
Re-read before editing; if the tree moved under you (`doctor()` fingerprint),
re-issue `context(fresh: true)`. If the substrate is too poisoned to continue,
stop and report it.

---

_"See the asset. Recover the intent. Verify the ground. Grade the risk. Then act."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
