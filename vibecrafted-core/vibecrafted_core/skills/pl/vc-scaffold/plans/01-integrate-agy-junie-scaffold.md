---
title: Integrate agy and junie into vc-scaffold
description: Plan for adapting the installation manifests, diagnostic utilities, and founder-first scaffold planning configs to include agy and junie
type: implementation_plan
project: Vetcoders/vibecrafted
created: 2026-05-23
parent_branch: release/v2.0.0
---

# Plan: `vc-scaffold` — bootstrap i integracja planowania dla `agy` i `junie`

Ten plan opisuje kroki potrzebne do skonfigurowania instalatora, sweepów diagnostycznych oraz warstw planowania scaffoldu founder-first tak, by w pełni wspierały `antigravity-cli` (`agy`) i `junie`.

---

## 1) Cel i uzasadnienie

Aby przejście na `agy` i `junie` było bezszwowe zarówno dla founderów, jak i operatorów, proces bootstrapu `vibecrafted` musi konfigurować ścieżki toolchainu, symlinki i diagnostykę od ręki. Dodatkowo system pisania planów (`vc-scaffold`) musi być wyposażony w konfiguracje dla obu agentów.

---

## 2) Szczegółowe zmiany

### Komponent: Bootstrapping frameworka

#### [MODIFY] [scripts/install-foundations.sh](file:///Users/tester/Libraxis/vc-runtime/vibecrafted/scripts/install-foundations.sh)

- Zaktualizuj `AGENT_PACKAGES`, podmieniając Gemini na `agy`:
  ```diff
  -  "gemini:@google/gemini-cli"
  +  "agy:@google/antigravity-cli"
  ```
- Dodaj odniesienie do instalatora Junie CLI:
  ```bash
  # Check and register junie npm or binary download channel
  "junie:junie-cli"
  ```

#### [MODIFY] [install.toml](file:///Users/tester/Libraxis/vc-runtime/vibecrafted/install.toml)

- Zaktualizuj opisy intro/reason tak, by powoływały się na `antigravity-cli (agy)` i `junie` zamiast `gemini-cli`.
- W `[diagnostics.commands]` podmień `gemini` na `agy` i dodaj `junie`:
  ```toml
  agents = ["claude", "codex", "agy", "junie"]
  ```
- W `[diagnostics.paths]` zaktualizuj docelowe symlinki:
  ```toml
  symlinks = ["$HOME/.agents", "$HOME/.claude", "$HOME/.codex", "$HOME/.agy", "$HOME/.junie"]
  ```

---

### Komponent: Skrypty diagnostyki i instalatora

#### [MODIFY] [scripts/vetcoders_install.py](file:///Users/tester/Libraxis/vc-runtime/vibecrafted/scripts/vetcoders_install.py)

- Zaktualizuj rdzeniową listę metadanych:
  ```python
  AGENT_RUNTIMES = ["codex", "claude", "agy", "junie"]
  SYMLINK_TARGET_CHOICES = ["agents", "claude", "codex", "agy", "junie"]
  ```
- Zarejestruj mapowania version i help-command, by identyfikować aktywne executable na ścieżce:
  ```python
  "agy": [["--version"], ["help"]],
  "junie": [["--version"], ["-h"]]
  ```
- W blokach generowania kodu shell wrappera czysto zmapuj warianty komend `agy-` i `junie-`.

---

### Komponent: `skills/vc-scaffold/`

#### [MODIFY] [SKILL.md](file:///Users/tester/Libraxis/vc-runtime/vibecrafted/skills/vc-scaffold/SKILL.md)

- Zarejestruj `agy` i `junie` w prawidłowych targetach agent runtime dla planowania architektury.
- Zaktualizuj definicje modeli, dodając konfiguracje JetBrains Junie i Antigravity Gemini.

#### [NEW] [agy.yaml](file:///Users/tester/Libraxis/vc-runtime/vibecrafted/skills/vc-scaffold/agents/agy.yaml)

Utwórz mapowanie configu agenta scaffoldu dla `agy`:

```yaml
agent:
  name: agy
  short_description: "Antigravity Gemini CLI - sandboxed, stream-filtered, and highly robust."
  default_prompt: "Use /vc-scaffold to output robust structural plans while leveraging agy sandbox parameters."
```

#### [NEW] [junie.yaml](file:///Users/tester/Libraxis/vc-runtime/vibecrafted/skills/vc-scaffold/agents/junie.yaml)

Utwórz mapowanie configu agenta scaffoldu dla `junie`:

```yaml
agent:
  name: junie
  short_description: "JetBrains Junie CLI - standard IDE-centric code generator."
  default_prompt: "Use /vc-scaffold to map clean multi-file plans optimized for Junie's workspace-wide parser."
```

---

## 3) Plan weryfikacji

- Uruchom komendę sprawdzenia diagnostycznego:
  ```bash
  python3 scripts/vetcoders_install.py doctor
  ```
- Wykonaj dry-run skryptu install foundations:
  ```bash
  bash scripts/install-foundations.sh --check
  ```
- Zwaliduj loader parsera scaffoldu:
  ```bash
  pytest tests/tui/test_frontier_resolution.py
  ```
