# Contributing a New Vibecrafted Skill

This guide walks an operator (human or agent) through authoring a new `vc-*`
skill from scratch and getting it merged into vibecrafted.

If you have not read [`skills/LIVING_TREE_RULE.md`](../skills/LIVING_TREE_RULE.md)
yet, do that first. Every contribution lands on a Living Tree branch under
concurrent agent activity, and the skill you author will run inside that same
discipline.

---

## What is a "skill"?

A vibecrafted skill is a self-contained operator move. One trigger phrase or
operator situation maps to one named workflow that produces one decisive
outcome. The shape on disk:

```
skills/<skill-name>/
├── SKILL.md         # default doc, YAML frontmatter at top
├── README.md        # optional operator-facing overview
├── examples/        # at least one realistic trigger + expected behavior
│   └── *.md
├── scripts/         # optional shipped scripts (chmod +x, set -euo pipefail)
└── references/      # optional deeper docs the agent loads on demand
```

`SKILL.md` is the contract. Everything else is supporting material.

Look at three shipped skills to calibrate scope:

- [`skills/vc-init/SKILL.md`](../skills/vc-init/SKILL.md) — full-shape default
  reference, multi-sense pipeline, foundation deps, deep authority labels.
- [`skills/vc-marbles/SKILL.md`](../skills/vc-marbles/SKILL.md) — execution-shape
  reference: tight loop, single deliverable per round, falsifier-driven.
- [`skills/vc-polarize/SKILL.md`](../skills/vc-polarize/SKILL.md) — minimal-shape
  reference, narrow purpose, leans on a sibling foundation tool.

If your draft starts looking longer than `vc-init`, you are probably packing
two skills into one. Split.

---

## Scaffolding a new skill

Use the scaffolder. Do not copy an existing skill dir by hand — placeholder
substitution, exec bits, and date-stamping all happen automatically.

```bash
# From the repo root:
make skill-new NAME=vc-my-new-skill

# Or call the script directly:
tools/vc-skill-new.sh vc-my-new-skill
```

The scaffolder enforces:

- name starts with `vc-`
- lowercase letters, digits, single hyphens only
- no collision with an existing `skills/` entry
- the default template at `skills/_template/` is the source of truth

On success it copies `skills/_template/` to `skills/vc-my-new-skill/` and
substitutes:

| Placeholder                | Becomes                            |
| -------------------------- | ---------------------------------- |
| `{{SKILL_NAME}}`           | `vc-my-new-skill`                  |
| `{{SKILL_NAME_NO_PREFIX}}` | `my-new-skill`                     |
| `{{CREATED_DATE}}`         | today's date in `YYYY-MM-DD` (UTC) |

It also prints operator next-steps and the discoverability commands.

---

## Frontmatter contract

Every `SKILL.md` opens with YAML frontmatter between two `---` delimiters.
Required keys (gated by `make test-skills`):

| Key           | Required             | Notes                                                                           |
| ------------- | -------------------- | ------------------------------------------------------------------------------- |
| `name`        | yes                  | Must match the directory name exactly.                                          |
| `description` | yes                  | One paragraph. Folded scalar (`>`) is fine. Include trigger phrases at the end. |
| `version`     | strongly recommended | Semver. Start at `0.1.0`. Bump on every PR.                                     |

Optional but encouraged:

| Key             | When to use                                                                        |
| --------------- | ---------------------------------------------------------------------------------- |
| `requires:`     | Foundation tools or sibling skills this depends on.                                |
| `agent_target:` | If the skill is biased toward one agent (claude / codex / gemini).                 |
| `triggers:`     | Explicit operator phrases as a YAML list, when the description prose is too dense. |

The smoke gate at `tests/skill_loader_smoke.sh` only checks structural
validity (delimiters, `name`, `description`). Stylistic discipline is on you.

---

## Trigger phrase discipline

The `description` field is read by the launcher when the operator types a
freeform request. Include trigger phrases in **both English and Polish** when
reasonable. Bias toward phrases an operator would actually type at 23:47 when
they are tired and the deploy is broken, not bookish formal commands.

Good: `"polarize", "wyostrz", "one sharp truth", "code smear"`

Bad: `"invoke polarization workflow", "execute conceptual disambiguation"`

If your trigger set overlaps with an existing skill, choose: either absorb your
draft into the existing skill, or sharpen the boundary so the operator
unambiguously knows which one to reach for.

---

## Authoring checklist

Before opening a PR:

- [ ] Replace every `TODO` marker in `SKILL.md`, `README.md`, and every file in
      `examples/`.
- [ ] At least one realistic `examples/*.md` pair (trigger phrase +
      expected agent behavior).
- [ ] `make test-skills` passes green from a clean checkout.
- [ ] `make doctor` lists your skill cleanly.
- [ ] If you added executable scripts under `scripts/`, they are `chmod +x`,
      start with `#!/usr/bin/env bash` + `set -euo pipefail`, and pass
      `shellcheck` cleanly.
- [ ] Cross-link to adjacent vc-\* skills in the **When To Use** section so the
      operator knows the boundary.
- [ ] Anti-Patterns section enumerates at least two ways the skill is likely
      to be misused.

---

## Verifying discoverability

```bash
make test-skills              # frontmatter + helper sourcing + doctor gate
make doctor | grep vc-my-new-skill   # operator-facing discovery surface
```

If `make doctor` does not list your skill, the install path did not register it.
Re-run the installer in dev mode (`make setup-dev`) and re-check.

For deeper verification, the launcher (`vibecrafted start`) should accept
`vc-<your-name>` as a valid argument once the skill is on disk in `skills/`
and the helper shim is reinstalled.

---

## Submitting the PR

vibecrafted commits ship with the `[<agent>/<workflow>]` prefix per the
[VetCoders Global Agent Charter](../AGENTS.md):

```
[claude/skill-authoring] feat(skills): add vc-my-new-skill

- skills/vc-my-new-skill/SKILL.md: trigger + acceptance + anti-patterns
- skills/vc-my-new-skill/README.md: operator overview
- skills/vc-my-new-skill/examples/example-prompt.md: realistic trigger pair

Authored-By: claude <agents@vetcoders.io>
session_id: 019e93be-379d-7303-9ad4-ffae468db99f
time: 2026-06-05T12:52:47-06:00
runtime: iterm2
```

Use `make commit-safe` (race-protected) under any active agent session:

```bash
cat >/tmp/vc-skill-commit.txt <<'MSG'
[claude/skill-authoring] feat(skills): add vc-my-new-skill

Adds a focused operator workflow with examples and discoverability notes.

Authored-By: claude <agents@vetcoders.io>
session_id: 019e93be-379d-7303-9ad4-ffae468db99f
time: 2026-06-05T12:52:47-06:00
runtime: iterm2
MSG

make commit-safe \
  MSG_FILE=/tmp/vc-skill-commit.txt \
  FILES="skills/vc-my-new-skill/SKILL.md \
         skills/vc-my-new-skill/README.md \
         skills/vc-my-new-skill/examples/example-prompt.md"
```

The CI gate at `.github/workflows/skill-loader.yml` will run `make test-skills`
across ubuntu + macos. Open the PR against `develop`.

---

## Anti-Patterns for skill authoring

- **Cargo-cult cloning** — copying `vc-init` and find-replacing the name.
  `vc-init` is the most complex skill in the repo. Use the scaffolder.
- **Multi-purpose skills** — if your `When To Use` section has more than three
  bullets describing fundamentally different situations, split the skill.
- **Vague triggers** — `"do the thing"` is not a trigger phrase. Be specific.
  The launcher's matcher is keyword-driven; ambiguous triggers route to the
  wrong skill.
- **No falsifier** — if the skill claims an outcome but nothing in its
  acceptance criteria can be checked from outside, the skill is unfalsifiable.
  Rewrite the acceptance section.
- **Skipping examples** — agents pick up new skills cold by reading
  `examples/`. Empty examples directory = your skill will be misused.
- **Stealing branding** — the default footer is
  `𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI` (or
  omitted entirely). No personal Co-Authored-By signatures in skill files.

---

## Where the wiring lives

| Surface              | Path                                                                          |
| -------------------- | ----------------------------------------------------------------------------- |
| Scaffolder           | [`tools/vc-skill-new.sh`](../tools/vc-skill-new.sh)                           |
| Template source      | [`skills/_template/`](../skills/_template)                                    |
| Frontmatter gate     | [`tests/skill_loader_smoke.sh`](../tests/skill_loader_smoke.sh)               |
| Living Tree Rule     | [`skills/LIVING_TREE_RULE.md`](../skills/LIVING_TREE_RULE.md)                 |
| Commit safety helper | [`scripts/lib/living-tree-commit.sh`](../scripts/lib/living-tree-commit.sh)   |
| CI gate              | [`.github/workflows/skill-loader.yml`](../.github/workflows/skill-loader.yml) |

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
