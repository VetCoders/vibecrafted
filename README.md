<p align="center">
  <img width="1536" height="677" alt="𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." src="https://github.com/user-attachments/assets/4c238bf2-3087-472a-a420-1f68f717f5ad" />
</p>

<h1 align="center">Ship AI-built software without the vibe hangover</h1>

<p align="center">
  <em>The release engine for AI-built software.</em><br>
  <em>It mapped itself, fixed itself, packaged itself, and built its own distribution path.</em>
</p>

<p align="center">
  <a href="https://vibecrafted.io/">Website</a> ·
  <a href="docs/QUICK_START.md">Quick Start</a> ·
  <a href="docs/runtime/MANIFESTO_EN.md">Manifesto</a> ·
  <a href="docs/FAQ.md">FAQ</a>
</p>

---

## The Weekend Hangover

**We are AI-native. AI generates code, but it doesn't deliver it.**

Most AI tools finish their job at the first draft. They leave you with a codebase that looks like it works, but falls apart when you try to ship it. You get hit with the [**Vibe Hangover**](docs/THE_VIBE_HANGOVER.md):

- **Auth held together with tape** that kills your enterprise deals during technical reviews.
- **God tables** with 35 columns that cause timeouts and massive serverless bills.
- **Silent failures** where a crashed Stripe webhook loses 8% of your revenue and you never get an alert.
- **Deploy and pray** strategies that take down the app on a Friday afternoon.

_(Read the full use case: [The 4 ways AI-coded MVPs break in production](docs/THE_VIBE_HANGOVER.md))_

---

## The Promise

**We ship AI-built software.**

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. is not another code generator. It is the release engine you run after AI has produced a repo and before a real user touches it. It forces that repo through perception, verification, convergence, install truth, packaging, and launch-readiness checks until a stranger can install it, trust it, and actually use it.

---

## The VetCoders Axioms

1. **AI-Native, not AI-assisted:** We don't write the code. We craft the delivery.
2. **Perception over Memory:** The agent must see the structural truth now, not rely on stale summaries.
3. **Code Mapping over Green Quality Gates:** Passing tests on broken architecture is just a faster train on the wrong tracks.
4. **Intentions over RAG:** Retrieve _why_ we built it, not just a blind vector search of _how_.
5. **Move On over Backward Compatibility:** If the abstraction is rotting, cut it. Don't preserve garbage "just in case."

---

## The Hero Loop

**It's obvious AI will generate code. 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. asks: _what is still wrong?_**

The system finds the problems, fixes them, and repeats the loop until nothing important is left.

**1. The Draft:** You build an MVP using Cursor, Copilot, or Claude.
**2. The Finding:** Quality gates and structural maps locate the exact failures.
**3. The Fix:** The agent eliminates the counterexamples.
**4. The Close:** We run the loop. We don't stop until P0 / P1 / P2 = 0.

---

## The System Under The Hood

Behind this simple effect is an architecture built to orchestrate, map, and execute.
_(No longer guessing the architecture, but seeing it)._

| Layer               | How it works                                                                                                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Seeing it All**   | The agent stops guessing architecture. It uses **Loctree** to see the entire project structure, dead code, and dependencies before it changes anything.                               |
| **Convergence**     | `vc-marbles` runs the loop. It is not trying to "prove correctness." It only asks "what is still wrong?" and fixes it.                                                                |
| **Multi-Agent**     | `vc-agents` lets you spin up Claude, Codex, and Gemini in parallel right in your terminal. Compare their results or have them tackle different architectural slices at the same time. |
| **The Final Check** | `vc-dou` (Definition of Undone) asks if it's shippable: Can you install it? Can someone trust it? Is there an onboarding page?                                                        |

---

## The Three Marks

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. has three typographic signatures — one for each layer of craft:

| Mark                      | Layer              | When to use                              |
| ------------------------- | ------------------ | ---------------------------------------- |
| `⚒🅅·🄸·🄱·🄴·🄲·🅡·🄰·🄵·🅃·🄴·🄳·` | **Produced with**  | Full product built through the framework |
| `𝓥𝓲𝓫𝓮𝓬𝓻𝓪𝓯𝓽𝓮𝓭`             | **Designed with**  | Design, UI, visual identity, brand work  |
| `//𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.`          | **Developed with** | Source code, engineering, infrastructure |

The `` is not decoration. It is the mark.

---

## Install

Non-destructive. Interactive. Transparent. Reversible.

Prefer the guided browser path when you are onboarding a founder, PM, or less terminal-native operator:

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui
```

The guided path stages the local control plane, bootstraps the foundation layer, runs the same compact installer truth used by automation, and leaves a readable `START_HERE.md` behind.

Use the direct compact path when you are scripting the install or you already know you want the terminal-only flow:

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
```

Inside a local checkout, `make vibecrafted` opens the terminal-native installer wizard — the built-in `vetcoders-installer` runner driven from `install.toml`, with reason + consent per phase and cargo-style sticky progress. `make install` routes through the same runner with auto-approve, so automation and humans share one engine.

Shell is our everyday workforce entry and all the tools are terminal-native. Nevertheless if you need GUI we also offer it! Run `make wizard` to keep the same trust-building cadence directly in the browser.

Verify:

```bash
make -C $VIBECRAFTED_ROOT/.vibecrafted/tools/vibecrafted-current doctor
```

---

## Quick Start

```bash
cd $VIBECRAFTED_ROOT/your-project
vibecrafted init claude
vibecrafted justdo codex --prompt "Add JWT authentication"
```

Type `vibecrafted help` for the command deck, or `vc-` and hit tab once the shell helpers are installed.

When you want to walk the release surface explicitly, run:

```bash
vibecrafted dou claude --prompt "Audit launch readiness"
vibecrafted decorate codex --prompt "Polish the release surface"
vibecrafted hydrate codex --prompt "Package the product"
vibecrafted release codex --prompt "Prepare release steps"
```

---

## For Founders

Free for personal use and for startups. No limits on repos or agents.

For enterprise: **info@vibecrafted.io**

---

<p align="center">
  <em>Move fast, but with taste.</em><br>
  <em>Finish the whole thing, not just the code.</em>
</p>

<p align="center">
  <code>//𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.</code>
</p>

<p align="center">
  <sub>(c)2024-2026 VetCoders · <a href="https://vibecrafted.io">vibecrafted.io</a></sub>
</p>
