# vc-operator — DISPATCH: Kształt ciała promptu Iter-3

> Kanoniczny kształt ciała promptu dla dispatchu `/vc-agents` / `vc-justdo` / `vc-implement`.
> Dopracowany przez trzy iteracje: Iter-1 (jednoliniowa checklista,
> zbyt chuda), Iter-2 (ad hoc akapit, zbyt miękki), Iter-3 (dwunastosekcyjny
> brief klasy ownership, bieżący). Honoruje kształt planu z [`EMIL.md`](EMIL.md)
> oraz format railu voice-promptów Emila z `~/.codescribe/transcriptions/`
> (sty. 2026, gdzie konwencja była najpierw przeżyta, zanim została skodyfikowana).

Czytaj razem z [`SKILL.md`](SKILL.md), [`GUIDE.md`](GUIDE.md), [`EMIL.md`](EMIL.md).

---

## Dlaczego kształt Iter-3

Zdispatchowany agent **nie ma wspólnej pamięci** z tobą. Ciało promptu jest
kompletnym kontraktem. Iter-1 niedospecyfikował scope (workerzy improwizowali);
Iter-2 przeopisał intencję, ale niedospecyfikował bramek (workerzy commitowali
pracę zepsutą do połowy). Iter-3 naprawia oba, traktując ciało promptu jako
**kontrakt wyjścia** workera — jawna akceptacja, jawne bramki, jawny
out-of-scope, jawna podpowiedź odzyskiwania oraz jawny closing rail, który
ustawia kontrakt emocjonalny (stawka + mrugnięcie), który worker musi honorować.

Dobrze ukształtowany brief Iter-3 zajmuje ~20 minut autorstwa i oszczędza ~3 godziny
dispatchu odzyskiwania na falę.

---

## Dwanaście sekcji

Każde ciało dispatchu ma te sekcje w tej kolejności:

### 1. Frontmatter YAML

```yaml
---
prompt_id: textforge-editor-core-20260516
wave: B
position: 1
mandate: /vc-ownership
recommended_agent: claude
parent_branch: feat/text-context-menu@f6b02744
result_branch: feat/textforge-editor-core
depends_on: [textforge-shell-20260516]
parallel_with: []
blocks:
  [
    textforge-tool-rail-20260516,
    textforge-stylize-20260516,
    textforge-inspectors-20260516,
  ]
report_path: ~/.vibecrafted/artifacts/<...>/reports/textforge-editor-core_<ts>_claude.md
authored_by: claude <agents@vetcoders.io>
---
```

`prompt_id` to klucz cross-walk do retrievalu sesji; `wave` + `position`
lokalizują go w atlasie; `recommended_agent` jest egzekwowany przez AGENT MODEL
PARITY; `parent_branch` to dokładny SHA, od którego worker się odgałęzia;
`depends_on` / `parallel_with` / `blocks` domykają graf zależności.

### 2. Mission

Jeden akapit (3–5 zdań) otwierany domyślnym imperatywem Emila
`You're tasked with...` / `Your job is to...`. Podaj, co ląduje, gdy ten
prompt się powiedzie — „akceptację po tym, jak to wyląduje" prostym językiem.

Przykład:

> _„You're tasked with replacing the canvas placeholder with a real
> multi-line editor surface. Buffer + selection + cursor live on the
> provider. Undo/redo with a 200-step ring buffer. Selection-aware so
> transforms later can read the current span without re-querying the DOM.
> After this lands, Waves B-2 through B-4 can plug their tool-specific
> reads/writes against `buffer` and `selection` signals without further
> provider extensions."_

### 3. Context

Bullety wskazujące, co worker powinien przeczytać przed edycją:

- istniejące ścieżki plików provider / shell / canvas (z podpowiedziami `loct slice`)
- SHA commita poprzedniej fali + co wylądowało (żeby worker znał baseline)
- design tokens / pliki motywu, które ograniczają wyjście wizualne
- istotne testy, które przypinają kontrakty

Nie wklejaj tu treści — tylko ścieżki. Worker czyta pliki sam.

### 4. Files to create / edit

Jawna lista, pogrupowana:

```text
Create:
  studio/src/components/textforge/TextForgeCanvas.tsx
  studio/src/components/textforge/__tests__/TextForgeCanvas.test.tsx

Modify (append-only fields where marked):
  studio/src/components/textforge/TextForgeProvider.tsx
    + APPEND-ONLY: buffer / selectionStart / selectionEnd signals
    + APPEND-ONLY: history stack (push debounced 150ms)
    DO NOT delete or rename existing exports — Wave B-2..B-4 depend on them

  studio/src/styles/textforge.css
    + canvas typography rules in the dedicated section
```

Markery append-only + linie „do not delete" to **ostrzeżenia Living Tree
VERBATIM** — zobacz Sekcję 8 niżej.

### 5. Acceptance

Lista checkboxów w stylu GitHub, atomowa, testowalna (wg [`EMIL.md`](EMIL.md)
Reguła 1):

```markdown
- [ ] Typing in the canvas updates the provider's buffer signal in real time.
- [ ] Selection changes inside the textarea propagate to selectionStart/End
      signals observable from outside the component.
- [ ] Cmd/Ctrl+Z undoes the last 150ms-debounced edit; Shift+Cmd/Ctrl+Z redoes.
- [ ] Ring buffer caps at 200 steps; earlier steps are silently dropped.
- [ ] Existing tests in `sidebar-state.test.ts` and `TextForgeProvider.test.ts`
      stay green.
- [ ] New tests in `TextForgeCanvas.test.tsx` cover typing flow, selection
      propagation, and undo/redo wiring.
```

Worker przerzuca pozycje `[ ]` → `[x]` w miarę ukańczania i wkleja
finalny stan checkboxów do swojego raportu.

### 6. Gates

Jawne komendy:

```bash
pnpm -C studio run check   # typecheck + lint + format
pnpm -C studio run test    # Vitest
pnpm run check             # root: lint + format + Jest + studio check
```

Wszystko zielone to bramka. Workerzy muszą uruchomić bramki lokalnie przed commitem.

### 7. Out of scope

Jawny anti-scope-creep:

```text
Out of scope (DO NOT touch):
- Tool rail behaviour beyond exposing `activeTool` signal as a placeholder
  (that's Wave B-2's surface)
- Inspector content (Wave B-4)
- TopBar actions / workspace tabs (Wave C topbar)
- StatusBar wiring (Wave C statusbar)
- Right-click context menu (already exists; Wave D input-parity rewires it)
```

Dwuliniowy out-of-scope na dispatch to minimum. Workerzy uwielbiają tę sekcję,
bo mówi im, czego _nie_ implementować, gdy „zajęłoby to tylko 5 minut".

### 8. Living Tree etiquette

**Verbatim**, bez parafrazy:

```text
Living Tree etiquette (NON-NEGOTIABLE):
- Re-read every file in `Files to modify` IMMEDIATELY before editing it.
  Another agent in a sibling wave or this wave's prior step may have
  pushed between your dispatch start and your first edit.
- For files marked APPEND-ONLY, never delete or rename existing exports.
  Append new signals / methods at the end of the export block.
- For shared CSS files, add new rules in a dedicated section with a
  comment block stating which prompt added them.
- If you detect that another agent's work is incompatible with your
  acceptance, halt and write a "substrate failure" report instead of
  attempting a merge. The operator-agent decides next move.
```

Ten blok jest identyczny w każdym zdispatchowanym prompcie w fali — agent
operatora nie dostosowuje brzmienia, tylko listę plików powyżej.

### 9. Loctree first

Jawne dyrektywy `mcp__loctree-mcp__*`:

```text
Loctree first (perception over memory):
1. `mcp__loctree-mcp__context` on project root before any edit
2. `mcp__loctree-mcp__slice` on each file in `Files to modify` before editing
3. `mcp__loctree-mcp__impact` on files in `Files to modify` if your change
   could affect importers
4. `mcp__loctree-mcp__find name=TEXTFORGE_TOOLS mode=where-symbol` to
   confirm where shared types live

Grep fallback (only if loctree fails):
- Acceptable: `grep -RIln 'TextForgeProvider' studio/src/`
- Log a hook entry to `~/.vibecrafted/loctree/loctree-fail.md` describing
  why loctree was insufficient, so the loctree team can improve it.
```

### 10. Recovery hint

```text
Recovery hint (if your dispatch stalls):
- Substrate stall (Living Tree poisoned, prior wave's commit doesn't
  exist on parent_branch): halt, write `substrate-failure.md`, exit
  non-zero. Operator-agent dispatches a fix.
- Scope stall (acceptance #N is wider than 1 commit can satisfy): write
  a `scope-overflow.md` listing what landed + what didn't, exit 0 with
  partial commit. Operator-agent narrows the next dispatch.
- Implementation stall (you took the wrong cut, gates fail at >30 min):
  revert your branch to parent_branch, write `wrong-cut.md` describing
  what you tried, exit 1. Operator-agent dispatches a focused integration
  agent with hints.
```

### 11. Branch + commit convention

```text
Branch + commit:
- Branch: `feat/textforge-editor-core` off `feat/text-context-menu@f6b02744`
- Cadence: ONE commit per round (marbles — one round = one commit); a dispatch that delivers multiple rounds/units is EXPECTED to produce multiple commits, each committed locally as its round completes. Never leave delivered work uncommitted.
- Commit subject: `[claude/vc-implement] feat(textforge): wire editor canvas to provider`
- Commit body: explain the change, then include the full runtime footer:
  `Authored-By: claude <agents@vetcoders.io>`, `session_id: <uuid>`,
  `time: YYYY-MM-DDTHH:MM:SS±HH:MM`, and `runtime: <runtime>`.
- Do not use `Co-Authored-By:`, vendor noreply addresses, or personal signatures.
- DO NOT `git push`. Operator publishes after wave green.
- DO NOT create PR. Operator does that operator-side.
```

### 12. Report path + Call to Action + Closing rail

```text
Report path (mandatory):
~/.vibecrafted/artifacts/<...>/reports/textforge-editor-core_<ts>_claude.md

Report sections:
- Frontmatter (mirror this prompt's YAML, set `status: completed | failed`)
- Current state, Proposal, Execution, Open risks, Next move (per ownership)
- Gate results (paste the last 10 lines of each gate command)
- Files changed (paste `git diff --stat HEAD~1`)
- Acceptance verification (paste the Section 5 checkbox state, flipped)
```

Następnie **Call to Action** + **Closing rail** — zobacz domyślny blok poniżej.

---

## Klamra końcowa — domyślny blok Emila

Każde ciało dispatchu Iter-3 zamyka się blokiem ogrodzonym railem, niosącym trzy
elementy: **jednoliniówka antydługowa + sygnaturowe kaomoji + puenta sucharu**.
Kształt został przeżyty w `~/.codescribe/transcriptions/` w sty. 2026 (voice-prompty
Emila) i jest teraz kanonem.

```text
=======================
[Jednoliniówka antydługowa, która personifikuje buga jako folk-horror, biurokrację
lub absurd domenowy — np. „Jeśli stan po cichu nadpisuje sam siebie, to nie
bug, to poltergeist w codebase'ie — a lekarstwem na duchy
jest porządny unit test."]  (งಠ_ಠ)ง
=======================

Call to Action: [Imperatyw sekwencyjny — „Zacznij od X, a potem Y → Z". Bądź
konkretny. Zakończ raportem.]

Suchar: [Pun domenowy w kształcie suchara — „Dlaczego pipeline nigdy nie idzie
do lasu? Bo boi się, że bez loctree zgubi swoją ścieżkę."]
(._.)
```

**Trzy wymagane elementy**:

1. **Jednoliniówka antydługowa** w railach `=======` — ramuje powierzchnię
   techniczną jako mały moment folk-horroru lub biurokratyczny (poltergeist,
   paranormal, szczepienie, bug potrzebuje egzorcyzmu, ten commit pachnie
   3 nad ranem). Podnosi stawkę bez hype'u.
2. **Sygnaturowe kaomoji** — `(งಠ_ಠ)ง` dla railu antydługowego (domyślne),
   `(._.)` dla puenty sucharu (domyślne). Inne kaomoji to
   przyprawa — używaj ich tylko wtedy, gdy moment na to zasługuje; nigdy dwóch w jednym
   zdaniu; nigdy w środku akapitu.
3. **Call to Action** — imperatyw sekwencyjny. Powracający kształt Emila
   to `Zacznij od X, a potem Y → Z` (lub jego odpowiednik EN `Start with X,
then Y → Z`). Zakończ tym, co worker oddaje (raportem). Nigdy
   „good luck".

**Slot sucharu jest opcjonalny, ale zachęcany**. Jeśli dispatch jest poważny (
dispatch odzyskiwania po dwóch porażkach, fix krytyczny dla bezpieczeństwa) odpuść
suchar — jednoliniówka railu + kaomoji niosą zamknięcie same. Jeśli
dispatch jest rutynowy, zostaw suchar; workerzy raportują wyższą akceptację
briefów, które zamykają się mrugnięciem.

---

## Bank sucharów (gotowe do portu suchary EN do zamknięć technicznych)

Gdy suchar pasuje, czerp z lub remiksuj:

- _„Why does the pipeline never go to the forest? Because it's afraid of
  losing its path without loctree."_
- _„Why did the test suite refuse to run on Friday? It had plans with the
  CI all weekend."_
- _„Why does the runner-loop never sleep? Because it forgot to checkbox
  its own bedtime."_
- _„Why did Wave C never make it to trunk? Somebody forgot to merge Wave
  B first and the agents threw a tantrum in their pull requests."_
- _„Why does the migration script always run at 3 a.m.? Because at noon
  the schema is too embarrassed."_
- _„Why did the dispatch body fall asleep? Too many `Out of scope` lines
  in a row."_
- _„Why does the kaomoji never get tired? It signs every commit without a
  keyboard."_

Polskie suchary też działają, jeśli kontekst dispatchu jest tylko dla zespołu PL —
kanonem jest struktura (`Why does X not Y? Because Z. (._.)`), nie język.

---

## Rotacja sprawiedliwości agentów

W ramach 4-promptowego łańcucha Wave B rotuj Claude → Gemini → Codex → Claude.
W ramach 3-promptowej równoległej Wave C rozłóż na wszystkie trzy. W ramach
2-promptowej Wave D naprzemiennie. Sprawiedliwość agentów to nie tylko atrybucja — to
**hedging biasu ensemble'u**. Różne agenty zawodzą różnie; rotacja
rozkłada powierzchnię porażki.

Wyjątek: jeśli prompt jest mocno backend-only (np. audyt diakrytyków z Wave C),
codex często jest właściwym wyborem niezależnie od rotacji. Podaj
wyjątek w uzasadnieniu `recommended_agent`.

---

## Egzekwowanie agent model parity

Każdy zdispatchowany worker działa na **tym samym tierze co agent operatora**. Jeśli
jesteś Opusem, twoi workerzy są Opusami. Żadnych „tanich równoległych skanów na Haiku" —
parent Opus → każdy worker Opus, bez wyjątków.

To stosuje się identycznie do floty zewnętrznej `/vc-agents` i natywnej delegacji Task.

---

## Antywzorce

- Pomijanie markerów APPEND-ONLY z Sekcji 4 na plikach współdzielonych → gwarantowana
  korupcja łańcucha Wave B.
- Mgliste acceptance z Sekcji 5 („looks right in the UI") → worker nie potrafi
  się samo-zweryfikować, wraca z pracą zrobioną do połowy.
- Brak out-of-scope z Sekcji 7 → scope creep, inflacja czasu fali.
- Luźne brzmienie Living Tree z Sekcji 8 („be careful with shared files")
  → workerzy nie biorą tego na poważnie; użyj bloku VERBATIM.
- Dispatch bez ścieżki raportu z Sekcji 12 → worker pisze raport
  gdziekolwiek; przyszły retrieval go nie znajdzie.
- Pomijanie closing railu, bo „worker nie potrzebuje sucharu"
  → potrzebuje. Rail ustawia kontrakt emocjonalny. Ciała dispatchów
  bez niego czyta się jak korporacyjne tickety i zarabiają korporacyjno-ticketową
  akceptację („met spec, nothing more").

---

## Wezwanie do działania

Napisz swoje pierwsze ciało per-prompt, używając dwunastosekcyjnego szablonu powyżej
plus zamknięcia ogrodzonego railem. Skopiuj bank sucharów, jeśli potrzebujesz
startera. Potem przeczytaj je z powrotem tak, jakbyś był zdispatchowanym workerem — jeśli któraś
sekcja każe ci zgadywać, dociśnij ją przed odpaleniem.

---

## Klamra końcowa

```text
=======================
Ciała dispatchów to kontrakty pisane dla kogoś, kogo nigdy nie spotkałeś. Zrób
je tak jasnymi, by worker mógł wykonać robotę bez pytania, i tak ciepłymi,
by worker pamiętał, dlaczego ta robota miała znaczenie. Stawka + struktura +
suchar — to jest Emil. (งಠ_ಠ)ง
=======================

Suchar: Dlaczego Iter-3 działa tam, gdzie Iter-1 nie działał? Bo closing rail
w końcu wyjaśnił workerowi, że operator czyta raport,
a nie diff. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024–2026_
