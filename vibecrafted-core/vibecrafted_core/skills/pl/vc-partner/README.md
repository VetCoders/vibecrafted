# VetCoders Partner

Proaktywna postawa wspólnego sterowania dla sesji, w których operator i agent
muszą zachować pierwotny kształt, a jednocześnie posuwać się naprzód zdecydowanie.

`vc-partner` to nie nakładka na rój plannerów ani nie słabszy tryb ownership. To
postawa, która utrzymuje mózg sterujący współdzielony, podczas gdy agent wykonuje
ciężką pracę, uruchamia właściwe runtime'y i sprawdza każdy wynik względem
pierwotnego kształtu.

## Do czego się nadaje

Użyj `vc-partner`, gdy:

- definicja problemu jest równie ważna co implementacja
- pierwotny kształt musi przetrwać compaction i delegację
- prawda runtime'u może zmienić plan
- operator chce proaktywnej pracy bez cichego przejęcia
- lane'y zapisu wymagają weryfikacji tylko-do-odczytu przed „done"

## Rdzeniowy model działania

Domyślna pętla to:

1. zdefiniuj problem
2. uchwyć `original_shape`
3. spisz kontrakt sukcesu (success contract)
4. zbuduj plan z `vc-scaffold`
5. wybierz lane wykonania
6. uruchom pracę zapisu
7. uruchom `vc-review`, `vc-followup`, `vc-audit` oraz `vc-dou`
8. domknij luki przez `vc-marbles` lub inny skupiony lane zapisu
9. dowieź dopiero, gdy DoU jest czyste albo pozostałe luki są jawne

## Kluczowe reguły

- wywołanie skilla to nie wywołanie runtime'u
- dziennik partnera to pamięć misji tylko-do-dopisywania (append-only)
- workerzy mogą wykonywać, ale nie redefiniują pierwotnego kształtu
- review sprawdza prawdę implementacji
- followup sprawdza wierność kształtu
- audyt falsyfikuje twierdzenia o ukończeniu
- DoU sprawdza niedokończoną pracę na powierzchni produktu

## Pliki

- `SKILL.md` - instrukcje postawy
- `FLOW.md` - mapa procesu
- `CONTRACT.md` - wiążący podział postawa/runtime
- `JOURNAL.md` - dziennik misji tylko-do-dopisywania (append-only)
- `RUNTIME.md` - oczekiwania co do artefaktów runtime'u
- `TAXONOMY.md` - lokalna taksonomia

## Relacja z resztą stacku

- `vc-init` otwiera prawdę o repo/runtimie/intencji.
- `vc-scaffold` pomaga zbudować plan.
- `vc-implement` i `vc-workflow` prowadzą lane'y zapisu.
- `vc-operator` dyryguje zespołami polowymi, gdy trzeba.
- `vc-ownership` przejmuje ster, gdy wspólne sterowanie nie jest już pożądane.
- `vc-review`, `vc-followup`, `vc-audit` oraz `vc-dou` domykają stronę odczytu.
