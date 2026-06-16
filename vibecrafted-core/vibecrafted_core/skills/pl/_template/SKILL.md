---
name: "{{SKILL_NAME}}"
version: 0.1.0
description: "Template for a new Vibecrafted skill; replace before shipping."
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v2 -->

> **Warstwa operatorskiego CLI / slash-commandów:** wywołanie `/vc-<workflow>` lub
> `vibecrafted <workflow> <agent>` oznacza dispatch przez launcher Vibecrafted.
>
> **Warstwa ładowania skilla / czatu:** załadowanie tego `SKILL.md` w Codeksie, Claude,
> Gemini lub innym lokalnym agencie nie oznacza self-dispatchu. Przeczytaj i zastosuj
> skill w bieżącym wątku, chyba że operator wprost prosi o runtime'owy launch, dispatch
> lub natywną delegację.
>
> Natywne in-process subagenty są dopuszczone wyłącznie przez bounded doktrynę
> `vc-delegate`.

<!-- /fleet-imperative -->

# {{SKILL_NAME}} — TODO one-line tagline

> Scaffolded {{CREATED_DATE}} via `tools/vc-skill-new.sh`.
> Replace every TODO marker before opening a PR.

---

## Wejście operatora

### Reguła Living Tree / Worktree

Ten workflow działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie twórz
worktree gita, nie przełączaj się na niego ani nie przenoś do niego wykonania, chyba że
operator wprost poprosi o worktree w tym prompcie. Czytaj pliki ponownie przed edycją,
dostosowuj się do równoległych zmian i zgłoś awarię podłoża (substrate failure), jeśli
bieżące drzewo jest zbyt zatrute, by bezpiecznie kontynuować.

Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

Standardowy launcher:

```bash
vibecrafted {{SKILL_NAME_NO_PREFIX}} claude --prompt 'TODO concrete operator example'
vc-{{SKILL_NAME_NO_PREFIX}} codex --prompt 'TODO shell-shortcut example'
```

---

## Cel

TODO — Zastąp tę sekcję. Określ **jeden** rezultat, który ten skill wytwarza.
Skille istnieją po to, by skompresować powtarzalny ruch operatora w nazwaną, powtarzalną
powierzchnię. Jeśli ta sekcja czyta się jak lista możliwości — zawęź ją.

Poprzeczka z `CONTRIBUTING-SKILLS.md`: jedna ostra oś, nie scyzoryk szwajcarski.

---

## Kiedy używać

Warunki wyzwalające (zastąp wszystkie punkty):

- TODO — podstawowa sytuacja operatora, w której ten skill to właściwy wybór
- TODO — wtórna sytuacja, jeśli istnieje
- TODO — jawne rozgraniczenie z istniejącymi skillami vc-\*

**Kiedy NIE używać:**

- TODO — sąsiedni skill obsługujący podobną, lecz odmienną sytuację
- TODO — sytuacja, którą należy eskalować zamiast tego do `vc-implement` lub `vc-marbles`

---

## Pozycja w pipelinie

Gdzie to się wpasowuje w łańcuch workflow VetCoders?

- Upstream: TODO (np. następuje po `vc-init`, działa po `vc-research`)
- Downstream: TODO (np. emituje handoff dla `vc-release` lub `vc-dou`)

---

## Kryteria akceptacji

Przebieg skilla jest **gotowy**, gdy:

- [ ] TODO — konkretne, falsyfikowalne sprawdzenie #1
- [ ] TODO — konkretne, falsyfikowalne sprawdzenie #2
- [ ] TODO — deliverable widoczny dla operatora (plik, raport, commit)

Jeśli któregokolwiek punktu akceptacji nie da się odhaczyć dowodem, skill nie został
ukończony — powiedz to wprost w raporcie końcowym.

---

## Antywzorce

- TODO — typowy tryb porażki #1 (np. uruchomienie tego skilla przed `vc-init`)
- TODO — typowy tryb porażki #2 (np. rozszerzanie scope poza jedną ostrą oś)
- Pominięcie ponownego odczytu Living Tree przed edycją, gdy aktywni są współbieżni agenci
- Ogłaszanie „gotowe" bez odhaczenia powyższych kryteriów akceptacji

---

## Przykłady

Zobacz [`examples/example-prompt.md`](examples/example-prompt.md) — minimalna para
fraza-trigger + oczekiwane zachowanie.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
