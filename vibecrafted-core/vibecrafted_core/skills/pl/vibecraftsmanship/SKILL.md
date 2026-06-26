---
name: vibecraftsmanship
description: "Meta-doctrine for human taste, agent force, Loctree/AICX structure, and reality-tested shipping posture."
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# Vibecraftsmanship — Karta meta-doktryny

> "Vibecraftsmanship to ustrukturyzowana, wspólna inżynieria ludzi i AI.
> To nie jest ślepe pisanie promptów. Ludzki gust wyznacza kierunek.
> Agentyczna siła rozszerza przestrzeń poszukiwań. Rzeczywistość decyduje
> o tym, co przetrwa."

Piąta karta. Tam gdzie ownership/operator/partner deklarują każdy **jak działać**,
vibecraftsmanship deklaruje **jak myśleć o działaniu** — i co czyni to działanie uczciwym.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Przegląd

Vibecraftsmanship to nie workflow. To **postawa nad postawami** — meta-decyzja, którą
operator i operator-agent podejmują wspólnie, zanim którekolwiek z nich wybierze kartę
taktyczną. To kompas, który mówi ci, _której_ z trzech postaw (ownership, operator,
partner) wymaga bieżąca praca, oraz filtr przetrwania, który mówi ci, czy praca
faktycznie się dowiozła, czy tylko odegrała dowiezienie.

Trzy osie, wszystkie operacyjne jednocześnie, żadna nieopcjonalna:

1. **Ludzki gust** — kierunek. Operator wybiera, co tworzyć, dlaczego i co znaczy tu
   „dobre". Gust to nieruchoma kotwica; agenci go rozszerzają, nigdy nie zastępują.
2. **Agentyczna siła** — rozszerzanie przestrzeni poszukiwań. Równolegli agenci,
   roje triple-research, pętle marbles, dispatch cross-tier — to mnoży powierzchnię
   możliwości, spośród których operator może wybierać.
3. **Rzeczywistość** — filtr przetrwania. Kod, który się kompiluje, testy, które
   przechodzą, bramki, które robią się zielone, commity, które lądują, klienci, którzy
   kupują. To, co przetrwa kontakt z rzeczywistością, się liczy; to, co nie — jest
   informacją, nie dostarczeniem.

Te trzy nie są ważone. To ograniczenia, które wszystkie muszą być spełnione jednocześnie.
Kierunek bez poszukiwań daje małe pomysły dobrze wykonane. Poszukiwania bez kierunku
dają szum. Każde z nich bez rzeczywistości daje dema. Wszystkie trzy razem dają dowieziony
produkt.

## Kiedy używać

Uruchamiaj vibecraftsmanship, gdy **żadna z kart taktycznych jeszcze nie pasuje** —
bo pytanie jest strukturalne, nie operacyjne. Konkretnie:

- **Decyzja o postawie na starcie sesji** — przed wywołaniem jakiejkolwiek karty taktycznej:
  „czy ta praca to cięcie ownership, fala operator, czy triage partner?"
- **Korekta dryfu framingu** — operator zauważa, że agent działa w złej postawie
  (jedzie solo, gdy potrzebne było wspólne sterowanie; koordynuje flotę, gdy pracą jest
  jeden slice; partneruje, gdy autoryzowano dostarczenie).
- **Sanity-check konwencjonalnego szacunku** — gdy konkurencyjne źródło (szacunek
  Gemini, konwencjonalny osobodzień, „wszyscy mówią X tygodni") wydaje się błędne;
  uruchom, aby zastosować przeskalowane dowody empiryczne.
- **Audyt przestrzeni poszukiwań** — „czy zbadaliśmy dość alternatyw, czy committujemy
  się przedwcześnie?". Vibecraftsmanship wymaga uczciwej odpowiedzi.
- **Audyt przetrwania** — „czy to faktycznie dowieziono, czy tylko odegraliśmy
  dowiezienie?". Gdy podejrzewasz, że praca jest zielona-na-papierze, ale nie realna.

NIE uruchamiaj vibecraftsmanship dla: ograniczonego taska kodowego (użyj vc-ownership),
wielofalowego dispatchu (użyj vc-operator) ani wspólnego triage (użyj vc-partner).
Ta karta jest na moment **przed** tymi decyzjami.

## Domyślny tryb operacyjny — zewnętrzna powierzchnia dispatchu

**TWARDA ZASADA (egzekwowanie osi Siły):** Gdy agent zamierza zdispatchować zewnętrzną
flotę (Codex / Claude / Gemini jako równoległych workerów produkujących artefakty-dostawy
— raporty, kod, plany), domyślną powierzchnią wykonania jest **`vibecrafted <workflow>
<agent>` przez Bash**, NIGDY natywne narzędzie `Agent`. Natywny `Agent` jest
zarezerwowany dla zwiadu w procesie (Explore, ogólny lookup, szybki research tylko do
odczytu), nie dla workerów-dostawców.

**Powód:** zewnętrzny dispatch przez `vibecrafted` tworzy kanoniczny katalog
(`~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/`), trwałe transkrypty, status
`meta.json`, odtwarzalny `launch.sh` — obserwowalność klasy operatorskiej. Natywny
`Agent` ukrywa pracę w ulotnym wyjściu taska, które znika z kontekstu rodzica po powrocie
z wywołania, nie zostawiając żadnego odzyskiwalnego artefaktu dla operatora, post-mortemu
ani innych agentów.

**Sygnał wykrycia (STOP i przekieruj):** jeśli łapiesz się na wywoływaniu
`Agent(run_in_background: true)` z briefem dłuższym niż ~200 słów, który produkuje
artefakty na dysku — to worker-dostawca przebrany za zwiadowcę. Przekieruj przez
`vibecrafted`. To samo dotyczy każdego wieloagentowego równoległego dispatchu z wymogami
trwałości.

**Odruchowy check przed dispatchem:**

1. Czy ci agenci produkują dostawy (raporty, kod, plany)? → `vibecrafted`
2. Czy ci agenci robią zwiad / lookup / tylko odczyt? → natywny `Agent` ok
3. Jeśli wybrano `vibecrafted`: zobacz [vc-agents](../vc-agents/SKILL.md) po routing
   agentów (codex/claude/gemini wg `vc-why-matrix`) oraz
   [vc-operator](../vc-operator/SKILL.md) po prowadzenie kształtu fal.

Ta zasada istnieje, bo **dyscyplina przegrywa z ergonomią**. Natywny `Agent` jest
pierwszym, po co agent sięga, bo jest na liście narzędzi najwyższego poziomu.
`vibecrafted` to jeden skok przez Bash dalej — trochę więcej tarcia. Bez jawnego
domyślnego trybu operacyjnego odruch zawsze wygrywa. Karta bez operacyjnych zębów = dryf
dozwolony.

## Domyślny tryb operacyjny — autonomiczne samodzielne tempo (natywne dla Claude Code)

**TWARDA ZASADA (egzekwowanie osi Siły, druga kanoniczna powierzchnia):** Gdy agent
wchodzi w zachowanie autonomiczne — operator nieobecny, decyzje odroczone, cykliczny
monitoring, wieloturowe wykonanie bez ręcznych re-promptów — domyślnym mechanizmem jest
natywny dla Claude Code skill **`/loop`** (odpowiednik: `ScheduleWakeup` z sentinelem
`<<autonomous-loop-dynamic>>` dla trybu dynamicznego tempa). NIE ciche czekanie. NIE
polling w ciasnych sleepach Basha. NIE „po prostu odpowiem w następnej turze, kiedy
operator wróci".

**Powód:** `/loop` to kanoniczna power-funkcja Claude Code do autonomicznego samodzielnego
tempa — wypełnia lukę między „operator prowadzi każdą turę" a „agent odpala i zapomina".
Bez wejścia w `/loop` agent cofa się do jednoturowej bierności: operator musi
re-promptować, żeby kontynuować pracę, nawet gdy kolejne kroki są oczywiste. `/loop`
czyni autonomiczny ogon agenta obserwowalnym i ograniczonym (interwał heartbeat,
harmonogram fallback, jawny warunek stopu).

**Kiedy wejść w `/loop`:**

- Operator zadeklarował „bez odbioru" / „decyduj autonomicznie" / „wychodzę"
- Oczekiwanie na pracę zewnętrzną (CI, zdispatchowana flota, długo trwający build)
- Wielofalowy dispatch, gdzie fale kończą się asynchronicznie
- Operacja na podłożu ze znanym oknem oczekiwania (rebase, instalacja, sync)
- Cykliczna obserwacja (niańczenie PR-ów, monitoring deploya)

**Kiedy NIE wchodzić w `/loop`:**

- Jednoturowa odpowiedź bez kontynuacji
- Operator aktywnie zaangażowany w rozmowę
- Praca jawnie zawężona do „zrób tę jedną rzecz i stop"

**Złożenie z zewnętrznym dispatchem:**

- Zewnętrzny dispatch (`vibecrafted <workflow> <agent>`) produkuje pracę asynchroniczną,
  która wymaga `await`. Wejdź w `/loop`, aby utrzymać heartbeat między zdarzeniami
  `task-notification` z harnessu.
- `/loop` + `vibecrafted` = kanoniczny wzorzec autonomicznego operatora. Jeden deklaruje
  „pozostaję zaangażowany"; drugi deklaruje „używam obserwowalnej powierzchni
  zewnętrznej". Oba razem = w pełni zrealizowana oś Siły vibecraftsmanship.

**Sygnał wykrycia (STOP i wejdź w loop):** jeśli łapiesz się na kończeniu tury słowami
„ruch należy do operatora" lub „czekam na odpowiedź", podczas gdy istnieje już
autoryzowana praca w kolejce, która mieści się w bieżącym zakresie i warunkach stopu —
to przeoczone wejście w `/loop`. Przemyśl od nowa: zaplanuj samodzielnie tempowany check,
zadeklaruj, co zrobisz na każdym ticku, zatrzymaj się, gdy warunek stopu zostanie spełniony.

## Zależności

- [vc-ownership](../vc-ownership/SKILL.md) — postawa solowego dostarczania end-to-end
- [vc-operator](../vc-operator/SKILL.md) — postawa prowadzenia wielofalowej floty
- [vc-partner](../vc-partner/SKILL.md) — postawa wspólnego sterowania wykonawczego
- [vc-init](../vc-init/SKILL.md) — fundamentowa bramka percepcji przed kartą
- [vc-agents](../vc-agents/SKILL.md) — wymagane dla domyślnego trybu operacyjnego
  (dispatch zewnętrznej floty przez `vibecrafted`, NIGDY natywny `Agent`)

Vibecraftsmanship odwołuje się, ale nie zastępuje. Komponuje trzy postawy w jeden spójny
kształt partnerstwa. Zobacz [COMPOSITION.md](./COMPOSITION.md).

## Trzy osie

Tu skrótowo. Pełne pogłębienie w [AXES.md](./AXES.md).

### 1. Ludzki gust (gust = kierunek)

Operator jest właścicielem: co tworzyć, dlaczego teraz, jak wygląda „dobre", który
kręgosłup jest główny (albo czy wszystkie mają równą intensywność), które framingi są
uczciwe. Agenci proponują; operator wybiera. Gdy agent wybiega naprzód z framingiem
nieautoryzowanym przez operatora, to **dryf** — zatrzymaj się, wyrównaj ponownie.

Antywzorzec: agent ranguje/priorytetyzuje/rekomenduje w sposób, o który operator nigdy
nie prosił (framing „główny kręgosłup vs równoległe R&D", gdy operator chciał 4 równych labów).

### 2. Agentyczna siła (siła agentów = przestrzeń poszukiwań)

Agenci rozszerzają powierzchnię możliwości. Równoległy dispatch (Fala B, 4 laby
jednocześnie), triple-research (claude+codex+gemini te same pytania), pętle marbles
(zbieżność przez iteracje), cross-tier (sprawiedliwość peer-frontier), izolacja cwd per
lab. Chodzi NIE o prędkość — chodzi o to, że operator może wybierać z szerszego menu,
niż dałaby szeregowa praca człowieka w tym samym oknie.

Antywzorzec: agenci wywoływani szeregowo, gdy możliwa była równoległość. Pojedynczy agent
zdispatchowany, gdy 3 perspektywy by triangulowały. Zmockowane wyjścia, gdy dostępne
były realne dowody.

### 3. Rzeczywistość (rzeczywistość = filtr przetrwania)

Commity lądują albo nie. Bramki robią się zielone albo czerwone. Buildy się udają albo
podłoże zawodzi. Klienci kupują albo odchodzą. Vibecraftsmanship traktuje **to, co
przetrwa kontakt z rzeczywistością** jako jedyną uczciwą metrykę. Dema się nie liczą.
Zmockowane testy się nie liczą. „Zaimplementowałem to" bez commita się nie liczy.

Empirycznie: w sesji z 2026-05-24 przetrwało 5 z 6 implementacji Fali A/B (realne commity
w realnych repo z realnymi dowodami z bramek). 1 trafiła na awarię podłoża (brak B-4
krunvm) — to informacja, nie dostarczenie. Konwencjonalny szacunek 18-32 tygodni na tę
samą powierzchnię został empirycznie sfalsyfikowany przez faktyczne dostarczenie w 3
godziny. Pensieve, premium edytor markdown: gemini szacował 3-6 miesięcy, rzeczywistość
dowiozła w 28 godzin. Rzeczywistość wygrywa.

Antywzorzec: ogłaszanie ukończenia bez commita. Oznaczanie PASS bez dowodów z bramki.
Szacowanie bez odniesienia do wcześniejszego empirycznego współczynnika kompresji.

## Złożenie z kartami taktycznymi

Vibecraftsmanship przecina w poprzek **3 postawy**, nie 10 technik, 2 fundamenty czy
4 skille późnego etapu. Tabela routingu w [COMPOSITION.md](./COMPOSITION.md).

## Dowody empiryczne

Ta sesja (2026-05-24) to kanoniczne studium przypadku. Oś czasu, decyzje i falsyfikacje
w [EVIDENCE.md](./EVIDENCE.md).

## Antywzorce

- **Dryf w locie** bez nazwania go: operator zauważa agenta w złej postawie, ale nie
  koryguje → zmarnowane cykle dispatchu
- **Szacowanie w konwencjonalnych osobodniach (ED)** bez świadomości empirycznej
  kompresji → błędne decyzje o zakresie
- **Rankowanie-gdy-prawdą-była-równa-intensywność**: agent narzuca
  primary/secondary/tertiary na równoległe opcje operatora
- **Odgrywanie poszukiwań**: dispatchowanie 3 agentów, gdy 1 to właściwa odpowiedź,
  albo 1, gdy 3 perspektywy wyłapałyby martwy punkt
- **Pomijanie sprawdzenia przetrwania**: ogłaszanie gotowości bez zielonej bramki +
  wylądowanego commita + kontaktu z rzeczywistością
- **Uruchamianie karty taktycznej bez decyzji o postawie**: wskakiwanie w vc-operator,
  gdy pracą był 1 slice (vc-ownership) albo wspólna decyzja (vc-partner)
- **Briefy dłuższe niż lądujące commity**: operator-agent pisze rozwlekłą ceremonię,
  ale workery dowożą więcej LOC, niż wyjaśniają briefy — odwróć proporcję
- **Zapominanie, że techniki są ortogonalne**: marbles/research/audit/review/polarize/prune
  to narzędzia dostępne w KAŻDEJ postawie, nie same wybory postawy

## Styl wyjścia

Domyślnie: powiedz, która oś jest aktualnie nośna dla następnego ruchu. Przykłady:

- „Decyzja gustu: wybiera operator. Opcje na stole: A, B, C z trade-offami."
- „Decyzja siły: poszukiwania niedostatecznie zbadane. Spawnowanie triple-research."
- „Decyzja rzeczywistości: commity wylądowały, ale bramki czerwone — przetrwania jeszcze nie ma."

Gdy wszystkie trzy są wyrównane, zadeklaruj to: „Triada wyrównana, można dispatchować.
Postawa: operator. Karta taktyczna: vc-operator. Go."

## Klamra końcowa

```text
=======================
Triada ponad taktykę. Postawa ponad narzędzie. Rzeczywistość ponad deklaracje.
Operator wybiera. Agenci rozszerzają. Rzeczywistość decyduje.
( ◕ ◡ ◕)
=======================

Suchar: Dlaczego triada nigdy się nie psuje? Bo każda oś łapie to,
czego nie widzą dwie pozostałe. (._.)
```

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
