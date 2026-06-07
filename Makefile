.DEFAULT_GOAL := help

PYTHON   ?= python3
INSTALLER := scripts/vetcoders_install.py
GUI_INSTALLER := scripts/installer_gui.py
MANIFEST := install.toml
INSTALLER_DIR := scripts/installer
SHELL_INSTALLER := agents/scripts/install-shell.sh
SOURCE   := $(CURDIR)
BRANCH   ?= main
VERSION_FILE := VERSION
RUNTIME ?= none

.PHONY: help vibecrafted gui-install wizard wizard-dev check test test-skills test-install test-parity test-zellij test-iterm2-migrate test-memex test-aicx-sync test-hammerspoon install install-auto install-all install-hammerspoon skills helpers setup-dev dry-run doctor list update uninstall restore migrate migrate-dry init-hooks seed-commit-msg-hooks bundle bundle-check foundations foundations-check semgrep version version-show version-bump bump-patch bump-minor bump-major iterm-plugin iterm-plugin-refresh iterm-plugin-show iterm-plugin-uninstall iterm-plugin-migrate demo demo-full commit-safe test-race-protection skill-new

help:
	@printf "\n"
	@printf "  \033[1m\033[38;5;173m⚒  𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Framework\033[0m\n"
	@printf "  ─────────────────────────────────────\n"
	@printf "\n"
	@printf "  \033[36m▸\033[0m  make install       \033[2mInstall interactively with checkpoints and REASON\033[0m\n"
	@printf "  \033[36m▸\033[0m  make setup-dev     \033[2mOpen the meta-installer for options and local setup\033[0m\n"
	@printf "  \033[36m▸\033[0m  make wizard        \033[2mOpen the browser-guided installer\033[0m\n"
	@printf "\n"
	@printf "  \033[2mOptions live inside the installer. Use setup-dev when you want to choose\033[0m\n"
	@printf "  \033[2martifacts storage, runtime horse, shell helpers, skills, or dry-run mode.\033[0m\n"
	@printf "\n"
	@printf "  \033[33m◆\033[0m  make install-auto  \033[2mAutomation path: same installer, auto-approved\033[0m\n"
	@printf "  \033[33m◆\033[0m  make install-all   \033[2mIdempotent runtime knife: foundations, venv launchers, store cleanse\033[0m\n"
	@printf "  \033[33m◆\033[0m  make install RUNTIME=wezterm \033[2mInstall with a lab runtime selected\033[0m\n"
	@printf "\n"
	@printf "  \033[32m✓\033[0m  make doctor        \033[2mVerify installation health\033[0m\n"
	@printf "  \033[32m✓\033[0m  make test          \033[2mRun installer + marketplace pytest gates\033[0m\n"
	@printf "  \033[32m✓\033[0m  make check         \033[2mRun basic linters on shell scripts\033[0m\n"
	@printf "\n"
	@printf "  ╭─────────────────────────────────────────╮\n"
	@printf "  │ Vibecrafted with AI Agents by VetCoders │\n"
	@printf "  ╰─────────────────────────────────────────╯\n"
	@printf "\n"

vibecrafted: install

install: init-hooks
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "bootstrapping uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi; \
	export PATH="$$HOME/.local/bin:$$PATH"; \
	VIBECRAFTED_RUNTIME="$(RUNTIME)" uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --quiet

# BUNDLE_DIR accepts an external prebuilt Svelte site/dist tree
# (e.g. from the sibling vibecrafted-io repo). When empty, `make wizard`
# first tries to build and serve the sibling site checkout so the local
# control plane matches the branded install surface; otherwise it falls
# back to the built-in inline HTML.
BUNDLE_DIR ?=

wizard: init-hooks
	@if [ -n "$(BUNDLE_DIR)" ]; then \
		echo "[wizard] Launching wizard with explicit bundle $(BUNDLE_DIR)"; \
		$(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)" --bundle-dir "$(BUNDLE_DIR)"; \
		exit 0; \
	fi; \
	if [ -n "$$VIBECRAFTED_SITE_BUNDLE" ]; then \
		echo "[wizard] Using VIBECRAFTED_SITE_BUNDLE=$$VIBECRAFTED_SITE_BUNDLE"; \
		$(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)"; \
		exit 0; \
	fi; \
	site_repo=""; \
	for p in "$(CURDIR)/../vc-runtime/vibecrafted-io" "$(CURDIR)/../vibecrafted-io" "$$HOME/Libraxis/vc-runtime/vibecrafted-io"; do \
		if [ -d "$$p/site" ]; then site_repo="$$p"; break; fi; \
	done; \
	if [ -z "$$site_repo" ]; then \
		echo "[wizard] vibecrafted-io sibling not found — falling back to inline HTML"; \
		$(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)"; \
		exit 0; \
	fi; \
	echo "[wizard] Building branded install surface at $$site_repo/site"; \
	if [ ! -d "$$site_repo/site/node_modules" ]; then \
		(cd "$$site_repo/site" && pnpm install --frozen-lockfile=false) || { echo "[wizard] site dependency install failed — falling back to inline HTML"; $(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)"; exit 0; }; \
	fi; \
	(cd "$$site_repo/site" && pnpm run build) || { echo "[wizard] site build failed — falling back to inline HTML"; $(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)"; exit 0; }; \
	echo "[wizard] Launching wizard with bundle from $$site_repo/site/dist"; \
	$(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)" --bundle-dir "$$site_repo/site/dist"

gui-install: wizard

# Development helper preserved as an explicit alias for LiveInstaller work.
# `make wizard` already rebuilds the sibling site when it is available.
wizard-dev: wizard

install-auto: init-hooks
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "bootstrapping uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi; \
	export PATH="$$HOME/.local/bin:$$PATH"; \
	VIBECRAFTED_RUNTIME="$(RUNTIME)" uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --yes --quiet

# Output discipline: the shell installers (foundations, frontier, runtime) are
# chatty. By default their output goes to the install log so the compact Python
# installer's [1/4..4/4] storytelling is the only on-screen output.
# VERBOSE=1 shows the full bazaar.
VERBOSE ?= 0
ifeq ($(VERBOSE),1)
INSTALL_QUIET :=
else
INSTALL_QUIET := >> "$(HOME)/.vibecrafted/install.log" 2>&1
endif

install-all: init-hooks
	@bash scripts/install-foundations.sh $(INSTALL_QUIET)
	@bash agents/scripts/install-frontier-config.sh --source "$(SOURCE)" $(INSTALL_QUIET) || printf '[warn] Frontier config skipped (non-fatal)\n'
	@$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --with-shell --compact --non-interactive --mirror
	@bash scripts/install-runtime.sh --runtime "$(RUNTIME)" --yes $(INSTALL_QUIET)

skills:
	@$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --non-interactive

helpers:
	@bash $(SHELL_INSTALLER) --source "$(SOURCE)"

foundations:
	@bash scripts/install-foundations.sh

foundations-check:
	@bash scripts/install-foundations.sh --check

setup-dev: init-hooks
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "bootstrapping uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi; \
	export PATH="$$HOME/.local/bin:$$PATH"; \
	VIBECRAFTED_RUNTIME="$(RUNTIME)" uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --advanced --quiet

dry-run:
	@uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --dry-run

doctor:
	@$(PYTHON) $(INSTALLER) doctor

list:
	@$(PYTHON) $(INSTALLER) list --source "$(SOURCE)"

bundle:
	@$(PYTHON) scripts/build_marketplace_bundle.py --output "$(SOURCE)/vibecrafted-framework.plugin"

bundle-check:
	@tmp_root="$${TMPDIR:-/tmp}"; \
	tmp_bundle="$$(mktemp "$$tmp_root/vibecrafted-bundle.XXXXXX")"; \
	trap 'rm -f "$$tmp_bundle"' EXIT; \
	$(PYTHON) scripts/build_marketplace_bundle.py --output "$$tmp_bundle"; \
	if cmp -s "$$tmp_bundle" "$(SOURCE)/vibecrafted-framework.plugin"; then \
		echo "Bundle is current."; \
	else \
		echo "Bundle drift detected. Run 'make bundle'."; \
		exit 1; \
	fi

version version-show:
	@version="$$(sed -n '1p' "$(VERSION_FILE)" 2>/dev/null | tr -d '[:space:]')"; \
	if [ -z "$$version" ]; then echo "VERSION file missing or empty: $(VERSION_FILE)" >&2; exit 1; fi; \
	printf "version: %s\n" "$$version"; \
	printf "tag: v%s\n" "$$version"; \
	if git rev-parse --verify "refs/tags/v$$version" >/dev/null 2>&1; then \
		echo "tag-state: exists"; \
	else \
		echo "tag-state: missing"; \
	fi

version-bump:
ifeq ($(origin VERSION),command line)
	@$(PYTHON) scripts/version_bump.py "$(VERSION)" --file "$(VERSION_FILE)"
else
	@echo "VERSION is required. Usage: make version-bump VERSION={patch|minor|major|x.y.z}" >&2 && exit 1
endif

bump-patch:
	@$(MAKE) version-bump VERSION=patch

bump-minor:
	@$(MAKE) version-bump VERSION=minor

bump-major:
	@$(MAKE) version-bump VERSION=major

semgrep:
	@if command -v semgrep >/dev/null 2>&1; then \
		semgrep scan --config auto --error --quiet --exclude-rule html.security.audit.missing-integrity.missing-integrity .; \
	else \
		uvx semgrep scan --config auto --error --quiet --exclude-rule html.security.audit.missing-integrity.missing-integrity .; \
	fi

test:
	@if command -v uv >/dev/null 2>&1; then \
		PYTHONPATH="$(SOURCE)" uv run --with pytest pytest tests/tui -q; \
	else \
		PYTHONPATH="$(SOURCE)" $(PYTHON) -m pytest tests/tui -q; \
	fi

test-skills:
	@bash tests/skill_loader_smoke.sh

# Plan 03 (META_22) — install.sh / install.ps1 cross-platform smoke.
# Host-only assertions: pre-flight, detection helpers, hint matrix, .ps1
# entry shape. Full install matrix runs in .github/workflows/install-linux.yml.
test-install:
	@bash tests/install_smoke.sh

update:
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		printf "Git repo detected — pulling origin/$(BRANCH)...\n"; \
		git fetch origin; \
		git checkout "$(BRANCH)" -- . 2>/dev/null || git merge --ff-only "origin/$(BRANCH)"; \
		printf "Re-installing...\n"; \
		$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --with-shell --mirror --non-interactive; \
	else \
		printf "Tarball install — re-running bootstrap installer...\n"; \
		bash "$(SOURCE)/install.sh" --ref "$(BRANCH)"; \
	fi

uninstall:
	@$(PYTHON) $(INSTALLER) uninstall

restore:
	@$(PYTHON) $(INSTALLER) restore

migrate:
	@bash scripts/migrate_agents_workspace.sh

migrate-dry:
	@bash scripts/migrate_agents_workspace.sh --dry-run

check:
	@$(PYTHON) scripts/check_shell.py
	@echo "Check complete."

iterm-plugin:
	@uv run --project vibecrafted-core --quiet python -m vibecrafted_core.iterm2_profiles install

iterm-plugin-refresh:
	@uv run --project vibecrafted-core --quiet python -m vibecrafted_core.iterm2_profiles refresh

iterm-plugin-show:
	@uv run --project vibecrafted-core --quiet python -m vibecrafted_core.iterm2_profiles show

iterm-plugin-uninstall:
	@uv run --project vibecrafted-core --quiet python -m vibecrafted_core.iterm2_profiles uninstall

# Plan 10 (META_22) — operators with v1.7 [experimental] dynamic profiles run
# this once on v1.8.0 upgrade. Reads vibecrafted-experimental.json, writes
# vibecrafted.json with cleaned names + preserved GUIDs, .bak backup,
# removes the legacy file. Idempotent: re-running is safe (no-op).
iterm-plugin-migrate:
	@uv run --project vibecrafted-core --quiet python -m vibecrafted_core.iterm2_profiles migrate-from-experimental

demo:
	@bash scripts/vc-dashboard

demo-full:
	@bash scripts/vc-dashboard --html

init-hooks:
	@if [ "$$CI" = "true" ]; then \
		echo "CI detected - skipping git hook bootstrap."; \
	elif git rev-parse --git-dir >/dev/null 2>&1; then \
		git config core.hooksPath scripts/hooks >/dev/null; \
		chmod +x scripts/hooks/pre-commit scripts/hooks/pre-push scripts/hooks/commit-msg; \
		command -v uv >/dev/null 2>&1 || { echo "bootstrapping uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }; \
		uvx ruff --version >/dev/null 2>&1 || echo "  [warn] ruff unavailable via uvx"; \
		command -v semgrep >/dev/null 2>&1 || uvx semgrep --version >/dev/null 2>&1 || echo "  [warn] semgrep unavailable"; \
		npx --yes prettier --version >/dev/null 2>&1 || echo "  [warn] prettier unavailable via npx"; \
	else \
		true; \
	fi

seed-commit-msg-hooks:
	@bash scripts/install-agent-commit-msg-hooks.sh ..

# -----------------------------------------------------------------------------
# Living Tree race protection (Plan 07 — kronika 2026-04-16/17 incident learning)
#
# Two invocation modes:
#
#   Single-line:
#     make commit-safe MSG="<subject>" FILES="path1 path2"
#
#   Multi-line (Plan 07-b — closes Limitation #2):
#     make commit-safe MSG_FILE=/tmp/msg.txt FILES="path1 path2"
#
# MSG_FILE reads the commit message from a file (subject + blank line + body).
# Use this for any multi-line message — avoids Makefile $$ escaping vs. shell
# expansion interaction that historically broke MSG="..." with embedded
# newlines/quotes/dollars.
#
# Helper handles three race detectors: HEAD shift, foreign-file inclusion,
# and (informationally) tree-hash mismatch. Plan 07-b relaxed tree-hash
# alone from race-signal to informational notice (pre-commit hooks like
# prettier --write legitimately mutate staged content; that is not a race).
# -----------------------------------------------------------------------------

commit-safe:
	@if [ -z "$(FILES)" ]; then \
		echo "usage:" >&2; \
		echo "  make commit-safe MSG=\"<subject>\" FILES=\"path1 path2 ...\"" >&2; \
		echo "  make commit-safe MSG_FILE=<path>  FILES=\"path1 path2 ...\"" >&2; \
		echo "" >&2; \
		echo "Race-protected commit helper for Living Tree workflow." >&2; \
		echo "MSG_FILE supports multi-line commit bodies (Plan 07-b)." >&2; \
		exit 1; \
	fi
	@if [ -n "$(MSG_FILE)" ] && [ -n "$(MSG)" ]; then \
		echo "make commit-safe: pass MSG OR MSG_FILE, not both" >&2; \
		exit 1; \
	fi
	@if [ -z "$(MSG)" ] && [ -z "$(MSG_FILE)" ]; then \
		echo "make commit-safe: MSG=\"...\" or MSG_FILE=<path> is required" >&2; \
		exit 1; \
	fi
	@if [ -n "$(MSG_FILE)" ]; then \
		bash scripts/lib/living-tree-commit.sh --message-file "$(MSG_FILE)" -- $(FILES); \
	else \
		bash scripts/lib/living-tree-commit.sh "$(MSG)" -- $(FILES); \
	fi

test-race-protection:
	@bash tests/race_protection_test.sh

# -----------------------------------------------------------------------------
# Plan 06 (META_22) — AGENT MODEL PARITY automated enforcement.
#
# Verifies the bash + Python parity layers (scripts/lib/spawn.sh and
# vibecrafted-core/vibecrafted_core/agent_dispatch.py) reject same-family
# downgrades, allow cross-family delegation, and honor the
# VIBECRAFTED_SPAWN_ALLOW_DOWNGRADE=1 operator override with an audit
# warning. Captures kronika 2026-04-10 doctrine.
# -----------------------------------------------------------------------------

test-parity:
	@bash tests/spawn_parity_test.sh
	@if command -v uv >/dev/null 2>&1; then \
		uv run --with pytest pytest tests/agent_dispatch_test.py -q; \
	else \
		PYTHONPATH="$(SOURCE)/vibecrafted-core" $(PYTHON) -m pytest tests/agent_dispatch_test.py -q; \
	fi

# -----------------------------------------------------------------------------
# Plan 04 — skill-authoring scaffolder.
#
# `make skill-new NAME=vc-my-skill` wraps tools/vc-skill-new.sh. The script
# enforces name validation (vc- prefix, lowercase, no collisions) and copies
# skills/_template/ with placeholder substitution. See
# docs/CONTRIBUTING-SKILLS.md for the full operator authoring guide.
# -----------------------------------------------------------------------------

skill-new:
	@if [ -z "$(NAME)" ]; then \
		echo "usage: make skill-new NAME=vc-<skill-name>" >&2; \
		echo "" >&2; \
		echo "Scaffold a new vc-* skill from skills/_template/." >&2; \
		echo "See docs/CONTRIBUTING-SKILLS.md for the authoring guide." >&2; \
		exit 2; \
	fi
	@bash tools/vc-skill-new.sh "$(NAME)"

# -----------------------------------------------------------------------------
# Plan 12 (META_22) — zellij multi-agent layouts smoke gate.
#
# Verifies:
#   - all shipped layouts under config/zellij/layouts/*.kdl parse via
#     `zellij --layout <name> setup --check`
#   - all four mesh themes (vetcoders-dragon/sztudio/silver/div0) load
#   - auto-theme.sh passes bash -n + shellcheck
#   - auto-theme.sh maps each canonical host (dragon, sztudio, silver, div0,
#     mgbook16 alias) to the correct mesh theme and falls back to neutral
#     for unknown hosts
#
# Tolerant of missing zellij — falls back to script-level checks only.
# -----------------------------------------------------------------------------

test-zellij:
	@bash tests/zellij_layouts_smoke.sh

# -----------------------------------------------------------------------------
# Plan 10 (META_22) — iTerm2 stack GA promotion smoke gate.
#
# Verifies the migrate-from-experimental subcommand:
#   - sets up a fixture vibecrafted-experimental.json
#   - runs `python -m vibecrafted_core.iterm2_profiles migrate-from-experimental`
#     against a sandboxed install dir
#   - asserts the new vibecrafted.json exists with cleaned profile names
#     and preserved GUIDs
#   - asserts the .bak backup was created and the legacy file removed
#   - asserts the migration is idempotent (second invocation is no-op)
#
# This is a bash smoke wrapper around the same logic that
# test_iterm2_profiles.py pytest suite covers in-process; both run on CI.
# -----------------------------------------------------------------------------

test-iterm2-migrate:
	@bash tests/iterm2_migration_test.sh

# -----------------------------------------------------------------------------
# Plan 09 (META_22) — memex cross-session retrieval client smoke gate.
#
# Two tiers run together:
#   1. bash integration smoke (tests/memex_integration_test.sh) — asserts
#      SKILL.md Sense 1 documentation, public surface, populated-memex
#      fallthrough via injected MCP stub, graceful degradation on
#      unreachable endpoint, config precedence (TOML > env), pure
#      defaults disable cleanly, empty-query short-circuit.
#   2. pytest unit tier (vibecrafted-core/tests/test_memex_client.py) —
#      covers HTTP success/failure parsing, MCP bridge transport,
#      config layer precedence, malformed responses, limit clamping.
#
# The bash tier owns the OPERATOR-VISIBLE contract (markdown + sandbox
# shell). The pytest tier owns the implementation correctness contract.
# Both must pass for `make test-memex` to be green.
# -----------------------------------------------------------------------------

test-memex:
	@bash tests/memex_integration_test.sh
	@if command -v uv >/dev/null 2>&1; then \
		uv run --project vibecrafted-core --with pytest python -m pytest vibecrafted-core/tests/test_memex_client.py -q; \
	else \
		PYTHONPATH="$(SOURCE)/vibecrafted-core" $(PYTHON) -m pytest vibecrafted-core/tests/test_memex_client.py -q; \
	fi

# -----------------------------------------------------------------------------
# Plan 08 (META_22) — AICX cross-machine sync v2 smoke gate.
#
# Two tiers run together:
#   1. bash end-to-end smoke (tests/aicx_sync_smoke.sh) — asserts the
#      two-machine fixture: dual-add discovery, dry-run is read-only,
#      authority-tier conflict resolution (repo_verified > aicx_agent),
#      same-tier tie surfacing, prior conflict-log decision honoured on
#      subsequent runs, corrupted chunk reported + skipped without crash,
#      CLI wrapper (scripts/aicx-sync.sh) help + unknown-command rejection
#      + TOML config-file fallback.
#   2. pytest unit tier (vibecrafted-core/tests/test_aicx_sync.py) —
#      covers Authority enum + aliases, AicxChunk normalization,
#      discover_chunks adds/conflicts/corrupted, resolve_conflict full
#      tier ladder + log honouring + last-write-wins on decisions,
#      apply_plan dry-run read-only invariant, record_decision validation,
#      CLI surface.
#
# The bash tier owns the OPERATOR-VISIBLE contract (CLI wrapper + cross-
# machine fixture). The pytest tier owns the implementation correctness
# contract. Both must pass for `make test-aicx-sync` to be green.
# -----------------------------------------------------------------------------

test-aicx-sync:
	@bash tests/aicx_sync_smoke.sh
	@if command -v uv >/dev/null 2>&1; then \
		uv run --project vibecrafted-core --with pytest python -m pytest vibecrafted-core/tests/test_aicx_sync.py -q; \
	else \
		PYTHONPATH="$(SOURCE)/vibecrafted-core" $(PYTHON) -m pytest vibecrafted-core/tests/test_aicx_sync.py -q; \
	fi

# -----------------------------------------------------------------------------
# Plan 11 (META_22) — Hammerspoon URL handler stack install + smoke gate.
#
# install-hammerspoon: copies config/hammerspoon/init.lua to
#   ~/.hammerspoon/init.lua, offering a .bak overwrite when an existing
#   config is present, and reloads Hammerspoon. macOS-only — exits 0 with
#   a notice on Linux/CI.
#
# test-hammerspoon: structural lints + sanitization unit tests (8 positive
#   + 4 negative cases) against the Lua param validator. Includes static
#   analysis (bash -n, shellcheck, optional luac -p) + handler-registration
#   grep checks. Live macOS integration is operator-driven (the test
#   surfaces the manual command rather than spawning iTerm2 tabs during CI).
#
# Stack agent-native runtime context (kronika 2026-05-08): OSC 8 hyperlink
# → iTerm2 Cmd+Click → macOS open URL → Hammerspoon URL handler →
# AppleScript spawn iTerm2 tab → CLI dispatch. See docs/HAMMERSPOON.md.
# -----------------------------------------------------------------------------

install-hammerspoon:
	@bash scripts/install-hammerspoon.sh

test-hammerspoon:
	@bash tests/hammerspoon_smoke.sh
