# Vibecraftsmanship — Złożenie z innymi skillami

Vibecraftsmanship to meta-doktryna. Nie zastępuje żadnego skilla —
mówi ci, który skill wywołać i dlaczego. Pakiet skilli rozwarstwia się
na 4 warstwy, a vibecraftsmanship przecina w poprzek tylko jedną z nich.

---

## Rozwarstwienie skilli

### Warstwa 1 — Fundamenty (przed kartą)

Uruchom przed jakąkolwiek kartą taktyczną. Dostarczają percepcji, intencji i
prawdy gruntowej.

- `vc-init` — triada percepcji + intencji + prawdy gruntowej
- `vc-scaffold` — planowanie architektury founder-first, gdy scope jest rozmyty

**Relacja do vibecraftsmanship**: fundamenty dostarczają podłoże,
na którym operują gust/siła/rzeczywistość. Nie da się wybrać postawy
bez znajomości prawdy repo.

### Warstwa 2 — Postawy (3 karty taktyczne)

Jak operator-agent siedzi względem pracy. Vibecraftsmanship to
meta-decyzja **spośród** tych trzech.

- `vc-ownership` — solowe dostarczanie end-to-end, agent prowadzi cały slice
- `vc-operator` — prowadzenie wielofalowej floty, agent dyryguje innymi agentami
- `vc-partner` — wspólne sterowanie wykonawcze, operator + agent współdecydują

**Relacja do vibecraftsmanship**: tabela routingu vibecraftsmanship
wybiera jedną z tych trzech na starcie sesji (i przekierowuje, gdy wykryje dryf
w locie). Zobacz tabelę routingu poniżej.

### Warstwa 3 — Techniki (ortogonalne do postawy)

Wzorce workflow dostępne WEWNĄTRZ dowolnej postawy. Marbles mogą być użyte
wewnątrz ownership, operator albo partner. Tak samo research, audit,
review, polarize, prune.

- `vc-marbles` — zbieżność pętli na istniejącym kodzie
- `vc-research` — triple-agent research bez luk
- `vc-audit` — falsyfikacja specu per-plan
- `vc-review` — percepcja diffu per-implementacja
- `vc-followup` — sprawdzanie kierunku trajektorii
- `vc-polarize` — decydujące cięcie jednoosiowe po marbles
- `vc-prune` — kuracja repo + strip silencerów
- `vc-intents` — audyt prawdy intencji-vs-runtime
- `vc-delegate` — delegacja do natywnego subagenta
- `vc-agents` — spawn zewnętrznej floty

**Relacja do vibecraftsmanship**: techniki to narzędzia, nie postawy.
Vibecraftsmanship NIE wybiera spośród technik — robi to aktywna postawa,
na podstawie tego, czego potrzebuje bieżący krok. Traktuj techniki jako
ortogonalną pulę.

### Warstwa 4 — Późny etap (powierzchnia produktu)

Na moment, gdy kod jest gotowy, ale produkt jeszcze nie jest dowieziony, znaleziony, sprzedany.

- `vc-dou` — audyt Definition of Undone
- `vc-decorate` — wizualne wykończenie późnego etapu
- `vc-hydrate` — pakowanie + go-to-market
- `vc-release` — finalne dowiezienie na zewnątrz

**Relacja do vibecraftsmanship**: późny etap uruchamia oś rzeczywistości
najmocniej — czy produkt przetrwa kontakt z **klientem**
rzeczywistości, nie tylko rzeczywistości dewelopera. Vibecraftsmanship może wywołać
późny etap, gdy sprawdzenie przetrwania ujawni, że produkt jest „gotowy w repo", ale
jeszcze nie dowieziony do nikogo.

---

## Tabela routingu — która postawa na który moment

| Moment                                                                 | Postawa      | Karta taktyczna |
| ---------------------------------------------------------------------- | ------------ | --------------- |
| Jeden bounded feature, jeden branch, cały slice posiadany end-to-end   | Ownership    | `vc-ownership`  |
| Plan wielofalowego dispatchu, wieloagentowy z założenia, wiele branchy | Operator     | `vc-operator`   |
| Triage zanim plan istnieje, potrzebna wspólna definicja problemu       | Partner      | `vc-partner`    |
| Pętla zbieżności na istniejącym kodzie (w dowolnej postawie)           | (technika)   | `vc-marbles`    |
| Research przed implementacją z 3 perspektywami                         | (technika)   | `vc-research`   |
| Falsyfikacja specu po ukończeniu                                       | (technika)   | `vc-audit`      |
| Code review per-PR albo per-branch                                     | (technika)   | `vc-review`     |
| Sprawdzenie trajektorii („czy idziemy w dobrym kierunku?")             | (technika)   | `vc-followup`   |
| Decydujące cięcie jednoosiowe po nadmiarze marbles                     | (technika)   | `vc-polarize`   |
| Kuracja martwego kodu + strip silencerów                               | (technika)   | `vc-prune`      |
| Orientacja w repo przed jakąkolwiek pracą                              | (fundament)  | `vc-init`       |
| Od pomysłu do planu, gdy scope rozmyty                                 | (fundament)  | `vc-scaffold`   |
| Audyt gotowości powierzchni produktu                                   | (późny etap) | `vc-dou`        |
| Pass dopracowania spójności wizualnej                                  | (późny etap) | `vc-decorate`   |
| Pakowanie + listing + onboarding                                       | (późny etap) | `vc-hydrate`    |
| Finalne dowiezienie + DNS + weryfikacja                                | (późny etap) | `vc-release`    |

---

## Kiedy eskalować postawę w locie

Sygnały wykrycia dryfu (zadaniem vibecraftsmanship jest je nazwać):

### Eskalacja Ownership → Operator

Trigger: „ten slice rozrósł się w N równoległych cięć, z których żadnego
oryginalny agent nie utrzyma w pamięci roboczej jednocześnie".

Akcja: wywołaj vc-operator, napisz master-dispatch, ukształtuj w fale
pozostałą pracę.

### Eskalacja Operator → Partner

Trigger: „plan dispatchu wciąż wymaga decyzji po stronie operatora,
które nie są udokumentowane, a operator nie odpowiada w trakcie fali".

Akcja: zapauzuj dispatch, wywołaj vc-partner, współdecyduj o oczekujących
niejednoznacznościach, potem wznów.

### Eskalacja Partner → Ownership/Operator

Trigger: „faza współdecyzji zbiegła do jasnego planu, czas wykonać".

Akcja: jawne przekazanie postawy. Tryb partner się kończy; zaczyna ownership albo
operator. Zadeklaruj to.

### Dowolna → rekalibracja Vibecraftsmanship

Trigger: dowolne z:

- operator nazywa korektę framingu (rescheduled-not-retired,
  equal-intensity-not-ranked, brief-brevity-rule)
- empiryczny współczynnik kompresji ujawnia, że szacunek był o rząd
  wielkości błędny
- wzorzec awarii podłoża powtarza się u wielu agentów (sygnał,
  że sama strategia podłoża wymaga przemyślenia)
- cisza operatora przez >10 min na pytanie, które wymaga odpowiedzi

Akcja: wywołaj vibecraftsmanship, aby nazwać, która oś jest zepsuta (gust /
siła / rzeczywistość), wyrównaj ponownie, potem wejdź w odpowiednią kartę
taktyczną.

---

## Antywzorzec: wywoływanie vibecraftsmanship, gdy wystarcza karta taktyczna

Vibecraftsmanship to **5. karta**, przeznaczona na meta-momenty. NIE
wywołuj jej dla:

- „zaimplementuj feature X" (użyj vc-ownership albo vc-implement)
- „zdispatchuj 3 fale pracy" (użyj vc-operator)
- „debuguj ze mną ten problem" (użyj vc-partner)
- „uruchom testy" (użyj techniki bezpośrednio)
- „zrób review tego PR-a" (użyj vc-review)

Wywołuj vibecraftsmanship, gdy pytanie dotyczy **samej postawy**,
nie pracy.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
