# vc-polarize — PROCEDURE: Cykl życia, punktowanie, bramki, context corpus

> Pełna procedura per-krok dla przebiegu polarize. Referencja dla
> punktowania osi pryzmatu, ośmiu etapów cyklu życia, kontraktu
> retencji context-corpus, zestawu minimalnych bramek oraz playbooka
> trybów awarii.

Czytaj wraz z [`SKILL.md`](SKILL.md) i [`FLOW.md`](FLOW.md).

---

## Wejścia

Dozwolone:

- bieżąca prawda workspace'u
- świeże evidence z `vc-init` / loctree / AICX
- prism packi generowane przez `loct context --with-aicx --task ...`
- niedawne raporty marbles
- raporty DoU / release / hydrate / decorate, gdy są istotne
- README, quickstart, installer, marketplace, command help, powierzchnie release'u
- ograniczenia operatora: nabywca, kanał launchu, zakazane twierdzenia,
  pożądana śmiałość

Niedozwolone:

- niepoparte twierdzenia
- uśrednianie konkurencyjnych kierunków
- traktowanie Prism Score jako metryki wstydu
- używanie nieświeżych context packów jako bieżącej prawdy kodu
- punktowanie liczby plików zamiast dryfu autorytetu

---

## Prism Score (pełne kryteria osi)

Użyj stabilnego scorera Loctree do oceny Prism Score. Punktuj każdą oś
od `0` do `3`, suma `0..15`:

| Oś                  | Znaczenie                                                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Spread              | Ile powierzchni niesie koncept: kod, shell env, testy, docs, artefakty, AICX, publiczne copy.                                     |
| Runtime Centrality  | Czy koncept siedzi na entrypoincie, instalatorze, cyklu życia marbles, cyklu życia research, release lub control plane operatora. |
| Authority Diversity | Czy evidence pochodzi z kodu RepoVerified, struktury LoctreeDerived, testów, pamięci AICX/operatora, publicznych docs.            |
| Drift Risk          | Prawdopodobieństwo, że powierzchnie sobie przeczą lub nieświeże artefakty tworzą fałszywą prawdę.                                 |
| Closure Evidence    | Czy bramki, testy, raporty, pliki stanu, launch cardy lub artefakty czynią domknięcie maszynowo sprawdzalnym.                     |

Pasma i działania:

- `0..4`: `abort` — stop przed dispatchem agenta i pokaż ścieżkę prism
  JSON
- `5..8`: `memo` — wyemituj tylko lokalne memo i cienki przykład
  context-corpus
- `9..12`: `pass` — uruchom pełny przebieg polarize z wstrzykniętym
  payloadem prism
- `13..15`: `doctrine` — uruchom pełny przebieg doctrine z oczekiwaniem
  regression-contract

---

## Cykl życia (osiem etapów)

### 1. Perceive

Uruchom sprawdzenia prawdy repo. Potwierdź gałąź, dirty tree, bieżący
head oraz czy prism packi są nieświeże względem żywego kodu.

### 2. Collect

Przeczytaj prism packi, najnowsze istotne raporty marbles, publiczne /
instalacyjne / release'owe powierzchnie oraz command help.

### 3. Score

Użyj stabilnego scorera Loctree do oceny Prism Score na pięciu osiach
powyżej. Zapisz pasmo.

### 4. Choose

Wybierz jedną oś do uczynienia autorytatywną. Odrzuć konkurencyjne osie
jawnie, z podanymi powodami.

### 5. Align

Edytuj tylko powierzchnie poparte dowodem z runtime'u. W trybie konceptu
preferuj kontrakty, testy, docs i schematy artefaktów. W trybie produktu
wyrównaj publiczne copy, CTA, onboarding i tezę release'u.

### 6. Gate

Uruchom wąskie bramki dla dotkniętych powierzchni i szersze bramki, jeśli
są release-facing. Zobacz Minimalne bramki poniżej.

### 7. Emit

Napisz artefakty polaryzacji i handoffy (thesis, concept-contract,
surface-map, decision-ledger, dou-handoff, release-brief).

### 8. Stop

Nie kontynuuj w DoU, hydrate, decorate ani release, chyba że operator
poprosił o ten łańcuch.

---

## Minimalne bramki

Read-only / tylko doctrine:

```bash
git status --short --branch
```

Zmiany w docs lub skillach:

```bash
git diff --check
```

Zmiany w command deck / help:

```bash
pytest tests/tui/test_vibecrafted_launcher.py -q
```

Zmiany w instalatorze / release-facing:

```bash
make check
make semgrep
```

Sidecary korpusu:

```bash
python3 -m json.tool <sidecar>.json
```

---

## Kontrakt Context Corpus

Runner jest producentem packów prism context-corpus. Dla `pass` i
`doctrine` przechwytuje linię stdoutu `session: <uuid>` dispatchowanego
agenta i opakowuje domyślny ekstraktor:

```bash
aicx extract --agent <agent> --session <uuid> --output <raw-path>
```

Nie regeneruj treści od zera, nie przepisuj surowych packów Markdown ani
nie mieszaj ich w zwykłe chunki konwersacji AICX. Dla `memo` runner
zapisuje tylko cienkie lokalne memo i sidecar. Dla `abort` nie zapisuje
żadnego packu context-corpus, bo nie powstała żadna użyteczna prawda.

### Ścieżka retencji

```
$HOME/.aicx/context-corpus/<org>/<repo>/<YYYY_MMDD>/loct-context-pack/<batch>/
  raw/
  sidecars/
  index.jsonl
```

### Schemat sidecara

```json
{
  "schema_version": "context_corpus.v1",
  "artifact_family": "loct-context-pack",
  "truth_status": {
    "role": "example",
    "runtime_authoritative": false,
    "stale_against_current_head": false,
    "current_head_when_ingested": "ded1e0b"
  },
  "learning_use": {
    "allowed": ["format_examples", "section_order", "keyword_index"],
    "forbidden": ["current_code_truth", "implementation_claims", "gate_status"]
  },
  "keywords": ["installer", "contract"],
  "band": "pass",
  "total_score": 11
}
```

Sidecary z pasma memo ograniczają `learning_use.allowed` do
`["format_examples"]`.

Prawda runtime'u musi zawsze pochodzić ze świeżego `loct context`,
świeżych odczytów repo i istotnych bramek — nigdy z packów korpusu.

---

## Tryby awarii

- **Brak evidence prism:** poproś o pack `loct prism --task ...`.
- **Pasmo prism za niskie:** abortuj przed dispatchem agenta i wypisz
  `vc-polarize aborted: prism score <n>/15 is below threshold.
Inspect <path-to-prism.json>`.
- **Runtime nie może poprzeć pożądanej obietnicy:** odeślij z powrotem do
  `vc-workflow` lub `vc-marbles`.
- **Pozostają dwie wykonalne osie:** wyemituj memo decyzyjne; nie uśredniaj ich.
- **Publiczne powierzchnie przeczą prawdzie release'u:** zablokuj handoff release'u.
- **Context pack jest nieświeży:** użyj go tylko jako evidence korpusu /
  przykładu, potem zregeneruj świeży kontekst.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
