#!/usr/bin/env bash
# iterm2_migration_test.sh — Plan 10 (META_22) verification gate.
#
# Asserts that the iTerm2 stack GA promotion + experimental→GA migration
# works end-to-end against a sandboxed install dir (no real
# ~/Library/Application Support/iTerm2 access).
#
# Scenarios:
#   1. legacy vibecrafted-experimental.json present, vibecrafted.json absent
#      → migrate writes vibecrafted.json, removes legacy, creates .bak
#   2. profile names lose the [experimental] prefix
#   3. profile GUIDs are preserved verbatim (operator does not see iTerm2 duplication)
#   4. Dynamic Profile Parent Name references are rewritten to the GA name
#   5. running the migration twice is idempotent (second run = no-op)
#   6. clean state (no legacy, no new file) → "nothing to migrate"
#
# Designed to run inside `make test-iterm2-migrate`. Uses the in-process
# Python CLI via `uv run` so the helper is exercised the same way an
# operator would invoke it.
#
# Vibecrafted with AI Agents (c)2024-2026 LibraxisAI

set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$HERE/.." && pwd)

PASS=0
FAIL=0

red()   { printf '\033[31m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
amber() { printf '\033[33m%s\033[0m' "$*"; }

ok() {
    printf '  %s %s\n' "$(green ok)" "$1"
    PASS=$((PASS + 1))
}

fail() {
    printf '  %s %s\n' "$(red FAIL)" "$1"
    if [[ -n "${2:-}" ]]; then
        printf '       %s\n' "$2"
    fi
    FAIL=$((FAIL + 1))
}

section() {
    printf '\n%s\n' "$(amber "── $1 ──")"
}

# Sandboxed install dir — never touches the operator's real iTerm2 dir.
SANDBOX=$(mktemp -d -t vibecrafted-iterm2-migrate.XXXXXX)
trap 'rm -rf "$SANDBOX"' EXIT

LEGACY_FILE="$SANDBOX/vibecrafted-experimental.json"
GA_FILE="$SANDBOX/vibecrafted.json"
BAK_FILE="$SANDBOX/vibecrafted-experimental.json.bak"

# Helper: invoke the migration CLI with the sandbox as the install dir.
# We override default_install_dir() via a tiny Python wrapper rather than
# polluting the public CLI with a --target-dir flag (operators don't need
# it; CI does).
run_migrate() {
    cd "$REPO_ROOT"
    uv run --project plugins/iterm2 --quiet python -c "
import sys
from pathlib import Path
from vibecrafted_iterm2 import iterm2_profiles as p
p.default_install_dir = lambda: Path('$SANDBOX')
raise SystemExit(p._cli(['migrate-from-experimental']))
"
}

write_legacy_fixture() {
    cat > "$LEGACY_FILE" <<'JSON'
{
  "Profiles": [
    {
      "Name": "[experimental] Vibecrafted Legacy",
      "Guid": "fixture-parent-guid",
      "Tags": ["plugin", "parent"]
    },
    {
      "Name": "[experimental] Vibecrafted / Classic",
      "Guid": "fixture-classic-guid",
      "Tags": ["plugin", "mesh", "ssh"],
      "Dynamic Profile Parent Name": "[experimental] Vibecrafted Legacy"
    },
    {
      "Name": "[experimental] Vibecrafted / Project",
      "Guid": "fixture-vibecrafted-guid",
      "Tags": ["plugin", "repo", "framework"],
      "Dynamic Profile Parent Name": "[experimental] Vibecrafted Legacy"
    }
  ]
}
JSON
}

assert_json_field() {
    local file="$1"
    local jq_filter="$2"
    local expected="$3"
    local label="$4"

    local actual
    actual=$(python3 -c "
import json, sys
doc = json.load(open('$file'))
# jq_filter is a Python-evaluable expression on doc.
print($jq_filter)
" 2>/dev/null)
    if [[ "$actual" == "$expected" ]]; then
        ok "$label"
    else
        fail "$label" "expected '$expected', got '$actual'"
    fi
}

section "Scenario 1: migrate v1.7 experimental → GA"

write_legacy_fixture
[[ -f "$LEGACY_FILE" ]] || { fail "fixture setup"; exit 1; }
[[ ! -f "$GA_FILE" ]] || { fail "GA file already exists pre-migration"; exit 1; }

run_migrate > "$SANDBOX/run1.out"

if [[ -f "$GA_FILE" ]]; then
    ok "GA file vibecrafted.json created"
else
    fail "GA file vibecrafted.json missing after migration"
fi

if [[ ! -f "$LEGACY_FILE" ]]; then
    ok "legacy vibecrafted-experimental.json removed"
else
    fail "legacy file still present after migration"
fi

if [[ -f "$BAK_FILE" ]]; then
    ok ".bak backup created"
else
    fail ".bak backup missing"
fi

if grep -q "migrated" "$SANDBOX/run1.out"; then
    ok "CLI reports 'migrated' status"
else
    fail "CLI did not print 'migrated' status" "$(cat "$SANDBOX/run1.out")"
fi

section "Scenario 2: profile names cleaned"

assert_json_field "$GA_FILE" "doc['Profiles'][0]['Name']" \
    "Vibecrafted Legacy" \
    "parent profile name cleaned"
assert_json_field "$GA_FILE" "doc['Profiles'][1]['Name']" \
    "Vibecrafted / Classic" \
    "classic profile name cleaned"
assert_json_field "$GA_FILE" "doc['Profiles'][2]['Name']" \
    "Vibecrafted / Project" \
    "vibecrafted profile name cleaned"

# Belt-and-suspenders: no [experimental] anywhere in the new file.
if grep -q "\[experimental\]" "$GA_FILE"; then
    fail "[experimental] prefix leaked into vibecrafted.json"
else
    ok "no [experimental] prefix in vibecrafted.json"
fi

section "Scenario 3: GUIDs preserved verbatim"

assert_json_field "$GA_FILE" "doc['Profiles'][0]['Guid']" \
    "fixture-parent-guid" \
    "parent GUID preserved"
assert_json_field "$GA_FILE" "doc['Profiles'][1]['Guid']" \
    "fixture-classic-guid" \
    "classic GUID preserved"
assert_json_field "$GA_FILE" "doc['Profiles'][2]['Guid']" \
    "fixture-vibecrafted-guid" \
    "vibecrafted GUID preserved"

section "Scenario 4: parent references rewritten"

assert_json_field "$GA_FILE" \
    "doc['Profiles'][1]['Dynamic Profile Parent Name']" \
    "Vibecrafted Legacy" \
    "classic parent reference cleaned"
assert_json_field "$GA_FILE" \
    "doc['Profiles'][2]['Dynamic Profile Parent Name']" \
    "Vibecrafted Legacy" \
    "vibecrafted parent reference cleaned"

section "Scenario 5: idempotent re-run"

run_migrate > "$SANDBOX/run2.out"

if grep -q "already migrated" "$SANDBOX/run2.out"; then
    ok "second invocation reports 'already migrated'"
else
    fail "second invocation did not report idempotent state" \
        "$(cat "$SANDBOX/run2.out")"
fi

if [[ -f "$GA_FILE" ]] && [[ ! -f "$LEGACY_FILE" ]]; then
    ok "tree shape unchanged after second invocation"
else
    fail "second invocation mutated tree shape"
fi

section "Scenario 6: nothing to migrate (clean state)"

rm -f "$GA_FILE" "$BAK_FILE" "$LEGACY_FILE"
run_migrate > "$SANDBOX/run3.out"

if grep -q "nothing to migrate" "$SANDBOX/run3.out"; then
    ok "clean state reports 'nothing to migrate'"
else
    fail "clean state did not report 'nothing to migrate'" \
        "$(cat "$SANDBOX/run3.out")"
fi

if [[ ! -f "$GA_FILE" ]] && [[ ! -f "$LEGACY_FILE" ]]; then
    ok "no files created on clean-state migration"
else
    fail "clean-state migration created unexpected files"
fi

# -----------------------------------------------------------------------------

printf '\n%s\n' "$(amber "── summary ──")"
printf '  passed: %d\n' "$PASS"
printf '  failed: %d\n' "$FAIL"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi

exit 0
