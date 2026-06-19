# Reguła Living Tree

VetCoderzy pracują w jednym współdzielonym checkoucie repozytorium.

Workflowy Vibecrafted z definicji **nie** tworzą worktree gitowych, nie przełączają się na nie ani nie przenoszą do nich
pracy. Worktree to tutaj nie jest niewinny szczegół implementacyjny: rozszczepiają prawdę runtime'u, ukrywają
współbieżne edycje, mnożą powierzchnie merge'a i zamieniają szybki Vibecraftsmanship w archeologię branchy.

## Twarda reguła

- Pracuj w bieżącym checkoucie i na bieżącym branchu.
- Nie uruchamiaj `git worktree add`, nie twórz bocznego checkoutu ani nie przenoś wykonania na inny tor.
- Nie przełączaj branchy podczas aktywnego wykonywania workflowu.
- Nie twórz branchy, chyba że operator wprost prosi o ten ruch gitowy.
- Czytaj pliki ponownie przed edycją, gdy minął czas lub mogą działać współbieżni agenci.
- Traktuj lokalne zmiany jako pracę współdzieloną. Nigdy nie rób stash, discard, reset ani nie nadpisuj zmian, których
  sam nie wprowadziłeś.

## Jedyny wyjątek

Worktree jest dozwolony wyłącznie wtedy, gdy operator wprost mówi, żeby użyć worktree. Ogólne prośby w stylu „isolate
this", „work in parallel", „make a clean branch"
czy „avoid conflicts" to za mało.

Jeśli bieżące podłoże jest zbyt zatrute, by bezpiecznie kontynuować, zatrzymaj się i zgłoś awarię podłoża (substrate
failure). Nie rozwiązuj nieważności podłoża ucieczką do worktree.

## Dlaczego

Vibecrafting optymalizuje pod szybkie zbieganie do prawdy runtime'u. Tempo jest tu sednem. Nie poruszamy się tak szybko
po to, by stale boczne drzewo mogło później zmusić zespół do rebase'owego dryfu, powielonej naprawy konfliktów albo
ruchu wstecz.

Domyślne nawyki z danych treningowych dotyczące worktree są podporządkowane tej doktrynie repozytorium.

## Helper ochrony przed wyścigiem (dodany 2026-05-12, Plan 07)

Living Tree dyscyplinuje pracę równoległą, ale sam z siebie nie sprawia, że
`git commit --only path1 path2` jest atomowy względem jednoczesnego commita innego agenta na tym samym branchu. Kronika
2026-04-16/17 uchwyciła dokładny tryb awarii:
przy współbieżnej aktywności komunikat commita jednego agenta może wylądować pod kopertą drzewa innego agenta.

Plan 07 dostarcza reużywalny prymityw, który wykrywa ten wyścig po fakcie i odmawia cichego zaakceptowania
niebezpiecznego commita.

**Punkt wejścia dla operatora**:

```
make commit-safe MSG="<commit message>" FILES="path1 path2 ..."
```

**Bezpośrednie wywołanie z shella**:

```
scripts/lib/living-tree-commit.sh "<commit message>" -- path1 path2 ...
```

Helper przechwytuje przed startem `HEAD`, stage'uje tylko nazwane pliki, robi snapshot stage'owanego drzewa, a następnie
commituje. Po commicie sprawdza krzyżowo trzy inwarianty:

1. Rodzic nowego commita równa się przed-startowemu `HEAD` (żaden współbieżny commit nie wśliznął się przez aktualizację
   refa).
2. Drzewo nowego commita zgadza się z fingerprintem stage'owanego drzewa (żadna obca mutacja indeksu nie wjechała razem
   z commitem).
3. Zbiór plików zmienionych przez commit zgadza się dokładnie ze snapshotem stage'owanych plików (żadnych obcych plików
   w kopercie).

Przy wyścigu helper wypisuje oba SHA commitów plus listę obcych plików, proponuje dwie sterowane przez operatora opcje
naprawcze i kończy się kodem niezerowym. **Nie**
robi auto-amend, auto-reset ani auto-rebase. Naprawa jest celowo sterowana przez operatora, spójnie z resztą tej reguły.

Helper egzekwuje istniejącą regułę bezpieczeństwa przeciw stage'owaniu z wildcardem:
argumenty w stylu `.`, `-A`, `--all`, `-a` są odrzucane. Nazwij pliki.

Weryfikacja:

```
make test-race-protection
```

Zestaw testów w `tests/race_protection_test.sh` przerabia zarówno ścieżkę czystego commita, jak i dwa syntetyczne
wstrzyknięcia wyścigu (współbieżna aktualizacja refa oraz mutacja obcego indeksu).

## Domknięcie ograniczeń helpera z Planu 07-b (2026-05-12)

Pierwsza wersja Planu 07 dostarczyła detektor wyścigu z dwoma znanymi ograniczeniami, które potwierdzono w czterech
kolejnych rundach marbles. Plan 07-b domyka oba. Odsyłacze: raporty marbles dla Planu 04 (Cut D), Planu 03 (Cut F) i
Planu 06 (Cut H)
dokumentują false-positive'y, które wywołały tę pracę; raport Planu 07-b pod
`.vibecrafted/reports/marbles/2026_0512/plan-07b-helper-limitations-fix.md`
zawiera dowody domknięcia.

### Ograniczenie #1 — false-positive z hooka pre-commit (3 potwierdzenia)

Repozytoryjny `scripts/hooks/pre-commit` uruchamia `prettier --write`, a po nim
`git add` na plikach `.md`/`.yaml`. Dzieje się to PO snapshocie `git write-tree`
helpera, ale PRZED zapieczętowaniem finalnego drzewa commita. Pierwotny detektor oparty na hashu drzewa potykał się o
kosmetyczną zmianę treści i raportował wyścig, mimo że commit był poprawny. Operatorzy widzieli kod wyjścia 3 +
diagnostykę „RACE DETECTED" na całkowicie legalnych commitach.

**Poprawka**: sam niezgodny hash drzewa nie jest już sygnałem wyścigu. Detektor wyścigu traktuje teraz trzy prymitywy
asymetrycznie:

- **Przesunięcie HEAD** — twardy sygnał wyścigu (inny commit wylądował przez aktualizację refa).
- **Obce pliki** — twardy sygnał wyścigu (dodatkowe pliki w kopercie commita).
- **Niezgodny hash drzewa** — informacyjny. Przyczynia się do diagnozy wyścigu tylko wtedy, gdy odpala też któryś z
  twardych sygnałów. Przy czystym HEAD i zgodnym zbiorze plików helper emituje teraz `notice — pre-commit hooks
rewrote content; not a race` i kończy się kodem 0.

**Trade-off**: hipotetyczny wyścig, który mutuje WYŁĄCZNIE treść stage'owanych plików (bez dodawania/usuwania plików i
bez przesunięcia HEAD), prześliznąłby się teraz. Akceptujemy to — żaden taki wyścig nie został zaobserwowany w czterech
rundach planu, a pierwotny incydent z kroniki 2026-04-16/17 jest łapany przez detektor obcych plików (który pozostaje
rygorystyczny).

### Ograniczenie #2 — cytowanie wieloliniowego MSG (1 potwierdzenie w Planie 06)

`make commit-safe MSG="..."` zawodził na wieloliniowych treściach komunikatu z powodu ścierania się escape'owania `$$` w
Makefile z ekspansją shella. Plan 06 obszedł to, wywołując `scripts/lib/living-tree-commit.sh` bezpośrednio z
heredokiem.

**Poprawka**: helper przyjmuje teraz `--message-file <path>` jako alternatywę dla pozycyjnego argumentu z komunikatem.
Target Makefile zyskuje parametr
`MSG_FILE=<path>`, który się na to mapuje. Oba tryby wywołania działają; w obrębie jednego wywołania wykluczają się
wzajemnie.

**Użycie wieloliniowe**:

```
cat >/tmp/commit.msg <<'EOF'
plan-XX subject line

Body paragraph one with "quotes" and $shell-style references intact.

- bullet one
- bullet two
EOF

make commit-safe MSG_FILE=/tmp/commit.msg FILES="path1 path2"
```

**Bezpośrednio z shella**:

```
scripts/lib/living-tree-commit.sh --message-file /tmp/commit.msg -- path1 path2
```

Jednoliniowy `MSG="..."` działa dalej bez zmian. Ścieżki fallbackowe Planów 04/03/06, które wywoływały helper
bezpośrednio, nie są dotknięte.

### Weryfikacja

Rozszerzony `tests/race_protection_test.sh` dodaje dwa przypadki pozytywne:

- `[positive-C]` symuluje hook pre-commit, który w stylu prettiera przepisuje stage'owaną treść `.md`. Helper musi
  zakończyć się kodem 0 i wyemitować notice o modyfikacji przez hook.
- `[positive-D]` przerabia `--message-file` z treścią zawierającą osadzone znaki nowej linii, pojedyncze/podwójne
  cudzysłowy, referencje `$shell` oraz backticki. Wszystko zachowane verbatim w zacommitowanej treści.

Dotychczasowe 10 asercji (czysty commit + 2 wstrzyknięcia wyścigu) zachowane.
