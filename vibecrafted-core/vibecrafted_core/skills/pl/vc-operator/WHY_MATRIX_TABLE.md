Operator mode active — W2-A WHY_MATRIX_TABLE

# vc-operator — WHY_MATRIX_TABLE

Źródło prawdy dla kroku 4 w `RUNNER.md`. Wybierz `recommended_agent` przez lookup:
`(task_kind, sensitivity)` -> uszeregowani agenci. Następnie wpisz wybranego agenta plus
jedno uzasadnienie z lookupu we frontmatter dispatchu. Ta tabela routuje wszystkich trzech
frontierowych peerów wg mocnych stron; Gemini nigdy nie jest wykluczany z powodu tarcia narzędziowego.
Kolejność rankingu od najlepiej dopasowanego; wybieraj rank 1, chyba że zachodzi override
wrażliwości albo uczciwy remis.

| task_kind                           | domyślna wrażliwość                                                               | uszeregowani agenci          | uzasadnienie lookupu                                                                                                                                                                                                 |
| ----------------------------------- | --------------------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| research                            | szeroki skan evidence, niepewny teren                                             | 1. gemini 2. claude 3. codex | Gemini pierwszy do dalekosiężnego reframingu i syntezy; Claude drugi do narracji evidence; Codex trzeci, gdy research musi skondensować się do dokładnych komend.                                                    |
| reframing                           | niejednoznaczny plan, niejasny kształt produktu lub architektury                  | 1. gemini 2. claude 3. codex | Gemini pierwszy do alternatywnych framów i poszerzania przestrzeni opcji; Claude drugi do czytelnych dla człowieka tradeoffów; Codex trzeci do przekucia wybranego framu w konkretne cięcia.                         |
| single_shot_implementation          | jeden bounded feature, kilka plików, brak rodzeństwa na współdzielonym pliku      | 1. codex 2. gemini 3. claude | Codex pierwszy do precyzyjnej bounded implementacji; Gemini drugi, gdy slice'owi pomaga większy kontekst; Claude trzeci, gdy proza follow-upu liczy się bardziej niż gęstość kodu.                                   |
| wide_implementation_with_many_edits | wiele plików, wysokie ryzyko pętli edycji                                         | 1. codex 2. claude 3. gemini | Codex pierwszy do wąskiej dyscypliny stagingu; Claude drugi do ostrożnego, popartego raportem postępu; Gemini trzeci, bo bieżące narzędzia pokazały ryzyko pętli przy szerokiej edycji, a nie wykluczenie zdolności. |
| surgical_edits_known_file           | dokładny plik i kontrakt znane                                                    | 1. codex 2. claude 3. gemini | Codex pierwszy do precyzji na poziomie linii; Claude drugi do ostrożnych edycji forensicznych; Gemini trzeci, chyba że szerszy kontekst zmienia odpowiedź lokalną dla pliku.                                         |
| doc_authoring                       | trwała doktryna, dokumenty dla operatora, kontrakt prozy                          | 1. claude 2. gemini 3. codex | Claude pierwszy do czytelnej doktryny i kształtu raportu; Gemini drugi do ekspansywnego framingu; Codex trzeci do zwięzłych tabel i dokumentów wiernych komendom.                                                    |
| lookup_table_authoring              | jawna macierz, checklista, szablon dispatchu, markdown schematyczny               | 1. codex 2. claude 3. gemini | Codex pierwszy do deterministycznego kształtu tabeli; Claude drugi do dopracowania sformułowań; Gemini trzeci do sprawdzenia, czy kategorie nie pomijają szerszego wzorca operatorskiego.                            |
| audit_forensics                     | przegląd ukończonej pracy, archeologia porażek, triage raportów                   | 1. claude 2. codex 3. gemini | Claude pierwszy do findingów uszeregowanych po evidence; Codex drugi do dowodu z runtime'u i reprodukcji komend; Gemini trzeci do syntezy drugiej opinii w poprzek zaszumionych raportów.                            |
| polarization_decision_making        | wybór jednego kierunku po zaszumionych marbles lub konkurujących planach          | 1. gemini 2. claude 3. codex | Gemini pierwszy do zbieżności na poziomie big-picture; Claude drugi do wyjaśnienia decyzji; Codex trzeci do uczynienia wybranej ścieżki wykonywalną.                                                                 |
| refactor_at_scale                   | zmiana strukturalna w poprzek modułów, wielu konsumentów                          | 1. claude 2. codex 3. gemini | Claude pierwszy do ostrożnego rozumowania wielo-plikowego; Codex drugi do kontrolowanych edycji i bramek; Gemini trzeci do alternatyw architektonicznych, zanim cięcie zostanie sfinalizowane.                       |
| recovery_dispatch                   | wcześniejszy worker się zaciął, substrat zatruty albo padła bramka wymaga naprawy | 1. codex 2. claude 3. gemini | Codex pierwszy do reprodukcji porażki i ciasnego patchowania; Claude drugi do forensicznego domknięcia; Gemini trzeci, gdy odzyskiwanie potrzebuje reframingu, a nie bezpośredniej naprawy.                          |
| release_surface_hydration           | dokumenty instalacji, onboarding, marketplace, powierzchnia wiarygodności         | 1. claude 2. gemini 3. codex | Claude pierwszy do copy powierzchni zaufania i kompletności; Gemini drugi do perspektywy pierwszego użytkownika; Codex trzeci do okablowania dokładnych komend i manifestów.                                         |

## Override'y wrażliwości

Użyj najpierw domyślnego wiersza, a potem zastosuj najwęższy pasujący override.

| profil wrażliwości                                                       | override kolejności     | dlaczego                                                                |
| ------------------------------------------------------------------------ | ----------------------- | ----------------------------------------------------------------------- |
| ciasny budżet tokenów, dokładne komendy, dokładny scope pliku            | codex > claude > gemini | Precyzja i niska ceremonia liczą się bardziej niż eksploracja.          |
| narracja w długim kontekście, framing founder/produkt, niejasne dlaczego | gemini > claude > codex | Większa powierzchnia reframingu liczy się przed wykonywalnymi cięciami. |
| evidence w stylu legal/security/incident, raport musi przetrwać audyt    | claude > codex > gemini | Findingi potrzebują jawnej severity, evidence i zaufania czytelnika.    |
| ryzyko kolizji na współdzielonym pliku lub brudne Living Tree            | codex > claude > gemini | Wygrywa wąski staging i dyscyplina przy porażce substratu.              |
| brief kreatywny, nazewnictwo, copy launchowe, emocjonalny rail           | claude > gemini > codex | Ton i trwała proza są głównym deliverable.                              |
| szerokie porównanie benchmarkowe lub rynkowe                             | gemini > codex > claude | Najpierw szerokość eksploracji, potem weryfikacja wierna komendom.      |

## Nota o rozstrzyganiu remisów

Gdy lookup zostawia dwóch lub trzech agentów jednakowo dopasowanych, wybierz wg bieżącego
kontekstu (fokus operatora, worker poprzedniej fali, bieżące obciążenie). AGENT FAIRNESS
to nie kwota rotacji — to uczciwe przypisanie autorstwa i równa godność.
Nie dispatchuj round-robinem; dispatchuj wg dopasowania.

## Granulacja dispatchy zależna od modelu

Model parity jest podłogą, a granulacja określa ilość spójnej pracy należącej
do jednego dispatchu. Używaj `agent_dispatch.dispatch_granularity(model)`
zamiast traktować każdy model jak anonimowego workera o identycznym rozmiarze.

| klasa modelu                                           | kształt cuta | pliki na cut |                    równoległe cuty | powód                                                                      |
| ------------------------------------------------------ | ------------ | -----------: | ---------------------------------: | -------------------------------------------------------------------------- |
| frontier (`opus`, GPT-5.5/5.6, Gemini Pro, Grok Build) | coherent     |         do 8 | do 3 przy rozłącznych scope plików | Amortyzuj powtarzany kontekst i zachowaj rozumowanie nad całym kontraktem. |
| standard (`sonnet`, GPT-5, Gemini auto/default)        | bounded      |         do 4 |                               do 2 | Utrzymuj jawne szwy integracyjne bez nadmiernej fragmentacji.              |
| economy (`haiku`, Spark, Flash)                        | surgical     |         do 2 |                                  1 | Małe sekwencyjne powierzchnie dowodu ograniczają drift i koszt retry.      |
| nieznany model                                         | surgical     |            1 |                                  1 | Brak telemetrii nie jest zgodą na szeroki dispatch.                        |

Koszt zgłoszony przez providera wygrywa. Gdy go nie ma, akceptuj tylko jawny
estimate z `cost_source: estimated:<rate-card>`; nigdy po cichu nie zamieniaj
nieznanego kosztu na zero. Koszt wpływa na cut, ale nie pozwala obniżyć tieru.

## Noty ze stopki

- AGENT PEER PARITY: Claude, Codex i Gemini to peerowi frontierowi workerzy. Routuj
  wg dopasowania do zadania i ergonomii narzędziowej; nie traktuj tarcia narzędziowego
  jako niższości modelu.
- AGENT MODEL PARITY: tier rodzica ustala tier workera. Rodzic Opus -> worker Opus;
  żadnych tanich skanów, żadnych skrótów równoległych na niższym tierze.
- AGENT FAIRNESS: każde `Authored-By:` commita pasuje do agenta, którego ręce
  napisały kod. Żadnego round-robina, żadnej kwoty; tylko uczciwe przypisanie autorstwa.
- Krok 4 w `RUNNER.md` konsumuje tę tabelę jako `(task_kind, sensitivity) -> agent`.
  Ciało dispatchu powinno nieść wybranego agenta i jednoliniowe uzasadnienie.

```text
=======================
Operator agents pick by lookup, not by judgment. Mermaid was prose;
table is verdict. Gemini is not a defect — it is a different reach.
Route, do not reject.
( •_•)>⌐■-■
=======================

Suchar: Czemu tabela nigdy nie kłóci się z agentem?
Bo już napisała wiersz. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024-2026_
