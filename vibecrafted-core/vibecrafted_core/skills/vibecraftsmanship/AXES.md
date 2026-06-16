# Vibecraftsmanship — Three Axes Deep Dive

The trinity is operational, not philosophical. Each axis has concrete
triggers, anti-patterns, and survival tests.

---

## Axis 1: Ludzki gust (taste = direction)

### What it owns

- **What to make**: feature scope, product surface, integration boundary
- **Why now**: timing relative to runway, market, ICP, narrative
- **What "good" looks like**: quality bar, polish level, ship readiness
- **Which framing is honest**: primary-vs-parallel, equal-intensity,
  rescheduled-vs-retired, fork-and-forget vs sync-with-upstream
- **Which ICP segment**: developer-skeptic-of-AI, survival-cheat,
  Day-2-Operations-rescue, audit-grade differentiation
- **Stop conditions**: when to push, merge, ship, pause, kill

### What agents do for this axis

- Propose: rank options, surface trade-offs, identify blind spots
- Verify: check current state of repo / market / ICP against framing
- Document: capture operator decisions in journals + memory for continuity
- Adapt: when operator corrects framing mid-flight, re-align immediately

### What agents NEVER do for this axis

- Decide unilaterally what "good" means
- Impose ranking when operator wanted equal-intensity
- Apply conventional estimates without checking operator-rescaled ones
- Push without operator authorization (irreversible)
- Sign commits as themselves when work was agent's (AGENT FAIRNESS)

### Concrete examples from 2026-05-24 session

- Operator picked **wezterm as 1-of-4 parallel labs**, not "primary spine".
  Agent's initial framing (primary/parallel/premium) was drift. Corrected.
- Operator picked **fork-and-forget for microsandbox** ("zrywamy kiść z
  gałęzi która wystaje na naszą miedzę"). Agent could not have predicted
  this posture — it's operator's taste call.
- Operator picked **rescheduled over retired** for vc-mux/vc-frame.
  Semantic distinction that shapes how teams interpret postponement.
  Agent had drift'd to "retirement" framing; corrected mid-flight.
- Operator picked **microsandbox + Zentty in one lab**, with Zentty as
  inspiration-only (GPL boundary). Agent would have separated them; this
  is taste, not optimization.

### Trigger to invoke Taste call

- "I see N options with trade-offs A/B/C. Operator picks?"
- "Framing X feels off — want to recalibrate?"
- "Scope creep candidate — in or out of this iteration?"
- Operator's silent corrections in conversation — read them as Taste signals

### Survival test for Taste

If you can't say WHY this is good in operator's terms (not abstract
"clean code"), the Taste axis is not yet satisfied.

---

## Axis 2: Agentyczna siła (agent power = search space expansion)

### What it owns

- **Parallelism**: how many agents on same problem simultaneously
- **Triangulation**: when 3 perspectives catch blind spots 1 would miss
- **Convergence**: marbles loops over iterations toward truth
- **Cross-tier fairness**: claude/codex/gemini peer-frontier (not
  hierarchy)
- **Substrate isolation**: per-lab cwd, separate target_repos, Living
  Tree discipline
- **Reach beyond serial human**: 4-7×, 80-150×, 1000-1800× compression
  ratios empirically observed depending on stack + parallelism

### What this axis does NOT mean

- **Not speed**: speed is a side effect. The point is **wider menu** for
  operator to choose among, in same wall-clock window.
- **Not headcount substitution**: agents don't replace human judgment;
  they expand the surface of options that judgment selects from.
- **Not "more agents = better"**: 1 well-targeted dispatch beats 3
  dispersed ones. Triple-research is for triangulation, not for
  triplicate output.

### Operational default — external dispatch surface (HARD RULE)

For deliverable-producing fleet (reports, code, plans, persistent
artifacts), Power axis is **only honestly satisfied** when dispatch goes
through `vibecrafted <workflow> <agent>` via Bash — NOT through native
`Agent` tool. Native `Agent` is for in-process scouting only (Explore,
quick lookup, read-only research).

**Why this matters for the Power axis:** native `Agent` returns transient
output that vanishes from parent context after the call. No canonical
store, no transcript, no `meta.json`, no reproducible launcher. That
breaks the **"wider menu for operator"** promise — operator can't review
the run, can't compare across runs, can't hand transcript to another
agent. The search-space expansion happened in-process but left no
artifact to choose among. Power without observability = theatre.

`vibecrafted` produces full lineage under
`~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/`:
`<run_id>.meta.json` (status) + `<run_id>.md` (report) +
`<run_id>.transcript.log` (live stream) + `tmp/<run_id>_launch.sh`
(reproducer). That is the artifact substrate Power axis requires.

**Reflex check** (run BEFORE each external dispatch):

1. Deliverable-producing (artifact on disk)? → `vibecrafted` mandatory
2. In-process scouting (read-only lookup)? → native `Agent` ok
3. Multi-agent parallel with persistence? → `vibecrafted` mandatory
4. > 200-word brief producing artifacts? → that's deliverable, reroute

This is enforced because **discipline loses to ergonomics**. Native
`Agent` is one-call-away in the top tool list. `vibecrafted` is one Bash
hop away. Without an explicit hard rule, reflex always picks the easier
path. Empirical proof: 2026-05-25 operator-side agent self-critique
documented this exact drift mid-dispatch (see [EVIDENCE.md](./EVIDENCE.md)
case study #2).

### Concrete patterns from this session

- **Triple-research swarms** (rsch-005022 + 3 spine swarms × 3 agents =
  9 reports): each swarm gave operator gap-free synthesis. Single-agent
  research would have missed cross-validated signals (e.g., wezterm
  6/9 vote across 9 independent agents).
- **Wave A 2-parallel** (vibecrafted + vc-console, different repos = no
  Living Tree collision): 33 min wall-clock for 999+1089 LOC.
- **Wave B 4-parallel** (wezterm + vc-apprt + locterm + microsandbox,
  different repos): all 4 launched same minute, terminal states reached
  in 30-60 min. Conventional serial would have been 4× that.
- **Marbles loop** (B-2): codex iterated incremental Zig 0.16 fixes,
  loop 1/3 converged to terminal state when report-failed signal hit
  (Phase 0+1+2 commits landed, repo-wide test failed on inherited
  pre-existing substrate). Marbles correctly stopped — didn't burn
  iterations on irrelevant ground.
- **Per-lab cwd** (B dispatch shape): each agent started in own lab dir,
  reports landed per-lab, no shared-dir confusion. Living Tree
  discipline.

### Anti-patterns

- **Single agent for novel terrain**: when problem is unknown, 1 agent
  is gambling. Use triple-research for blind-spot coverage.
- **3 agents for known problem**: when answer is clear, parallel is
  waste — pick the right agent (per WHY_MATRIX_TABLE) and ship.
- **Sequential when parallel was possible**: if 2+ tasks share no
  state, serial is leaving compression on the floor.
- **Mocked outputs as "search"**: synthetic test passing while real
  substrate broken is NOT search-space expansion — it's pretending.
- **Tier mixing**: parent Opus dispatching workers Sonnet → cache miss
  - quality regression. Always parent-tier (MODEL PARITY).

### Trigger to invoke Power call

- "Have we explored enough alternatives, or premature-committing?"
- "Is this problem 1-agent or triple-research shape?"
- "Are these tasks parallel-safe (no shared state)?"
- "Marbles or polarize — convergence or decisive cut?"

### Survival test for Power

If operator's menu of options didn't get **wider** after dispatch, the
Power axis is not yet earning its keep.

---

## Axis 3: Rzeczywistość (reality = survival filter)

### What it owns

- **Commits**: real or not
- **Gates**: green or red, on real evidence
- **Substrate**: present or missing (krunvm, Zig 0.16, libkrun, etc.)
- **Build truth**: app compiles, runs, opens, accepts input
- **Runtime truth**: tests pass on real path, not mocked
- **Ship truth**: customer can install, find, buy, use
- **Estimate honesty**: empirical compression ratio applied, not
  conventional ED parroted

### What this axis demands

- **No claim without evidence**: "I implemented X" requires commit SHA +
  gate output. Empty claim = not real.
- **No PASS without gate green**: even if implementation looks right,
  red gate = not yet survived. Substrate-failure is information; it is
  NOT a pass.
- **No estimate without empirical reference**: when a source says "3-6
  months", check whether their assumptions match VetCoders working
  pattern. Pensieve falsified gemini's 3-6 months in 28 hours of real
  work.

### Concrete reality contacts from this session

- **A-1**: 999 LOC, 25 files, ruff+mypy+pytest 148+ green. Commit
  `0fc9206`. SURVIVED.
- **A-2**: 1089 LOC, 17 files, IPC smoke green, BUT tui-agent catalog
  drift + Linux cairo pkg-config red. Worker marked FAILED honestly.
  CORE PATH survived, edge cases flagged as orthogonal cleanups.
- **B-1**: caught events.jsonl schema drift (real `kind:"state"` not
  brief's `"spawn-update"`) — that's reality teaching the brief.
  Adapted, shipped commit `02645e75c`. SURVIVED, smarter.
- **B-2**: 3 commits, 74/74 apprt tests, smoke green. zig build test
  red on **inherited pre-existing** ghostty-test/panels-test SIGBUS.
  Worker marked FAILED on strict gate. CORE survived, substrate
  pre-existing failure surfaced as information.
- **B-3**: 1382 LOC, pytest 173/173 (148+ → +20 new), GPL boundary
  smoke clean. Commit `eb6beb8`. SURVIVED with style.
- **B-4**: code in worktree complete, BUT krunvm missing on host →
  msbserver can't build → no commit. SUBSTRATE-FAILURE. Worker
  honestly marked failed. Code is information; reality hasn't
  authorized it yet.
- **Pensieve**: 27 commits / 4485 Swift LOC / 28 hours real work.
  Bear-class markdown editor with TextKit 2 editor + swift-markdown
  preview + signed/notarized release pipeline. SURVIVED reality
  better than gemini's 3-6 month estimate predicted.

### Anti-patterns

- **Demo-grade claims**: "it works" without commit + gate
- **Mocked PASS**: tests green on mock data, broken on real
- **Hidden substrate dependencies**: brief assumed krunvm; reality
  rejected
- **Conventional ED quoted as authority**: cross-swarm reports gave
  18-32 week estimates; reality shipped same surface in 3 hours
- **"Production ready" without measurement**: per CLAUDE.md NO HYPE
  POLICY

### Trigger to invoke Reality call

- "Did this actually land, or did we perform landing?"
- "Are these gates green on real evidence or mock?"
- "Is the substrate present (toolchain, deps, runtime)?"
- "What empirical compression ratio applies here?"

### Survival test for Reality

If the commit isn't on a branch with green gate output you can paste
into a report, Reality has not yet ruled.

---

## When axes conflict

Sometimes gust says "ship this", siła says "we haven't explored
enough", rzeczywistość says "gates red". The trinity is not a
voting system — it's a constraint set. ALL THREE must be satisfied
simultaneously.

Conflict resolution:

- **Taste vs Power**: operator's call. Direction can override search ("I
  pick A, stop exploring") or expand it ("explore deeper before I
  pick").
- **Taste vs Reality**: Reality wins. Operator can want
  ship, but if gates red, ship is performative — fix the gate first.
- **Power vs Reality**: Reality wins. Agents producing more
  options doesn't change whether commits land. Fix the substrate, then
  explore.

The honest answer when conflict is unresolvable: declare it as
substrate-failure or scope-overflow, document what's blocked, hand to
operator for triage. Don't pretend the trinity is aligned when it isn't.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
