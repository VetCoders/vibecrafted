---
name: vc-hydrate
version: 1.0.0
description: >
  Packaging and go-to-market hydration skill. Takes DoU audit findings and
  executes the non-code work that bridges the gap between "it works" and
  "someone can buy this." Generates marketplace listings, SEO fixes,
  distribution artifacts, onboarding flows, landing page content, and
  representation surfaces for products that do not naturally have a public web UI.
  Trigger phrases: "hydrate", "package for market", "prepare for launch",
  "przygotuj do launchu", "fix the packaging gap", "marketplace listing",
  "nawodnij", "make it shippable", "go-to-market", "distribution",
  "SEO fix", "landing page", "onboarding", "completion sprint".
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v2 -->

> **Operator CLI / slash-command layer:** invoking `/vc-<workflow>` or
> `vibecrafted <workflow> <agent>` means dispatching the external Vibecrafted
> fleet through the launcher. In that layer, the invocation is an imperative to
> act, not a no-op, and not native in-process subagents.
>
> **Skill-loading / chat layer:** loading this `SKILL.md` inside Codex, Claude,
> Gemini, or another local agent does not mean self-dispatch. Read and apply the
> skill in the current thread; do not spawn another agent unless the operator
> explicitly asks you to launch, dispatch, run the fleet, or gives a concrete
> command such as `vc-init codex` / `vibecrafted init claude`.
>
> The sole native in-process carve-out is `vc-delegate`.

<!-- /fleet-imperative -->

# vc-hydrate — The Antidote to Always-in-Production

> "The code is dry — structurally complete but missing the fluid that makes it flow to users. Hydration means: make the path from stranger to user frictionless."

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "parallel", or "clean branch" are not enough. Re-read files before editing, adapt to concurrent changes, and report a substrate failure if the current tree is too poisoned to continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate

Before this workflow performs repo-specific analysis, planning, implementation, review, release, or delegation, it MUST run or consume the `vc-init` procedure for the assigned repo. If fresh `vc-init` evidence is absent, perform the init pass first and treat workflow-specific work as blocked until repo truth exists.

`Loctree:loctree` is the default structural perception skill for that pass. Use Loctree before grep or docs-driven claims to produce or refresh the Code-Derived Application Map: repo-view, focus, slice, impact, find, and follow as relevant. Search for existing symbols and contracts before creating new ones; run impact before delete or major refactor; run slice before editing.

The point is to find the hooks: load-bearing hubs, twins, dead code, drift, runtime entrypoints, and blast-radius traps. If the task is explicitly non-repo or no-code, state the no-repo exception in the report. Otherwise, missing `vc-init`/Loctree evidence is a process failure.

Enter via `vibecrafted start` (or `vc-start`). Then launch through the command deck:

```bash
vibecrafted hydrate codex --prompt 'Package for marketplace'
vc-hydrate claude --prompt 'Generate missing SEO and landing page'
vibecrafted hydrate gemini --file /path/to/dou-report.md
```

Hydrate is the packaging agent that DoU calls for. It treats "create a DMG installer" and "write SEO-friendly copy" as first-class engineering tasks, not afterthoughts.

**Canonical rule:** every serious product needs a presentation surface, even if it is not itself a web product. Desktop apps, CLI tools, MCP servers, local runtimes, and internal systems still need an external face that lets a stranger discover, understand, see, assess, and adopt.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Pipeline Position

```
scaffold → init → workflow → followup → marbles → dou → decorate → [HYDRATE] → release
```

## When To Use

- After a `vc-dou` audit identifies packaging gaps
- Before any marketplace submission or public launch
- When the team says "it works, now make it findable/installable/buyable"
- Periodic hydration sprint (recommended: pair with DoU every 2 weeks)
- When Plague Score > 40

## Hydration Domains

### Domain 1 — Repository Hydration

Fix repo governance gaps from DoU. Generate contextually appropriate content:

- **LICENSE** — detect project intent (commercial / open-source / dual), pick MIT/Apache-2.0/proprietary
- **CONTRIBUTING.md** — extract from README if present; cover setup, coding standards, PR process, code-of-conduct link
- **CHANGELOG.md** — parse git log for unreleased changes; Keep-a-Changelog format; version headers match published versions
- **SECURITY.md** — standard responsible disclosure template; GitHub Security Advisories preferred
- **CI workflows** — language-detection driven (Rust: cargo check/clippy/test/fmt; Node: lint/test/build; Python: ruff/pytest); always include dependency audit + license check

**Version sync:** `grep -rn "version" Cargo.toml package.json pyproject.toml` then compare to published versions (`cargo search`, `npm view`) and website badges/refs. Mismatch → P1 finding.

### Domain 2 — Distribution Hydration

Make the product installable without a dev toolchain:

- **CLI Tools (Rust):** `cargo install <name>` works; GitHub Releases with prebuilt binaries (linux-x86_64, macos-arm64, macos-x86_64); install script `curl -sSfL <url> | sh`; Homebrew formula (tap or core); shell completions generated and included. Generate GitHub Actions release workflow: cross-compile targets, GitHub Release assets, auto-update Homebrew formula.
- **Desktop Apps (macOS):** `.app` bundle with proper Info.plist; DMG with background image and Applications symlink; code signing with Developer ID; notarization via notarytool; Homebrew cask formula; Sparkle (or equivalent) for auto-updates. Use `create-dmg` template (`--volname`, `--background dmg-background.png`, `--window-size 600 400`, `--icon-size 100`, `--app-drop-link 400 200`).
- **Web Apps:** Dockerfile, docker-compose.yml for local preview, env-var docs (`.env.example`), health check endpoint (`/health` or `/api/health`), graceful shutdown handling.

### Domain 3 — Discoverability Hydration

Fix SEO and web presence:

**SSR / pre-rendering for SPA sites.** Problem: JS-rendered sites are invisible to crawlers. Solutions in order of preference:

1. Static pre-rendering at build time (best for landing pages)
2. SSR with hydration (for dynamic content)
3. Hybrid: static landing + SPA for app
4. Minimum: `<noscript>` fallback with key content

For Leptos (WASM): enable SSR mode or generate static HTML; pre-render critical routes at build time; ensure `<title>`, `<meta>`, `<h1>` exist in initial HTML.

**Meta tags template** per public page: `<title>{Product} — {Tagline} | {Company}</title>`, meta description (≤155 chars), meta keywords (5-8 relevant), Open Graph set (`og:title`, `og:description`, `og:image`, `og:type=website`), Twitter card set (`twitter:card=summary_large_image`, `twitter:title`, `twitter:description`).

**Security headers (server config):** `Strict-Transport-Security: max-age=63072000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'self'`.

**robots.txt + sitemap.xml** — generate from actual URL structure; ensure no duplicate content across domains; submit to Google Search Console (manual step — flag for user).

### Domain 4 — Commercial Surface Hydration

Build the stranger-to-customer path.

**Landing page structure:**

1. Hero: tagline + 1-sentence value prop + primary CTA
2. Problem: pain point in user's words
3. Solution: how product solves it (3 bullets max)
4. Social proof: stats, testimonials, case studies
5. How it works: 3-step visual flow
6. Pricing: clear tiers or "contact us"
7. CTA repeat: same primary CTA

Generate as: Markdown (static site generators), HTML (direct use), copy doc (designer handoff).

**Representation surface scaffolding (mandatory when missing).** If the product is not a web app, Hydrate still scaffolds a presentation surface:

- **Desktop apps** — landing/showcase, screenshots/product shots, "how it works", install path (DMG/MSI/AppImage/Homebrew cask), trust signals (security, local-first, offline, privacy)
- **CLI tools** — landing or docs-style one-pager, command examples, install command, sample output, who-it's-for
- **MCP servers / infra tools** — explainer page, architecture diagram, workflow examples, install + connection path, real-world use cases
- **Internal/hybrid products** — founder-facing showcase, capability summary, screenshots/diagrams/mocks, runtime-vs-presentation explanation

Hydrate should never assume "no website needed" means "no representation needed."

**Marketplace listings:**

For Claude Code Skills Marketplace:

```markdown
# {Skill Name}

{One-line description}

## What it does

{2-3 sentences explaining the value}

## When to use

{Bullet list of trigger scenarios}

## How it works

{Brief technical explanation}

## Requirements

- {Required tools/dependencies}
- {Optional enhancements}

## Part of

{Suite name} — {suite description}
```

For crates.io / npm / PyPI: description (<250 chars, keyword-rich), keywords (5 relevant terms), categories (matching registry), homepage (landing URL), repository (GitHub URL), documentation (docs URL), readme (path).

### Domain 5 — Onboarding Hydration

Create the "first 5 minutes" experience:

- **CLI tools:** install command (one line, copy-pasteable) → first command (immediate value) → "what just happened" → next steps (2-3 progressive commands) → where to get help
- **Web apps:** signup (<3 fields) → onboarding wizard (<5 steps) → sample data or demo mode → quick win within 60s → docs link
- **Skills/plugins:** install command → trigger phrase to test → expected output → customization options

### Domain 6 — Representation Layer Hydration

For products that are real, usable, and valuable but currently invisible from the outside. Build the minimum intentional external-facing surface required for the product to be legible to strangers.

Possible artifacts: `docs/index.html` landing page, one-page static showcase, product one-pager (Markdown/HTML), feature explainer, screenshots/diagram pack, social preview image, concise positioning copy, CTA layer ("install"/"try"/"request access"/"contact").

Recommended structure: product name + 1-line value prop → what it is → who it's for → why it exists → how it works → how to try/install/access → visual proof (screenshots, diagrams, examples).

**This is not optional garnish. It is the product's public face.**

## Hydration Sprint Protocol

1. **Ingest DoU report.** Extract all P0/P1 findings. Sort by impact (commercial surface > discoverability > repo governance).
2. **Triage into domains.** Map each finding to a domain (1-6). Some findings map to multiple — list all.
3. **Generate artifacts.** Per finding: missing files → create them; missing meta → generate HTML; missing install path → CI workflow; missing landing → write copy; missing representation → scaffold appropriate to product type; missing marketplace listing → generate listing.
4. **Verify via DoU.** Re-run on affected areas. Target: Plague Score reduction ≥20 points.
5. **Present to user.** Hydration Report with before/after Plague Scores, table of artifacts generated per domain (status), and remaining manual steps (DNS, API keys, marketplace submit button, etc.).

## Pipeline Integration

```
Phase 1 — Craft:     scaffold → init → workflow → followup
Phase 2 — Converge:  marbles ↻ (loop until P0=P1=P2=0)
Phase 3 — Ship:      dou → decorate → hydrate → release
```

Hydrate produces packaging artifacts. `vc-decorate` polishes visual coherence before hydration. After hydration, `vc-release` handles deployment and go-to-market launch. Re-run DoU after hydration to verify the gap closed.

## Subagent Delegation

For large hydration sprints, split domains across subagents using `vc-agents`:

```
Agent 1: Repo Hydration (LICENSE, CONTRIBUTING, CI, CHANGELOG)
Agent 2: Distribution Hydration (release workflows, installers)
Agent 3: Discoverability Hydration (SEO, meta tags, pre-rendering)
Agent 4: Commercial Hydration (landing copy, marketplace listings)
```

Each agent receives: DoU findings for its domain, template artifacts from this skill, standard living-tree preamble.

## Anti-Patterns

- Hydrating without a DoU audit first (fixing what you assume, not what's measured)
- Generating files without repo context (LICENSE type must match project intent)
- Writing marketing copy without understanding the product (run vc-init first)
- Assuming desktop / CLI / MCP / local products do not need a representation layer
- Treating hydration as one-off (it's a recurring sprint, like refactoring)
- Hydrating everything at once (prioritize: P0 commercial gaps first)
- Forgetting to re-run DoU after hydration (verify the fix)

## "Done Done" Definition

A project is hydrated when:

- A stranger can **DISCOVER** it (search engines, marketplace, word of mouth)
- A stranger can **UNDERSTAND** it (landing, README, value prop clear in 30s)
- A stranger can **SEE** it (representation surface exists, even if not web-native)
- A stranger can **INSTALL** it (one command, no dev toolchain, <5 minutes)
- A stranger can **USE** it (onboarding, quick win within 60 seconds)
- A stranger can **PAY** for it (pricing, signup, trial — if commercial)
- A stranger can **CONTRIBUTE** (CONTRIBUTING.md, issue templates, CI — if open source)

Until all six are true, the project is in the Always-in-Production state. Hydration is the antidote.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
