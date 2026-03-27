.DEFAULT_GOAL := help

PYTHON   ?= python3
INSTALLER := scripts/vetcoders_install.py
SHELL_INSTALLER := skills/vc-agents/scripts/install-shell.sh
SOURCE   := $(CURDIR)
BRANCH   ?= main

.PHONY: help vibecrafted vibecraft check install skills helpers setup-dev dry-run doctor list update uninstall restore migrate

help:
	@printf "\n"
	@printf "  \033[1m𝗩𝗶𝗯𝗲𝗖𝗿𝗮𝗳𝘁 𝗙𝗿𝗮𝗺𝗲𝘄𝗼𝗿𝗸\033[0m\n"
	@printf "  ─────────────────────────────────────\n"
	@printf "\n"
	@printf "  \033[36m▸\033[0m  make vibecrafted   \033[2mSafely install or update the VibeCraft framework (Orchestrator)\033[0m\n"
	@printf "\n"
	@printf "  \033[33m◆\033[0m  make install       \033[2mSkills + shell helpers (Direct)\033[0m\n"
	@printf "  \033[33m◇\033[0m  make skills        \033[2mSkills only\033[0m\n"
	@printf "  \033[33m◇\033[0m  make helpers       \033[2mShell helpers only\033[0m\n"
	@printf "\n"
	@printf "  \033[36m▸\033[0m  make setup-dev     \033[2mSelective interactive install\033[0m\n"
	@printf "  \033[36m▸\033[0m  make dry-run       \033[2mPreview install actions\033[0m\n"
	@printf "\n"
	@printf "  \033[32m✓\033[0m  make doctor        \033[2mVerify installation health\033[0m\n"
	@printf "  \033[32m↻\033[0m  make update        \033[2mPull latest + re-install\033[0m\n"
	@printf "  \033[32m◇\033[0m  make list          \033[2mShow bundle + runtime foundations\033[0m\n"
	@printf "  \033[32m✓\033[0m  make check         \033[2mRun basic linters on shell scripts\033[0m\n"
	@printf "\n"
	@printf "  \033[33m◆\033[0m  make migrate       \033[2mMigrate .ai-agents/ to ~/.vibecrafted/artifacts/\033[0m\n"
	@printf "  \033[33m◇\033[0m  make migrate-dry   \033[2mPreview migration (dry run)\033[0m\n"
	@printf "\n"
	@printf "  \033[31m✕\033[0m  make uninstall     \033[2mRemove skills + helpers\033[0m\n"
	@printf "  \033[31m↺\033[0m  make restore       \033[2mUndo last install/uninstall\033[0m\n"
	@printf "\n"
	@printf "  ╭─────────────────────────────────────────╮\n"
	@printf "  │ Vibecrafted with AI Agents by VetCoders │\n"
	@printf "  ╰─────────────────────────────────────────╯\n"
	@printf "\n"

vibecrafted:
	@echo "Starting VibeCraft Orchestrator..."
	@$(PYTHON) scripts/setup_vibecraft.py

vibecraft: vibecrafted

install:
	@$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --with-shell --non-interactive

skills:
	@$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --non-interactive

helpers:
	@bash $(SHELL_INSTALLER) --source "$(SOURCE)"

setup-dev:
	@$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --advanced

dry-run:
	@$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --dry-run

doctor:
	@$(PYTHON) $(INSTALLER) doctor

list:
	@$(PYTHON) $(INSTALLER) list --source "$(SOURCE)"

update:
	@printf "Pulling origin/$(BRANCH)...\n"
	@git fetch origin
	@git checkout $(BRANCH) -- . 2>/dev/null || git merge --ff-only origin/$(BRANCH)
	@printf "Re-installing...\n"
	@$(PYTHON) $(INSTALLER) install --source "$(SOURCE)" --with-shell --non-interactive

uninstall:
	@$(PYTHON) $(INSTALLER) uninstall

restore:
	@$(PYTHON) $(INSTALLER) restore

migrate:
	@bash scripts/migrate_agents_workspace.sh

migrate-dry:
	@bash scripts/migrate_agents_workspace.sh --dry-run

check:
	@echo "Checking shell scripts..."
	@find skills scripts -name "*.sh" -o -name "*.zsh" | xargs shellcheck -e SC1090,SC1091,SC2155,SC2034,SC2154 || true
	@echo "Check complete."
