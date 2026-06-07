# Runtime Integration Roadmap — od luźnych scaffoldów do JEDNEGO runtime

> Status: draft · branch `feat/runtime-integration` · 2026-06-05
> Companion: `docs/runtime/CONTRACT.md` (kontrakt) + (planowany) `docs/runtime/TOPOLOGY.md` (mapa).

## 0. Brutalna prawda (dlaczego to jeszcze NIE żyje)

Pięć komponentów (`core`, `mcp`, `server`, `app`, `vm`), **zero w codziennym użyciu**.
Wszystkie to wyniki scaffoldów (W1-a/b/c i pochodne), budowane **horyzontalnie** —
każda fala dorzucała swój kawałek, **nic nie zostało spięte wertykalnie i nie jest
dogfoodowane**. Dowód siedzi w pamięci AICX wszystkich pięciu scope'ów: recydywujący
`AicxFailure` — _"closed the run as failed: blocked by W1-a's incomplete
`server/control-core` substrate"_. To nie awaria komponentu — to **brak integracji**.

**Antidotum: pion zamiast poziomu.** Najcieńsza rurka end-to-end przez wszystkie realne
szwy → używana codziennie → dopiero potem szerokość. Scaffold się skończył; teraz spięcie.

## Niezmienniki (trzymają cały plan)

1. **Work decoupled from view** — silnik (`core`) niezależny od tego, czy ktoś patrzy.
2. **Artifact-as-truth** — każdy run = `report` + `transcript` + `validation`. Prawda w artefakcie, nie w panelu.
3. **One contract, many eyes** — control-plane: Python-writer → **typed** Rust-reader (`control-core`) → web + TUI. Żaden front nie parsuje JSON na piechotę.
4. **Degrade, don't die** — brak zellij → headless; brak TTY → działa dalej; crash → zapisuje failure. Nigdy „Refusing AppleScript".
5. **Vertical slices, dogfood daily** — „działa w demie" ≠ done. Done = używane codziennie bez fallbacku.
6. **Seal-then-widen** — najpierw JEDNA ścieżka żyje codziennie, potem dokładamy oczy/substrat.
7. **Determinism** — vm/sandbox; zero cargo-ghostów; instalacja się nie zmienia pod nogami (klasa zellij-SIGKILL/stale-binary).

## Ścieżka krytyczna (jedno zdanie)

`control-plane schema (control-core)` → **walking skeleton** (1 komenda E2E: core→artifact→TUI)
→ **seal seams** (szel out, mux natywny, degradacja) → **widen** (web/tray/iterm)
→ **substrate** (sandbox/vm/remote) → **resilience/release**.

---

## Faza 0 — Freeze & Truth _(zabij wieloznaczność)_

**Cel:** jeden launcher, jeden zapis stanu, jeden kontrakt. Koniec dwóch światów.

- Smoke każdego z 5 → oznacz REALNIE odpalalne vs scaffold-skeleton (tabela w TOPOLOGY.md).
- **Zamroź control-plane schema** jako źródło prawdy: typed kontrakt run-state + events, wersjonowany. Pisze `core/control_plane.py`, czyta `server/control-core`.
- Wytnij resztki szela: pępowiny `core` → `agents/scripts/await.sh`, `agent_dispatch.py` → `agents/scripts/lib/meta.sh`; napraw `doctor` spawn-pipeline (ma walidować core, nie usunięty `common.sh`).

**DoD:** `vibecrafted doctor` zielony bez warnów o szelu · jeden udokumentowany kontrakt schematu · zero martwych launcherów w drzewie.

## Faza 1 — Walking Skeleton _(najcieńsza pionowa rurka, dogfood)_

**Cel:** JEDNA komenda end-to-end, bez szela, używana codziennie.
sas

```
vc-implement <agent>  →  core.AsyncSupervisor.run  →  realny spawn
                      →  artifact (report+transcript+validation)
                      →  zapis do control-plane
                      →  app/tui-agent (mission_control) pokazuje run NA ŻYWO + wynik
```

- Bez web, bez sandbox, bez tray, bez vm — ale **przez wszystkie realne szwy tej rurki**.
- Kontrakt spinany: `core`-writer ↔ `control-core`-reader ↔ `tui-agent`.

**DoD (dogfood, twardy):** przez **3 dni z rzędu** zespół odpala realne zadania TĄ rurką —
zero fallbacku do szela, runy widoczne w TUI, raporty czytelne. Nie używasz codziennie → Faza 1 NIE skończona.

## Faza 2 — Seal the Seams _(rurka nie pęka pod brakiem substratu)_

- **Degradacja jako test runtime** (nie tylko kod): kill terminal/zellij w trakcie runu → runtime przeżywa, artifact kompletny; brak TTY → headless; crash → failure zapisany.
- `app/mux-agent` przejmuje natywne sesje (`mux_gen` + `jsonl_bridge`) — **zellij-launcher + osascript znikają**.
- `control-core/tests/schema_fidelity.rs` zielony — kontrakt Py↔Rust nie dryfuje.

**DoD:** „zabij terminal w połowie runu" → runtime żyje, raport kompletny; schema_fidelity gate w CI.

## Faza 3 — Widen Surfaces _(one contract, many eyes)_

- `server/web` (Leptos) czyta **ten sam** kontrakt `control-core` → dashboard.
- `tray-agent` (menubar) + `iterm2_plugin` jako dodatkowe oczy.

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
- Przeżywa brak zellij / brak TTY / crash.
- **Używane codziennie przez zespół** (dogfood) — to jest definitywny test.
