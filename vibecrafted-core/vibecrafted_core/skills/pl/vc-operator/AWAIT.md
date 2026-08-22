# vc-operator — AWAIT: Orkiestracja sterowana powiadomieniami

> Stosunek agenta operatora do czasu. Dispatch to fire-and-await,
> nie fire-and-forget i nie fire-and-poll.

Czytaj razem z [`SKILL.md`](SKILL.md), [`GUIDE.md`](GUIDE.md), [`DISPATCH.md`](DISPATCH.md).

---

## Doktryna

Po dispatchu uzbrój `vibecrafted await <agent> --run-id <id>` natychmiast,
po stronie supervisora. JSON control-plane, pliki raportów, transkrypty, karty
terminala i zaplanowane wybudzenia są wyłącznie diagnostyczne, nie są sygnałem
wybudzenia. Hedge'owanie await ad-hoc pollerami/watcherami to naruszenie
Class 3; napraw `control_plane.await_run`, nie normalizuj hedge'u.

Liveness jest zawsze 3-sygnałowy przed deklaracją done: await verdict,
stan terminalny run meta i martwy worker pid; jeśli raport jest obiecany,
potwierdź jego obecność. Dwa zgodne sygnały wystarczą do działania, trzy do
deklaracji done; rozjazd = traktuj jako live i uzbrój await ponownie. Znany
skew: rc=0-on-live oraz meta `active`/`stalled` po realnym zakończeniu.

Zobacz `docs/runtime/AGENT_OPS.md` dla kanonu awarii Class 1/2/3. CLI await jest
podstawowym kanałem wybudzenia supervisora; notify taska i heartbeat są
diagnostycznym fallbackiem pętli czatu operatora, nie zamiennikiem uzbrojenia
await.

Dla trybu operatora przekłada się to na:

- **Sygnał podstawowy**: foreground/supervisor-side
  `vibecrafted await <agent> --run-id <id>`, albo komenda framework loop, która
  deleguje do tego await.
- **Sygnał diagnostyczny**: payload `<task-notification>`, ścieżka raportu,
  JSON control-plane, transcript, opcjonalna karta-viewer albo zaplanowany heartbeat.
  One wyjaśniają stan; nie zastępują kanonicznego await.
- **Antywzorzec**: krótkointerwałowy polling. Ponowne sprawdzanie statusu
  zadania co 60 sekund spala prompt cache i sygnalizuje operatorowi, że nie
  ufasz własnej infrastrukturze.

`vibecrafted loop await-run` to kanoniczny lokalny most runtime'owy dla
interaktywnego łańcuchowania await:

```bash
vibecrafted loop await-run --run-id <run-id> --agent <agent> \
  --then-cmd "vibecrafted workflow <agent> --file <next-plan.md>"
```

`--then-cmd` celowo wykonuje się przez `bash -lc` po udanym await. Używaj go
wyłącznie do zatwierdzonych przez operatora komend kontynuacji z aktywnego
planu. Nie używaj go do push, deploy, publikacji, zakupu, usunięcia ani innych
widocznych na zewnątrz / destrukcyjnych działań, chyba że plan jawnie
autoryzuje ten krok.

---

## Cykl życia await jednego dispatchu

```text
1. Odpal:  vibecrafted implement claude --file 01-textforge-editor-core.md
          → run_id = impl-181153-86836
          → tracker zadania w tle = b1h5dkw7s
          → odłączony worker headless; receipt podaje ścieżki stanu i transkryptu

2. Potwierdź start (~30s po odpaleniu):
          → sprawdź, że tracker zadania żyje
          → potwierdź stan control-plane i pid workera
          → arm: vibecrafted await claude --run-id impl-181153-86836
          → napisz do operatora „Fala B-1 odpalona, canonical await armed"

3. Zaplanuj zapasowy heartbeat:
          → ScheduleWakeup delaySeconds=1800 (30 min)
          → reason: „Wave B-1 diagnostic heartbeat for impl-181153-86836"

4. Bezczynność:
          → odpowiadaj na czat operatora, jeśli pinguje
          → trzymaj treść promptu dla Fali B-2 w gotowości, na wypadek gdybyśmy musieli szybko odpalić
          → nie polluj, nie tailuj logów, nie czytaj /tmp/.../tasks/*.output

5. Await wraca:
          → vibecrafted await <agent> wychodzi z prawdą settlement/report
          → potwierdź martwy worker pid i terminalny stan run meta; jeśli raport był
            obiecany, potwierdź obecność raportu
          → przeczytaj plik raportu workera (NIE plik /tmp output —
            zobacz „Co czyta agent operatora")
          → zweryfikuj, że commit wylądował na oczekiwanej gałęzi
          → zweryfikuj, że bramki w raporcie są zielone
          → zweryfikuj kryteria akceptacji jedno po drugim

6. Zdecyduj o kolejnym kroku:
          → zielono → odpal następny prompt w fali (albo czekaj na ukończenie rodzeństwa)
          → failed → wywołaj dispatch odzyskiwania (zobacz Doktrynę odzyskiwania niżej)
          → stall (notify nigdy nie przyszedł; odpala heartbeat) → zbadaj
```

---

## Konfiguracja diagnostycznego heartbeat

Zapasowy heartbeat jest tylko diagnostyczny. Ustawia się go per długo działający
dispatch, żeby supervisor mógł sprawdzić, dlaczego kanoniczny await jeszcze nie
wrócił.

| Kontekst fali                     | Opóźnienie heartbeat | Uzasadnienie                                                |
| --------------------------------- | -------------------- | ----------------------------------------------------------- |
| Fala A (fundament, ~15–25 min)    | 1800s (30 min)       | Fundament jest krytyczny; sprawdź raz, jeśli notify zasnął. |
| Krok Fali B (~10–20 min każdy)    | 1500s (25 min)       | Ciasny łańcuch; odzyskuj szybko, jeśli notify wypadnie.     |
| Fala C równolegle (~15–25 min)    | 1800s (30 min)       | Trzy równoległe; jeden heartbeat pokrywa wszystkie.         |
| Fala D finalna (~20–30 min każda) | 2400s (40 min)       | Najcięższe dispatche; daj margines.                         |

Pole reason heartbeat powinno zawsze zawierać run_id i nie może sugerować, że
jest sygnałem wybudzenia:

```text
ScheduleWakeup delaySeconds=1800
  reason: "Wave B-1 diagnostic heartbeat for impl-181153-86836 — inspect if canonical await has not returned"
```

Heartbeat jest zmarnowany (no-op), jeśli notify przyszedł pierwszy. To
zamierzony koszt. Polling co 60s spala 30 trafień cache, by zrobić to, co
jeden notify + jeden heartbeat robią za darmo.

---

## Co czyta agent operatora po notify

Trzy źródła, w tej kolejności:

1. **Raport workera** w `~/.vibecrafted/artifacts/<...>/reports/<prompt-id>_<ts>_<agent>.md`.
   Źródło autorytatywne. Jeden odczyt, pełna treść.
2. **Commit workera** przez `git log -1 <result-branch>` — potwierdź
   SHA, autora, message, zmienione pliki.
3. **Sidecar `meta.json` workera** w tej samej ścieżce co raport
   (z rozszerzeniem `.meta.json`) — potwierdź `status`, `gate`, `exit_code`,
   `duration_s`, `commit`.

**Nie czytaj** surowego `/tmp/<runtime>/<...>/tasks/<task-id>.output`,
chyba że badasz stall. Ten plik to żywy transkrypt JSONL i przepełni
twoje okno kontekstu, jeśli będziesz go tailować bezmyślnie.

---

## Doktryna odzyskiwania

Gdy dispatch zatnie się lub padnie:

### Najpierw diagnoza

Trzy modalności awarii, trzy diagnostyki:

| Modalność               | Sygnał                                                      | Czytaj                                                                        |
| ----------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Awaria podłoża**      | raport ma `status: failed` z powodem `substrate-failure`    | pełny raport, potem `git status` na gałęzi workera                            |
| **Scope overflow**      | częściowy commit + `scope-overflow.md` w raporcie           | sekcję `scope-overflow.md`, by zobaczyć, co wylądowało / co nie               |
| **Stall implementacji** | bramki failed, commit jest na gałęzi, ale czerwony          | wyjście bramki w raporcie, potem `git diff <baseline>..<branch>`              |
| **Utrata notify**       | odpala heartbeat, żaden `<task-notification>` nie przyszedł | plik wyjścia zadania przez frameworkową komendę `read-output`, NIE surowe cat |
| **Worker zawiesił się** | brak commita, brak raportu po 2× oczekiwanym czasie         | ostatnie 100 linii pliku wyjścia zadania                                      |

### Wybierz kształt odzyskiwania

| Awaria              | Odzyskiwanie                                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Podłoże             | najpierw fix po stronie operatora na trunku → ponowny dispatch oryginalnego promptu bez zmian                            |
| Scope overflow      | napisz _węższą_ treść promptu, dispatchuj jako nowy prompt_id z `recovers: <original-id>` we frontmatterze               |
| Stall implementacji | skupiony agent integracyjny: ten sam scope, ostrzejsze podpowiedzi o złym cięciu, którego należy unikać; nowy prompt_id  |
| Utrata notify       | ręczne potwierdzenie ukończenia przez raport + git, potem kontynuuj; zbadaj pipeline notify poza falą                    |
| Worker zawiesił się | zakończ zadanie w tle, napisz close-out `agent-hang.md`, odzyskiwanie przez świeżego agenta (ten sam tier, inna rotacja) |

### Odzyskiwanie to pełnoprawny dispatch

Dispatch odzyskiwania:

- ma własny `prompt_id` (np. `textforge-editor-core-recovery-20260516`)
- ma własną ścieżkę raportu + meta.json
- ma własny commit
- odnosi się do oryginału przez `recovers: <original-prompt-id>` we frontmatterze
- **nie jest** „odpaleniem jeszcze raz" — to inny brief z inną akceptacją
- liczy się jako jeden z promptów fali w trackerze (status `recovered`)

Dwie awarie na tym samym prompcie → **zatrzymaj falę**. Napisz handoff
w punkcie stopu z prośbą do operatora o triage. Trzy awarie to stall floty —
wystaw uczciwy komunikat „potrzebuję wskazówek po stronie operatora" i pauzuj.

---

## Czat operatora podczas awaitowania

Gdy operator pinguje cię podczas await:

- Odpowiedz na jego pytanie.
- Jeśli pyta „status", odpowiedz skompresowanym kształtem wave-trackera ze
  [`SKILL.md`](SKILL.md), sekcja Format wyjścia.
- Jeśli pyta „co dalej", pokaż przypisanie promptów następnej fali, ale
  nie odpalaj jej bez jawnego zielonego światła.
- Nie interpretuj „czy nadal jesteśmy na kursie" jako autoryzacji do posunięcia
  się naprzód. Interpretuj to jako „daj mi snapshot trackera".

---

## Domyślnie headless, zawsze obserwowalny

Każdy zwykły dispatch floty domyślnie uruchamia odłączonego workera headless.
vc-frame jest powierzchnią obserwacji stanu runu i trwałych transkryptów; jego
karty nie hostują workera, a utrata pane'a nie może zatrzymać runu.

Prawdziwy PTY jest zarezerwowany dla interaktywnej User Session, bare resume
albo jawnego `--runtime terminal` dla ścieżki providera, która dowodowo go
wymaga. Obecność TTY lub żywej sesji repo nigdy nie włącza terminala domyślnie.

W razie wątpliwości:

1. Uruchom normalnie, bez override'u runtime.
2. Natychmiast uzbrój supervisor-side
   `vibecrafted await <agent> --run-id <id>`.
3. Obserwuj receipt, stan control-plane, transkrypt i raport; opcjonalnie
   wyświetl te powierzchnie w vc-frame.

Zabronione: uzależnianie liveness workera od pane'a, karty, attach session lub
procesu viewera.

---

## Antywzorce

- Polling co 60s podczas czekania → marnowanie cache, sygnalizowanie braku zaufania.
- Tailowanie `/tmp/.../tasks/<id>.output`, by „sprawdzić postęp" → ryzyko
  przepełnienia kontekstu, a plik jest w JSONL, nie do czytania przez człowieka.
- Ustawianie heartbeat krótszego niż oczekiwany czas trwania fali → odpala się
  przed przyjściem notify; marnuje siatkę bezpieczeństwa.
- Kontynuowanie odpalania następnej fali, gdy notify poprzedniej fali nie przyszedł
  → gwarantowane naruszenie zależności.
- Traktowanie heartbeat jako sygnału podstawowego → niweczy infrastrukturę notify.
- Restartowanie zaciętego dispatchu przez ponowne odpalenie tej samej treści promptu →
  ten sam tryb awarii, ten sam wynik; użyj dispatchu odzyskiwania.

---

## Wezwanie do działania

Po odpaleniu każdego promptu zaplanuj heartbeat przez `ScheduleWakeup`
natychmiast — nie czekaj, aż operator ci przypomni. Potem zamknij swoją
odpowiedź linią run_id + tracker i zachowaj ciszę aż do odpalenia notify
albo heartbeat.

---

## Klamra końcowa

```text
=======================
Awaitowanie to najbardziej kunsztowny ruch agenta operatora. Z zewnątrz
wygląda jak nic i od środka czuje się jak nic, ale to ta dyscyplina, która
zamienia flotę w łańcuch zamiast w stampedę.
(งಠ_ಠ)ง
=======================

Suchar: Dlaczego pętla pollingu nigdy nie skończyła swojej książki? Bo co 60
sekund zaczynała od rozdziału pierwszego. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024–2026_
