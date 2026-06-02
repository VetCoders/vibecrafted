.PHONY: gates fmt fmt-check lint test check workspace-check clean help bindings xcode app app-debug dmg dmg-signed

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
	@$(MAKE) -C shell-agent dmg

dmg-signed:
	@$(MAKE) -C shell-agent dmg-signed

help:
	@printf '%s\n' 'targets: gates fmt fmt-check lint test check workspace-check clean bindings xcode app app-debug dmg dmg-signed'
