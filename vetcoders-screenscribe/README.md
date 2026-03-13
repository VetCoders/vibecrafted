# VetCoders ScreenScribe

Skill do pracy z `ScreenScribe`: analizą nagranych screencastów oraz samym
repo narzędzia.

To nie jest ogólny skill od “video AI”. To jest workflow dla bardzo konkretnego
pipeline’u:

- wyciągnięcie audio z nagrania
- transkrypcja komentarza
- wykrywanie bugów / change requestów / problemów UX
- zrzuty ekranu w istotnych momentach
- raporty JSON / Markdown / HTML Pro

## Kiedy używać

Używaj `vetcoders-screenscribe`, gdy użytkownik chce:

- przeanalizować nagrane demo aplikacji
- zamienić komentarz głosowy z review w uporządkowane findings
- przepuścić przez pipeline jeden lub wiele plików `.mov` / `.mp4`
- wygenerować screenshoty, transcript lub raport HTML Pro
- debugować albo rozwijać repo `ScreenScribe`

To jest dobry skill wszędzie tam, gdzie “nagranie ekranu + mówiony feedback”
ma się zamienić w inżynierski output, a nie tylko w surową transkrypcję.

## Co potrafi ScreenScribe

Główne tryby narzędzia:

- `review`
- `analyze`
- `transcribe`
- `config`
- `version`

Najczęstsze mapowanie:

- pełny actionable review z narracją:
    - użyj `review`
- transcript only:
    - użyj `transcribe`
- tryb interaktywny / serverowy:
    - użyj `analyze`

## Canonical run path

Skill zakłada pracę z repo `ScreenScribe` w sposób reprodukowalny, zwykle przez:

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
uv run python -m screenscribe --help
```

Przykłady:

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
uv run python -m screenscribe review /absolute/path/to/video.mov
```

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
uv run python -m screenscribe transcribe /absolute/path/to/video.mov -o /absolute/path/to/transcript.txt
```

## Jak myśleć o tym skillu

Najważniejsza zasada:

- nie traktuj ScreenScribe jak “jakiegoś tam modelu do wideo”
- traktuj go jak realny pipeline z etapami, artefaktami i failure modes

Zanim ruszysz:

- ustal input video set
- ustal, czy celem jest `review`, `analyze`, czy `transcribe`
- sprawdź, czy ważniejsza jest szybkość, głębokość, czy interaktywność
- upewnij się, że provider config i FFmpeg są dostępne

## Pliki

- `SKILL.md` — canonical workflow i komendy
- `evals/evals.json` — eval harness dla skilla

## Pozycja w arsenale VetCoders

`vetcoders-screenscribe` jest skillem produktowo-praktycznym:

- bierze nagrania, które zwykle kończą jako chaos w feedback loopie
- zamienia je w strukturalne findings
- pozwala debugować i rozwijać sam pipeline ScreenScribe bez zgadywania jego CLI

Jeśli `vetcoders-partner` jest trybem pracy dla trudnych sesji, to
`vetcoders-screenscribe` jest wyspecjalizowanym narzędziem do zamiany
review video w konkret inżynierski.
