# Vibecrafted SKILL.md — spec lokalizacji EN → PL

> Wklej całość jako **system prompt / instrukcje operacyjne** dla wykonawcy (Cowork / Claude / Gemma / Bielik).
> Cel: spolszczyć prozę SKILL.md tak, by plik **dalej działał jako skill**.
> Zasada nadrzędna: tłumaczymy tylko prozę. Reszta zostaje bit-w-bit.
>
> **PRIORYTET #1 — JAKOŚĆ, nie prędkość ani ilość.** Lepiej wolno i dobrze.
> Jeden plik = jeden skupiony przebieg + autoreview. Żadnego batchowania „na hurra".

---

## 0. Reguła krytyczna — frontmatter zostaje w EN

Pola `name` i `description` w YAML frontmatter to **literalne stringi do matchowania**, po których runtime decyduje, czy
załadować skill. **NIE TŁUMACZ ICH.** Zostaw verbatim. (Tłumaczenie `description` może rozregulować triggering.)

Jeśli kiedykolwiek potwierdzisz, że runtime matchuje semantycznie po polsku — dopiero wtedy to się zmienia. Domyślnie:
EN.

---

## 0a. Struktura wyjścia — lustro 1:1 drzewa EN

Tłumaczenia PL trafiają do **osobnego drzewa, które odwzorowuje strukturę EN 1:1.**
Ten sam układ katalogów, te same nazwy plików, te same ścieżki względne.

**Roota (finalne):**

- EN (źródło, read-only): `~/Library/Mobile Documents/com~apple~CloudDocs/AI_notes/SKILLS/skills-original_EN`
- PL (cel, lustro 1:1): `~/Library/Mobile Documents/com~apple~CloudDocs/AI_notes/SKILLS/skills-PL`

```
skills-original_EN/        →  skills-PL/
  vc-decorate/SKILL.md     →    vc-decorate/SKILL.md
  vc-init/SKILL.md         →    vc-init/SKILL.md
  vc-init/references/…      →    vc-init/references/…      (Fala 2)
  …                              …
```

Zasady:

- **Nie nadpisuj** plików EN. Plik PL leży pod tą samą ścieżką względną, ale w rootcie PL.
- Nazwa pliku zostaje **identyczna** (`SKILL.md`, nie `SKILL-PL.md`) — strukturę różnicuje root, nie nazwa.
- **Twórz brakujące katalogi i pliki** pod `skills-PL/` w miarę potrzeby, zachowując hierarchię EN.
- Tłumaczymy **tylko pliki `.md`**. Assety nie-doc (`agents/openai.yaml`, `engines/*.py`, `scripts/*.sh`,
  `*.pyc`, `*.fileloc`) **nie są tłumaczone** — nie kopiuj ich do drzewa PL (chyba że operator chce w pełni uruchamialne
  lustro — wtedy kopiuj 1:1 bez zmian).

> **Uwaga o pliku przykładowym.** W `skills-PL/` leży już `vc-decorate-PL-przykład.md` (płaski, z sufiksem).
> To **tylko referencja stylu i terminologii** — NIE jest to docelowy format nazewnictwa.
> Docelowo `vc-decorate` ląduje jako `skills-PL/vc-decorate/SKILL.md` (pełne lustro, czysta nazwa),
> tłumaczone **świeżo z aktualnego EN** — przykład służy do dopasowania głosu, nie do kopiowania.

> Triggering bezpieczny: drzewo PL jest poza zakresem skanowania runtime'u, a frontmatter i tak
> zostaje w EN (sekcja 0), więc lustro pozostaje funkcjonalne, gdyby kiedyś przełączyć na nie runtime.

---

## 0b. Kolejność fal

1. **Fala 1 — wszystkie `SKILL.md`** (30 plików). Najpierw to, w całości.
2. **Fala 2 (opcjonalna) — pozostałe `.md`** (`FLOW.md`, `README.md`, `references/*.md`,
   `PHASES.md`, `CONTRACT.md`, `TAXONOMY.md`, itd.) — dopiero po akceptacji Fali 1.

Nie mieszaj fal. Domknij i zatwierdź Falę 1, zanim ruszysz drugą.

---

## 1. NIE TŁUMACZ (zostaw verbatim)

- Cały **frontmatter YAML** — klucze i wartości `name`, `description`, oraz wszystkie pozostałe klucze.
- Wszystkie **bloki kodu** (```), **inline `code`**, komendy shell, **ścieżki**, **URL-e\ \*\*, zmienne env, flagi.
- **Nazwy komend / narzędzi**: `vc-init`, cała rodzina `vc-*`, `Loctree` / `loct-*`, `screenscribe`,
  `unicode-puzzles-mcp`, `search_unicode`, `slice` / `impact` / `focus`, itp.
- **Etapy pipeline'u** (w tym `dou`):
  `scaffold → init → workflow → followup → marbles → dou → decorate → hydrate → release`
- **DoU / dou** — nigdy nie tłumacz. „Definition of Undone" zawsze po angielsku.
- **Nazwy bloków Unicode** (Box Drawing, Dingbats, Enclosed Alphanumerics, Braille Patterns…).
- **Stopka brandingowa** (wordmark `𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.` + linia `… LibraxisAI`) — verbatim.
- **Nazwy własne / org**: Vetcoders, LibraxisAI, Loctree.

---

## 2. Zostaw jako loanword (NIE polonizuj na siłę)

`runtime`, `review`, `merge`, `workflow`, `branding`, `spacing`, `hover`, `focus`,
`commit`, `deploy`, `build`, `prompt`, `token`, `landing page`.

Brzmią naturalniej w polskim dev-slangu niż siłowe kalki.

---

## 3. Ustalone tłumaczenia (używaj spójnie w całym zestawie)

| EN                   | PL                                        |
| -------------------- | ----------------------------------------- |
| identity             | tożsamość                                 |
| drift                | **dryf** (w parze z „tożsamość")          |
| blast radius         | zasięg zmiany                             |
| findings             | ustalenia (NIE „findingi")                |
| central store / repo | wspólny katalog (NIE „centralny magazyn") |
| runtime truth        | twardy wymóg runtime'u                    |

Jeśli trafisz na nowy termin, którego nie ma w tabeli — przetłumacz naturalnie, ale **trzymaj się jednej wersji w
obrębie całego zestawu plików**.

---

## 4. Styl

- Naturalna, idiomatyczna polszczyzna. **Minimal-intervention**: jeśli zdanie jest już dobre — zostaw.
- Zero anglicyzmowych kalek tam, gdzie istnieje czyste polskie słowo.
- Trzymaj **rejestr oryginału** (bezpośredni, techniczny). Nie upiększaj, nie dodawaj waty.
- Nie dodawaj i nie usuwaj treści — tłumacz wyłącznie prozę.

---

## 5. Zachowaj strukturę 1:1

- Nagłówki, listy, tabele, odstępy, separatory `---`, kotwice — bez zmian.
- Delimitery frontmatter (`---`) i **kolejność kluczy** — bez zmian.
- Liczba i pozycja bloków kodu — identyczna jak w oryginale.

---

## 6. Output

Zwróć **cały plik** z identyczną strukturą; zmieniona ma być wyłącznie proza. Bez komentarzy, bez ```-fence wokół
całości, bez preambuły — sam plik.

---

## 7. Szybki sanity-check triggeringu (po tłumaczeniu)

Dla każdego pliku porównaj frontmatter EN vs PL — `name` i `description` muszą być **identyczne**:

```bash
# z poziomu roota skills/ — porówna frontmatter EN z jego lustrem PL
diff <(sed -n '/^---$/,/^---$/p' skills-original_EN/vc-init/SKILL.md) \
     <(sed -n '/^---$/,/^---$/p' skills-PL/vc-init/SKILL.md)
```

Jeśli diff nie jest pusty → model ruszył frontmatter → popraw przed akceptacją.

---

## 8. Kontrola jakości (priorytet #1)

Per plik, w tej kolejności:

1. **Przebieg tłumaczenia** — jeden plik, pełne skupienie.
2. **Autoreview** — przeczytaj PL na głos „w głowie": czy brzmi jak pisał Polak-dev, nie jak kalka? Zdania już dobre w
   oryginale po polsku nie mają być przekombinowane.
3. **Spójność terminologiczna** — sprawdź każdy termin z sekcji 3. Jeśli trafił się **nowy** termin, dopisz go do żywego
   glosariusza (niżej) i trzymaj tę samą wersję we wszystkich kolejnych plikach.
4. **Integralność strukturalna** — frontmatter, bloki kodu, ścieżki, liczba sekcji bez zmian (sanity-check z sekcji 7).
5. **Wątpliwości → flaga, nie zgadywanie.** Niejednoznaczny termin albo gra słów, której nie da się oddać 1:1 →
   zatrzymaj się i zapytaj operatora, nie wymyślaj.

**Żywy glosariusz (dopisuj w trakcie):**

```
EN → PL
(nowe terminy z Fali 1 lądują tutaj, żeby Fala 2 i kolejne orgi były spójne)
```

---

## 9. Kicker dla Cowork (gotowy do wklejenia)

> Wklej całego tego speca jako kontekst, a poniższy blok jako zadanie.

```
Tłumaczysz dokumentację skilli Vibecrafted EN → PL wg specu powyżej.
Priorytet bezwzględny: JAKOŚĆ, nie prędkość ani ilość.

Roota:
- EN (źródło, read-only):
  ~/Library/Mobile Documents/com~apple~CloudDocs/AI_notes/SKILLS/skills-original_EN
- PL (cel, lustro 1:1):
  ~/Library/Mobile Documents/com~apple~CloudDocs/AI_notes/SKILLS/skills-PL

Struktura: odtwórz w skills-PL hierarchię z skills-original_EN 1:1 — twórz brakujące
katalogi i pliki. Plik PL ma identyczną ścieżkę względną i nazwę (vc-init/SKILL.md →
skills-PL/vc-init/SKILL.md). NIE nadpisuj EN. Tłumacz tylko .md; nie ruszaj yaml/py/sh.

Referencja stylu: w skills-PL leży vc-decorate-PL-przykład.md — PRZECZYTAJ go, żeby złapać
głos i terminologię, ale to tylko ściąga. NIE kopiuj jego nazwy ani treści: vc-decorate
przetłumacz świeżo z aktualnego EN i zapisz jako skills-PL/vc-decorate/SKILL.md.

Plan:
1. PILOT: przetłumacz NAJPIERW tylko 3 pliki — vc-init/SKILL.md, vc-decorate/SKILL.md,
   vibecraftsmanship/SKILL.md — zapisz do lustra PL, pokaż mi wynik + listę użytych terminów
   i ZATRZYMAJ SIĘ na moją akceptację. Nie ruszaj reszty.
2. Po moim OK: dokończ Falę 1 (wszystkie pozostałe SKILL.md, łącznie 30), plik po pliku,
   z autoreview i sanity-checkiem frontmattera per plik.
3. Prowadź żywy glosariusz nowych terminów i trzymaj go spójnie przez cały zestaw.
4. Fala 2 (reszta .md: FLOW.md, README.md, references/*, itd.) — dopiero gdy ją zlecę osobno.

Po każdym pliku: krótka nota co przetłumaczone + potwierdzenie, że frontmatter nietknięty
(diff pusty). Wątpliwy termin albo nieprzetłumaczalna gra słów → pytaj, nie zgaduj.
```
