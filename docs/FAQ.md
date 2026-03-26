# VibeCraft FAQ

Questions the community will ask. Answers pending — if you know the answer, PR it.

## Installation

- Why does the installer write to `~/.vibecrafted/` and not `~/.agents/` like other tools?
- What happens to my existing skills in `~/.agents/skills/` after installation?
- Why does `make install` ask me questions instead of just installing silently?
- Can I install VibeCraft without giving it write access to my `.zshrc`?
- What if I already have a Starship/Atuin/Zellij config — will VibeCraft overwrite it?
- How do I move my installation to a custom directory?
- Why is Gemini excluded from symlink creation by default?
- What does `make doctor` actually check?
- How do I completely remove VibeCraft from my system?
- Why does the installer back up my existing state before every install?

## Skills & Agents

- What is the difference between a skill and an agent?
- Why can't I just use ChatGPT/Copilot instead of this framework?
- How does VibeCraft decide which AI model to use for a task?
- What is the Marbles loop and why does it exist?
- Why do agents sometimes produce worse code than a single prompt?
- How does `vc-followup` decide between P0, P1, and P2 severity?
- What happens when two agents edit the same file at the same time?
- Can I add my own custom skills to the framework?
- Why is there no `vc-test` skill?
- What is the Definition of Undone and why is it not the Definition of Done?

## Architecture

- Why are skills stored centrally instead of per-project?
- What is the relationship between `~/.vibecrafted/skills/`, `~/.claude/skills/`, and `~/.agents/skills/`?
- Why does VibeCraft use symlinks instead of copying skill files?
- What is the `~/.vibecrafted/artifacts/` directory for?
- Why do artifact paths include the date?
- How does the central store know which GitHub org/repo I'm working in?
- What is `VIBECRAFTED_HOME` and when would I change it?
- Why is there a `config/` directory with Starship and Zellij configs?
- What is mise and why does VibeCraft include a `mise.toml`?

## Runtime Foundations

- What is loctree and why does VibeCraft depend on it?
- What is aicx-mcp and why is it called a "decisions retrieval engine" not a "memory system"?
- Can I use VibeCraft without installing loctree or aicx?
- Why does prview generate artifacts instead of just printing to terminal?
- What is ScreenScribe and when would I use it instead of a bug report?

## Workflow

- What does "Craft, Converge, Ship" actually mean in practice?
- How long does a typical Marbles convergence loop take?
- When should I use `vc-ship` vs running individual skills manually?
- How do I know when convergence is "done"?
- What is the ralph-loop and how does it relate to vc-marbles?
- Can I run VibeCraft in CI/CD or is it only for interactive use?
- How does VibeCraft handle merge conflicts between parallel agents?

## For Skeptics

- Is this just a fancy prompt wrapper?
- Can two veterinarians really build enterprise software with AI?
- Why should I trust a framework built by people who aren't professional programmers?
- What makes VibeCraft different from AutoGPT/CrewAI/LangChain agents?
- Does VibeCraft actually work on large codebases or only toy projects?
- Why is the marble metaphor useful and not just marketing?

---
VibeCrafted by VetCoders | vibecrafted.io
