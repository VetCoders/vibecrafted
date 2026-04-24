# Quick Start

You have an AI-built repo. You want to ship it without the vibe hangover.

## 1. Install

Terminal-native path for the human kickoff:

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
```

The bootstrap explains what it will do and asks before proceeding on an
attended terminal. Pass `--yes` if you want to pre-approve that bootstrap
prompt.

This path stages the control plane, bootstraps the foundation layer, and runs
the compact installer truth used by automation as well.

Optional browser-guided path for operators who prefer a GUI:

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui
```

Non-destructive. Interactive. Tells you what it does before it does it.
Asks before touching your shell config. Everything reversible with
`make -C $VIBECRAFTED_ROOT/.vibecrafted/tools/vibecrafted-current uninstall`.

Inside a local checkout, `make vibecrafted` runs the terminal-native installer
wizard (default shell-first front door) and `make install` stays
direct/non-interactive. If you prefer the browser-guided surface, run
`make wizard` or the alias `make gui-install`.

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
vibecrafted implement codex --prompt "Add user authentication with JWT"
# legacy alias still works: vibecrafted justdo codex --prompt "..."
```

`vibecrafted implement` (alias: `justdo`) runs the autonomous delivery contract in `vc-implement`:

- **Orient** — map the repo, load prior intent, and choose the smallest shape that works
- **Implement** — make the change, add tests, and integrate with the live runtime
- **Converge** — run followup, then `vc-marbles` if P0 or P1 findings remain
- **Return** — hand back a verified surface with the next truthful move called out

## 5. Run phases individually

```bash
vibecrafted scaffold claude --prompt "Plan the auth architecture"   # vc-scaffold
vibecrafted init claude                                             # vc-init
vibecrafted intents codex --prompt "Audit what from the plan landed" # vc-intents
vibecrafted workflow claude --prompt "Plan and implement auth"      # vc-workflow
vibecrafted review codex --prompt "Audit the auth changes"          # vc-review
vibecrafted marbles codex --count 3 --depth 3                       # vc-marbles
vibecrafted ownership codex --prompt "Take this surface to done"    # vc-ownership
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

For the full route inventory, see [SKILLS](./SKILLS.md). For the framework-wide
flow map, see [WORKFLOWS](./WORKFLOWS.md).

Preparing the public launch surface and directory submissions?
Use [Release Kickoff](./RELEASE_KICKOFF.md) together with
[Submission Forms](./SUBMISSION_FORMS.md).

---

`//𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.`
