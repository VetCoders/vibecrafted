# Template — one scope = one canary agent

```text
You are a canary cataloger in repo {ROOT} (Living Tree: do not switch branch,
do not worktree, do not commit, do not stash).

SENSE was already done. Your ONLY scope id={SCOPE_ID}:
Paths (exclusive):
{PATH_LIST}

For every def/class/fn/struct/mod (language plugin rules) and each module file:
1. Read the file fully.
2. Catalog: one sentence of runtime role (not name paraphrase).
   authority=repo_verified|inferred
3. CANARY: if unit has NO docstring/rustdoc — add 1–3 lines, English, match neighbors.
   If docs exist — leave them (docstring_added=false).
4. NO logic/signature/import changes.
5. Run compile/lint only on files you touched; fix only your own mess.

Return JSON matching the catalog schema. `merge-catalog --strict` resolves a
language plugin from every unit's `file` and enforces that plugin's
`REQUIRED_FIELDS` and `KIND_ENUM`: `role` and `authority` are required for
every supported language, not just Rust. A violation names the catalog file and
unit and rejects the entire scope before any merged catalog is written.
files_touched, notes (dead/twins/name-mismatch — honest, will be loct-cross-checked).
```
