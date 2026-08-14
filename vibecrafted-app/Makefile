.PHONY: gates fmt fmt-check lint test check workspace-check clean help bindings xcode app app-debug dmg dmg-signed notarize release

gates: fmt-check lint test

fmt:
	cargo fmt --all

fmt-check:
	cargo fmt --all --check

lint:
	cargo clippy --workspace --all-targets -- -D warnings

test:
	cargo test --workspace

check: workspace-check

workspace-check:
	cargo check --workspace

clean:
	cargo clean

bindings:
	@$(MAKE) -C shell-agent bindings

xcode:
	@$(MAKE) -C shell-agent xcode

app:
	@$(MAKE) -C shell-agent app

app-debug:
	@$(MAKE) -C shell-agent app-debug

dmg:
	@$(MAKE) -C .. dmg

dmg-signed:
	@$(MAKE) -C .. dmg-signed

notarize:
	@$(MAKE) -C .. notarize

release:
	@$(MAKE) -C .. release

# Help colors
HELP_C_CYAN   := \033[36m
HELP_C_GREEN  := \033[32m
HELP_C_YELLOW := \033[33m
HELP_C_RESET  := \033[0m

help:
	@printf '%s\n' 'targets: gates fmt fmt-check lint test check workspace-check clean bindings xcode app app-debug dmg dmg-signed notarize release'
