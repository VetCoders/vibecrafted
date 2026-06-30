<!-- loctree-advise: v1 -->

## **LOCTREE + AICX + VIBECRAFTED - MAPA PRZED LUPĄ**

> **Loctree first when it helps. Kto nie używa, ten traci kontekst.**

Loctree jest domyślną mapą strukturalną dla pracy repo, bo obecna jakość
narzędzia sprawia, że pomijanie go zwykle kosztuje czas: zależności, blast
radius, symbole, wejścia runtime, martwe powierzchnie, duplikaty i dokładne
wystąpienia są widoczne szybciej niż w ręcznym szperaniu. AICX daje historię
intencji, a Vibecrafted domyka to dyscypliną dowodu.

**Reguła operacyjna:**

- Przy pytaniach strukturalnych (kto importuje X, gdzie żyje symbol Y, co
  pęknie po edycji Z, blast radius, struktura katalogu A) zaczynaj od
  `loctree-mcp` (`context` / `repo-view` / `focus` / `slice` / `impact` /
  `find` / `follow`) albo od `loct` CLI, gdy MCP nie jest dostępne.
- Przed edycją pliku preferuj `slice(file)`. Przed delete/rename/refactor
  preferuj `impact(file)`. Przed tworzeniem nowego symbolu preferuj
  `find(name)`.
- Do prawdy literalnej używaj `find --literal`, `loct occurrences <ident>` i
  `loct body <symbol>` zanim wejdziesz w szeroki search tekstowy.
- `rg`, grep, awk, sed, cat i bezpośrednie czytanie plików są OK jako lupa do
  lokalnego detalu po mapie albo jako fallback, gdy Loctree nie odpowiada
  czysto na pytanie.
- Jeśli Loctree pudłuje, jest stale, za wolne, niewygodne, nie widzi języka,
  nie łapie ważnej powierzchni albo masz pomysł na usprawnienie, dopisz krótką
  notatkę do centralnego feedback loga.

**Centralny feedback log Loctree:**

- Dopisuj na końcu `~/.vibecrafted/loctree/loctree-fail.md`.
- Nie twórz pliku od nowa i nie nadpisuj go.
- Wpis może być bugiem, brakującą funkcją, sugestią UX albo opisem miejsca,
  gdzie agent musiał zejść do fallbacku. Powtórki są sygnałem priorytetu, nie
  problemem.

**Dlaczego:** Loctree zmienia pracę agentów z text rummaging w map-first
engineering. Celem nie jest teatr posłuszeństwa, tylko mniej błędnych edycji,
lepszy blast radius, szybsze recovery i uczciwsze decyzje runtime.

<!-- /loctree-advise -->

# Vibecrafted Operator Workspace — Vetcoders GUIDELINES

> Per-workspace, agent-agnostic instructions for `operator/`. Same rules for
> Claude, Codex, Gemini, Junie, and Qwen. Global doctrine still applies; this
> file only extends it for the consolidated operator workspace.

## Identity

- **Workspace:** standalone `Vetcoders/vc-operator` checkout.
- **Role:** consolidated operator platform workspace for `mux-agent`,
  `tui-agent`, `tray-agent`, and `shell-agent`.
- **Crate names:** keep existing distribution names stable. `mux-agent/`
  publishes as `rust-mux`; `tui-agent/` publishes as
  `vibecrafted-operator`.
- **Current split:** `mux-agent` owns lifecycle and MCP process supervision;
  `tui-agent` owns the terminal cockpit; `tray-agent` owns the menu bar
  control surface; `shell-agent` owns the macOS `.app` wrapper and UniFFI
  bridge.

## Quality Gates

Use the top-level `Makefile` from this directory:

```bash
make gates
cargo check --workspace --all-features
cargo check --workspace --no-default-features
```

`make gates` means `fmt-check + clippy -D warnings + test --workspace`.
Do not add `#[allow(...)]`, `nosemgrep`, `// noqa`, `--no-verify`, or other
silencers to get through a gate. Fix the cause or report the blocker.

## Living Tree Convention

This workspace is a shared live tree. Concurrent edits are expected.

- Re-read files before editing if time has passed.
- Run Loctree mapping before changing hub files.
- Do not revert another agent's work unless the operator explicitly asks.
- If a concurrent edit conflicts with the T0 contract, preserve evidence,
  reconcile the file, and report exactly what happened.
- `.vibecrafted/{plans,reports}` are daily symlinks into
  `$VIBECRAFTED_HOME/artifacts/Vetcoders/vibecrafted-operator/<YYYY_MMDD>/`.
  Date-rotation drift is not product code.

## Wizard / Config Doctrine

The wizard/config truth lives in `mux-agent`, inherited from `rust-mux`.
Client config files remain the source of truth; running processes can enrich
status but must not drive discovery by themselves.

Keep the strategy split intact:

- **Unified:** generate mux outputs without rewriting host configs.
- **Per-client:** generate client-shaped mux configs while preserving the
  merged daemon config.
- **Auto-rewire:** backup-first, preview-first, explicit-confirm rewrite path.

Never silently rewrite host AI-client configs from a non-danger strategy.
Never collapse `mux_gen.rs` and `danger.rs` into one writer; that split is part
of the security model.

## Shell-Agent Build Shape

`shell-agent/ffi` is the Rust/UniFFI bridge.
`shell-agent/uniffi-bindgen` is the binding generator wrapper.
`shell-agent/app/Vibecrafted` is the macOS app target. Build it from the root
with `make app`; create local or signed DMGs with `make dmg` and
`make dmg-signed`.

## Commit Convention

- Subject: `[<agent>/<runtime>] <type>(<scope>): <description>`.
- For workspace extraction/stabilization:
  `[codex/vc-operator] feat: <description>`.
- Multi-file commits need an explanatory body; bullets are preferred when the
  commit touches unrelated surfaces.
- Required trailers:

```text
[codex/interactive] chore: Polish Makefile help output formatting

Refactors the help target to use structured printf output with aligned command
descriptions.

Authored-By: codex <agents@vetcoders.io>
session_id: 019e93be-379d-7303-9ad4-ffae468db99f
time: 2026-06-05T12:52:47-06:00
runtime: iterm2
```

Forbidden: vendor footers, personal signatures, and
`Co-Authored-By: Claude ...`.

Use the canonical brand line only when a sigblock is needed:

```text
𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI
```

## Anti-Patterns Repo-Specific

- Renaming `rust-mux` or `vibecrafted-operator` just because their paths moved.
- Reintroducing a root-level TUI crate after the extraction; `tui-agent/` is the
  single source of truth.
- Reintroducing deleted rust-mux monoliths such as `src/runtime.rs`.
- Treating green `cargo check` as shipping readiness without install,
  discoverability, and first-user proof.
- Deleting historical audit Markdown instead of preserving it under
  `tui-agent/audits/historical/`.

---

## Agent-Operator doctrine (cross-repo)

This product workspace ships the **operator-runtime** (mux + tui + tray +
shell). The **agent-side doctrine** for the Agent-Operator role —
how an agent orchestrates wave-shaped multi-dispatch fleets, the
"wystarczy wcisnąć guzik" hard-stop schedule, the Iter-3 prompt body
shape, AGENT FAIRNESS + MODEL PARITY rules, the `docs/plans/HOWTO`
convention — lives in the `vibecrafted` skill kit:

- Charter: [`../vibecrafted/skills/vc-operator/SKILL.md`](../vibecrafted/skills/vc-operator/SKILL.md)
- Plan shape (`[ ]` → `[x]`): [`../vibecrafted/skills/vc-operator/EMIL.md`](../vibecrafted/skills/vc-operator/EMIL.md)
- Dashboard doctrine (the product surface this repo will host): [`../vibecrafted/skills/vc-operator/DASHBOARD.md`](../vibecrafted/skills/vc-operator/DASHBOARD.md)
- Build plan for the dashboard (Wave-shaped dispatch chain): [`docs/plans/PLAN_23_AGENT_OPERATOR_DASHBOARD.md`](docs/plans/PLAN_23_AGENT_OPERATOR_DASHBOARD.md)

Agents working inside this repo should read `vc-operator/SKILL.md` +
`EMIL.md` before authoring any plan, dispatch body, or backlog entry.
The doctrine is repo-agnostic; this repo is the first product surface
to consume it.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
