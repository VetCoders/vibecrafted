---
name: what_is_vibecrafted_pl
version: 0.1.0
description: >
  A convergence framework for AI-native software development.
  Architecture manifesto (Polish version).
---

# Vibecrafted. — Manifest Architektury

## Definicja

**Vibecrafted.** to framework konwergencji dla AI-assisted software development, zbudowany przez VetCoders.
Nie służy jedynie do generowania kodu. To **system**, w którym kod pisany przez agentów AI jest systematycznie doprowadzany do jakości produkcyjnej — poprzez zamknięte pętle weryfikacji, strukturalne narzędzia analityczne i multi-agentową orkiestrację.

## Rdzeń Filozoficzny

Największym ograniczeniem AI w programowaniu nie jest brak sztucznej "inteligencji", lecz rosnąca wraz ze wzrostem wielkości projektu entropia i halucynacje.
Zamiast żądać od modeli bezbłędnego kodu przy pierwszym podejściu, architektura Vibecrafted. opiera się na **procesie**.
Zadaje agentom bezlitosne pytanie: _"Co jest jeszcze źle?!"_ — a następnie zmusza ich do rygorystycznej weryfikacji własnej pracy w pętli opierającej się na kontrprzykładach (counterexample convergence), aż do ostatecznego zamknięcia pętli jakościowej.

## Geneza (Origin Story)

Wszystko zaczęło się od dwojga lekarzy weterynarii z Polski, biorących udział w kursie na Harvard Medical School ("AI in Health Care: From Strategies to Implementation"). Postanowili zbudować zaawansowaną aplikację wspierającą lekarzy weterynarii w ulepszaniu i interpretowaniu obrazów USG przy użyciu AI. Nie mieli doświadczenia w programowaniu. Zamiast uczyć się kodować od zera, zaczęli po prostu delegować zadania do agentów AI.
Baza kodu z czasem rozrosła się na tyle, że ci agenci przestali rozumieć szerszy kontekst. Zamiast rozwijać produkt, niszczyli go — dopisując zbędne łatki po to, by ratować już raz zaimplementowane funkcjonalności. Wtedy czysta upartość wymusiła na nich sformułowanie nowej, rygorystycznej metodologii.
Gdy bezwzględny system zasad iteracyjnej weryfikacji zaczął sprawnie wykorzystywać modele AI, nowa metoda wymknęła się ramom "zwykłego narzędzia". Stała się spójnym frameworkiem.
**Frameworkiem, który z czasem ugruntował się na tyle mocno, że w końcu napisał, ulepszył i zbudował samego siebie.**

## Ontologia Narzędziowa

| Warstwa            | Narzędzie                           | Zasada Działania                                                                                                                      |
| ------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Zmysły**         | Loctree                             | Strukturalna analiza codebase — martwy kod, cykle, zależności, blast radius. Agent nie zgaduje architektury — czyta ją.               |
| **Orientacja**     | vc-init                             | Trzy bazy przed działaniem: pamięć (co zrobiono), wzrok (stan kodu teraz), prawda (czy kompilator i linty działają).                  |
| **Konwergencja**   | vc-marbles                          | Pętla rygorystycznej walidacji i naprawy. Eliminacja kontrprzykładów w kaskadach zmian (tryb solo, duo, trio, wieloagentowy).         |
| **Orkiestracja**   | vc-agents                           | Wywoływanie konkretnych i sprofilowanych agentów w tle (headless), z zachowaniem raportowania, stałych transkryptów i logiki `aicx`.  |
| **Jakość**         | vc-followup, vc-dou                 | Followup jako twarda recenzja po wdrożeniach. DoU (Definition of Undone) mierzy dystans oddzielający projekt od wejścia na produkcję. |
| **Dystrybucja**    | vc-decorate, vc-hydrate, vc-release | Pakietowanie, estetyka, dystrybuowanie z repozytorium prosto jako instalowalny produkt i marka.                                       |
| **Bezpieczeństwo** | rust-ai-locker                      | Rozdzielenie procesów budowania — gwarantuje, że agenci asynchroniczni nie crashują maszyny jednoczesną ciężką kompilacją.            |

## Dowód Koncepcji (Proof of Concept)

Vibecrafted. jest żywym dowodem na własną poprawność. Pełen framework zaprojektował dla siebie skille, mechanizmy działania, CI (Continuous Integration), installer oraz landing page. Każda zmiana realizowana za pomocą tego systemu posiada konkretny "evidence chain" — agent najpierw znajduje powód odrzucenia (counterexample), a potem potrafi empirycznie udowodnić spójność.

_Produced with ⚒🅅·🄸·🄱·🄴·🄲·🅡·🄰·🄵·🅃·🄴·🄳·_
