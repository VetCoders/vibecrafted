---
name: "{{SKILL_NAME}}"
version: 0.1.0
description: "Template for a new Vibecrafted skill; replace before shipping."
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v2 -->

> **Operator CLI / slash-command layer:** invoking `/vc-<workflow>` or
> `vibecrafted <workflow> <agent>` means dispatching through the Vibecrafted
> launcher.
>
> **Skill-loading / chat layer:** loading this `SKILL.md` inside Codex, Claude,
> Gemini, or another local agent does not mean self-dispatch. Read and apply the
> skill in the current thread unless the operator explicitly asks for runtime
> launch, dispatch, or native delegation.
>
> Native in-process subagents are allowed only through the bounded
> `vc-delegate` doctrine.

<!-- /fleet-imperative -->

# {{SKILL_NAME}} — TODO one-line tagline

> Scaffolded {{CREATED_DATE}} via `tools/vc-skill-new.sh`.
> Replace every TODO marker before opening a PR.

---

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not
create, switch to, or move execution into a git worktree unless the operator
explicitly asks for one in this prompt. Re-read files before editing, adapt to
concurrent changes, and report substrate failure if the tree is too poisoned to
continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

Standard launcher:

```bash
vibecrafted {{SKILL_NAME_NO_PREFIX}} claude --prompt 'TODO concrete operator example'
vc-{{SKILL_NAME_NO_PREFIX}} codex --prompt 'TODO shell-shortcut example'
```

---

## Purpose

TODO — Replace this section. State the **one** outcome this skill produces.
Skills exist to compress a recurring operator move into a named, repeatable
surface. If this section reads like a list of capabilities, narrow it.

The bar from `CONTRIBUTING-SKILLS.md`: one sharp axis, not a Swiss-army knife.

---

## When To Use

Trigger conditions (replace all bullets):

- TODO — primary operator situation where this skill is the right call
- TODO — secondary situation, if any
- TODO — explicit non-overlap with existing vc-\* skills

**When NOT to use:**

- TODO — adjacent skill that handles a similar-but-distinct situation
- TODO — situation that should escalate to `vc-implement` or `vc-marbles` instead

---

## Pipeline Position

Where does this fit in the VetCoders workflow chain?

- Upstream: TODO (e.g. follows `vc-init`, runs after `vc-research`)
- Downstream: TODO (e.g. emits handoff for `vc-release` or `vc-dou`)

---

## Acceptance Criteria

The skill run is **done** when:

- [ ] TODO — concrete, falsifiable check #1
- [ ] TODO — concrete, falsifiable check #2
- [ ] TODO — operator-visible deliverable (file, report, commit)

If any acceptance bullet cannot be ticked with evidence, the skill has not
completed — say so explicitly in the final report.

---

## Anti-Patterns

- TODO — common failure mode #1 (e.g. running this skill before `vc-init`)
- TODO — common failure mode #2 (e.g. expanding scope beyond the one sharp axis)
- Skipping the Living Tree re-read before edit when concurrent agents are active
- Claiming "done" without ticking the acceptance criteria above

---

## Examples

See [`examples/example-prompt.md`](examples/example-prompt.md) for a minimal
trigger phrase + expected behavior pair.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
