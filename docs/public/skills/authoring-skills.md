---
title: "Authoring skills"
description: "Write your own vc-* skill: scaffold the layout, meet the frontmatter contract, wire the launcher, and pass the discoverability gates."
section: skills
order: 30
---

# Authoring skills

A skill is one operator move: one trigger situation, one named workflow, one
decisive outcome. If your draft describes three fundamentally different
situations, you are writing three skills. This page distills the contribution
contract into the steps that matter.

## Scaffold, do not copy

Use the scaffolder from the repository root. It handles placeholder
substitution, executable bits, and date-stamping; hand-copying an existing
skill directory skips all of that.

```bash
make skill-new NAME=vc-my-new-skill
# or directly:
tools/vc-skill-new.sh vc-my-new-skill
```

The scaffolder enforces the naming rules — the name starts with `vc-`, uses
lowercase letters, digits, and single hyphens, and must not collide with an
existing skill — then copies the template into `skills/vc-my-new-skill/`:

```text
skills/vc-my-new-skill/
├── SKILL.md         # the contract; YAML frontmatter at the top
├── README.md        # operator-facing overview
├── examples/        # at least one realistic trigger + expected behavior
├── scripts/         # optional; chmod +x, bash strict mode, shellcheck-clean
└── references/      # optional deeper docs loaded on demand
```

## Frontmatter contract

`SKILL.md` opens with YAML frontmatter between `---` delimiters. The
structural gate (`make test-skills`) requires:

| Key           | Required    | Notes                                                             |
| ------------- | ----------- | ----------------------------------------------------------------- |
| `name`        | yes         | Must match the directory name exactly.                            |
| `description` | yes         | One paragraph; folded scalar is fine; trigger phrases at the end. |
| `version`     | recommended | Semver, starting at `0.1.0`; bump on every change.                |

Optional keys: `requires:` (foundation tools or sibling skills),
`agent_target:` (when biased toward one agent), `triggers:` (an explicit
phrase list when the description is dense).

The description is what the launcher matches when an operator types a
freeform request. Write triggers an exhausted operator would actually type
at midnight — short, concrete phrases, not formal command prose. If your
trigger set overlaps an existing skill, either merge into it or sharpen the
boundary until the routing is unambiguous.

## Classify before wiring the launcher

Pick the skill's class before writing any invocation examples, and use only
this skill's real literals — never a pasted generic placeholder:

| Class         | When                                           | Worker form                  | Interactive           |
| ------------- | ---------------------------------------------- | ---------------------------- | --------------------- |
| Core launcher | Registered as a first-class CLI launcher       | `vibecrafted <name> <agent>` | `/vc-<name>`          |
| Meta          | Lifecycle umbrella, dispatch, operator posture | documented special form      | load skill / slash    |
| Foundation    | Perception or memory sense only                | none — no fake worker        | loads in other skills |

Keep the invocation rail in `SKILL.md` short and link the shared catalogue;
progressive disclosure puts long procedure under `references/`, not in the
body.

## Acceptance criteria and anti-patterns

Two sections make a skill trustworthy:

- **Acceptance criteria with a falsifier.** If nothing in the acceptance
  section can be checked from outside the session, the skill is
  unfalsifiable — rewrite it until "done" is provable from artifacts.
- **Anti-patterns.** Enumerate at least two realistic ways the skill will be
  misused, so agents picking it up cold recognize the boundary. Cross-link
  adjacent skills in the "when to use" section for the same reason.

Ship at least one realistic `examples/*.md` pair (trigger phrase plus
expected behavior). Agents learn new skills cold by reading examples; an
empty examples directory guarantees misuse.

## Install and verify

Skills install with the framework; each core launcher gets a `vc-<skill>`
shortcut and a `/vc-<skill>` interactive form. Verify discoverability before
opening a pull request:

```bash
make test-skills                      # frontmatter + loader smoke gate
make doctor | grep vc-my-new-skill    # operator-facing discovery surface
```

If `make doctor` does not list the skill, the install path did not register
it — re-run the installer in dev mode (`make setup-dev`) and check again.
Once the skill is on disk and the shim reinstalled, the launcher accepts it
as a valid argument.

Common authoring failures, in rough order of frequency: cloning the most
complex shipped skill and find-replacing the name; documenting a generic
universal CLI instead of the real launcher; dumping the full delegation
catalogue into the skill body; removing worker paths because interactive
felt freer; and vague triggers that route operators to the wrong skill.
