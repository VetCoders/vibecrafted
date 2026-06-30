---
name: vc-screenscribe
version: 1.2.1
description: >
  Screenscribe workflow skill for analyzing screencast recordings and for
  working inside the Screenscribe repo itself. Use this whenever the user
  mentions Screenscribe, screencast review, app review videos, bug demo
  recordings, HTML Pro reports, transcript-first artifact extraction,
  extracting actionable findings from narrated videos, batch video analysis,
  or wants to debug/build/improve the Screenscribe project or the default
  https://github.com/vetcoders/Screenscribe repository. Prefer this skill even
  if the user does not explicitly ask for "Screenscribe" but clearly wants a
  spoken screen recording turned into structured engineering findings.
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# Vibecrafted. Screenscribe

Użyj tego skilla do dwóch powiązanych zadań:

1. Uruchom screenscribe na realnych nagraniach i zamień je w użyteczne wyjścia.
2. Pracuj nad bazą kodu screenscribe bez zgadywania jego CLI, bramek czy modelu raportu.

## Checkpoint orientacji

Dla pracy z repo screenscribe uruchom lub skonsumuj procedurę `vc-init` przed
edycją, planowaniem albo oceną release'u. `Loctree:loctree` to domyślny skill
percepcji strukturalnej dla tego przebiegu i musi wyprodukować lub odświeżyć
Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map).

Jeśli brakuje świeżych dowodów z `vc-init`, wykonaj najpierw przebieg init i traktuj
pracę z repo screenscribe jako zablokowaną, dopóki nie ma aktualnej prawdy repo.

Dla czystych przebiegów analizy wideo zadeklaruj wyjątek „bez repo" i używaj
zainstalowanego CLI screenscribe bezpośrednio.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Czym jest screenscribe

Screenscribe to pipeline screencastów, nie mgliste „coś do wideo z AI".

Jego największa wartość to produkcja artefaktów:

- wyciąga audio z wideo
- transkrybuje komentarz z timestampami
- wykrywa bugi, change requesty i problemy UI
- przechwytuje screenshoty w istotnych momentach
- generuje wyjścia: transcript, JSON, Markdown oraz opcjonalnie HTML Pro

Główne komendy udostępniane przez projekt:

- `review`
- `analyze`
- `transcribe`
- `preprocess`
- `config`
- `version`

## Kiedy używać

Użyj tego skilla, gdy użytkownik chce:

- przeanalizować nagranie ekranu z review aplikacji
- zamienić mówiony komentarz o bugach w ustrukturyzowane findingi
- przetworzyć jeden lub wiele plików `.mov` / `.mp4`
- wygenerować raporty HTML Pro, screenshoty, transcripty lub bundle'e transcript-first
- uruchomić screenscribe w trybie dry-run, estimate, resume lub batch
- wyciągnąć najpierw artefakty i pozwolić agentowi/modelowi przeanalizować je później
- zdebugować wyjście, prompty, providerów lub generowanie raportów screenscribe
- zmodyfikować repo screenscribe, utrzymując uczciwość jego bramek jakości

## Domyślny mindset

Nie traktuj screenscribe jak endpointu modelu.
Traktuj go jak konkretny pipeline z realnymi etapami, realnymi artefaktami i realnymi punktami awarii.

Domyślnie wybieraj najkrótszą działającą ścieżkę.
Jeśli użytkownik daje ci wideo i chce findingów z review, pierwszym ruchem zwykle jest po prostu:

```bash
screenscribe review /absolute/path/to/video.mov
```

Nie zaczynaj od krążenia wokół `uv run`, wnętrzności repo czy `--help`, chyba że:

- użytkownik jawnie chce pracy z repo/debugiem
- brakuje komendy `screenscribe`
- pierwszy realny przebieg zawiódł i diagnozujesz przyczynę

Zawsze ustal:

- jaki jest zestaw wejściowych plików wideo
- czy celem jest `review`, `preprocess`, `analyze` czy `transcribe`
- czy użytkownik chce szybkości, głębi, interaktywności czy wyciągnięcia artefaktów
- czy dostępna jest konfiguracja providera oraz FFmpeg

## Tabela szybkich decyzji

Użyj tego mapowania:

- Użytkownik chce pełnego, użytecznego review z jednego lub wielu wideo z narracją:
  - użyj `screenscribe review ...`
- Użytkownik chce bundle'a artefaktów transcript-first do dalszej pracy modelu/agenta:
  - użyj `screenscribe preprocess ...`
- Użytkownik chce tylko transcriptu:
  - użyj `screenscribe transcribe ...`
- Użytkownik chce interaktywnego/odwróconego serwera flow:
  - użyj `screenscribe analyze ...` lub repo `make analyze`
- Użytkownik chce zmienić samo narzędzie:
  - pracuj w repo i uruchom bramki jakości repo

## Najpierw szybka ścieżka

Dla zwykłej, użytkowej analizy wideo preferuj zainstalowane CLI bezpośrednio:

```bash
screenscribe review /absolute/path/to/video.mov
```

Batch:

```bash
screenscribe review /path/video1.mov /path/video2.mov -o /absolute/output/dir
```

Bundle transcript-first:

```bash
screenscribe preprocess /absolute/path/to/video.mov
```

Tylko transcript:

```bash
screenscribe transcribe /absolute/path/to/video.mov -o /absolute/path/to/transcript.txt
```

To jest ścieżka domyślna, dopóki nie zawiedzie.

## Lane transcript-first

`preprocess` to lane (tor) artifact-first.
Używaj go, gdy użytkownik chce deterministycznych części pipeline'u bez angażowania się w analizę semantyczną/VLM.

Oczekiwany bundle:

```text
{video}_preprocess/
  transcript.txt
  transcript.timestamped.txt
  transcript.segments.json
  transcript.vtt
  preprocess.json
  audio.mp3
```

To najlepszy kształt handoffu, gdy:

- późniejszy model/agent ma wybrać timestampy lub POI (points of interest)
- użytkownik chce najpierw prawdy transcriptu i timingu
- jakość analizy jest podejrzana, a paczka artefaktów liczy się bardziej

## Ścieżka repo / debug

Kanoniczne repo upstream:

- [Vetcoders/Screenscribe](https://github.com/vetcoders/Screenscribe)

Gdy potrzebna jest praca z repo, preferuj bieżący checkout screenscribe, jeśli użytkownik
już go otworzył. Nie zakładaj stałej lokalnej ścieżki. Jeśli żaden checkout nie jest
otwarty, odwołaj się do domyślnego repo powyżej i wspomnij o lokalnej ścieżce dopiero, gdy
faktycznie jest znana.

Wejdź do repo tylko wtedy, gdy:

- brakuje CLI lub jest zepsute
- potrzebny jest debug providera/configu/runtime'u
- użytkownik chce pracy nad samym screenscribe

Wtedy preferuj:

```bash
cd /path/to/Screenscribe
uv run python -m screenscribe review /absolute/path/to/video.mov
```

### Review

Pojedyncze wideo:

```bash
cd /path/to/Screenscribe
uv run python -m screenscribe review /absolute/path/to/video.mov
```

Batch:

```bash
cd /path/to/Screenscribe
uv run python -m screenscribe review /path/video1.mov /path/video2.mov -o /absolute/output/dir
```

Przydatne flagi:

- `--keywords-only`
- `--estimate`
- `--dry-run`
- `--no-vision`
- `--resume`
- `--lang en`
- `-o /path/output`

### Preprocess

```bash
cd /path/to/Screenscribe
uv run python -m screenscribe preprocess /absolute/path/to/video.mov
```

Przydatne flagi:

- `--no-audio`
- `--force`
- `--lang en`
- `-o /path/output`

### Transcribe

```bash
cd /path/to/Screenscribe
uv run python -m screenscribe transcribe /absolute/path/to/video.mov -o /absolute/path/to/transcript.txt
```

### Interaktywny serwer Analyze

Preferowane:

```bash
cd /path/to/Screenscribe
make analyze VIDEO=/absolute/path/to/video.mov PORT=8766
```

### Bezpieczne komendy triażu

Używaj ich tylko, jeśli normalna ścieżka `screenscribe review ...` lub `screenscribe preprocess ...` zawiodła:

```bash
screenscribe review --help
screenscribe preprocess --help
screenscribe version
ffmpeg -version
test -f ~/.config/screenscribe/config.env && echo CONFIG_OK || echo CONFIG_MISSING
```

## Oczekiwania wobec wyjścia

Dla normalnego przebiegu review oczekuj katalogu wyjściowego w stylu:

```text
{video}_review/
  {video}_transcript.txt
  {video}_report.json
  {video}_report.md
  {video}_report.html
  screenshots/
```

Dla preprocess oczekuj bundle'a transcript-first opisanego powyżej.

Raportując wyniki z powrotem użytkownikowi, zawsze podaj:

- wejściowe wideo
- dokładnie uruchomioną komendę
- ścieżkę katalogu wyjściowego
- czy przebieg był pełny, preprocess-only, dry-run, keywords-only czy no-vision
- istotne blokery lub ostrzeżenia

## Konfiguracja i zależności

Ważne zależności runtime'u:

- Python 3.11+
- `uv`
- FFmpeg
- skonfigurowane poświadczenia / endpointy providera

Główny plik konfiguracyjny:

- `~/.config/screenscribe/config.env`

Jeśli przebieg zawiedzie, sprawdź najpierw te rzeczy:

1. FFmpeg zainstalowany i widoczny w PATH
2. skonfigurowane klucze API
3. zgodność endpointu/modelu
4. uprawnienia ścieżki wyjściowej
5. czy użytkownik chciał `review`, a faktycznie potrzebował `preprocess`, `transcribe` lub `analyze`

Nie wymyślaj wartości konfiguracji ani nie udawaj sukcesu API.

## Workflow repo

Edytując lub debugując sam screenscribe, używaj natywnych bramek repo:

```bash
cd /path/to/Screenscribe
make lint
make typecheck
make test
```

Przydatne dodatki:

```bash
make security
make test-integration
make test-all
make format
```

Jeśli testy integracyjne potrzebują zewnętrznego dostępu do API, a kluczy brakuje, powiedz to jasno i uruchom testy jednostkowe plus statyczne bramki.

## Kolejność dochodzenia przy awariach

Gdy zachowanie screenscribe wygląda na błędne, debuguj w tej kolejności:

1. kształt komendy
2. poprawność pliku wejściowego
3. FFmpeg / wyciąganie audio
4. wyjście transkrypcji
5. wybór trybu detekcji lub preprocess
6. wyciąganie screenshotów
7. analiza semantyczna / zunifikowana
8. generowanie raportu
9. renderowanie/otwieranie HTML Pro

Nie skacz od razu do obwiniania modelu przed sprawdzeniem granic etapów pipeline'u.

## Format wyjścia dla tasków screenscribe

Użyj tej struktury odpowiedzi, gdy jest pomocna:

```markdown
Current state: what the input is and what Screenscribe path we are using.
Proposal: which command/workflow best fits and why.
Migration plan: concrete steps or fixes if repo work is involved.
Quick win: the smallest useful run or fix right now.
```

Jeśli task jest prosty, skompresuj to do krótkiego akapitu.

## Przykłady

**Przykład 1**
Wejście: „Przeleć mi ten review.mov i wypluj JSON + markdown z bugami."
Działanie: uruchom `screenscribe review /absolute/path/to/review.mov`, zwróć katalog wyjściowy i kluczowe findingi.

**Przykład 2**
Wejście: „Mam video, ale chcę tylko transcript, timestampy i pack dla agenta."
Działanie: uruchom `screenscribe preprocess /absolute/path/to/video.mov`, zwróć katalog bundle'a i listę artefaktów.

**Przykład 3**
Wejście: „W repo https://github.com/vetcoders/Screenscribe coś popsuliśmy w HTML Pro."
Działanie: potraktuj to jako pracę z repo, użyj natywnych komend repo i bramek jakości, a nie zwykłego przebiegu review.

## Antywzorce

Nie:

- traktuj screenscribe jak generyczny summarizer
- zaczynaj od hydrauliki repo, gdy wystarczyłby zwykły `screenscribe review <file>` lub `screenscribe preprocess <file>`
- sonduj `--help` przed pierwszym realnym przebiegiem przy zwykłej prośbie o analizę wideo
- uruchamiaj losowych komend repo, gdy `make` już definiuje ścieżkę jakości
- pomijaj raportowania katalogu wyjściowego
- ignoruj tego, czy użytkownik chce `review` vs `preprocess` vs `transcribe` vs `analyze`
- twierdź, że przebieg jest poprawny, jeśli brakuje FFmpeg lub konfiguracji providera
- zakładaj, że raport HTML istnieje, chyba że przebieg faktycznie go wyprodukował
- ufaj warstwie AI bardziej niż artefaktom transcriptu/screenshotów, gdy są ze sobą sprzeczne

## Definicja ukończenia

Task screenscribe jest gotowy, gdy:

- wybrano właściwą komendę
- przebieg lub zmiana kodu faktycznie się zakończyły
- artefakty wyjściowe są nazwane i zlokalizowane
- blokery są konkretne, jeśli przebieg nie mógł się zakończyć
- zmiany w repo, jeśli były, przechodzą najbliższe realne bramki jakości
