# PERCEPTION: How Agents See the Codebase

In the VibeCraft framework, agents don't just "read code"—they *perceive* the architecture. We achieve this primarily through **loctree**.

## Loctree integration

Loctree MCP provides structural code intelligence. Our agents start every deep architectural task by gaining codebase awareness through these baseline tools:

- `repo-view` - The entry point. It gives an overview of files, lines of code (LOC), languages, codebase health, and top hubs.
- `slice` - Before modifying a file, an agent runs this to see the file itself, all of its dependencies, and crucially, its consumers (who imports it).
- `find` - Before creating or redefining, agents search for symbols globally (with regex), finding definitions or mapping functional "crowds."
- `impact` - Before deleting or doing a major refactor, agents analyze the blast radius (direct and transitive consumers).
- `focus` - Used to understand a specific module, viewing internal edges and external dependencies.
- `tree` - A directory structure with LOC counts for spatial orientation.
- `follow` - Used to pursue structural signals, such as dead code, cycles, duplicate exports, and event pipelines.

## The VibeCraft Principle

Agents working within a "Living Tree" (a shared workspace) use these tools to proactively avoid collisions, understand side-effects, and make safe architectural decisions without demanding constant human micromanagement.

When you install VibeCraft, you gain this augmented perception engine by default in your AI context workflows.
