# Measure-Core — pancerz, który niesie każde cięcie scaffoldu

Plany scaffoldu są mierzalne, nie optymistyczne. Każda jednostka planu (cięcie/fala/task) jest
**adresowalna przez twierdzenie/wynik**: niesie Vector, czteroczłonową deltę, marker stanu i
delivery-verifier. To właśnie pozwala `vc-operator` czytać plan i mechanicznie odpalać trigger/stop.

## Pięciostanowy alfabet

```
[ ] OPEN      zarejestrowana intencja; brak twierdzenia, nic nie dowiezione
[~] CLAIMED   aktor twierdzi „done"; verifier NIE został uruchomiony       (pułapka optymizmu)
[?] UNKNOWN   verifier nie wydał verdictu (brak testu / nieosiągalny backend / brak evidence w którąkolwiek stronę)
[!] REFUTED   verifier się uruchomił; delivery przeczy twierdzeniu/intencji   (regresja, panic, 5xx, deadlock, 0-bajtów, overclaim)
[x] DELIVERED verifier się uruchomił; delivery ≥ intent ORAZ claim ≈ delivery   (jedyny zielony)
```

**INWARIANT:** tylko **verifier** przerzuca `[~]→[x]`. Twierdzenie nigdy samo nie dochodzi do `[x]`. O to
chodzi w całości — to oddziela zmierzony wynik od twierdzonego twierdzenia.

`[?]` (unknown) to uczciwa niewiedza i jest odrębne od `[!]` (known-bad). Zaparkuj `[?]` uczciwie;
nie fejkuj śledztwa, żeby zrobić z niego `[x]` albo `[!]`.

### Przejścia (co przerzuca każde)

```
[ ] → [~]   ląduje CLAIM (agent raportuje / commit)
[~] → [x]   delivery-verifier przechodzi (OUTCOME)
[~] → [!]   verifier zawodzi / INCIDENT (claim > delivery)
[~] → [?]   verifier nie może się uruchomić (brak testu / nieosiągalny)
[?] → [x]|[!]   gdy evidence wreszcie dociera
 *  → [!]   nowy INCIDENT otwiera ponownie (regresja)
```

## Oś Vector → delta

```
VECTOR: stabilize | implement | recon | e2e      (wybiera profil bramki = co liczy się jako delivery)
Vector → (intent | baseline | claim | delivery) → trigger/stop
```

- **intent** = oczekiwany wynik · **baseline** = obecny stan, ZMIERZONY (nigdy zakładany)
- **claim** = co raportuje agent (podejrzane) · **delivery** = co potwierdził verifier (+ ref do evidence)
- Vector wybiera **definicję delivery**: stabilize → „krwawienie zatrzymane + bramka zielona";
  implement → „feature działa + test"; recon → „mapa/odpowiedź z evidence"; e2e → „pełna ścieżka przechodzi".

## Trigger / stop (czytane przez vc-operator)

- `dou-index = |[x]| / total`; `delta = {[ ], [~], [?], [!]}` (wszystko, co nie jest jeszcze dowiezionym wynikiem).
- Jakiekolwiek `[!]` lub `[?]` → **STOP → recovery-vector**. Pełna fala `[x]` → **TRIGGER** następnej fazy.
- **STOP to nigdy nie kapitulacja.** Wyzwala fallback / failover / round-robin / handsoff. „502-i-umrzyj",
  zawieszenie, artefakt 0-bajtów to bug pipeline'u, nie akceptowalny wynik.
- **Observability jest częścią delivery-gate.** Ślepy watchdog/Sentry = delivery niezweryfikowane = `[?]`.

## Markery procesu (dla warstwy intents/blackbox)

Commity to granice WYNIKU; proces między nimi to miejsce, gdzie żyje chaos. Markery próbkują
proces, żeby przebieg dało się zrekonstruować:

| Marker           | Heurystyka                                        | Rola                            |
| ---------------- | ------------------------------------------------- | ------------------------------- |
| `[REUSE_FENCE]`  | content-hash + mtime bez zmian                    | snapshot reuse, pomiń rescan    |
| `[DRIFT]`        | working-tree rozjechał się >N bez commita         | zapis chaosu między-commitami   |
| `[BASELINE]`     | bramka zielona na czystym drzewie                 | człon `baseline`                |
| `[CLAIM]`        | agent raportuje done / commit                     | `[~]`                           |
| `[OUTCOME]`      | delivery-verifier zielony                         | `[x]`                           |
| `[INCIDENT]`     | panic / 5xx / exit≠0 / 0-bajtów / hang / deadlock | `[!]` (git nigdy ich nie widzi) |
| `[INTENT_SHIFT]` | przegląd operatora zmienia Vector                 | przełącza profil bramki         |

Task-list GFM `- [ ]`/`- [x]` to jeden artefakt z dwoma czytelnikami: renderuje się dla człowieka i parsuje
dla toolingu. Kolumna `state` to most między planem zwróconym ku człowiekowi a maszynowym trigger/stop.
