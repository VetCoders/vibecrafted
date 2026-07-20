# Delivery Proof Kernel v1 — specyfikacja prawdy o dostarczeniu

_Status: input contract for `vc-scaffold` · 2026-07-20 · owner: operator + Sol_

## 1. Po co istnieje ten dokument

Ten dokument nie jest planem implementacji i nie wskazuje workerowi listy linii
do zmiany. Opisuje problem, stan zastany, docelowy kontrakt runtime'u i dowody,
które muszą obalić fałszywe poczucie bezpieczeństwa przed uznaniem pracy za
dostarczoną.

Ma zostać przekazany świeżemu workerowi `vc-scaffold`. Jego zadaniem będzie
zbadać żywy checkout, skonfrontować tę specyfikację z aktualnym kodem i rozpisać
prawdziwy, wykonawczy scaffold. Kod jest źródłem prawdy o stanie obecnym, ale nie
jest wyrocznią dla docelowego kształtu.

Główna teza:

```text
proces się zakończył
≠ verifier rzeczywiście badał SUT
≠ zadeklarowany efekt został osiągnięty
≠ zmiana została dostarczona w obiecanym miejscu
≠ dowód dostarczenia został zapieczętowany
```

Vibecrafted musi reprezentować te fakty osobno i nie może już automatycznie
wyprowadzać jednego z drugiego.

## 2. Baseline rozpoznania

Rozpoznanie wykonano w checkoutcie:

```text
repo: VetCoders/vibecrafted
path: /Volumes/vc-workspace/vetcoders/vibecrafted
branch: feat/reduce-wrong-assumptions
observed HEAD: 15a35e8dc4825e8e1b6869f57212681913da6e8f
upstream: origin/feat/reduce-wrong-assumptions
upstream relation at observation: ahead 1, behind 0
```

To jest zapis obserwacji, nie wieczna zgoda na ten SHA. Worker scaffolda musi
przed pracą wykonać świeży fetch, zapisać branch, HEAD, upstream relation i stan
drzewa oraz jawnie stwierdzić jedno z dwóch:

```text
This is the operator-chosen checkout and the baseline for this plan.
```

albo:

```text
BLOCKED: live checkout no longer matches the declared execution substrate.
```

Nie wolno samodzielnie przełączać brancha, resetować drzewa ani uciekać do
worktree. Baseline ma chronić atrybucję regresji, a nie wymuszać martwą czystość
repozytorium.

W chwili rozpoznania w drzewie istniały cudze, aktywne zmiany Continuity Kernel.
Są one częścią Living Tree i nie należą do tej specyfikacji. Scaffold ma je
uwzględnić jako równoległą pracę, nie wciągać do własnych commitów i nie
projektować konfliktującego drugiego kernela capability.

## 3. Kierunek obecnego brancha

Branch `feat/reduce-wrong-assumptions` już realizuje właściwą zasadę po stronie
wejścia do runtime'u:

- wybór agentów w `vc-research` fail-closed zamiast optymistycznego zgadywania;
- Gemini został usunięty z aktywnej ścieżki wykonawczej, a Agy stał się jawnym
  następcą;
- `vc-frame` dostał widoczny session rail;
- CLI publikuje wersjonowany JSON capability zamiast rozproszonych założeń;
- watcher dry-run nie powinien zostawiać osieroconych procesów;
- rozwijany równolegle Continuity Kernel rozróżnia `supported`, `unsupported`,
  `unverified` i `probe_failed`, zamiast zamieniać brak dowodu w wsparcie.

Delivery Proof Kernel ma zastosować tę samą doktrynę na końcu procesu:

> Brak dowodu dostarczenia oznacza `unverified`, nie `completed`.

## 4. Stan obecny i szczeliny

### 4.1. Artifact validation potwierdza obecność, nie prawdę

`vibecrafted-core/vibecrafted_core/artifacts.py` uznaje raport za prawidłowy,
gdy plik istnieje i ma więcej niż zero bajtów. Analogicznie traktuje transcript.
Nie sprawdza:

- czy raport opisuje bieżący run, repo, branch i HEAD;
- czy zadeklarowane komendy naprawdę się wykonały;
- czy raport nie jest tylko salvage'em ostatniej wiadomości agenta;
- czy testowany był produkt, czy jego oracle/dawca;
- czy wynik dotyczy checkoutu, instalacji lub runtime'u obiecanego operatorowi.

`artifact_ok` jest użytecznym faktem transportowym. Nie jest dowodem delivery.

### 4.2. Lifecycle miesza zakończenie procesu z sukcesem produktu

`vibecrafted-core/vibecrafted_core/lifecycle.py` posiada szczegółowe stany
transportowe, ale `COMPLETED` jest osiągalne między innymi z
`PROCESS_SPAWNED`, `FIRST_OUTPUT_SEEN`, `ACTIVE`, `ARTIFACT_SEEN` i
`REPORT_STARTED`.

`lifecycle_runner.py` oznacza stage jako `completed`, gdy await zwraca
`artifact_ok`; gdy nie ma kolejnego stage'u, cały lifecycle również zostaje
`completed`. `ship.py` zwraca kod 0 dla `launching` i `completed`.

To opisuje wykonanie i przepływ batona. Nie dowodzi dostarczenia deklarowanego
efektu.

### 4.3. Dispatch ma verifier, ale nie ma kwalifikacji dowodu

`vibecrafted_core.dispatch` już ma wartościowe elementy:

- wersjonowany schema dispatchu;
- baseline branch/HEAD;
- `Verify.run`;
- matchery outputu i exit code;
- `VerifierEvidence`;
- tracker state `[x]`.

Jednak `Verify.run` pozostaje dowolnym stringiem shellowym. Runtime potrafi
zapisać exit code całej komendy i dopasować output, ale nie wie:

- jaki proces był Subject Under Test;
- czy pipe zamaskował błąd wcześniejszego procesu;
- czy oracle i subject są różnymi producentami;
- czy verifier w ogóle skonsumował output SUT;
- czy verifier potrafi być czerwony;
- czy wynik `[x]` odpowiada zakresowi `checkout`, `installed` albo `live`.

### 4.4. Scaffold-doctor jest obietnicą, nie istniejącą bramką

`vc-scaffold/SKILL.md` nazywa gate machine-checked. Repo nie posiada jednak
implementacji `DeliveryProofContract`, `DeliverySeal` ani wykonującego ten
kontrakt scaffold-doctora. Dokument
`docs/runtime/SCAFFOLD_SERVER_EDITOR_design.md` uczciwie mówi, że doctor dopiero
_should consume_ listę artefaktów i checkpointy.

Rustowy `ScaffoldArtifactStore` odkrywa, zapisuje i checkpointuje Markdown. Nie
waliduje semantycznie dowodu, który brief obiecuje.

### 4.5. Skill doctrine i runtime truth są w konflikcie

`vc-audit` słusznie mówi, że PASS wymaga task evidence, code evidence, test
evidence i negative check. Jest to jednak instrukcja dla modelu, nie
egzekwowalny kontrakt runtime'u.

`vc-dispatch` mówi dispatcherowi, aby po wyjściu workera nie uruchamiał ponownie
testów, tylko zaufał SHA, hookom i raportowanym gate'om, a prawdę rozstrzygał
późniejszy audit. Bez maszynowego proof kernela ta optymalizacja tworzy okno, w
którym tracker może być `[x]`, mimo że verifier nie dotknął SUT.

Docelowo dispatcher ma ufać `DeliverySeal`, nie prozie reportera.

### 4.6. Read modele powielają nieprecyzyjny status

Control plane, MCP, CLI, Rust `control-core`, server i interfejsy potrafią
projektować `completed`, `artifact_ok` i lifecycle state. Nie istnieje osobna,
typowana projekcja:

```text
execution_state
proof_state
delivery_state
```

Frontend nie może więc uczciwie powiedzieć, czy ogląda zakończony proces,
zweryfikowaną zmianę czy dostarczony produkt.

## 5. Incydenty, które nowy kontrakt musi umieć odtworzyć

### 5.1. Oracle sprawdza dawcę, nie biorcę

W AICX `tests/parser_oracle/compare.py --all` dla adapterów donorowych uruchamia
Transcript Builder, materializuje jego wynik i porównuje go z goldenem. Nie
uruchamia parsera AICX. Test może być zielony przy nieistniejącym lub całkowicie
zepsutym AICX.

Transcript Builder robi rzecz właściwą: jego conformance kit uruchamia własny
parser nad fixture'em, normalizuje rzeczywisty rezultat i porównuje całość z
goldenem. Bogate fixture'y obejmują między innymi paste dedup, skill payload,
notification, subagent merge i self-reference.

Kernel musi odróżniać:

```text
oracle output       = oczekiwana prawda / dawca
subject output      = rzeczywisty wynik badanego produktu
assertion           = porównanie subject output z oczekiwaniem
```

Porównanie oracle output z goldenem oracle'a nie jest dowodem subjectu.

### 5.2. Zielony grep przykrywa czerwone cargo test

Briefy AICX używały komend w rodzaju:

```bash
cargo test --workspace 2>&1 | grep "test result:"
```

Bez `pipefail` proces `cargo test` mógł zakończyć się kodem 101, a cała komenda
kodem 0, ponieważ ostatni `grep` znalazł linię. Dowód stawał się zielony dokładnie
wtedy, kiedy producent dowodu był czerwony.

Kernel nie może dziedziczyć semantyki exit code z przypadkowej powłoki.

### 5.3. Operacja na nieaktualnym checkoutcie

Przed dużym cięciem parsera nie został wystarczająco twardo zakwalifikowany
checkout i jego relacja do najnowszego origin. Plan mógł być logicznie dobry i
nieuchronnie odtworzyć regresje, ponieważ wystartował z błędnego podłoża.

Proof zaczyna się przed implementacją: repo identity, root, branch, HEAD,
upstream relation, dirty state i brief digest muszą tworzyć execution envelope.

### 5.4. `interrupted` albo `partial` opowiedziane jako `completed`

Raport, transcript, meta i control-plane state mogą się rozjechać. Agent może
przerwać pracę, zostawić niepusty raport lub poprawnie wyjść z procesu, a warstwa
wyżej zaprezentuje to jako ukończone.

Żaden `interrupted`, `partial`, `timed_out`, `stalled`, `recovery_required`,
nieznany exit code ani brak obiecanego artefaktu nie może awansować do
`delivery.delivered` przez projekcję kompatybilności.

## 6. Docelowa architektura

Jedna implementacja ma mieszkać w Pythonowym runtime core, logicznie jako:

```text
vibecrafted_core/delivery/
```

Nazwa katalogu jest kierunkiem ownership, nie poleceniem mechanicznej edycji.
Scaffolder ma potwierdzić najlepszy fizyczny kształt po zbadaniu aktualnego
kodu. Niezmienna jest zasada: jeden typowany kernel, żadnych czterech kopii
reguł w skillach.

Przepływ:

```text
ExecutionEnvelope
    ↓ preflight qualification
DeliveryProofContract
    ↓ deterministic executor
ExecutionEvidence[]
    ↓ assertion + negative control
ProofResult
    ↓ delivery-scope qualification
DeliveryRecord
    ↓ only vc-ship may issue
DeliverySeal
    ↓ read-only projections
CLI / MCP / control-core / vc-frame / reports
```

### 6.1. Rozdzielenie stanów

Runtime musi utrzymywać trzy ortogonalne osie:

```text
execution_state:
  created | launched | running | exited | interrupted | timed_out | failed

proof_state:
  undeclared | declared | running | passed | failed | invalid | stale

delivery_state:
  unverified | delivered | sealed | invalidated
```

Dozwolona ścieżka sukcesu:

```text
execution.exited(exit_code=0)
→ proof.running
→ proof.passed
→ delivery.delivered
→ delivery.sealed
```

Każda strzałka wymaga osobnego dowodu. Żadna nie jest automatyczną nazwą dla
poprzedniego stanu.

Legacy `completed` może pozostać jako status wykonania podczas migracji, ale
nie wolno go mapować na `delivered` ani `sealed` bez pieczęci.

## 7. Typowane kontrakty

### 7.1. `ExecutionEnvelope`

Envelope odpowiada wyłącznie na pytanie: _gdzie, kto i na jakim podłożu ma
wykonać brief?_

Minimalne pola:

```yaml
execution:
  schema: vibecrafted.execution-envelope.v1
  agent: codex
  repo: Loctree/aicx
  root: /Volumes/vc-workspace/Loctree/aicx
  branch: fix/example
  expected_head: <full sha>
  upstream_ref: origin/fix/example
  upstream_relation: { ahead: 0, behind: 0 }
  dirty_policy: living-tree-scoped
  baseline_status_digest: sha256:...
  protected_paths: []
  owned_paths: []
  brief_path: /absolute/path/to/brief.md
  brief_sha256: sha256:...
```

`vc-dispatch` jest właścicielem egzekucji envelope. Przed uruchomieniem sprawdza
agenta, repo identity, root, branch, HEAD, brief digest i politykę dirty tree.
Jeżeli frontmatter briefa przeczy runtime'owi, run zostaje `blocked` przed
spawnem. Dispatch nie interpretuje semantyki dowodu produktu.

Pogoda nad Bałtykiem pozostaje poza schematem.

### 7.2. `DeliveryProofContract`

Kontrakt odpowiada na pytanie: _co dokładnie ma zostać udowodnione i jak
udowodnimy, że sam dowód potrafi zawieść?_

Przykładowy kształt normatywny:

```yaml
proof:
  schema: vibecrafted.delivery-proof.v1
  id: parser-conformance
  execution_envelope_sha256: sha256:...

  subject:
    producer_id: Loctree/aicx
    public_surface: aicx extract codex --file <fixture> --emit session-record
    argv: [aicx, extract, codex, --file, <fixture>, --emit, session-record]
    cwd: /Volumes/vc-workspace/Loctree/aicx
    expected_exit: 0
    output: <run-artifact>/subject/session_record.json

  witness:
    input: <fixture>
    sha256: sha256:...
    expected_outcome: normalized-session-record-v1

  oracle:
    producer_id: VetCoders/transcript-builder
    argv: [python3, -m, tb_core, ...]
    version_probe: [python3, -m, tb_core, --version]
    output: <run-artifact>/oracle/session_record.json

  assertion:
    kind: normalized-structural-equality
    actual: <run-artifact>/subject/session_record.json
    expected: <run-artifact>/oracle/session_record.json
    normalizer_id: session-record-v1

  negative_controls:
    - id: missing-subject-output
      mutation: remove_isolated_actual
      expected: proof_failed
    - id: corrupt-subject-output
      mutation: corrupt_isolated_actual
      expected: proof_failed
    - id: oracle-substitution
      mutation: replace_actual_with_unrelated_oracle_output
      expected: proof_failed

  delivery_scope: checkout
  integration_target: null
  runtime_probes: []
```

Nie każde zadanie potrzebuje zewnętrznego oracle. Wtedy `oracle` może być
`null`, ale kontrakt nadal musi mieć witness, jawne expected outcome, assertion
i negative control. Oracle nie może być dekoracyjnym obowiązkiem.

### 7.3. `ExecutionEvidence`

Każdy proces dostaje osobny rekord. Minimalne pola:

- logiczna rola: `subject`, `oracle`, `assertion`, `negative_control`,
  `runtime_probe`;
- dokładne argv; shell string tylko jako jawnie oznaczony wyjątek;
- cwd oraz bezpieczny, zredagowany environment manifest;
- resolved executable path, wersja i — gdy praktyczne — digest binarki/skryptu;
- start/end, elapsed, timeout policy;
- osobny exit code procesu;
- digests stdout i stderr oraz ograniczone, zredagowane excerpt;
- input/output paths i ich SHA-256;
- repo/HEAD snapshot przed i po procesie;
- identyfikator parent contractu i runu.

Formatter, `tee`, `grep`, `tail` i renderer nie mogą być niewidzialną częścią
exit code producenta. Preferowane są argv arrays i programowe przetwarzanie
outputu. Jeżeli shell jest konieczny, executor ma jawnie uruchomić ścisłą
powłokę, zapisać `PIPESTATUS` każdego segmentu i uznać błąd dowolnego wymaganego
segmentu za błąd całego dowodu.

### 7.4. `ProofResult`

`ProofResult` jest deterministycznym wynikiem wykonania kontraktu:

- `passed`, `failed`, `invalid` lub `stale`;
- lista wykonanych evidence records;
- wynik każdej assertion;
- wynik każdego negative control;
- informacja, czy subject rzeczywiście się uruchomił;
- informacja, czy assertion skonsumowała jego output;
- przyczyny odmowy;
- digest kontraktu i executora/verifiera.

`invalid` oznacza wadliwy dowód, nie wadliwy produkt. Przykłady: subject i
oracle są tym samym producentem, assertion nie czyta subject outputu, negative
control nie robi się czerwony, zmienił się verifier albo envelope.

### 7.5. `DeliveryRecord`

`DeliveryRecord` jest wynikiem kwalifikacji scope. Łączy `ProofResult` z
twierdzeniem o miejscu dostarczenia i odpowiada na pytanie, którego sam test nie
potrafi rozstrzygnąć: _gdzie ten udowodniony efekt naprawdę istnieje?_

Minimalnie zawiera declared scope, checked scope, target identity, commit/tree
provenance, wyniki wymaganych runtime probes oraz status `delivered` albo
`unverified` z przyczynami odmowy. Może powstać po udanym proof, ale nie jest
jeszcze pieczęcią i nie daje żadnej powierzchni prawa do pokazania `sealed`.

### 7.6. `DeliverySeal`

`DeliverySeal` jest content-addressed, nieedytowalną pieczęcią wydawaną wyłącznie
przez `vc-ship` po udanym proof i kwalifikacji zakresu delivery.

Musi wiązać co najmniej:

- schema version, seal id, issued_at i issuer;
- run id, lifecycle id, cut id i proof id;
- ExecutionEnvelope digest;
- DeliveryProofContract digest;
- ProofResult digest;
- verifier/executor source digest i wersję;
- subject, witness, oracle i assertion evidence digests;
- negative control evidence digests;
- repo identity, branch, baseline HEAD, final HEAD i scoped dirty-state digest;
- commit lub commit range objęty dostarczeniem;
- zadeklarowany oraz faktycznie sprawdzony delivery scope;
- runtime probe digests, jeśli scope ich wymaga;
- report, transcript i control-plane snapshot digests;
- listę jawnie nieweryfikowanych powierzchni.

Pieczęć nie musi być kryptograficznie podpisana w v1. Musi być kanonicznie
serializowana i hashowana tak, by zmiana dowolnego składnika unieważniała
rekonstrukcję. Projekt nie może blokować późniejszego podpisu organizacyjnym
kluczem release.

## 8. Semantyka delivery scope

Zakres jest częścią twierdzenia, nie etykietą marketingową.

### `checkout`

Dowód wykonano na zadeklarowanym checkoutcie. Seal wiąże root, repo identity,
branch, HEAD, relevant path digests i diff. Nie twierdzi nic o origin, instalacji
ani produkcji.

### `branch`

Zmiana istnieje w commitach osiągalnych z zadeklarowanego local branch ref.
Seal zapisuje commit range i stan brancha. Nie twierdzi, że zmiana jest na
remote.

### `integrated`

Zmiana jest osiągalna z `integration_target` po świeżym fetchu, a proof został
wykonany na dokładnie tym integrowanym drzewie lub równoważnym, udowodnionym
tree hash. Lokalny commit na bocznym branchu nie spełnia tego scope.

### `installed`

Sprawdzono zainstalowany artefakt, nie ścieżkę z repo. Evidence musi zawierać
resolved executable/app path, provenance/version marker wiążący build z
commitem oraz realny smoke przez publiczny entrypoint.

### `live`

Sprawdzono wskazaną instancję runtime'u, usługę, store lub endpoint. Evidence
musi identyfikować target bez ujawniania sekretów i wykonać bezpieczny probe
widocznego efektu. Zielony test lokalny nie może zaspokoić `live`.

Scope może awansować tylko przez nowy proof albo rozszerzenie kontraktu i nową
pieczęć. Seal `checkout` nigdy nie staje się `installed` przez zmianę labelki.

## 9. Kwalifikacja verifiera i kontrola negatywna

Verifier jest dopuszczony do wydawania dowodu tylko wtedy, gdy sam został
sfalsyfikowany.

Minimalne reguły:

1. Subject został uruchomiony przez zadeklarowany publiczny entrypoint.
2. Output subjectu istnieje, ma digest i jest wejściem assertion.
3. Jeżeli istnieje oracle, ma inny `producer_id` niż subject.
4. Brak outputu subjectu powoduje failure.
5. Kontrolowane uszkodzenie outputu subjectu powoduje failure.
6. Podstawienie niepowiązanego outputu oracle nie przechodzi niezauważone.
7. Non-zero subject nie może zostać przykryty przez zielony formatter.
8. Zmiana kodu/configu verifiera po proof oznacza `stale`, nie ponowne użycie
   starego PASS.
9. Negative control działa na izolowanej kopii artefaktów. Nie niszczy checkoutu,
   instalacji ani live store.
10. Każdy materialny assertion ma co najmniej jedną kontrolę, która udowadnia,
    że assertion potrafi się zrobić czerwona.

Jeżeli negatywna kontrola przechodzi na zielono, wynik brzmi:

```text
proof.invalid: verifier did not detect the controlled falsehood
```

Nie wolno zamieniać tego w warning.

## 10. Living Tree i odporność na TOCTOU

Globalnie czyste drzewo nie jest wymagane i byłoby fałszywym założeniem w
Vibecrafted. Seal musi jednak wiedzieć, co zmieniało się podczas dowodu.

Runtime zapisuje:

- pełny status snapshot przed i po;
- owned/relevant paths wynikające z briefa, diffu i mapy zależności;
- digests plików wejściowych, SUT, verifiera i assertion;
- zmiany poza scope jako concurrent drift;
- zmiany w scope jako invalidating drift.

Wspólny branch nie pozwala używać `HEAD^` jako domniemania „commitu mojego
workera”. Allowlista i commit evidence muszą odnosić się do dokładnego
`CUT_COMMIT` zapisanego przy zakończeniu cutu, na przykład przez
`git diff-tree --no-commit-id --name-only -r "$CUT_COMMIT"`. Późniejszy commit
innego workera nie może zmienić znaczenia starszego dowodu.

Niezależna zmiana w odległej dokumentacji nie musi wywracać testu parsera.
Zmiana parsera, fixture'a, normalizera, build configu lub binarki podczas proof
musi unieważnić wynik i wymusić rerun.

## 11. Ownership między powierzchniami

### `vc-scaffold` — definiuje dowód

Scaffold ma tworzyć ExecutionEnvelope i DeliveryProofContract dla każdego
cutu, którego rezultat będzie twierdził coś więcej niż wykonanie procesu.

Machine scaffold-doctor odrzuca brief, gdy brakuje:

- subjectu i publicznego entrypointu;
- witnessa i jego digestu lub reguły wyliczenia digestu przy starcie;
- expected outcome/assertion;
- negative control;
- delivery scope;
- execution envelope z agentem, repo, rootem, branchem, HEAD i brief digest;
- producenta wymaganych narzędzi gate'owych;
- bezpiecznej polityki dla Living Tree.

Doctor ma walidować typowany artefakt, nie szukać słów kluczowych w Markdownzie.
Markdown jest czytelną projekcją kontraktu, nie jego jedynym storage.

### `vc-dispatch` — egzekwuje salę operacyjną

Dispatch:

- kwalifikuje ExecutionEnvelope;
- blokuje mismatch przed spawnem;
- uruchamia właściwego agenta w właściwym repo/root/branch/HEAD;
- zapisuje run, prompt i brief digests;
- transportuje proof contract bez interpretowania jego semantyki;
- zapisuje execution state.

Dispatch nie wystawia DeliverySeal i nie wymyśla własnej definicji PASS.

### `vc-ship` — wykonuje dowód i pieczętuje delivery

`vc-ship` jest jedynym wystawcą DeliverySeal. Może użyć wspólnego executora z
runtime core, ale tylko ship authority może awansować `delivered` do `sealed`.

Bez pieczęci bezpośredni worker run może uczciwie zakończyć się jako:

```text
execution.exited
proof.passed
delivery.unverified
```

To nie jest porażka. To precyzyjne stwierdzenie, że rezultat nie przeszedł
shipping authority.

### `vc-audit` — atakuje produkt, verifier i pieczęć

Audit pozostaje read-only wobec produktu, ale powinien umieć:

- odtworzyć proof z zapisanych digests;
- sprawdzić, czy subject output naprawdę uczestniczył w assertion;
- wykonać bezpieczne negative controls na kopiach evidence;
- wykryć oracle-subject tautology;
- wykryć stale verifier/envelope/repo state;
- zweryfikować scope claims;
- odmówić PASS, gdy seal nie istnieje lub nie da się zrekonstruować.

Audit nie poprawia pieczęci. Wydaje audit verdict i może ją unieważnić lub
zażądać nowego proof.

### Control plane, MCP, server, TUI — projekcje, nie nowi właściciele

Wszystkie powierzchnie czytają ten sam typowany rekord. Mogą pokazać:

```text
process: exited 0
proof: passed
delivery: sealed (installed)
```

albo:

```text
process: exited 0
proof: invalid
delivery: unverified
reason: negative control stayed green
```

Nie mogą lokalnie wyliczać `delivered` z `status == completed`.

## 12. Storage i zdarzenia

Docelowy run directory powinien posiadać kanoniczne, atomowo zapisane artefakty
o stabilnych schema ids. Fizyczne nazwy scaffolder ma uzgodnić z istniejącym
control-plane layoutem, ale logicznie potrzebne są:

```text
execution-envelope.json
delivery-proof-contract.json
proof/executions/<role>-<n>.json
proof/assertions.json
proof/negative-controls.json
proof/result.json
delivery-record.json
delivery-seal.json
```

Control plane publikuje osobne eventy, co najmniej:

```text
execution.exited
proof.started
proof.failed
proof.invalid
proof.passed
delivery.delivered
delivery.sealed
delivery.invalidated
```

Zapisy są atomic replace albo append-only tam, gdzie obowiązuje log. Każdy
derived record wskazuje digests rekordów źródłowych.

## 13. Bezpieczeństwo wykonania

- Preferuj argv arrays; shell jest jawnym capability, nie defaultem.
- Każdy proces ma timeout i limit outputu.
- Environment jest allowlistowany lub redagowany; sekrety nie trafiają do
  evidence, excerptów ani pieczęci.
- Negative controls operują w tempdir/content-addressed copy.
- Publiczne runtime probes są read-only lub używają dedykowanych test resources.
- Nie wolno uruchamiać destrukcyjnej mutacji live tylko po to, by udowodnić, że
  verifier ją zobaczy.
- Ścieżki muszą być kanonikalizowane i ograniczone do zadeklarowanych roots.
- Executable resolution jest zapisywane przed wykonaniem; późniejsza zmiana PATH
  nie może reinterpretować starego evidence.
- Kontrakt i seal mają wersjonowanie oraz fail-closed parsing nieznanych wersji.

## 14. Migracja bez pięknego kłamstwa

1. Istniejące runy pozostają czytelne jako legacy execution records.
2. Brak `delivery-seal.json` oznacza `delivery.unverified`.
3. Legacy `Verify.run` można zaimportować jako niekwalifikowany assertion, ale
   nie może samodzielnie wystawić seal.
4. Legacy `artifact_ok` zachowuje znaczenie: wymagane artefakty istnieją. Nie
   zostaje przemianowane na proof.
5. Legacy `[x]` w trackerze jest historycznym claimem, dopóki nie ma seal lub
   nowego audytu.
6. Skille dostają cienkie odwołanie do kernela. Nie kopiujemy semantyki proof do
   czterech SKILL.md.
7. Rust read model i MCP rozszerzają schema addytywnie. Stare rekordy są jawnie
   `unverified`, nie optymistycznie `sealed`.

## 15. TDD — obowiązkowe czerwone dowody przed implementacją

Scaffold musi zacząć od testów, które na obecnym kodzie są czerwone. Minimum:

| ID  | Fałszywe zabezpieczenie                                   | Oczekiwany wynik nowego kernela                     |
| --- | --------------------------------------------------------- | --------------------------------------------------- |
| T01 | Subject command nie został uruchomiony                    | `proof.invalid` lub `proof.failed`; brak seal       |
| T02 | Oracle porównuje swój output ze swoim goldenem            | odrzucenie: subject output nie był konsumowany      |
| T03 | Subject i oracle mają ten sam producer id                 | schema/doctor FAIL                                  |
| T04 | Subject exit 101, formatter/grep exit 0                   | proof FAIL z zachowanymi oboma exit codes           |
| T05 | Subject output został usunięty                            | negative control czerwony; verifier kwalifikuje się |
| T06 | Subject output został uszkodzony                          | assertion FAIL                                      |
| T07 | Negative control nie jest wykrywany                       | `proof.invalid`, nigdy warning                      |
| T08 | Brief digest różni się od envelope                        | dispatch BLOCKED przed spawnem                      |
| T09 | Repo/root/branch/HEAD różnią się od envelope              | dispatch BLOCKED przed spawnem                      |
| T10 | Relevant file zmienia się podczas proof                   | `proof.stale`; wymagany rerun                       |
| T11 | Zmienia się tylko niezależny plik poza scope              | drift zapisany; decyzja zgodna z policy             |
| T12 | Run jest interrupted/partial/timed_out                    | delivery nie awansuje                               |
| T13 | Raport istnieje i ma bajty, ale nie ma proof              | `artifact_ok=true`, `delivery=unverified`           |
| T14 | Verifier zmienił się po PASS                              | seal reconstruction FAIL / stale                    |
| T15 | Scope `installed`, lecz test uruchamia repo binary        | scope qualification FAIL                            |
| T16 | Scope `live`, lecz brak target probe                      | scope qualification FAIL                            |
| T17 | Commit nie jest osiągalny z integration target            | `integrated` FAIL                                   |
| T18 | Poprawny subject + witness + assertion + negative control | proof PASS                                          |
| T19 | Proof PASS + prawidłowy scope + ship authority            | deterministic DeliverySeal                          |
| T20 | Ten sam immutable input uruchomiony ponownie              | ten sam content digest, różny event time            |
| T21 | Filtr testów uruchamia zero testów                        | proof FAIL, nigdy vacuous green                     |

Testy nie mogą kończyć się na walidacji dataclass. Potrzebny jest realny E2E z
tymczasowym repo, dwoma odrębnymi producentami, rzeczywistymi subprocessami,
potokiem maskującym exit code i rekonstrukcją seal z dysku.

## 16. Kryteria akceptacji produktu

Implementacja spełnia spec dopiero, gdy:

- [ ] Jeden typowany kernel jest źródłem prawdy dla proof i seal.
- [ ] `vc-scaffold` emituje machine-readable contract i doctor potrafi go
      odrzucić przed dispatch.
- [ ] `vc-dispatch` fail-closed egzekwuje ExecutionEnvelope przed spawnem.
- [ ] Każdy subprocess ma własny exit code i evidence; pipeline nie maskuje
      producenta.
- [ ] Runtime potwierdza, że assertion skonsumowała output rzeczywistego SUT.
- [ ] Co najmniej jedna kontrolowana nieprawda musi zostać wykryta przed PASS.
- [ ] `vc-ship` jest jedynym wystawcą DeliverySeal.
- [ ] `vc-audit` potrafi niezależnie obalić verifier lub seal.
- [ ] `execution`, `proof` i `delivery` są osobnymi stanami w control plane.
- [ ] CLI, MCP, server/control-core i vc-frame nie wyprowadzają delivery z
      `completed` ani `artifact_ok`.
- [ ] Scope `checkout`, `branch`, `integrated`, `installed`, `live` ma różne,
      egzekwowalne wymagania.
- [ ] Stare runy są jawnie unverified, a nie wstecznie „zapieczętowane”.
- [ ] AICX false oracle i masked cargo exit są trwałymi regression fixtures.
- [ ] Dokumentacja skillowa odwołuje się do kernela zamiast duplikować jego
      semantykę.
- [ ] Realny lifecycle smoke pokazuje zarówno odmowę seal dla fałszywego
      verifiera, jak i seal dla poprawnego proof.

## 17. Non-goals v1

- Uniwersalne udowodnienie semantycznej poprawności każdego produktu.
- Kryptograficzny podpis organizacyjny pieczęci.
- Zastąpienie wszystkich istniejących lifecycle statusów w jednym cięciu.
- Nowy sandbox service tylko dla negative controls.
- Automatyczny push, merge, release albo mutacja produkcji.
- Drugi runtime proof w Rust. Rust ma być typed read projection, dopóki Python
  pozostaje canonical writerem.
- Parser Markdown jako fundament kontraktu.
- Uznanie raportu modelu za evidence bez maszynowego śladu wykonania.

## 18. Zadanie dla workera `vc-scaffold`

Worker ma otrzymać ten dokument w całości i:

1. wykonać świeży `vc-init`, Loctree mapę i literalny audit aktualnego kodu;
2. porównać live HEAD z baseline obserwacji oraz zapisać operator-chosen
   substrate statement;
3. uwzględnić równoległy Continuity Kernel i nie wejść w jego aktywne pliki bez
   rzeczywistej potrzeby;
4. sfalsyfikować wszystkie twierdzenia o stanie obecnym w tej specyfikacji;
5. zaprojektować jeden runtime-owned kernel, a nie markdownową kampanię;
6. rozpisać red-first TDD, ownership, zależności i fale możliwe do wykonania na
   jednym Living Tree bez worktrees;
7. przypisać każdego producenta narzędzia gate do konkretnego cutu;
8. umieścić ExecutionEnvelope i DeliveryProofContract w każdym briefie;
9. sprawić, by machine scaffold-doctor odrzucał pięknie opakowane kłamstwo;
10. zostawić operatorowi prawdziwy DRIVER, tracker i briefy, z których świeży
    agent może wykonać pracę bez zgadywania.

Najważniejszy test jakości scaffolda:

> Czy wszystkie briefy mogą zostać wykonane perfekcyjnie, a system nadal
> wystawić seal dla niedostarczonego produktu?

Jeżeli odpowiedź brzmi „tak” albo „nie wiadomo”, scaffold nie jest gotowy do
dispatchu.

## 19. Ostateczny kontrakt językowy

Po wdrożeniu wolno mówić:

```text
Proces zakończył się poprawnie.
Proof przeszedł i wykrywa kontrolowaną nieprawdę.
Efekt został sprawdzony w zakresie installed.
vc-ship wystawił DeliverySeal <id>.
```

Nie wolno skracać tego do „done”, jeśli któregokolwiek zdania nie da się
odtworzyć z typowanych artefaktów.

To nie jest dodatkowa biurokracja. To mechanizm, który pozwala ponownie ufać
autonomii agentów, ponieważ runtime przestaje nagradzać je za dobrze opowiedziane
zakończenie i zaczyna wymagać dowodu kontaktu z rzeczywistością.
