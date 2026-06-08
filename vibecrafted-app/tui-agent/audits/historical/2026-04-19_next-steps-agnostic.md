# Operator TUI: 10-Point Natural Next Steps (Terminal-Agnostic — COMPLETED 2026-04-30, hardened P.M.)

> **Status: 10/10 done + readiness contract hardened.** Ten terminal-agnostic
> plan został zrealizowany przez codex 2026-04-29 w commitach `8bc04a9`
> (queue scope + archive controls), `1d55925` (launch env + failure feedback),
> `3a3bfbd` (prompt artifact + clipboard ux), następnie domknięty przez stable
> zellij session naming (`8930d05`) i named-session readiness probe 2026-04-30.
> 2026-04-30 P.M. dokleciony przez claude: probe `--config-dir` parity, probe
> error preservation, hard timeout z child kill, fake-zellij e2e coverage
> (P1-01 / P2-01 / P2-02 / P2-03 z `2026-04-30_vc-review.md`). Plus rmcp-mux
> MCP daemon visibility w Monitor tabie + `MuxHealth` deep action. Zachowany
> jako historical evidence trail per `vc-intents` 2026-04-29 i 2026-04-30.

Ten plan traktuje `operator-tui` jako niezależne, samodzielne narzędzie, które żyje wewnątrz dowolnego obecnie używanego emulatora terminala (Ghostty, Alacritty, iTerm2, WezTerm). Skupia się na tym, aby TUI było solidnym pomostem do orkiestracji (Zellij + agenci) bez wymuszania konkretnego okna.

### 1. In-Place Multiplexer Hand-off (Exec)

Skoro działamy wewnątrz obecnego terminala, wywołanie `LaunchRuntime::Terminal` powinno sprowadzać się do eleganckiego przejęcia sesji przez `zellij attach` lub `zellij --session`. Należy upewnić się, że `operator-tui` używa mechanizmów pokrewnych do `exec` (zastąpienie procesu lub bezkolizyjne zawieszenie TUI na czas działania Zellij), aby nie tworzyć niepotrzebnej matrioszki procesów.

### 2. Bezkolizyjne Zarządzanie TTY (Suspend/Resume)

Dopracowanie mechanizmu `suspend_and_run` (w `launch.rs`). Przełączanie między trybem Raw (Ratatui) a subprocesem interaktywnym (Zellij) bywa kruche. Należy zagwarantować, że sygnały systemowe, przywracanie bufora ekranu i stan kursora działają perfekcyjnie, niezależnie od tego, jak ezoteryczny emulator terminala pod spodem wyświetla obraz.

### 3. Hermetyzacja Środowiska (Env Passthrough)

Bezpieczne przekazanie `ZELLIJ_CONFIG_DIR`, `VIBECRAFT_ROOT` oraz stanu sesji operatora do subprocesu. TUI musi działać jak zawór: odcina szum z powłoki użytkownika, ale dziedziczy kluczowe ustawienia terminala (np. wsparcie dla kolorów, TERM, wymiary ekranu) i wstrzykuje tylko to, co niezbędne dla agentów.

### 4. Dynamiczne Wykrywanie Toolingu (Zoxide/Starship)

Zamiast hardcodować zachowania powłoki, `operator-tui` przed odpaleniem sesji w Zellij powinno móc weryfikować w `PATH` dostępność narzędzi pomocniczych (Zoxide, Starship, Atuin). Na tej podstawie launcher może dynamicznie wstrzykiwać odpowiednie pliki `.zshrc` lub profile startowe do wewnątrz Zellij.

### 5. Asynchroniczny Watcher Stanu (Control-Plane)

Przebudowa mechanizmu odświeżania (obecnie w `app.rs` oparte na `Instant::now()`). Aby interfejs wydawał się w 100% responsywny (Vibe), TUI powinno asynchronicznie obserwować zmiany w katalogu `.ai-context/local/state/` (np. przez `notify`) i natychmiast aktualizować widok sesji bez czekania na "tick" pętli głównej.

### 6. Natywny Pager dla Raportów (Deep Controls)

W `launch.rs` funkcja `pager_command` obecnie mocno polega na systemowym poleceniu wstrzykniętym w `sh -lc`. Zamiast wyrywać użytkownika do powłoki za pomocą `less`, o wiele bardziej "pro" byłoby zintegrowanie w Ratatui prostego widoku (TextView), który potrafi wyrenderować log/transkrypt agenta w nowym panelu wewnątrz samego TUI.

### 7. Wzbogacenie Telemetrii Błędów TUI (Error Modal)

Jeśli wywołanie komendy launchera się nie powiedzie, aplikacja nie powinna po prostu wracać do czystego widoku lub "wypluwać" błędu po wyjściu. Wprowadzenie dedykowanego pop-upa (modal) w Ratatui, który wyłapie błąd z subprocesu i pozwoli operatorowi spokojnie go przeanalizować bez niszczenia układu TUI.

### 8. Integracja ze Schowkiem (Clipboard)

Wprowadzenie cross-platformowej obsługi schowka (np. przez crate `arboard`). Niezależnie od terminala, w którym działa TUI, operator naciskając `y` na danym wpisie powinien móc błyskawicznie skopiować UUID sesji, ścieżkę do najnowszego raportu czy gotową komendę `vibecrafted resume`.

### 9. Nawigacja i Filtrowanie Sesji

Gdy historia operacji (runs) zacznie pęcznieć, przewijanie jej strzałkami stanie się niewydajne. Dodanie skrótu `/` w UI otwierającego pasek szybkiego wyszukiwania (fuzzy search po nazwie agenta, typie lub statusie), co dramatycznie przyspieszy pracę w terminalu.

### 10. Testy Akceptacyjne Logiki Launchera

Rozszerzenie zestawu testów w `operator-tui/tests/`. Główny nacisk musi pójść na hermetyczność `build_launch_command`: czy TUI pod każdym względem produkuje deterministyczny, terminalo-agnostyczny łańcuch wywołania dla Zellij, niezależnie od tego, czy odpalamy to na Linuksie pod tmuxem, czy na macOS pod Ghostty.
