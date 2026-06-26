# Runtime Integration Status — from scaffolds to one runtime

> Status: living status note · branch `feat/runtime-integration` · refreshed 2026-06-11
> Companion: `docs/runtime/CONTRACT.md`, `docs/runtime/TOPOLOGY.md`,
> `docs/DOCUMENTATION_MAP.md`.

## What Is Live Now

The old version of this page correctly called out horizontal scaffolding. That
warning is still useful, but it is no longer the whole truth. This branch now
has active runtime lanes:

- `vibecrafted dispatch <file.toml>` exists in the command deck.
- `runtime/scripts/` is active spawn/await/meta/watcher runtime.
- `runtime/shell/lib/` is the installed shell facade layer.
- `runtime/vc-marbles/`, `runtime/vc-research/`, and `runtime/vc-operator/`
  show the per-workflow extraction pattern.
- `vibecrafted gui`, `tui`, and `dashboard` are live operator surfaces, even
  where they are still local/control-plane viewers rather than full supervisors.

The remaining job is still vertical integration: one narrow path that starts a
real worker, records durable artifacts, updates shared state, and shows the same
truth in at least one operator surface without falling back to an undocumented
side channel.

## Niezmienniki (trzymają cały plan)

1. **Work decoupled from view** — engine work is not dependent on a watched tab.
2. **Artifact-as-truth** — every run must leave report, transcript, metadata,
   and machine-readable status where applicable.
3. **One contract, many eyes** — Python writers, Rust readers, TUI, web, tray,
   and shell surfaces must not invent separate state schemas.
4. **Degrade, don't die** — no vc_frame, no TTY, crash, and interrupted shell paths
   should still produce an honest failure artifact.
5. **Vertical slices, dogfood daily** — demo success is not runtime truth.
6. **Seal then widen** — prove one path, then add eyes.
7. **Determinism** — install, sandbox, VM, and remote paths should not mutate
   under the operator's feet.

## Ścieżka krytyczna (jedno zdanie)

`dispatch/run schema` -> **walking skeleton** (1 command E2E:
supervisor -> worker -> artifacts -> shared state -> TUI/GUI visibility) ->
**seal seams** -> **widen** (web/tray/iTerm) -> **substrate**
(sandbox/vm/remote) -> **resilience/release**.

---

## Faza 0 — Freeze & Truth _(zabij wieloznaczność)_

**Goal:** one launcher language, one state contract, one artifact story.

- Smoke each runtime lane and mark it live, partial, or scaffold in
  `TOPOLOGY.md`.
- Freeze the run-state/event contract used by dispatch, watchers, TUI, and GUI.
- Keep shell compatibility where it is the installed facade; remove only
  duplicate or undocumented launchers.

**DoD:** `vibecrafted doctor` green enough to trust, one documented state
contract, no public docs pointing at dead launchers.

## Faza 1 — Walking Skeleton _(najcieńsza pionowa rurka, dogfood)_

**Goal:** one daily command path used for real work.

```
vibecrafted dispatch run ... OR vibecrafted implement <agent>
  -> real worker spawn
  -> artifacts (report + transcript + meta/result)
  -> shared state
  -> TUI/GUI/dashboard visibility
```

- Bez web, bez sandbox, bez tray, bez vm — ale **przez wszystkie realne szwy tej rurki**.
- Kontrakt spinany: `core`-writer ↔ `control-core`-reader ↔ `tui-agent`.

**DoD (dogfood, twardy):** przez **3 dni z rzędu** zespół odpala realne zadania TĄ rurką —
zero fallbacku do szela, runy widoczne w TUI, raporty czytelne. Nie używasz codziennie → Faza 1 NIE skończona.

## Faza 2 — Seal the Seams _(rurka nie pęka pod brakiem substratu)_

- **Degradacja jako test runtime** (nie tylko kod): kill terminal/vc_frame w trakcie runu → runtime przeżywa, artifact kompletny; brak TTY → headless; crash → failure zapisany.
- `app/mux-agent` przejmuje natywne sesje (`mux_gen` + `jsonl_bridge`) — **vc_frame-launcher + osascript znikają**.
- `control-core/tests/schema_fidelity.rs` zielony — kontrakt Py↔Rust nie dryfuje.

**DoD:** „zabij terminal w połowie runu" → runtime żyje, raport kompletny; schema_fidelity gate w CI.

## Faza 3 — Widen Surfaces _(one contract, many eyes)_

- `server/web` (Leptos) czyta **ten sam** kontrakt `control-core` → dashboard.
- `tray-agent` (menubar) + `vibecrafted_iterm2` jako dodatkowe oczy.

**DoD:** ten sam run widoczny **identycznie** w TUI i web — bez osobnego parsowania po każdej stronie.

## Faza 4 — Substrate & Remote _(reprodukowalność + zdalność)_

- `core/sandbox/*` (microsandbox, `MSB_*`) izoluje runy.
- `vm` (`Containerfile` + tailscale) — reprodukowalny, zdalny, headless.
- Determinizm instalacji: klasa cargo-ghost/codesign-SIGKILL fixnięta i **zagated** (re-sign po stripie itd.).

**DoD:** ten sam `vc-<workflow> <agent>` leci identycznie lokalnie i w vm/zdalnie.

## Faza 5 — Resilience & Release

- CI/CD gates, smoke, rollout safety, config drift (intent „Release & Runtime Resilience").
- Pakowanie `app` (`.dmg`) + kanał update.

**DoD:** P0/P1=0 · smoke green · `.dmg` instaluje się czysto · update path działa.

---

## Ryzyka / pułapki (z których już krwawiliśmy)

- **Powrót do horyzontalnego scaffoldu** (każdy robi swój kawałek) — to było piekło tygodni. Roadmapa wymusza pion.
- **Dryf schematu control-core** — bez gate `schema_fidelity` web i TUI się rozjadą.
- **„Działa w demie ≠ używane codziennie"** — dogfood gate w Fazie 1 jest twardy, nie kosmetyczny.
- **Niedokończony cut-over zostawia dwa launchery** — Faza 0 MUSI zabić wieloznaczność, inaczej dispatch znów spadnie na zdeprecjonowany szel (dzisiejsze „Refusing AppleScript").

## Mierniki „spięte w runtime" (kiedy to JEST runtime, nie scaffold)

- 1 launcher · 1 kontrakt · 0 szela.
- E2E run zawsze produkuje artifact i jest widoczny w ≥1 oku.
- Przeżywa brak vc_frame / brak TTY / crash.
- **Używane codziennie przez zespół** (dogfood) — to jest definitywny test.
