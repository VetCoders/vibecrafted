---
name: loctree
version: 2.0.0
description: >
  Holographic structural perception of the codebase. Loctree gives you 
  structural sight before you touch anything — architecture, dependencies, 
  blast radius, dead code. No edit without orientation. No delete without 
  impact. No create without search.
  The craftsman studies the grain before cutting.
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# Loctree — Twoje zmysły w bazie kodu

> Zanim mistrz stolarski zetnie, studiuje słoje.
> Zanim chirurg otworzy, czyta obrazowanie.
> Zanim edytujesz kod, czytasz strukturę.
> Loctree to sposób, w jaki widzisz.

## Checkpoint strukturalny

W pracy specyficznej dla repo ten skill jest strukturalną połową procedury
`vc-init`. `Loctree:loctree` musi wyprodukować lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map) przed implementacją, przeglądem, release'em, porządkowaniem lub usunięciem.

Jeśli brakuje świeżych dowodów z `vc-init`, najpierw wykonaj przebieg init i traktuj
pracę z repo specyficzną dla workflow jako zablokowaną, dopóki nie ma aktualnej prawdy repo.

Używaj repo-view, focus, slice, impact, find i follow w odpowiednim zakresie. Jeśli zadanie
nie jest specyficzne dla repo, powiedz to wprost, zamiast udawać, że mapa istnieje.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Rzemiosło

Modele językowe nie potrafią zgadnąć topologii architektury. I ty też nie powinieneś
udawać, że potrafisz. Twoja ekspertyza tkwi w interpretacji i chirurgicznym działaniu.
Twoje zmysły to twoje narzędzia.

Loctree zamienia rozległą bazę kodu w mapę, o której potrafisz rozumować.
Pokazuje ci rzeczy, które mają znaczenie, zanim zdecydujesz się na cięcie:

- **Gdzie jest ciężar** — które pliki to węzły nośne, które to liście
- **Co od czego zależy** — niewidzialne nici między modułami
- **Co jest martwe** — eksporty, których nikt nie importuje, kod, którego nikt nie woła
- **Co jest splątane** — cykliczne importy czekające, by pęknąć w runtime
- **Co jest zduplikowane** — symbole-twins (duplikaty), które mylą konsumentów

Rzemieślnik, który tnie bez studiowania materiału, produkuje odpady.
Agent, który edytuje bez kontekstu strukturalnego, produkuje szum.
Loctree to różnica między tymi dwoma.

## Twój diagnostyczny koń roboczy (referencja narzędzi)

Każde narzędzie to inna rozdzielczość. Używaj ich w kolejności od najszerszego:

1. Spojrzenie z dystansu i uzyskanie gruntownego przeglądu strukturalnego:

- mcp_loctree-mcp_repo-view
  Pobierz przegląd repozytorium: liczbę plików, LOC, języki, podsumowanie
  zdrowia, top węzły nośne. UŻYJ TEGO JAKO PIERWSZEGO na początku każdej sesji AI,
  aby zrozumieć bazę kodu.

2. Przegląd struktury katalogów bez szumu — użyj, gdy potrzebujesz
   przeglądu architektury projektu:

- `mcp_loctree-mcp_tree`
  Pobierz strukturę katalogów z licznikami LOC (lines of code). Pomaga
  zrozumieć układ projektu i znaleźć duże pliki/katalogi.

3. Pierwsze spojrzenie w przegląd modułu:

- `mcp_loctree-mcp_focus`
  Skup się na konkretnym katalogu: wylistuj pliki, ich LOC, eksporty i
  zależności w obrębie tego katalogu. Świetne do zrozumienia
  modułu lub podsystemu.

4. Kompletny holograficzny graf zależności dla pliku:

- `mcp_loctree-mcp_slice`
  Pobierz kontekst pliku: plik + wszystkie jego importy + wszystkie pliki, które
  od niego zależą. UŻYJ TEGO PRZED modyfikacją dowolnego pliku. Jedno wywołanie = pełne
  zrozumienie roli pliku.

5. Mikroskop — znajdź symbole, parametry, funkcje, typy itp.
   w bazie kodu (pierwszy wybór przed grepem):

- `mcp_loctree-mcp_find`
  Znajdź symbole, prześledź importy lub eksploruj funkcje. Tryby: 'symbols'
  (domyślny) — wyszukiwanie symboli/parametrów z regexem. 'who-imports' — jakie pliki
  importują ten plik (reverse deps). 'where-symbol' — gdzie ten symbol
  jest zdefiniowany. 'tagmap' — ujednolicone wyszukiwanie po słowach kluczowych (pliki + crowd + dead).
  'crowd' — funkcjonalne klastrowanie wokół słowa kluczowego.

6. Sygnały strukturalne — martwy kod, cykle, twins, hotspoty, trace,
   komendy, zdarzenia, pipeline'y:

- `mcp_loctree-mcp_follow`
  Podążaj za sygnałami strukturalnymi na poziomie pola. Zakresy: 'dead' — nieużywane eksporty
  z najbliższymi konsumentami. 'cycles' — cykliczne importy z najsłabszym ogniwem.
  'twins' — zduplikowane eksporty. 'hotspots' — pliki o dużej liczbie importerów. 'trace' —
  prześledź handler Tauri/IPC end-to-end (wymaga parametru handler).
  'commands' — pokrycie handlerów Tauri FE<->BE. 'events' — analiza przepływu
  emisji/nasłuchu zdarzeń. 'pipelines' — podsumowanie pipeline'u (events + commands + risks).
  'all' — dead + cycles + twins + hotspots.

7. Przydatne narzędzie do refactoru:

- `mcp_loctree-mcp_impact`
  Co się zepsuje, jeśli zmienisz lub usuniesz ten plik? Pokazuje bezpośrednich i tranzytywnych
  konsumentów. UŻYJ TEGO PRZED usunięciem lub dużym refactorem.

Wszystkie narzędzia przyjmują parametr `project` (domyślnie: bieżący katalog).
Pierwsze użycie automatycznie skanuje, jeśli nie istnieje snapshot. Kolejne wywołania używają cache'u.

## Dyscyplina rzemieślnika

To nie są ograniczenia. To nawyki kogoś, kto szanuje
materiał, z którym pracuje:

1. **Wiedz, zanim zetniesz** — nie łataj kodu, dopóki nie uruchomisz
   `repo-view` → `focus` → `slice` na obszarze, którego masz zamiar dotknąć.

2. **Zmierz zasięg zmiany przed usuwaniem** — uruchom `impact(file)` przed
   usunięciem lub scaleniem modułów. Zrozum, co zależy od tego, co
   masz zamiar zniszczyć.

3. **Szukaj przed tworzeniem** — uruchom `find(name)` przed dodaniem nowych
   funkcji, typów lub komponentów. Jeśli to już istnieje, użyj ponownie.
   Duplikacja to najczęstsza forma entropii generowanej przez agenta.

4. **Ogranicz zakres zmian** — preferuj modyfikacje ograniczone do funkcji nad
   globalnymi nadpisaniami. Czyste cięcie we właściwym miejscu bije szeroki zamach.

5. **Szanuj pliki o dużym wpływie** — pliki z wieloma importerami to ściany nośne.
   Dodaj kroki weryfikacji przed commitowaniem zmian w nich.

6. **Grep jest do detalu, nie do odkrywania** — nigdy nie używaj grepa/rg jako
   głównej warstwy mapowania. To jak próba zrozumienia miasta przez
   czytanie pojedynczych tabliczek z nazwami ulic. Używaj loctree do mapy, grepa do
   adresu.

## Standardowy workflow

### 1. Zmapuj teren

Uruchom `repo-view(project)` raz na task.
Odnotuj: top węzły nośne, martwe eksporty, cykle, twins, wskaźniki zdrowia.
To twoje pierwsze spojrzenie na pacjenta.

### 2. Zawęź zakres

Uruchom `focus(directory)` dla każdego docelowego modułu (maks. 1-3 katalogi).
Uchwyć zewnętrznych konsumentów i zależności.
To twoja sala operacyjna — wiedz, co jest w środku.

### 3. Prześwietl, zanim zetniesz

Dla każdego pliku, który planujesz zmodyfikować, uruchom `slice(file, consumers=true)`.
Zapisz: bezpośrednie zależności, bezpośredni konsumenci, ryzyko tranzytywne.
Żaden chirurg nie otwiera bez obrazowania.

### 4. Oceń ryzyko

Dla każdego kandydata na plik o dużym wpływie uruchom `impact(file)`.
Jeśli ryzyko jest wysokie, izoluj zmiany — nowy wariant, klasa o ograniczonym zakresie, warstwa adaptera.
Celem jest precyzja, nie brawura.

### 5. Sprawdź istniejące części

Uruchom `find(name)` dla nowych typów/funkcji/komponentów.
Obsługuje regex: `find("SymbolA|SymbolB")`.
Używaj ponownie istniejących wzorców, gdy są dostępne. Buduj na tym, co istnieje.

### 6. Podążaj za sygnałami

Uruchom `follow(scope)`, aby zagłębić się w problemy oznaczone przez repo-view.
Zakresy: `dead`, `cycles`, `twins`, `hotspots` lub `all`.
To są objawy. Podążaj za nimi do przyczyny źródłowej.

### 7. Detal na poziomie linii

Używaj `grep`, `rg`, `cat` dopiero po krokach 1-6.
Teraz wiesz, na co patrzysz. Teraz detal ma znaczenie.

### 8. Waliduj

Uruchom ponownie celowane testy/lint/typecheck.
Dla UI: dodaj wizualne sprawdzenie poprawności w różnych motywach/trybach.
Cięcie wykonane. Zweryfikuj, że pacjent jest stabilny.

---

## Doktryna operacyjna (model wykonania agenta)

_Ta sekcja jest do internalizacji przez agenta. Język rzemiosła powyżej
opisuje ten sam proces dla zrozumienia przez człowieka._

### Model roli

Nie jesteś architektem, który „ulepsza" kod na podstawie preferencji estetycznych.
Twoje zmysły (narzędzia loctree) dostarczają obiektywną prawdę strukturalną. Ty dostarczasz
ekspercką interpretację i precyzyjną naprawę.

**Narzędzia dostarczają dowodów. Ty dostarczasz działania.**

Narzędzia to świadkowie oskarżenia — zeznają o stanie
kodu. Ty interpretujesz zeznania i działasz na ich podstawie. Nie wymyślasz zeznań.
Nie ignorujesz zeznań. Działasz na podstawie tego, co pokazują ci narzędzia.

### Działanie oparte na dowodach

Każde działanie musi prowadzić do wyjścia narzędzia:

- „Usuwam ten eksport, bo `follow(dead)` pokazuje zero konsumentów"
- „Nie dotykam tego pliku, bo `impact` pokazuje 24 tranzytywnych zależnych"
- „Używam ponownie `formatDate`, bo `find('formatDate')` znalazł go w `utils/dates.ts`"

Jeśli nie potrafisz przytoczyć wyjścia narzędzia, by uzasadnić edycję, zgadujesz.
Zgadywanie to główne źródło entropii generowanej przez agenta.

### Kontrakt wyjścia

Przed refactorem zaraportuj:

1. **Podsumowanie repo** (3-5 punktów z `repo-view`)
2. **Zakres** (skupione katalogi i dlaczego)
3. **Pliki krytyczne** (z `slice`)
4. **Mapa ryzyka** (z `impact`)
5. **Plan** (uporządkowane fazy + punkty rollbacku)

Po implementacji zaraportuj:

1. **Zmienione pliki**
2. **Dlaczego** (prześledzone do dowodów z narzędzi)
3. **Walidacja**
4. **Ryzyko rezydualne**

### Antywzorce

- Uruchamianie szerokiego `grep` jako pierwszego i edytowanie na podstawie częściowych dopasowań
- Usuwanie/zmiana nazw plików bez `impact`
- Dodawanie nowych symboli bez `find`
- Globalne nadpisania, by naprawić lokalne problemy
- Pomijanie `slice`, bo „to mała zmiana"
- Przytaczanie wiedzy treningowej zamiast wyjścia narzędzia jako uzasadnienia

## Fallback

Jeśli loctree MCP jest niedostępne: przejdź na CLI `loct --for-ai`, jeśli jest obecne,
a następnie `rg --files` + `rg -n` + ręczne śledzenie zależności.
Ogłoś degradację. Nie udawaj, że masz pełne zmysły, gdy ich nie masz.

---

_„Poznaj materiał. Studiuj słoje. Potem tnij — raz, czysto, dobrze."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
