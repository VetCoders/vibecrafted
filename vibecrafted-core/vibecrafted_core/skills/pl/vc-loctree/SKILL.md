---
name: loctree
description: Strukturalna i literalna percepcja repozytorium przed edycją, usunięciem, refaktorem lub pracą w nieznanym kodzie. Loctree mapuje zakres, zależności, konsumentów, dokładne wystąpienia i blast radius; AICX dostarcza historię intencji.
metadata:
  version: "2.1.0"
  loctree_value: "primary repo map for structural/literal repository work"
  aicx_value: "intent, session, and decision-context retrieval"
  dogfooding: "required for repo-impacting work"
---

# Loctree — obrazowanie przed operacją

Loctree daje wzrok strukturalny: kształt repo, indeksowane literalne wystąpienia,
sąsiedztwo zależności, miejsca definicji, mosty runtime i blast radius. AICX daje
historię intencji. Żadne z nich nie zastępuje źródła, manifestów, testów ani
rzeczywistej próby runtime.

## Checkpoint strukturalny

W pracy repozytoryjnej ten skill jest strukturalną połową procedury `vc-init`.
`Loctree:loctree` musi utworzyć lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map) przed implementacją, review, releasem, porządkowaniem lub usunięciem.

Jeżeli nie ma świeżego dowodu `vc-init`, najpierw wykonaj init i traktuj dalszą
pracę repozytoryjną jako zablokowaną. Jeżeli zadanie nie dotyczy repo, powiedz to
wprost zamiast udawać, że mapa istnieje.

## Dobierz narzędzie do pytania

| Potrzeba                                | Powierzchnia                            |
| --------------------------------------- | --------------------------------------- |
| Szeroka orientacja zadania              | `loct context --task "..."`             |
| Szybki obraz repo                       | `loct repo-view`                        |
| Powiązania katalogu                     | `loct focus path/`                      |
| Zależności i konsumenci pliku           | `loct slice path/file`                  |
| Blast radius rename/delete              | `loct impact path/file`                 |
| Dokładne wystąpienia identyfikatora     | `loct find Identifier`                  |
| Definicje i re-exporty                  | `loct find Identifier --where-symbol`   |
| Szerokie kandydaty symboli/parametrów   | `loct find --discover Terms`            |
| Stronicowane/zwięzłe dowody literalne   | `loct occurrences Identifier --compact` |
| Ograniczone źródło definicji            | `loct body Symbol`                      |
| Dead/cycles/twins/hotspots/runtime flow | `loct follow <scope>`                   |

Używaj równoważnych wywołań `loctree-mcp`, gdy są dostępne. Parametr `project`
przekazuj tylko narzędziom, których schema rzeczywiście go przyjmuje.

Zwykłe CLI `loct find` jest dokładnym wyszukiwaniem literalnym z granicami
identyfikatora; `--literal` to jawny alias. `--discover` włącza szerokie kandydaty
AST/parametr/regex/fuzzy. Kandydat discovery nie jest dowodem literalnym.

## Kontrakt pracy

1. Potwierdź root repo, branch/HEAD, dirty state, zakres i świeżość snapshotu.
2. Użyj `context` dla szerokiego zadania albo od razu właściwego narzędzia.
3. Przed edycją zobacz `slice`; przed delete/rename zobacz `impact`.
4. Przed stworzeniem symbolu uruchom literal find i where-symbol.
5. Przeczytaj dokładne źródło i wykonaj najbliższą realną bramę produktu.
6. Przed destrukcją osobno sprawdź manifesty, generated/dynamic wiring,
   reflection, entrypointy, testy oraz installed/live runtime.

## Udowodnione mocne strony

- Granice identyfikatora oddzielają `LOCT_OPEN_BROWSER` od
  `LOCT_OPEN_BROWSER_ENV` oraz `hotspot` od `hotspots`.
- Literalne wyszukiwanie może widzieć śledzone, indeksowane pliki ukryte przez
  domyślne reguły ignore, jednocześnie deklarując swój universe.
- W żywych testach AICX i Vibecrafted zwykły find zgodził się z niezależnymi
  licznikami dokładnych słów (38/38 i 22/22), a `where-symbol` zawęził wynik do
  dwóch istotnych miejsc definicji/re-exportu.
- `slice`, `impact` i `follow trace` łączą znalezioną linię z rolą systemową.
  Na Screenscribe impact pokazał 5 bezpośrednich i 12 tranzytywnych
  reprezentowanych konsumentów, a trace połączył handler frontend/backend.

To przykłady kontraktu, nie uniwersalne obietnice wydajności ani pokrycia.

## Granice dowodu

- Zero konsumentów/dead to kandydat, nigdy zgoda na usunięcie.
- Impact przechodzi tylko po krawędziach reprezentowanych w snapshot graph.
- Brak literalnego wyniku dotyczy tylko zadeklarowanego indexed universe.
- Puste karty runtime/structural wymagają audytu pokrycia.
- Ciepły cache nie mówi nic o zimnym rescanie po zmianie drzewa.
- Czytaj emitted/total/truncation; nie zakładaj, że `--discover --limit`
  ogranicza globalny output, dopóki zainstalowana wersja tego nie dowiedzie.
- Pamięć AICX to dowód historyczny, nie aktualna prawda kodu.

Bezpośredni search tekstowy i czytanie plików pozostają poprawnym uzupełnieniem
dla prozy, lokalnego detalu, powierzchni ignored/generated i niezależnej kontroli.

Jeżeli Loctree jest błędne, stare, hałaśliwe, nieobsługiwane albo wymusza fallback,
dopisz reprodukcję do `~/.vibecrafted/loctree/loctree-fail.md`.

Raportuj: snapshot/HEAD, zakres i pokrycie, rozstrzygający dowód, niezależną
weryfikację, pozostałą niepewność i następny bezpieczny ruch.
