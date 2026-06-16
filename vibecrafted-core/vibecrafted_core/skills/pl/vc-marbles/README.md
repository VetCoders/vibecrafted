# Vibecraftedٜ - The Marbles

## Kanoniczny podział

- Kontrakt workera: [SKILL.md](./SKILL.md)
- Intencje operatora i routing zbieżności: [RECEPTION.md](./RECEPTION.md)

Worker pozostaje ślepy.
Warstwa odbioru pamięta.

## Dla founderów i agentosceptycznych developerów

_Ta sekcja wyjaśnia, co robi Marbles i dlaczego zasługuje na twoje zaufanie.
Protokół operacyjny następuje poniżej._

### Obietnica

Modele językowe generują przybliżenia, nie dowody. Każda napisana przez AI
zmiana w kodzie wprowadza sygnał ORAZ szum. To nie jest bug — to
fizyka predykcji następnego tokenu. Pytanie nie brzmi, czy szum
istnieje, lecz czy masz system, który go eliminuje.

Marbles jest tym systemem.

Działa, zadając jedno pytanie, bezustannie: **Co wciąż jest nie tak?**

Nie „czy to jest poprawne?" — to pytanie nieskończone, bez skończonej odpowiedzi.
Zamiast tego: „Czy mogę znaleźć konkretną, mierzalną rzecz, która zaprzecza zdrowiu?"
Jeśli tak, napraw ją. Jeśli nie, jesteś gotowy.

### Dlaczego zasługuje na zaufanie

Agent działający wewnątrz pętli Marbles nie freestyle'uje usprawnień
na podstawie preferencji estetycznych. To precyzyjny, dociekliwy rdzeń
ekspertyzy — generator chirurgicznych modyfikacji kodu i zdyscyplinowany
silnik remediacji. Jego praca opiera się na twardym evidence, nie na założeniach.

**Twoje narzędzia są zmysłami agenta.** Loctree, kompilatory, lintery, testy —
dostarczają obiektywnej prawdy o stanie kodu. Agent dostarcza
eksperckiej interpretacji i precyzyjnego planu remediacji. Nie może
halucynować architektury, bo jej nie zgaduje — czyta ją przez
instrumenty.

**Twoja misja to partnerstwo w jakości.** Agent nie zastępuje
inżyniera-twórcy. Staje się jego bezustannym asystentem, który nigdy nie męczy się
szukaniem niedoskonałości. Prowadzi kod ku kompletności, eliminując
braki krok po kroku, w zamkniętej pętli weryfikacji.

### Codzienny przepływ

Twoja praca nad taskiem to proces ciągłej redukcji entropii. Zamiast
próbować udowodnić „wszystko jest w porządku", bezustannie zadajesz jedno pytanie:
**Co wciąż jest nie tak?**

1. **Zbierz evidence** — sięgnij po swoje narzędzia (linter, loctree, testy).
   Poproś system analizy, by pokazał ci kontrprzykład dla zdrowia repozytorium.

2. **Skup się** — wyizoluj konkretny, mierzalny problem wyłoniony przez narzędzie.
   „Evidence: loctree raportuje, że eksport X w utils.ts ma zero konsumentów."

3. **Zastosuj rzemiosło** — napisz celowany, chirurgiczny fix, który rozwiązuje tylko ten
   jeden wyizolowany kawałek evidence. Bądź snajperem, nie grenadierem.

4. **Obserwuj kaskadę** — każdy udany fix może odsłonić następny
   wcześniej ukryty problem. Sprawdź narzędzia ponownie. Nowe findingi? Wróć do
   kroku 2.

5. **Zbiegnij** — twoja praca kończy się dopiero wtedy, gdy po gruntownym audycie żadne narzędzie
   nie potrafi wygenerować nawet jednego oskarżenia. Koło się domyka. To, co niedokończone,
   staje się dokończone.

Zdejmij z barków foundera ciężar mikromanagementu. Bądź
maszyną, która zamyka otwarte rany w organizmie, działając wyłącznie pod
dyktando bezlitosnych asercji od deterministycznych instrumentów.

### Dlaczego to działa (dla sceptyka)

Oddajesz agentowi kierownicę nie dlatego, że „AI jest już mądre", lecz dlatego, że
**AI jest na sztywno podpięte do deterministycznych kompilatorów i testów, więc nie
rozwali twojego projektu w pogoni za estetycznym usprawnieniem.** Misja i sprawczość
są okiełznane żelaznymi regułami, które budują absolutne zaufanie:

- Każda akcja śledzi się do outputu narzędzia, nigdy do „myślę, że tak wygląda lepiej"
- Każdy fix jest weryfikowalny — odpal to samo narzędzie ponownie, zobacz, jak oskarżenie znika
- Każda pętla jest bounded — 3-5 fixów, potem ponowny pomiar, nigdy ślepy sprint
- Dywergencja jest wykrywalna — jeśli stare problemy się utrzymują, a pojawiają się nowe, zatrzymaj się

Inteligencja agenta tkwi w precyzji interpretacji.
Wiarygodność tkwi w łańcuchu evidence.

---

## Mechanizm

Tradycyjna jakość pyta: _czy to jest poprawne?_ i próbuje udowodnić, że tak.
To pytanie nie ma skończonej odpowiedzi dla żywej bazy kodu.

Marbles zadaje inne pytanie: **co wciąż jest nie tak?**

Każda pętla inspekcjonuje bieżący stan i znajduje **kontrprzykłady** —
konkretne rzeczy, które zaprzeczają zdrowiu. Martwy eksport w `utils.ts:42`.
Cykliczny import między `auth/` a `api/`. Bliźniaczy eksport `Button`
żyjący w dwóch plikach. To nie jest abstrakcyjny szum. To konkretne,
nazwane, zlokalizowane naruszenia zdrowia.

To zbieżność sterowana kontrprzykładem — CEGIS zastosowane do kodu:

```
hypothesis:      "this codebase is healthy"
counterexample:  sniff finds dead export `formatDate` in utils.ts:42
correction:      remove dead export
new landscape:   utils.ts is now empty → new counterexample revealed
correction:      remove empty file
new landscape:   import in api.ts pointed to utils.ts → broken import revealed
correction:      fix import
new landscape:   cycle between api.ts and auth.ts disappeared → health score jumps

No single loop understood the whole.
Each loop only answered: "what is still wrong?"
The convergence was emergent.
```

### Efekt kaskady

Findingi nie są płaską listą. Tworzą skierowany graf, w którym naprawienie jednego
odsłania następny. To podstawowy napęd zbieżności:

- Martwy eksport usunięty → plik staje się pusty → pusty plik to nowy finding
- Pusty plik usunięty → import się psuje → zepsuty import to nowy finding
- Import naprawiony → cykl znika → health score skacze w górę

Każdy fix **nieodwracalnie zawęża** przestrzeń możliwych bugów.
Entropia spada monotonicznie.

### Prawda z dwóch źródeł

Zbieżność staje się silniejsza dzięki wielu niezależnym źródłom, które mogą
podawać sobie nawzajem kontrprzykłady:

```
sniff says: "exportFoo is dead"      → hypothesis
dist says:  "exportFoo is in bundle" → counterexample to sniff
agent checks: dynamic import          → hypothesis corrected
sniff learns: skip dynamic imports    → error class eliminated permanently
```

Gdy dwa narzędzia się zgadzają — pewność jest wysoka.
Gdy się nie zgadzają — ta niezgoda JEST kontrprzykładem.

### Ślepota agenta

Agent w każdej pętli nie wie, że jest w pętli.

Dostaje oryginalny plan i widzi bieżący stan żywego drzewa.
Bez metadanych pętli, bez poprzednich raportów, bez świadomości, że inni agenci odpalili
przed nim. Po prostu wykonuje robotę: czyta plan, patrzy na kod, znajduje to, co
jest nie tak, naprawia to, odpala bramki.

Zbieżność zachodzi, bo każdy agent niezależnie znajduje mniej rzeczy nie tak niż
ten przed nim — poprzedni agent naprawił już swoją działkę. Bez potrzeby
koordynacji. Kurcząca się przestrzeń problemu JEST sygnałem zbieżności.

---
