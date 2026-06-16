# vc-init — `backlog/HOWTO.md`: `docs/backlog/` jako czwarty zmysł percepcji

> `vc-init` wykonuje już trzy przebiegi percepcji — Loctree (struktura),
> historia sesji (intencje), twarde fakty (git + higiena .env). Ten
> HOWTO dodaje **czwarty zmysł**: czytanie `docs/backlog/` jako
> domyślnej, czytelnej dla zespołu powierzchni opisującej _dlaczego wybraliśmy
> ten kształt, co zostało, gdzie indziej ten wzorzec ma znaczenie_.

Czytaj razem z [vc-init SKILL](../SKILL.md), [vc-operator EMIL](../../vc-operator/EMIL.md),
[vc-scaffold plans HOWTO](../../vc-scaffold/plans/HOWTO.md).

---

## 1) Po co czwarty zmysł

Loctree pokazuje ci **co** (pliki, krawędzie, węzły nośne). Historia sesji
pokazuje ci **kto** (który agent co i kiedy zdecydował). Git pokazuje ci
**jak** (diffy, commity, gałęzie). Żaden z nich nie odpowiada na pytania:

- _„Dlaczego wybraliśmy ten kształt zamiast oczywistej alternatywy?"_
- _„Które sąsiadujące powierzchnie skorzystają z tej samej poprawki?"_
- _„Jaki jest plan operatora na kolejny horyzont?"_

Katalog `docs/backlog/` odpowiada na te pytania. Każdy wpis to
**czytelny dla zespołu i przyjazny pozyskiwaniu** dokument, który zamienia „co"
z komunikatów commitów na „dlaczego, co dalej, gdzie indziej to ma znaczenie".

Czytaj backlog jako część initu. To tam decyzje przyszłego-ciebie są
już udokumentowane.

---

## 2) Gdzie mieszka backlog

Lokalnie w repo, pod `docs/backlog/`. Każdy wpis to osobny plik:

```text
<repo-root>/docs/backlog/
├── README.md                                      ← convention guide
├── 2026-05-12-executetool-file-uri-sandbox.md
├── 2026-05-12-sidebar-line-art-icon-language.md
├── 2026-05-14-global-text-input-context-menu.md
├── 2026-05-14-stylizer-pl-diacritics-pattern.md
├── 2026-05-15-text-editor-portal-plan.md           ← forward plan
└── 2026-05-16-agent-operator-dashboard.md          ← forward plan
```

Nazwa pliku: `YYYY-MM-DD-<slug>.md`. Jeden plik na **wzorzec**, **decyzję**
lub **klaster follow-upów** — nie jeden plik na commit.

---

## 3) Dwa kształty wpisu

### 3.a) Wzorzec retro (domyślny — po wdrożeniu funkcji)

Spisany _po_ wdrożeniu commita. Zakotwiczony w SHA, który go dostarczył.
Reużywalny: ten sam wzorzec zastosowany do przyszłej powierzchni.

```markdown
# <Lesson, not symptom>

> Captured <YYYY-MM-DD> after `<branch>` <one-sentence trigger>.

Reference commit: `<short-sha>` on `<branch>`.

## Pattern delivered

- **`<file-path-1>`** — <concrete, function-level summary>.
- **`<file-path-2>`** — <concrete summary>.

## Why the pattern matters

[The principle — what general problem class this solves, beyond the
specific commit that delivered it.]

## Follow-ups worth surfacing

- **<Adjacent surface 1>**: <bulleted action items that could become
  future prompts>.
  _Scoped into [`<plan-file>`](./<plan-file>) Prompt N_ (when applicable).
- **<Adjacent surface 2>**: <bullets>.
  _Not yet scoped_ (italic note when explicitly left for later).

## Provenance

<What conversation / external reference / incident triggered the entry.>
```

### 3.b) Plan przyszłościowy (przed skoordynowanym, wielopromptowym rolloutem)

Spisany _przed_ odpaleniem dyspozycji o kształcie fali. Zakotwiczony w
commicie **bazowym (baseline)**, od którego plan startuje. Wciąż mieszka w
`docs/backlog/`, żeby pozyskiwanie go znalazło, gdy agent zapyta _„jaki był
zamierzony stan końcowy X?"_.

```markdown
# Plan: <Title>

> Captured <YYYY-MM-DD>. <Operator-voice paragraph: why current shape
> fails.>

Reference baseline branch: `<branch>@<sha>`.
Dispatch target: `vc-operator` on `<host>`.
Mandate: `<skill>` for every prompt.

## 1) Why the current shape fails (1:1)

[Operator's diagnosis verbatim.]

## 2) Target shape

[Diagram + structural description.]

## 3) Reusable pieces from the existing tree

[Table mapping new surface to reused surfaces.]

## 4) Out of scope for this plan

- [ ] [explicit non-goals]

## 5) N prompts for `vc-operator`

[Per-prompt outline pointing at `<artifact-root>/<plan-id>.md`.]

## 6) Dispatch order + dependencies

[Wave structure, mermaid or ASCII.]

## 7) Operator handoff

[How the plan reaches the operator-agent.]

## Close-out (added when plan lands)

Final retrospective bullet listing:

- [x] Prompt 1 → `<sha>`
- [x] Prompt 2 → `<sha>`
- ...
  Plus link to any retro entries written from the plan's discoveries.
```

Oba kształty mają wspólną domyślną linię `Reference commit:` (lub
`Reference baseline branch:`), żeby pozyskiwanie działało w nich
identycznie.

---

## 4) Kanoniczna formuła `Reference commit:`

Dokładna linia:

```text
Reference commit: `<short-sha>` on `<branch>`.
```

lub dla planów przyszłościowych:

```text
Reference baseline branch: `<branch>@<sha>`.
```

**Nie** używaj wariantów w stylu _„Branch: x"_, _„Initial commit: y"_,
_„Based on: z"_. Grep pozyskiwania dopasowuje domyślną formułę verbatim.
Z tego samego powodu rozpisz SHA w osobnej, dedykowanej linii.

---

## 5) Linkowanie krzyżowe

Gdy follow-up w jednym wpisie został wprowadzony do zakresu jako prompt
w późniejszym wpisie planu, oznacz ten punkt frazą **„Scoped into …"** plus
względnym linkiem do pliku planu:

```markdown
- **Curate Stylize submenu**: 62 entries surface every style including
  bugs and archaeological scripts. Triage to ~15 readable defaults; move
  historical scripts behind a "Stylize · All" toggle.
  _Scoped into [`2026-05-15-text-editor-portal-plan.md`](./2026-05-15-text-editor-portal-plan.md)
  Prompt 4 (`textforge-stylize`)_.
```

Dla follow-upów, których jeszcze **nie** wprowadzono do zakresu, oznacz kursywą:

```markdown
- **Diacritics outside Polish/Latin-1**: verify the round-trip for
  Vietnamese (`ế`, `ư̛`), Czech (`ř`, `š`), Spanish (`ñ`).
  _Not yet scoped_.
```

Milczenie jest dwuznaczne; jawne adnotacje nie są.

---

## 6) Jak `vc-init` konsumuje backlog (czwarty zmysł)

Po Loctree + historii sesji + twardych faktach dodaj czwarty przebieg:

```bash
# 1. Inventory the backlog
ls -la <repo-root>/docs/backlog/

# 2. Read every entry from the last 14 days
find <repo-root>/docs/backlog/ -name '*.md' -newer <14-days-ago> | \
  xargs -I{} bash -c 'echo "=== {} ===" && cat {}'

# 3. Note which entries reference the surface you're about to touch
grep -l '<file-path-or-symbol-you-need-to-edit>' <repo-root>/docs/backlog/*.md

# 4. Read the README convention guide once per session
cat <repo-root>/docs/backlog/README.md
```

Jeśli wpis backlogu odwołuje się do powierzchni, którą zaraz będziesz
edytować, **przeczytaj wpis przed edycją**. Jeśli go zignorujesz i wyprowadzisz
ponownie decyzję, którą wpis już rozstrzygnął, naruszyłeś cel tej konwencji.

---

## 7) Kiedy pisać nowy wpis

Napisz wpis retro, gdy:

- Wdrożył się commit, który ujawnił **wzorzec** możliwy do zastosowania
  gdzie indziej (np. NFD-split-and-reattach, pre-routing sandboxa).
- Commit zamknął **decyzję**, której uzasadnienie inaczej by przepadło
  (dlaczego wybraliśmy jedną bibliotekę zamiast drugiej, dlaczego zostawiliśmy
  zdeprecjonowany skill zamiast go wycofać).
- Fala lub PR wygenerowały **klastry follow-upów**, które nie zmieszczą się w
  bieżącym PR-ze, ale nie powinny przepaść.

Napisz wpis planu przyszłościowego, gdy:

- Operator daje ci wielopromptowy mandat, który nie zmieści się w jednej
  dyspozycji.
- Klastry follow-upów z wpisu retro nazbierały dość masy, by
  uzasadnić skoordynowany rollout.

**Nie** pisz wpisu na każdy commit. Backlog jest ziarnisty na poziomie
koncepcji, nie commitów.

---

## 8) Antywzorce

- **Wpisy na każdy commit**: rozwadniają pozyskiwanie. Jedna koncepcja na plik.
- **Zły format nazwy pliku**: pozyskiwanie krzyżuje przez
  `YYYY-MM-DD-<slug>.md`; odstępstwa zostają pominięte.
- **Felietonizowanie w sekcji `Provenance` wpisu retro**: ta sekcja to
  przyjazny pozyskiwaniu ślad _tego, co wywołało wpis_ — trzymaj ją
  faktograficzną.
- **Plan przyszłościowy bez commita bazowego**: pracownicy nie wiedzą, skąd
  się odgałęzić.
- **Pomijanie przewodnika po konwencji README w initcie**: przyszli agenci
  zgadują kształt i dryfują od domyślnej formuły.
- **Backlog jako lista TODO**: nim nie jest. TODO mieszkają w raportach
  pracowników i przekazaniach w punktach stopu. Backlog jest dla wzorców +
  decyzji + planów.

---

## 9) Dlaczego to czwarty zmysł, a nie osobny skill

Konwencja jest lekka — jeden katalog, dwa kształty, jedna domyślna
linia SHA. Nie potrzebuje własnego mandatu skilla. Ale **jest** to
odrębny kanał percepcji względem Loctree (struktura), historii sesji
(intencje), twardych faktów (stan). Odpowiada na pytanie _„czego się
nauczyliśmy, co inaczej by nie przetrwało?"_ — czyli dokładnie na pytanie,
na które init ma odpowiedzieć przed jakąkolwiek edycją.

Uhonorowanie czwartego zmysłu domyka pętlę: każda sesja czyta
backlog, każdy znaczący commit rozważa napisanie wpisu, każdy plan
ląduje jako wpis. Backlog staje się **pasem transmisyjnym** między
sesjami, między hostami, między operatorami.

---

## Wezwanie do działania

Po ukończeniu pierwszych trzech przebiegów initu przeskanuj `docs/backlog/`
w poszukiwaniu wpisów z ostatnich 14 dni lub odwołujących się do plików w
zakresie twojej edycji. Przeczytaj te wpisy przed pierwszą edycją. Jeśli twoja
edycja wdroży reużywalny wzorzec, naszkicuj wpis retro w
głowie, zanim napiszesz kod — to dopracuje implementację.

---

## Klamra końcowa

```text
=======================
Loctree shows what. Session history shows who. Git shows how. The backlog
shows why. Skip the backlog and you re-derive yesterday's decision in
tomorrow's wrong direction. (งಠ_ಠ)ง
=======================

Suchar: Why does the fourth sense feel like cheating? Because the previous
session already did half the work, and you just have to read it. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024–2026_
