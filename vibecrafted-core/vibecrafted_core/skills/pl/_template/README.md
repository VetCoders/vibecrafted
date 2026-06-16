# {{SKILL_NAME}}

TODO — jednoakapitowy, operatorski przegląd. Co ten skill robi prostym
językiem, kto powinien po niego sięgnąć i co dostaje w zamian.

Wygenerowane (scaffold) {{CREATED_DATE}} przez `tools/vc-skill-new.sh`. Zastąp każdy
marker TODO przed otwarciem PR.

## Szybka ściąga

| Pole                | Wartość                                        |
| ------------------- | ---------------------------------------------- |
| Nazwa               | `{{SKILL_NAME}}`                               |
| Wersja              | `0.1.0` (podbij przy pierwszym PR)             |
| Komenda operatora   | `vibecrafted {{SKILL_NAME_NO_PREFIX}} <agent>` |
| Skrót shellowy      | `vc-{{SKILL_NAME_NO_PREFIX}} <agent>`          |
| Dokument kanoniczny | [`SKILL.md`](SKILL.md)                         |

## Checklista autorska

Przed otwarciem PR:

- [ ] Zastąp każdy marker `TODO` w `SKILL.md` i w tym README
- [ ] Dodaj co najmniej jeden realistyczny przykład do `examples/`
- [ ] Uruchom `make test-skills` i potwierdź, że ten skill przechodzi sprawdzenia frontmatteru
- [ ] Uruchom `make doctor` i potwierdź, że skill rejestruje się czysto
- [ ] Jeśli skill dostarcza wykonywalne skrypty w `scripts/`, upewnij się, że mają
      `chmod +x` i zaczynają się od `set -euo pipefail`
- [ ] Frazy-triggery obejmują formy angielskie i polskie tam, gdzie to rozsądne
- [ ] Linkuj do sąsiednich skillów vc-\* w sekcji **Kiedy używać**

Zobacz [`docs/CONTRIBUTING-SKILLS.md`](../../docs/CONTRIBUTING-SKILLS.md) — pełny
przewodnik autorski.
