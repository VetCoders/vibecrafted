---
run_id: rsch-183346
agent: gemini
skill: vc-research
project: vibecrafted
status: completed
---

# Research: Vibecrafted Repository Overview (April 16, 2026)

## Problem

Understand the `vibecrafted` repository's capabilities, architecture, and usage patterns to provide a foundational guide for the ecosystem.

## Findings

### Primary Purpose

`vibecrafted` is a **release engine for AI-built software**. It bridges the gap between AI-generated code and production-ready software, specifically targeting "Vibe Hangover" issues like fragile auth and silent failures.

### CLI Architecture

The `vibecrafted` CLI acts as a "command deck" for modular skills. It handles session management, orchestration, and provides a unified interface for various AI agents (Claude, Codex, Gemini).

### Skills System

Skills are pluggable modules in `skills/`. Each is defined by:

- **SKILL.md**: Metadata and detailed operator instructions.
- **agents/**: Model-specific interface configurations.
- **Protocol**: Skills like `vc-marbles` (convergence) and `vc-dou` (readiness audit) form a rigorous delivery pipeline.

### Repository Structure

- `scripts/`: Implementation of the command deck and installer.
- `skills/`: Behavioral logic for agent tasks.
- `docs/`: Extensive philosophical and technical guidance.
- `artifacts/`: Storage for session-specific truth and agent perception.

## Implementation Notes for Future Agents

- Always run `vc-init` at the start of a session to perceive the "Living Tree".
- Use `vc-research` for triple-agent triangulation on complex decisions.
- Follow the `vc-marbles` protocol for stabilizing overgenerated code.
- Consult `docs/THE_VIBE_HANGOVER.md` for the core motivation behind the framework.
