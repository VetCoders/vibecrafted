.PHONY: help vibecraft check

help:
	@echo "VibeCraft Framework Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make vibecraft    - Safely install or update the VibeCraft framework."
	@echo "  make check        - Run basic linters on shell scripts."

vibecraft:
	@echo "Starting VibeCraft Orchestrator..."
	@python3 scripts/setup_vibecraft.py

check:
	@echo "Checking shell scripts..."
	@find skills scripts -name "*.sh" -o -name "*.zsh" | xargs shellcheck -e SC1090,SC1091,SC2155,SC2034,SC2154 || true
	@echo "Check complete."
