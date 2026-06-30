# vc-audit — PHASES: Ośmiofazowa procedura auditu

> Każdy audit przechodzi przez te osiem faz sekwencyjnie. Żadnej fazy nie
> wolno pominąć. Każda faza produkuje numerowaną sekcję w
> `audit_report.md` oraz odpowiadającą jej linię w `audit_trace.log`.

Czytaj razem z [`SKILL.md`](SKILL.md) i [`DISPATCH.md`](DISPATCH.md).

---

## Faza 1 — Context Receipt

Najpierw przeczytaj Loctree Context Pack. Wyprodukuj Context Processing
Receipt z:

- repo root, gałąź, commit, snapshot id
- `dirty_worktree`: true / false
- `snapshot_health`, `stale_snapshot`
- hotspoty / pliki o wysokim fan-in istotne dla tego planu
- bramki weryfikacji sugerowane przez kontekst
- zastrzeżenia autorytetu (`RepoVerified` vs `LoctreeDerived` vs
  `SemanticGuess` vs `AicxAgent` / `AicxOperator` / `AicxFailure`)

Jeśli `dirty_worktree` jest true:

- zapisz to wprost
- uruchom `git status` / `git diff` przed oceną stanu finalnego
- nie traktuj checkoutu jako czystego

Reguła autorytetu:

- `RepoVerified` można traktować jako evidence strukturalne ugruntowane w repo
- `LoctreeDerived` można traktować jako evidence wyprowadzone, wymagające ostrożności
- `SemanticGuess` trzeba traktować jako hipotezę, nie twardą prawdę
- etykiety `AICX*` nie wolno traktować jako faktów repo, chyba że niezależnie
  zweryfikowane

Jeśli etykieta autorytetu nie jest formalnie zdefiniowana w schemacie
kontekstu/taska, oznacz swoją interpretację jako inferred-not-verified.

Linia trace: `READ_CONTEXT_PACK`.

---

## Faza 2 — Task Ingestion Receipt

Przeczytaj każdy plik taska / planu w całości. Dla każdego wyprodukuj Task
Processing Record:

- `task_id`, `task_name`, plik źródłowy
- status z frontmattera (jako **twierdzenie**, nie prawda)
- deklarowane zależności
- deklarowany cel
- liczba acceptance criteria
- oczekiwane pliki do modyfikacji / utworzenia
- wymagane testy
- non-goals (wymagania negatywne)
- exit contract
- notatki o ryzyku
- notatki o stage'ach (jeśli są)
- `task_read_status`: `FULL_READ` / `PARTIAL` / `BLOCKED`

Jeśli którykolwiek task nie jest full-read, audit nie może zakończyć się
PASS. Powiedz to wprost w executive verdict.

Wyemituj w raporcie tabelę `Tasks Loaded`:

```
| Task ID | File | Full read | Acceptance criteria | Depends on | Stage notes |
```

Linia trace per task: `READ_TASK task_id_NN`.

### Dyscyplina warstwowego czytania

Gdy plik taska jest ucięty przez limity outputu narzędzia, czytaj go w
warstwowych spanach po ~1500–2000 linii za pomocą offset/limit w `Read`,
albo w spanach po ~80 000 znaków przez `python3 -c 'print(open(P).read()[A:B])'`.
Wprost podaj pokrycie w raporcie (np. „Read task-07 in 3 spans of 1800
lines, total 5400 lines, 100% coverage").

Zabronione: pisanie analizy na podstawie tekstu ostrzeżenia o ucięciu,
pierwszego podglądu 2KB albo samej nazwy pliku.

---

## Faza 3 — Atomic Requirements Extraction

Dla każdego taska zamień akapity acceptance w testowalne elementy. Każde
acceptance criterion staje się co najmniej jednym wymaganiem. Wyciągnij
też:

- non-goals jako **wymagania negatywne**
- zależności jako **dependency checks**
- komendy weryfikacyjne jako **obowiązki weryfikacyjne**
- exit contracts jako **wymagania procesowe / raportowe**
- staged status claims jako **wymagania stage'owe**

Wyemituj jeden rekord JSON na wymaganie do
`audit_requirements_matrix.jsonl`:

```json
{
  "task_id": "01-atlas-per-repo",
  "requirement_id": "01-R03",
  "requirement": "load_atlas_info no longer relies on latest/context-atlas fallback",
  "source_section": "Acceptance criteria",
  "expected_code_locations": ["loctree_rs/src/analyzer/html.rs"],
  "verification_type": "code + negative check + test"
}
```

Linia trace per task: `EXTRACT_REQUIREMENTS task_id_NN count=N`.

---

## Faza 4 — Positive + Negative Code Verification

Dla każdego wymagania uruchom oba checki.

**Positive check** — zweryfikuj, że oczekiwany kod istnieje.

**Negative check** — zweryfikuj, że stary fallback / stare zachowanie /
zabroniony non-goal **nie** jest już obecny.

Używaj Loctree przed grepem:

- `find(name)` tryb `who-imports` dla „kto zależy od nowego symbolu?"
- `slice(file)` przed oceną nośności huba
- `impact(file)` do weryfikacji zasięgu zmiany przy usunięciu
- `find(name)` tryb `where-symbol`, by potwierdzić, że zdeprecjonowana ścieżka zniknęła

Zaliczony positive check + zaliczony negative check + zaliczony test
= evidence STRONG. Cokolwiek mniej jest słabsze.

Linie trace per task:
`INSPECT_CODE task_id_NN files=N`,
`VERIFY_TESTS task_id_NN tests=N`,
`NEGATIVE_CHECK task_id_NN checks=N`.

---

## Faza 5 — Adversarial Pass

Nie jesteś przyjaznym recenzentem. Dla każdego wymagania aktywnie próbuj
udowodnić, że implementacja jest **niekompletna**.

Dla każdego wymagania odpowiedz na wszystkie pięć sub-checków:

1. **Positive evidence:** jaki kod wydaje się to implementować?
2. **Negative evidence:** czy stare zachowanie jest wciąż obecne? Czy
   zdeprecjonowany fallback jest wciąż podpięty? Czy non-goal jest
   naruszony? Czy implementacja jest w złej warstwie? Czy istnieje
   ścieżka, gdzie wymaganie jest omijane?
3. **Test strength:** czy test istnieje? Czy asercja dotyczy **dokładnie**
   wymaganego zachowania? Czy implementacja mogłaby być zepsuta, a test
   wciąż przechodziłby?
4. **Dependency check:** jeśli to zależy od innego wymagania, czy ta
   zależność jest faktycznie zaimplementowana? Czy to wymaganie używa
   nowej zależności, czy starego założenia?
5. **Evidence quality:** sklasyfikuj jako STRONG / MEDIUM / WEAK / NONE.

Linia trace per task: `DEPENDENCY_CHECK task_id_NN`.

---

## Faza 6 — Stage-Aware Verdict

Wiele tasków jest wielo-stage'owych. NIE WOLNO ci traktować statusu z
frontmattera jako prawdy, ale również NIE WOLNO ci oznaczać taska FAIL
tylko dlatego, że późniejszy stage jest w kolejce.

Dla każdego wielo-stage'owego taska wyciągnij:

- frontmatter_status
- delta najnowszego stage'u
- stage'e wspomniane w pliku
- który stage jest deklarowany jako wylądowany
- jaki scope pozostaje odroczony / w kolejce z założenia
- co dla tego taska oznacza „done"
- czy audit powinien oceniać ukończenie pełnego planu,
  tylko-wylądowany-stage, czy gotowość-zależności dla downstreamowych tasków

Wyemituj:

```
| Task | Stage audited | Landed scope | Deferred scope | Verdict | Evidence |
```

Wartości verdictu stage-aware:

- `STAGE_PASS` — wylądowany stage w pełni spełniony, odroczony scope
  jawnie poza scope'em tego auditu
- `STAGE_PASS_WITH_GAPS` — wylądowany stage w większości spełniony, z
  udokumentowanymi drobnymi lukami
- `STAGE_PARTIAL` — wylądowany stage ma co najmniej jedną kluczową lukę
- `STAGE_FAIL` — wylądowany stage przeczy taskowi
- `FULL_PLAN_INCOMPLETE_BY_DESIGN` — task jawnie odracza późniejsze
  stage'e i to odroczenie jest akceptowalne

Linia trace per task: `STAGE_CHECK task_id_NN`.

---

## Faza 7 — Per-Task Verdict Table

Wyprodukuj główną tabelę verdictów. Jeden wiersz na task. Każdy task
rozliczony dokładnie raz. Nie zwijaj tasków w narracyjne podsumowanie.

Kolumny:

| Task # | Task name | Frontmatter status | Stage audited | Requirements checked | Implemented | Partial | Missing | Contradictions | Negative checks | Test coverage | Overall verdict | Severity | Evidence summary | Recommended follow-up |

Verdicty: `PASS`, `PASS_WITH_GAPS`, `PARTIAL`, `FAIL`, `UNVERIFIED`,
`STAGE_PASS`, `STAGE_PASS_WITH_GAPS`, `STAGE_PARTIAL`,
`FULL_PLAN_INCOMPLETE_BY_DESIGN`.

Severity: P0 (implementacja przeczy taskowi / psuje taski zależne /
narusza non-goal), P1 (brak kluczowego acceptance criterion),
P2 (luka testowa / raportowa / procesowa), P3 (luka kosmetyczna / dokumentacyjna).

Linia trace per task: `CLASSIFY task_id_NN verdict=<verdict>`.

---

## Faza 8 — Self-Attack Pass + Model Check

### Self-Attack

Przed sfinalizowaniem przejrzyj **każdy** verdict PASS i PASS_WITH_GAPS.
Dla każdego odpowiedz:

- Jaki jest najmocniejszy powód, dla którego ten verdict może być błędny?
- Czego nie zweryfikowałem bezpośrednio?
- Które wymaganie ma najsłabsze evidence?
- Jaka pojedyncza komenda lub test najszybciej sfalsyfikowałyby mój verdict?

Jeśli po tym ataku którykolwiek PASS ma słabe evidence, obniż go do
PASS_WITH_GAPS lub UNVERIFIED. Nie broń swojej pierwszej odpowiedzi.
Atakuj ją.

Linia trace per atakowany task: `SELF_ATTACK task_id_NN`.

### Model Check

Wyemituj sekcję Model Check:

- poczynione założenia
- obszary, w których audit mógłby się mylić
- taski najtrudniejsze do zweryfikowania
- którym twierdzeniom z raportów odmówiłeś zaufania bez evidence z kodu
- które obszary kodu wymagają przeglądu przez człowieka
- które staged taski mogłyby być źle sklasyfikowane, jeśli oceniane wobec
  pełnego planu zamiast scope'u wylądowanego stage'u

Ustaw:

```
model_confidence: high | medium | low
```

Jeśli confidence nie jest `high`, powiedz dlaczego.

Cross-Task Findings (opcjonalne, ale zalecane) — zidentyfikuj wzorce
przez taski: powtarzający się brakujący wzorzec, zerwane łańcuchy
zależności, nieaktualne twierdzenia z raportów, stary fallback wciąż
obecny, testy zbyt słabe, naruszony non-goal, implementacja w złej
warstwie, niespójność context/atlas/LSP/API, pomieszanie stage'u/statusu.

| Finding | Affected tasks | Evidence | Severity | Recommendation |

Linia trace: `WRITE_REPORT`, potem `END`.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
