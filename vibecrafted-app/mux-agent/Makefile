SHELL := /bin/bash

.PHONY: help build release check fmt fmt-check clippy test test-full gates \
		wizard wizard-dry-run run run-tray proxy health daemon-status dashboard \
		status-file-init clean-runtime

CONFIG ?= $(HOME)/.codex/mcp-mux.toml
SERVICE ?= general-memory
SOCKET ?= /tmp/$(SERVICE).sock
CMD ?= npx
CMD_ARGS ?= @modelcontextprotocol/server-memory
STATUS_FILE ?= $(HOME)/.rust-mux/status/$(SERVICE).json
LOG_LEVEL ?= info

# Help colors
HELP_C_CYAN   := \033[36m
HELP_C_GREEN  := \033[32m
HELP_C_YELLOW := \033[33m
HELP_C_RESET  := \033[0m

help:
	@printf '\n$(HELP_C_CYAN)%s$(HELP_C_RESET)\n' 'rust-mux targets'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'build' '- cargo build'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'release' '- cargo build --release'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'check' '- cargo check --all-targets --all-features'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'fmt' '- cargo fmt --all'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'fmt-check' '- cargo fmt -- --check'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'clippy' '- cargo clippy --all-targets --all-features -- -D warnings'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'test' '- cargo test --all-targets --all-features'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'test-full' '- test + opcjonalny pakiet testów transportu (ignored)'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'gates' '- fmt-check + clippy + test'
	@printf '\n'
	@printf '  $(HELP_C_YELLOW)%s$(HELP_C_RESET)\n' 'WIZARD / RUNTIME'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'wizard' '- uruchom interaktywny wizard (zapisuje config)'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'wizard-dry-run' '- uruchom wizard bez zapisu'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'run' '- uruchom mux dla SERVICE z CONFIG'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'run-tray' '- uruchom mux z tray + STATUS_FILE'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'proxy' '- uruchom rust-mux-proxy dla SOCKET'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'health' '- health check dla SERVICE z CONFIG'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'daemon-status' '- status wszystkich usług z daemona'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'dashboard' '- uruchom tray dashboard (feature: tray)'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'status-file-init' '- utwórz katalog dla STATUS_FILE'
	@printf '    $(HELP_C_GREEN)%-18s$(HELP_C_RESET) %s\n' 'clean-runtime' '- usuń SOCKET i STATUS_FILE'
	@printf '\n'
	@printf '  $(HELP_C_YELLOW)%s$(HELP_C_RESET)\n' "ZMIENNE (OVERRIDE NP. 'MAKE RUN SERVICE=BRAVE-SEARCH')"
	@printf '%s\n' '  CONFIG=$(CONFIG)'
	@printf '%s\n' '  SERVICE=$(SERVICE)'
	@printf '%s\n' '  SOCKET=$(SOCKET)'
	@printf '%s\n' '  STATUS_FILE=$(STATUS_FILE)'
	@printf '%s\n' '  CMD=$(CMD)'
	@printf '%s\n' '  CMD_ARGS=$(CMD_ARGS)'
	@printf '%s\n' '  LOG_LEVEL=$(LOG_LEVEL)'

build:
	cargo build

release:
	cargo build --release

check:
	cargo check --all-targets --all-features

fmt:
	cargo fmt --all

fmt-check:
	cargo fmt -- --check

clippy:
	cargo clippy --all-targets --all-features -- -D warnings

test:
	cargo test --all-targets --all-features

test-full:
	cargo test --all-targets --all-features
	cargo test --all-targets --all-features -- --ignored

gates: fmt-check clippy test

wizard:
	cargo run --bin rust-mux -- wizard --config "$(CONFIG)" --service "$(SERVICE)"

wizard-dry-run:
	cargo run --bin rust-mux -- wizard --config "$(CONFIG)" --service "$(SERVICE)" --dry-run

run:
	cargo run --bin rust-mux -- --config "$(CONFIG)" --service "$(SERVICE)" --log-level "$(LOG_LEVEL)"

run-tray: status-file-init
	cargo run --bin rust-mux -- --config "$(CONFIG)" --service "$(SERVICE)" --tray --status-file "$(STATUS_FILE)" --log-level "$(LOG_LEVEL)"

proxy:
	cargo run --bin rust-mux-proxy -- --socket "$(SOCKET)"

health:
	cargo run --bin rust-mux -- health --config "$(CONFIG)" --service "$(SERVICE)"

daemon-status:
	cargo run --bin rust-mux -- daemon-status

dashboard: status-file-init
	cargo run --features tray --bin rust-mux -- dashboard --status-file "$(STATUS_FILE)"

status-file-init:
	mkdir -p "$(dir $(STATUS_FILE))"

clean-runtime:
	rm -f "$(SOCKET)" "$(STATUS_FILE)"
