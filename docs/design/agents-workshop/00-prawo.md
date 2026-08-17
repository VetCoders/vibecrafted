---
status: draft
kind: design-doc
layout_id: Layout-0
title: Prawo siatki i dwóch drzwi
owner: grok
authored_by: grok <agents@vetcoders.io>
session_id: 01a00bfd-5efc-7bf0-883f-a5d096f5235d
date: 2026-08-17
grid: 180x30
source_cheat: 182x40-live / 180x30-cells
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
grid: 180x30
```

Szukaj `session_id: 01a00bfd-5efc-7bf0-883f-a5d096f5235d` albo `authored_by: grok`.

## Siatka

Komórka TUI to nie piksel. 180×130 „żeby wyszło 4:3” to wieża ze 130 wierszy znaków.
Właściwa kratka makiety: **180×30**.

|           | żywa ściąga | pomyłka (piksele) | makieta |
| --------- | ----------- | ----------------- | ------- |
| szerokość | ~182        | 180               | **180** |
| wysokość  | ~40         | 130 (4:3 w px)    | **30**  |

```
wiersz   1     compact-bar
wiersze  2–29  ciało   (rail 26 + canvas 154)
wiersz  30     status-bar
```

Karta Nowy agent ma znowu 6 wierszy — jak na Twoim pierwszym rysunku.

## Korekty

Grok nie powinien był rysować 130 wierszy. Miał poprawić: „to piksele, nie komórki”.

Poza tym z recenzji użytkownika zostaje:

1. Karta nie przecina słów w tle.
2. Ścieżka w całości.
3. Na pasku NOW nie ma `[New dispatch]`.
4. W celu tab nazywa się `voc`, nie `Tab #6`.
5. Chrome jak żywy (SESSIONS/LOCK), karta po polsku.

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
