---

name: corrupt-skill
version: 0.0.1
description: >
Intentionally malformed SKILL.md used as a negative fixture for
tests/skill_loader_smoke.sh. The closing `---` frontmatter delimiter
is deliberately omitted so the smoke test must reject this file.
If the loader smoke ever accepts this fixture, the smoke is broken.

# Body without the closing frontmatter delimiter above.

This file MUST fail tests/skill_loader_smoke.sh's frontmatter check.
It exists as the falsifier per audit-22 Phase 4B discipline.
