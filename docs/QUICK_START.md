# Quick Start

You have a repo. You have AI agents. You want them to stop guessing
and start converging.

## 1. Install

```bash
curl -fsSLO https://raw.githubusercontent.com/VetCoders/vibecrafted/main/install.sh
bash install.sh
```

Non-destructive. Interactive. Tells you what it does before it does it.
Asks before touching your shell config. Everything reversible with
`make -C $VIBECRAFTED_ROOT/.vibecrafted/tools/vibecrafted-current uninstall`.

After install, open a new terminal or:

```bash
source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"
```

## 2. Verify

```bash
make -C $VIBECRAFTED_ROOT/.vibecrafted/tools/vibecrafted-current doctor
```

Green means ready. Yellow means the doctor tells you why.

## 3. Orient your agent

Go to any git repo:

```bash
cd $VIBECRAFTED_ROOT/your-project
vibecrafted init claude
```

This runs `vibecrafted init claude` — the command-deck front door for `vc-init`.
Your agent gets three things before touching anything:

- **Memory** — what was done before (indexed session history)
- **Sight** — what the code looks like now (structural map via loctree)
- **Ground truth** — whether quality gates actually pass

Your agent now has orientation instead of assumptions.

## 4. Build something

```bash
vibecrafted justdo codex --prompt "Add user authentication with JWT"
```

`vibecrafted justdo` chains the entire pipeline through `vc-justdo`:

- **Craft** — examines the repo, researches the approach, implements
- **Converge** — runs marbles loops: _"what is still wrong?"_ → fix → repeat
- **Ship** — checks product surface, decorates, packages for release

## 5. Run phases individually

```bash
vibecrafted scaffold claude --prompt "Plan the auth architecture"   # vc-scaffold
vibecrafted init claude                                             # vc-init
vibecrafted workflow claude --prompt "Plan and implement auth"      # vc-workflow
vibecrafted followup codex --prompt "Audit the auth changes"        # vc-followup
vibecrafted marbles codex --count 3 --depth 3                       # vc-marbles
vibecrafted dou claude --prompt "Audit launch readiness"            # vc-dou
vibecrafted decorate codex --prompt "Polish the surface"            # vc-decorate
vibecrafted hydrate codex --prompt "Package the product"            # vc-hydrate
vibecrafted release codex --prompt "Prepare release steps"          # vc-release
```

## 6. Multi-agent research

For hard problems, send the same question to multiple planners:

```
Research: what is the best auth strategy for this codebase?
```

`vc-partner` sends the same plan to Claude, Codex, and Gemini independently.
You get three expert opinions. Synthesize the strongest parts. Resume the
winning agent into implementation.

## 7. Convergence loops

When the code is close but not done:

```bash
vibecrafted marbles codex --prompt "Fill the gaps on the auth module" --count 3
```

The agent enters a convergence loop — tools find what is wrong, agent fixes it,
tools check the new landscape, repeat. Stops when no tool can find a single
remaining accusation.

## The tab trick

Type `vibecrafted help` for the command deck. Once shell helpers are loaded,
`vc-` wrappers stay available as shortcuts.

---

`// 𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍؞`
