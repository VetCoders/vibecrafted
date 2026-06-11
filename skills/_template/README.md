# {{SKILL_NAME}}

TODO — one-paragraph operator-facing overview. What this skill does in plain
language, who should reach for it, and what they get back.

Scaffolded {{CREATED_DATE}} via `tools/vc-skill-new.sh`. Replace every TODO
marker before opening a PR.

## Quick reference

| Field            | Value                                 |
| ---------------- | ------------------------------------- |
| Name             | `{{SKILL_NAME}}`                      |
| Version          | `0.1.0` (bump on first PR)            |
| Operator command | `vibecrafted {{SKILL_NAME_NO_PREFIX}} <agent>` |
| Shell shortcut   | `vc-{{SKILL_NAME_NO_PREFIX}} <agent>` |
| Canonical doc    | [`SKILL.md`](SKILL.md)                |

## Authoring checklist

Before opening a PR:

- [ ] Replace every `TODO` marker in `SKILL.md` and this README
- [ ] Add at least one realistic example to `examples/`
- [ ] Run `make test-skills` and confirm this skill passes frontmatter checks
- [ ] Run `make doctor` and confirm the skill registers cleanly
- [ ] If the skill ships executable scripts under `scripts/`, ensure they are
      `chmod +x` and start with `set -euo pipefail`
- [ ] Trigger phrases include both English and Polish forms where reasonable
- [ ] Cross-link to adjacent vc-\* skills in the **When To Use** section

See [`docs/CONTRIBUTING-SKILLS.md`](../../docs/CONTRIBUTING-SKILLS.md) for the
full authoring guide.
