# Ledger — tracker, journal, baton (księgowość jednego zapisującego)

Dyspozytor jest JEDYNYM ZAPISUJĄCYM do ledgera linii. Workerzy piszą kod
i raporty; tylko dyspozytor flipuje stany i dopisuje do journala. To właśnie
sprawia, że evidence jest godne zaufania, gdy nadchodzą skille audytowe.

## Tracker (`plans/<line>/tracker.md`)

Nagłówek: repo, gałąź baseline + SHA, wskaźniki atlas/journal, roster agentów.

Tabela: `| Cut | Wave | Agent | Brief | State | Evidence |`

Stany:

- `[ ]` planned — brief istnieje, nie dispatchowany
- `[~]` in flight — zdispatchowany; evidence = run_id + notatki dispatchu (highlighty
  BATON, hardening EXTRA)
- `[?]` delivered but operator-verify pending — używane dla pozycji acceptance
  manualnych/runtime'owych, których headless worker nie może wykonać
- `[!]` failed / stalled / substrate failure — evidence = ślad diagnostyczny
- `[x]` settled — flipowany WYŁĄCZNIE przez dyspozytora, tylko z evidence

Evidence dla `[x]` ZAWSZE zawiera: SHA(-y) commita + wyniki bramek
zaraportowane przez workera + kto zweryfikował + które pozycje acceptance
zostają `[?]` dla operatora. Raport to claim; commit (przeszedł hooki) + diff,
który matchuje brief + sekcja bramek z raportu razem stanowią proof. Dyspozytor
NIE uruchamia ponownie lintów/testów — zduplikowane bramki to koszt bez
informacji; ostateczna prawda należy do vc-followup / vc-audit / vc-dou.

Planowanie fal też mieszka w trackerze: wylistuj twarde nakładania plików
wprost („C1→C2: messages.rs; C5b↔C7: settings/") — wszystko inne jest
kandydatem do dispatchu RÓWNOLEGŁEGO, a maksymalizacja tej równoległości
to obowiązek, nie opcja.

## Journal (`JOURNAL.md`, append-only)

Otwórz go w pierwszej minucie linii — to czarna skrzynka, jeśli kontekst
dyspozytora padnie w połowie linii. NIGDY nie przepisuj ani nie zmieniaj
kolejności; dopisuj datowane sekcje. Każdy wpis odnotowuje jedno przejście lub
zdarzenie:

- dispatch (run_id, rozmiar promptu, wynik sprawdzenia placeholderów)
- delivery + flip (SHA, esencja diffa, bramki z raportu, co zostaje `[?]`)
- stall + recovery (pełne evidence: elapsed kontra CPU, zamrożony plik sesji,
  sprawdzenie orphana, co dziedziczy nowy run)
- korekty w locie (decyzja operatora wiernie co do ducha + brief korygujący,
  który zrodziła)
- korekty doktryny od operatora (te należą też do pamięci trwałej — journal jest
  per-linia, pamięć jest na zawsze)
- findingi po linii → wpisy backtrackera z kotwicami w prawdzie kodu

## Baton

Baton nie jest plikiem — to warstwa BATON kolejnego promptu plus kolumna
evidence w trackerze. Komponując go, odpowiedz na trzy pytania następnego
workera: co wylądowało przede mną (SHA + dotknięte pliki), co może się ruszyć,
gdy pracuję (operator testuje na żywo, równolegli workerzy i ich ogrodzone
obszary) oraz co przychodzi po mnie (żebym ogrodził swój scope).

## Backtracker (`99_BACKTRACKER.md`)

Findingi po linii ze smoke'a operatora / audytu: jedna sekcja na finding,
słowa operatora wiernie co do ducha + kotwice kodu z narzędzi strukturalnych
(file: line + jednolinijkowe dlaczego). Findingi stają się cięciami backlogowymi
(wiersze `C<n>` w trackerze, stan `[ ]`) i są dispatchowane na guzik operatora
— możliwie wszystkie w jednym runie z commitami per-pozycja i kolejnością
wykonania w EXTRA (małe regresje najpierw, duże feature'y na końcu).

## Reguła pracy własnej

Własne edycje repo dyspozytora (hotfixy przydzielone przez operatora, księgowość
linii wewnątrz repo) idą za marbles: jedna jednostka = jeden commit, message
ukształtowany przez hooka, PRAWDZIWY session id w trailerach (z harnessu, nigdy
uuidgen), commitowane natychmiast — gromadzenie niezacommitowanej pracy na Living
Tree to tryb awaryjny, nie bezpieczny wybór. Version bumpy i pushe zostają na
guzikach operatora.
