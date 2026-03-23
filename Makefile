.DEFAULT_GOAL := help

PYTHON   ?= python3
INSTALLER := scripts/vetcoders_install.py
SHELL_INSTALLER := vc-agents/scripts/install-shell.sh
SOURCE   := $(CURDIR)
BRANCH   ?= main

.PHONY: help install skills helpers setup-dev dry-run doctor list update uninstall restore

help:
	@printf "\n"
	@printf "  \033[1m𝕍𝕖𝕥ℂ𝕠𝕕𝕖𝕣𝕤 𝕊𝕜𝕚𝕝𝕝𝕤\033[0m\n"
	@printf "  ───────────────────────────────────────\n"
	@printf "\n"
	@printf "  \033[33m◆\033[0m  make install       \033[2mSkills + shell helpers\033[0m\n"
	@printf "  \033[33m◇\033[0m  make skills        \033[2mSkills only\033[0m\n"
	@printf "  \033[33m◇\033[0m  make helpers       \033[2mShell helpers only\033[0m\n"
	@printf "\n"
	@printf "  \033[36m▸\033[0m  make setup-dev     \033[2mSelective interactive install\033[0m\n"
	@printf "  \033[36m▸\033[0m  make dry-run       \033[2mPreview install actions\033[0m\n"
	@printf "\n"
	@printf "  \033[32m✓\033[0m  make doctor        \033[2mVerify installation health\033[0m\n"
	@printf "  \033[32m↻\033[0m  make update        \033[2mPull latest + re-install\033[0m\n"
	@printf "  \033[32m◇\033[0m  make list          \033[2mShow bundle + runtime foundations\033[0m\n"
	@printf "\n"
	@printf "  \033[31m✕\033[0m  make uninstall     \033[2mRemove skills + helpers\033[0m\n"
	@printf "  \033[31m↺\033[0m  make restore       \033[2mUndo last install/uninstall\033[0m\n"
	@printf "\n"
	@printf "  ╭─────────────────────────────────────────╮\n"
	@printf "  │ Vibecrafted with AI Agents by VetCoders │\n"
	@printf "  ╰─────────────────────────────────────────╯\n"
	@printf "\n"

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
