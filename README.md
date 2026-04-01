<p align="center">
  <img width="1536" height="677" alt="VibeCrafted" src="https://github.com/user-attachments/assets/4c238bf2-3087-472a-a420-1f68f717f5ad" />
</p>

<h1 align="center">A framework that created itself؞</h1>

<p align="center">
  <em>...and its tooling, and its release pipeline, and its distribution channels.</em><br>
  <em>Check what it can craft for you.</em>
</p>

<p align="center">
  <a href="https://vetcoders.github.io/vibecrafted/">Website</a> ·
  <a href="docs/QUICK_START.md">Quick Start</a> ·
  <a href="docs/VIBECRAFTED.md">Manifesto</a> ·
  <a href="docs/FAQ.md">FAQ</a>
</p>

---

## What is VibeCrafted

VibeCrafted is a convergence framework for AI-assisted software development.

It does not write code for you. It gives you a **system** where AI-written code
is systematically improved until it meets production quality — through closed
verification loops, structural analysis tools, and multi-agent orchestration.

Every other tool says: _"AI will write your code."_
VibeCrafted says: _"AI will write your code — then prove it is good, or fix it until it is."_

That is not a promise of intelligence.
That is a promise of **process that converges to quality.**

### Proof

This framework built itself. Its skills, its installer, its CI pipeline,
its landing page, its docs, its distribution channels.
Meta-recursive. Every commit is evidence.

---

## The Three Marks

VibeCrafted has three typographic signatures — one for each layer of craft:

| Mark                        | Layer              | When to use                              |
| --------------------------- | ------------------ | ---------------------------------------- |
| `⚒🅅·🄸·🄱·🄴·🄲·🅡·🄰·🄵·🅃·🄴·🄳·؞` | **Produced with**  | Full product built through the framework |
| `𝓥𝓲𝓫𝓮𝓬𝓻𝓪𝓯𝓽𝓮𝓭؞`              | **Designed with**  | Design, UI, visual identity, brand work  |
| `// 𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍؞`           | **Developed with** | Source code, engineering, infrastructure |

The `؞` is not decoration. It is the mark.

---

## What You Get

| Layer             | Tool                                | What it does                                                                                                                                                           |
| ----------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Senses**        | Loctree                             | Structural codebase analysis — dead code, cycles, dependencies, blast radius. The agent reads architecture through instruments, not guesswork.                         |
| **Orientation**   | vc-init                             | Three senses before action: memory (what was done before), sight (what the code looks like now), ground truth (do the tools actually work).                            |
| **Convergence**   | vc-marbles                          | The loop: _"What is still wrong?"_ — find counterexamples to health, eliminate them, observe the cascade, repeat until nothing is wrong. Solo, duo, trio, multi-agent. |
| **Orchestration** | vc-agents                           | Spawn Claude, Codex, Gemini in terminal. Headless, background, with reports, transcripts, and metadata.                                                                |
| **Quality**       | vc-followup, vc-dou                 | Followup examines what went wrong. DoU (Definition of Undone) measures what is not yet ready to ship.                                                                  |
| **Craft**         | vc-workflow                         | The full pipeline: Examine → Research → Implement. One command, structured phases.                                                                                     |
| **Ship**          | vc-decorate, vc-hydrate, vc-release | From code to product: brand polish, packaging, market-facing distribution.                                                                                             |
| **Safety**        | rust-ai-locker                      | Resource locking. Two agents cannot crash the system with simultaneous compilation.                                                                                    |

---

## Install

Non-destructive. Interactive. Transparent. Reversible.

```bash
curl -fsSLO https://raw.githubusercontent.com/VetCoders/vibecrafted/main/install.sh
bash install.sh
```

The installer stages a local control plane under `~/.vibecrafted/tools/`,
then runs the orchestrator interactively. It tells you what it does before
it does it. It asks before touching your shell config.

Verify:

```bash
make -C ~/.vibecrafted/tools/vibecrafted-current doctor
```

If you have a local checkout:

```bash
make vibecrafted
```

Undo everything:

```bash
make -C ~/.vibecrafted/tools/vibecrafted-current uninstall
```

---

## Quick Start

```bash
cd ~/your-project
vibecrafted init claude
vibecrafted justdo codex --prompt "Add JWT authentication"
```

The `vibecrafted` launcher is the main front door. The legacy `vc-*` wrappers
still work as shortcuts once shell helpers are loaded.

```
vibecrafted workflow claude --prompt "Plan and implement auth module"
vibecrafted marbles codex --count 3 --depth 3
```

Or run phases individually:

```
vibecrafted scaffold claude --prompt "Map the architecture"
vibecrafted workflow claude --prompt "Plan and implement auth module"
vibecrafted followup codex --prompt "Audit the recent implementation"
vibecrafted marbles codex --count 3 --depth 3
```

Type `vibecrafted help` for the command deck, or `vc-` and hit tab once the
shell helpers are installed.

---

## The Philosophy

We do not treat AI like magic.

We treat it like a stochastic engine that produces both signal and noise.
The signal is valuable. The noise is physics, not failure.

The framework exists because **the noise is manageable** — if you have
a system that finds it, names it, and eliminates it, one counterexample
at a time.

That system is called **Marbles**.

Read the full manifesto: [VIBECRAFTED.md](docs/VIBECRAFTED.md)

---

## Requirements

- macOS or Linux
- Git, Python 3.10+, `make`
- One or more agent CLIs: Claude Code, Codex, or Gemini CLI
- Recommended foundations: [Loctree](https://github.com/Loctree/loctree-suite), AICX, prview

---

## For Founders

Free for personal use and for startups. No limits on repos or agents.

For enterprise: **info@vibecrafted.io**

---

## Contributing

We build tools for AI agents to build tools. Read [CONTRIBUTING.md](CONTRIBUTING.md).

---

<p align="center">
  <em>Move fast, but with taste.</em><br>
  <em>Be radical when radical is cleaner.</em><br>
  <em>Finish the whole thing, not just the code.</em>
</p>

<p align="center">
  <code>// 𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍؞</code>
</p>

<p align="center">
  <sub>(c)2026 VetCoders · <a href="https://vibecrafted.io">vibecrafted.io</a></sub>
</p>
