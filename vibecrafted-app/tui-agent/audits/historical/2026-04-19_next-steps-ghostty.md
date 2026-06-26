# Operator TUI: 10-Point Natural Next Steps (Ghostty-first — SUPERSEDED 2026-04-19)

> **Status: superseded.** Plan zakładał Ghostty-first surface (`terminal_binary`,
> "new Ghostty window for reports", Ghostty env passthrough). Zastąpiony przez
> `2026-04-19_next-steps-agnostic.md` (terminal-agnostic shape), który codex
> zrealizował 2026-04-29 w commitach `8bc04a9` / `1d55925` / `3a3bfbd`.
> Zachowany jako historical evidence trail per `vc-intents` 2026-04-29 verdict.

Ten plan skupia się wyłącznie na architekturze, refaktoringu i rozwoju narzędzia `operator-tui` (Rust), aby w pełni obsłużyć nowy ekosystem oparty na Ghostty i zoptymalizować doświadczenie operatora.

### 1. Bezpieczna Iniekcja Zmiennych Środowiskowych

W module `launch.rs` (w `LaunchCommand::spawn`) należy dodać jawną propagację zmiennych środowiskowych specyficznych dla VibeCrafted (np. `VC_FRAME_CONFIG_DIR`, `VIBECRAFT_ROOT`). Zapobiegnie to wyciekom i konfliktom z globalnym środowiskiem systemu.

### 2. Rozszerzenie `LaunchCommand` pod Ghostty

Zaktualizowanie struktury `build_launch_command`, aby poprawnie formatowała zagnieżdżone polecenia. Wywołanie Ghostty wymaga przekazania parametrów do vc-frame (`ghostty -e vc-frame attach ...`). Należy upewnić się, że argumenty są poprawnie parsowane i escapowane przez `std::process::Command`.

### 3. Graceful Error Handling przy Spawnowaniu

Aktualnie `suspend_and_run` zwraca ogólny błąd, jeśli proces nie wstanie. Należy przechwycić `stderr` z wywołania Ghostty i wyświetlić go w `status_line` interfejsu (w `app.rs`), aby operator natychmiast wiedział, dlaczego terminal nie wystartował (np. brak binarki w `PATH`).

### 4. Dynamiczna Konfiguracja Terminala w `AppConfig`

Dodanie pola `terminal_binary` do `AppConfig` w `config.rs`. Choć domyślnie używamy Ghostty, odczytywanie ścieżki do terminala z głównego konfigu `vibecrafted` pozwoli na łatwiejsze testowanie i fallback na środowiskach CI/CD (np. headless).

### 5. Async Launch & Nieblokujący Interfejs

Przepisanie mechanizmu `suspend_and_run` tak, aby interfejs Ratatui nie zamarzał całkowicie, jeśli proces startowy powłoki zaliczy "zwiechę". Odejście od blokującego `child.wait()` na rzecz asynchronicznego monitorowania stanu procesu (tokio/std::thread).

### 6. Wzbogacenie `DeepAction` (Akcje Głębokiego Dostępu)

W `app.rs` rozszerzenie `DeepAction`. Zamiast polegać tylko na systemowym `$PAGER` dla akcji `OpenReport` czy `OpenTranscript`, możemy dodać opcję "Open in new Ghostty window", co otworzy logi w osobnym, niezależnym od vc-frame, czystym oknie terminala.

### 7. Weryfikacja Kondycji Sesji (Healthcheck)

Po wywołaniu vc-frame przez Ghostty, `operator-tui` mogłoby sprawdzić (np. po gnieździe vc-frame lub przez szybki poll), czy sesja faktycznie żyje. Umożliwi to automatyczne oznaczenie Run'a jako `Failed`, jeśli vc-frame natychmiastowo zginie po starcie.

### 8. Optymalizacja Kontekstu (Paging i Historia)

Przebudowa funkcji `pager_command`. Aktualny skrypt basha z `if/elif` jest podatny na błędy parsowania przy nietypowych znakach w ścieżkach. Należy to zastąpić bezpiecznym, natywnym wywołaniem procesu podglądarki (`less` lub `bat`) prosto z Rusta.

### 9. Testy Jednostkowe Komend Startowych

Napisanie dedykowanych testów w `tests/` lub w samym `launch.rs`, które zweryfikują ciągi znaków generowane przez `build_launch_command`. Musimy mieć 100% pewności (Test Gate), że kombinacja `LaunchRuntime::Terminal` + Ghostty + vc-frame renderuje perfekcyjnego stringa.

### 10. Udoskonalenie Widoku Błędów (TUI Polish)

Jeśli Ghostty rzuci paniką, powrót do `operator-tui` po `LeaveAlternateScreen` potrafi zgubić logi błędu. Stworzenie dedykowanego modala/pop-upa w Ratatui (`ui.rs`), który przed ponownym wejściem w pętlę zdarzeń wyświetli dokładny powód awarii subprocesu.
