---
title: Matryca Delegacji
kind: doctrine_matrix
version: 3.0.0
description: "Kanoniczny model wywoływania, wykonywania i delegacji dla floty Vibecrafted."
scope: framework
status: active
language: pl
---

# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Matryca Delegacji (Delegation Matrix)

> Model wywoływania, wykonywania i delegacji dla floty Vibecrafted.

<!-- fleet-imperative: v3 -->

## Model Wywoływania, Wykonywania i Delegacji

Skill lub workflow `vibecrafted` może zostać wywołany na trzy odrębne sposoby:

### 1. User-Launched Worker

Użytkownik może wywołać `vibecrafted workflow <agent>` z poziomu CLI (launchera). Tworzy to osobny, nieinteraktywny przebieg workera odpowiedzialny za wykonanie pełnego pipeline'u.

### 2. Interactive Skill Invocation

Użytkownik może wywołać `/vc-workflow` lub załadować skill wewnątrz istniejącej sesji agenta. W takim przypadku bieżący agent musi załadować i wykonać pełny skill w ramach tej samej sesji. Nie wolno mu zewnętrzniać workflow do osobnego workera `vibecrafted` tylko dlatego, że delegacja jest dostępna. Może — a gdy to wymagane, musi — użyć swojej natywnej floty subagentów w procesie do dokładnego dokończenia workflow.

### 3. Agent-Operator Delegation

Podczas prowadzenia szerszej orkiestracji agent-operator może użyć `vibecrafted workflow <agent>` jako agent `vc-dispatch`, tak samo jak użytkownik. Uruchamia to osobną sesję workflow przez runtime `vibecrafted` i deleguje pełny pipeline do zewnętrznego agenta floty.

---

## Mandat Wykonawczy i Cykle Życia

Niezależnie od tego, czy agent działa w ramach wywołania interaktywnego, czy nieinteraktywnego, ma ten sam mandat: kompleksowo wykonać instrukcje pipeline'u z danego skilla i użyć dostępnych natywnych subagentów, gdy to konieczne.

Różnica polega wyłącznie na tym:

- **gdzie** wykonuje się workflow
- **czyją uwagę** zajmuje

Niemniej jednak:

- **Headless worker** zachowuje prawo do tworzenia i koordynowania własnych natywnych subagentów — bycie workerem ogranicza zakres i cykl życia jego przebiegu, ale nie odbiera mu uprawnień delegacji.
- **Agent otrzymujący skill interaktywnie** musi wykonać go lokalnie w ramach bieżącej sesji, używając w razie potrzeby natywnych subagentów.

---

## Natywne Subagenty vs Zewnętrzny Workflow

Subagent działający jako część natywnej floty agenta może przypominać osobnego workera, ale różni się integracją i cyklem życia kontekstu:

- **Natywne Subagenty (Native Subagents)**: żyją w tym samym procesie co agent orkiestrujący. Dzielą tę samą pamięć, konfigurację i kontekst wykonawczy.
- **Zewnętrzni Workerzy (External Workers)**: są uruchamiani jako osobne procesy `vibecrafted`. Komunikują się z orkiestratorem przez zdefiniowane interfejsy i mają niezależne cykle życia.

Decyzja o użyciu natywnych subagentów lub delegacji do zewnętrznego workera zależy od przypadku użycia, ale fundamentalna zasada pozostaje niezmienna: **uprawnienie do wykonania workflow zachowuje agent, chyba że wyraźnie oddelegował je zdefiniowanymi kanałami.**

---

## Wyjątki i Odnośniki

- **Wyjątki Natywnych Subagentów**: Zdefiniowane ze szczegółowymi ograniczeniami w [`vc-delegate`](../vc-delegate/SKILL.md).
- **Dyspozytura Zewnętrznej Floty**: Zdefiniowana w [`vc-dispatch`](../vc-dispatch/SKILL.md).
- **Wielofalowa Orkiestracja Operatora**: Zdefiniowana w [`vc-operator`](../vc-operator/SKILL.md).

<!-- /fleet-imperative -->
