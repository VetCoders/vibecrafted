#!/usr/bin/env bash
# vc-skill-new.sh — Plan 04 skill scaffolder.
#
# Scaffold a new vc-* skill from skills/_template/ with placeholder
# substitution. Validates name, refuses collisions, and emits operator
# next-step hints on success.
#
# Usage:
#   tools/vc-skill-new.sh <skill-name>
#
# Constraints on <skill-name>:
#   - Must start with the literal prefix "vc-".
#   - After the prefix: one lowercase letter followed by lowercase letters,
#     digits, or hyphens. No uppercase, no underscores, no leading digit,
#     no trailing hyphen, no double-hyphen.
#   - Must not collide with an existing directory under skills/.
#
# Behavior:
#   - Copies skills/_template/ to skills/<skill-name>/.
#   - Substitutes placeholders in every text file:
#       {{SKILL_NAME}}            → user-supplied name (e.g. vc-foo-bar)
#       {{SKILL_NAME_NO_PREFIX}}  → name with "vc-" stripped (e.g. foo-bar)
#       {{CREATED_DATE}}          → today's date in ISO-8601 (UTC)
#   - Sets executable bit on any scaffolded scripts/*.sh.
#   - Prints discoverability hints (doctor + read the skill).
#
# This script is append-only. It never deletes, never overwrites existing
# skills, never edits files outside the new skill directory.

set -euo pipefail

# ----- arg parsing ------------------------------------------------------------

if [[ $# -ne 1 ]]; then
    cat >&2 <<'USAGE'
usage: tools/vc-skill-new.sh <skill-name>

Scaffold a new vc-* skill from skills/_template/.

The name must start with "vc-" and use only lowercase letters, digits, and
single hyphens. Examples:

  tools/vc-skill-new.sh vc-foo
  tools/vc-skill-new.sh vc-payments-audit

See docs/CONTRIBUTING-SKILLS.md for the full authoring guide.
USAGE
    exit 2
fi

SKILL_NAME=$1

# ----- name validation --------------------------------------------------------

if [[ ! "$SKILL_NAME" =~ ^vc- ]]; then
    echo "vc-skill-new: name must start with 'vc-' (got: $SKILL_NAME)" >&2
    exit 2
fi

# Full pattern: vc- + [a-z] + ([a-z0-9-]*[a-z0-9])?
# Disallow trailing hyphen by requiring the body to end on alnum if it has
# more than one char. Also reject any double hyphen.
if [[ ! "$SKILL_NAME" =~ ^vc-[a-z]([a-z0-9-]*[a-z0-9])?$ ]]; then
    echo "vc-skill-new: invalid name '$SKILL_NAME'" >&2
    echo "  expected: vc- + lowercase letter + [a-z0-9-]* (no uppercase, no underscore," >&2
    echo "  no trailing hyphen, must start the suffix with a letter)" >&2
    exit 2
fi

if [[ "$SKILL_NAME" == *"--"* ]]; then
    echo "vc-skill-new: invalid name '$SKILL_NAME' — double hyphen not allowed" >&2
    exit 2
fi

# ----- locate repo + template -------------------------------------------------

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TEMPLATE_DIR="$REPO_ROOT/skills/_template"
SKILLS_DIR="$REPO_ROOT/skills"
TARGET_DIR="$SKILLS_DIR/$SKILL_NAME"

if [[ ! -d "$TEMPLATE_DIR" ]]; then
    echo "vc-skill-new: template directory missing at $TEMPLATE_DIR" >&2
    echo "  (this should not happen — re-pull the repo or check Plan 04 shipped)" >&2
    exit 2
fi

if [[ ! -f "$TEMPLATE_DIR/SKILL.md" ]]; then
    echo "vc-skill-new: template is incomplete — missing $TEMPLATE_DIR/SKILL.md" >&2
    exit 2
fi

if [[ -e "$TARGET_DIR" ]]; then
    echo "vc-skill-new: target already exists at $TARGET_DIR" >&2
    echo "  refusing to overwrite — pick a different name or remove the existing" >&2
    echo "  directory manually if you are certain you want to start over" >&2
    exit 2
fi

# ----- compute substitutions --------------------------------------------------

SKILL_NAME_NO_PREFIX="${SKILL_NAME#vc-}"
CREATED_DATE=$(date -u +%Y-%m-%d)

# ----- copy template ----------------------------------------------------------

# Copy recursively. Use cp -R for portability across macOS (BSD) and Linux
# (GNU). The template is small enough that this is fine.
cp -R "$TEMPLATE_DIR" "$TARGET_DIR"

# Drop any stray hidden files that should not propagate from the template
# (e.g. macOS .DS_Store). The template directory is committed without them
# but be defensive.
find "$TARGET_DIR" -name '.DS_Store' -type f -delete 2>/dev/null || true

# ----- placeholder substitution ----------------------------------------------

# Substitute in every regular file. Use a portable in-place pattern that
# works on both BSD (macOS) and GNU sed: write to a temp file and move
# back. This avoids the BSD-vs-GNU `-i` argument incompatibility.

substitute_file() {
    local file="$1"
    local tmp
    tmp="$(mktemp "${file}.XXXXXX.tmp")"
    # Order matters: SKILL_NAME_NO_PREFIX must be substituted BEFORE
    # SKILL_NAME, otherwise the longer placeholder would not match
    # (its first 12 chars are "{{SKILL_NAME"). Using awk via sed-style
    # would be safer but two passes with sed is portable and clear.
    sed \
        -e "s|{{SKILL_NAME_NO_PREFIX}}|${SKILL_NAME_NO_PREFIX}|g" \
        -e "s|{{SKILL_NAME}}|${SKILL_NAME}|g" \
        -e "s|{{CREATED_DATE}}|${CREATED_DATE}|g" \
        "$file" >"$tmp"
    mv "$tmp" "$file"
}

# Find regular text files only. Skip binary/image files defensively. The
# template currently has none, but be future-proof.
while IFS= read -r -d '' f; do
    # Probe MIME-ish: treat anything matching common text extensions or
    # detected as text by `file` as substitutable.
    case "$f" in
        *.md|*.txt|*.sh|*.yml|*.yaml|*.toml|*.json|*.py)
            substitute_file "$f"
            ;;
        *)
            if file "$f" 2>/dev/null | grep -qiE 'text|empty'; then
                substitute_file "$f"
            fi
            ;;
    esac
done < <(find "$TARGET_DIR" -type f -print0)

# ----- exec-bit on shipped scripts -------------------------------------------

if [[ -d "$TARGET_DIR/scripts" ]]; then
    while IFS= read -r -d '' script; do
        chmod +x "$script"
    done < <(find "$TARGET_DIR/scripts" -type f -name '*.sh' -print0)
fi

# ----- success report ---------------------------------------------------------

cat <<EOF
vc-skill-new: scaffolded $SKILL_NAME at skills/$SKILL_NAME/

Next moves:
  1. Edit skills/$SKILL_NAME/SKILL.md and replace every TODO marker.
  2. Edit skills/$SKILL_NAME/README.md and tick the authoring checklist.
  3. Drop a realistic example into skills/$SKILL_NAME/examples/.
  4. Verify it parses cleanly:

       make test-skills

  5. Verify operator discoverability:

       make doctor | grep $SKILL_NAME

  6. Read the full authoring guide:

       cat docs/CONTRIBUTING-SKILLS.md

  7. Open a PR. The CI gate will run make test-skills against your branch.
EOF
