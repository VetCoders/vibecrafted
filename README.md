# VibeCraft Framework

The definitive toolkit for AI-guided engineering.

VibeCraft is not just a collection of prompts; it is a structured, opinionated framework for orchestrating AI agents (Codex, Claude, Gemini) to build, refactor, and ship software at veterinary speed.

## The Paradigm
We follow the **Living Tree** methodology. Agents work directly in your repository. We do not use isolated worktrees for active implementation unless testing destructive operations. We believe in *Product truth beating local elegance*.

Read more in our core documents:
- [VIBECRAFTED.md](docs/VIBECRAFTED.md) - The core philosophy.
- [PERCEPTION.md](docs/PERCEPTION.md) - How our agents see your code using loctree.

## Installation

We strictly adhere to a **"No 'why?' questions" rule** for installation. 
Our installer is 100% transparent, interactive, and non-destructive. It explains everything it does and only adds a single `source` line to your shell configuration. It never overwrites your global configs.

To install or update the VibeCraft Framework:

```bash
make vibecraft
```

This will run our safe, interactive orchestrator (`setup_vibecraft.py`), guide you through the process, and set up your environment with our customized sidecar frontier configurations (starship, zellij) for use *only* within VibeCraft workflows.

## Directory Structure

- `skills/` - The core AI skills (e.g., `vc-ship`, `vc-ownership`, `vc-workflow`). These are the brains of the operations.
- `docs/` - Core architectural documentation.
- `scripts/` - Installation and migration scripts.
- `config/` - The VibeCraft frontier configs (starship, atuin, zellij) loaded dynamically as sidecars.

## Getting Started

Once installed, simply run your preferred VibeCraft command in the terminal. For example:
- `vc-ship`: Ship a feature from idea to completion.
- `vc-dou`: Run a "Definition of Undone" audit.
- `vc-workflow`: Run the full Examine -> Research -> Implement pipeline.

For a full list of commands, just type `vc-` and hit tab.
