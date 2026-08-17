---
status: draft
kind: design-doc
layout_id: Layout-0
title: Prawo siatki i dwóch drzwi
owner: grok
authored_by: grok <agents@vetcoders.io>
session_id: 01a00bfd-5efc-7bf0-883f-a5d096f5235d
date: 2026-08-17
grid: 182x130
source_cheat: 182x40
scope: agents-workshop
product: vibecrafted
next: layout-factory
---

# Agents workshop — prawo, korekty, Layout-1..n

Te pliki są po to, żeby **człowiek** zobaczył warsztat zanim ktokolwiek ruszy plugin.
Nie są kalką bałaganu z żywej ściągi. Są spakowanym celem na siatce ze ściągi.

## Frontmatter — jak mnie znaleźć

Każdy Layout ma:

```
owner: grok
authored_by: grok <agents@vetcoders.io>
session_id: 01a00bfd-5efc-7bf0-883f-a5d096f5235d
date: 2026-08-17
grid: 182x130
```

Szukaj `session_id: 01a00bfd-5efc-7bf0-883f-a5d096f5235d` albo `authored_by: grok`.

## Siatka

|             | żywa ściąga      | makieta do recenzji                               |
| ----------- | ---------------- | ------------------------------------------------- |
| szerokość   | ~182             | **182**                                           |
| wysokość    | ~40              | **130**                                           |
| po co wyżej | okno na laptopie | widać rozmowę i kartę naraz, bez 20 pustych dziur |

```
wiersz    1     compact-bar
wiersze   2–129 ciało   (rail 26 + canvas 156)
wiersz    130   status-bar
```

Żywe okno zostaje ~40. 130 to widok recenzji (jakbyś zescrollował TUI).

## Korekty po przejściu oczami użytkownika (delta 40→130)

Poprzednie 182×40 były nie do użycia jako makieta:

1. Środek był pusty. Wyglądało jak zepsuty TUI, nie warsztat.
2. Karta „Nowy agent” przecinała słowa w tle (`THIS ta│`). Nie da się tego czytać.
3. Ścieżka ucinała się na `vibecr`. Nie sprawdzisz, gdzie się rodzi.
4. Na pasku NOW wisiał już `[New dispatch]`. Za wcześnie — myli drzwi.
5. `Tab #6` w celu. W celu ten tab nazywa się `voc`.
6. Trzy kopie tej samej pustej ramki na trzy stany fokusu. Człowiek nie porównuje, tylko się gubi.
7. Angielskie notatki projektowe w środku „produktu”. Tu chrome zostaje jak żywy (SESSIONS/LOCK), karta mówi po polsku.

Wektor z naszych klatek:

float+PANE+strzałki → talia hosta → brakowało `[New agent]` → rytuał 3 osi, nie KDL → headless to inne drzwi.

## Dwa launchery

| drzwi   | przycisk                                | narodziny                                      |
| ------- | --------------------------------------- | ---------------------------------------------- |
| teraz   | `[New agent]`                           | interaktywny TTY na **tym** tabie              |
| później | `[New dispatch]`                        | worker, najlepiej headless, tylko przez serwer |
| zawsze  | z wewnątrz żywego interaktywnego agenta | dispatch jak dziś                              |
| zawsze  | Quick cmd                               | osobny widok, nie atrapa paska                 |

## Nawigacja karty

| klawisz        | skutek                          |
| -------------- | ------------------------------- |
| `↑` `↓`        | wiersz agent → rytuał → ścieżka |
| `←` `→`        | chip (w ścieżce: kursor)        |
| `spacja`       | zaznacz chip                    |
| `enter`        | launch                          |
| `esc` / Anuluj | nic się nie rodzi               |

## Layout factory (za tydzień)

CUT-1..n były briefami do cięcia kodu.
**Layout-1..n** są rysunkami do cięcia powierzchni.

Nie generujemy jeszcze KDL. Te pliki są ziarnem fabryki.

## Pliki

| id       | plik          | co widzisz               |
| -------- | ------------- | ------------------------ |
| Layout-0 | ten dokument  | prawo                    |
| Layout-1 | `Layout-1.md` | warsztat, jedna twarz    |
| Layout-2 | `Layout-2.md` | Nowy agent (karta)       |
| Layout-3 | `Layout-3.md` | po Enter                 |
| Layout-4 | `Layout-4.md` | voc jako drzwi tego taba |
| Layout-5 | `Layout-5.md` | Nowy dispatch, później   |

HTML studio: `preview.html` (lewe taby Layout-1..n, jeden canvas). Analog `/scaffold/editor`.
