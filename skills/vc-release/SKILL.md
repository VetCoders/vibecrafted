---
name: vc-release
version: 0.1.0
description: >
  Ship code to market: release mechanics, financial awareness, legal basics,
  deployment reality. Trigger phrases: "release", "ship to market", "publish",
  "deploy to production", "vc-release", "go live", "launch", "wypuść wersję",
  "deploy", "release prep", "launch path".
---

# vc-release: Ship to Market

This is where "done in the repo" meets "done in the world." You're moving code from your machine to people's machines.
That's not abstract—it's financial, legal, and operational reality.

## Pipeline Position

```
scaffold → init → workflow → followup → marbles → dou → decorate → hydrate → [RELEASE]
                                                                             ^^^^^^^^^
```

Release is the final skill in the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. pipeline. It executes after:

- `vc-dou` has verified the product surface is complete
- `vc-decorate` has ensured visual coherence
- `vc-hydrate` has packaged distribution artifacts, SEO, and onboarding

Release takes those hydrated artifacts and pushes them into the world:
tags, changelogs, registry publishes, deployment, and go-to-market.

## Release Mechanics: The Real Work

**Git workflow:**

- Tag the exact commit. `git tag -a v1.2.3 -m "Release 1.2.3"` Not "v1.2.3-rc" unless you mean it.
- Changelog is non-negotiable. Include what changed, why it matters, breaking changes explicit.
- Push tags: `git push origin v1.2.3`

**GitHub Releases:**

- Automated: GitHub Actions creates the release artifact on tag push.
- Manual: Click Releases, Draft New, attach binaries, link to changelog, publish.
- Artifact names matter. `myapp-v1.2.3-linux-x86_64.tar.gz` tells users what they're downloading.

**Language-specific publishing:**

- npm: `npm publish` after version bump. Scope matters (`@org/package`). Publish to npm, not your server.
- Crates (Rust): `cargo publish` after `Cargo.toml` version bump. Check `cargo.io` first—names are claimed.
- PyPI: Build wheel+sdist, then `twine upload`. Or use `poetry publish`.
- Docker: Tag, push to registry. Consider multi-arch builds (amd64 + arm64).

None of this is optional if you want real adoption.

## Financial Awareness: You're Running a Business Now

**Distribution costs:**

- Hosting a download server: ~$20/month for bandwidth you'll actually use.
- CDN (Cloudflare, Fastly): Free tier works until you don't. Then ~$0.02 per GB. Scale matters.
- Docker registry: Docker Hub free tier gets rate-limited. Paid: ~$7/month for private repos.
- npm bandwidth: Free unless you egregiously abuse it. But every download costs npm money.

**Pricing model reality:**

- Open source means free, but free is not free to you. Support costs money (time).
- Freemium works if you have a clear paid tier. Don't list it and pretend it's open source.
- Enterprise license model: dual-license the code, charge enterprises. Works if your code solves enterprise problems.

**ROI thinking:**

- How much time did you spend? Is the market's willingness to pay worth it?
- If you're shipping a library, ROI is often indirect: reputation, hiring signal, future revenue.
- If it's a product, break-even is the minimum milestone.

## Legal Basics: Not Optional

**LICENSE file:**

- MIT? Simple, permissive, safe default.
- Apache 2.0? More explicit indemnity language. Enterprise prefers this.
- GPL? Viral license—anyone using your code must also open-source. Know what you're signing.
- Proprietary? Then don't claim open source.
- Custom? Don't. Use a standard license or talk to a lawyer.

**SECURITY.md:**

- Include it. Tells security researchers how to report vulnerabilities responsibly.
- Format: email, PGP key (if you're serious), disclosure timeline.
- Example: "Email security@yoursite.com with details. We'll acknowledge within 48h, fix within 14 days."

**Privacy and terms of service:**

- If you collect data (telemetry, analytics, user accounts), have a privacy policy.
- If your software is user-facing, have terms of service. Liability disclaimers matter.
- GDPR-aware if you serve Europe. CCPA-aware if you serve California.

**README.md—also legal armor:**

- Explicit about what this does and doesn't do.
- "This tool is provided as-is. We make no guarantees about production use."
- If it's new/beta, say so. Users need to know.

## Deployment Reality: Caddy vs Docker vs Nginx

This is where most people get lost. Let's be concrete.

**Nginx:**

- Use when: You're running a web server at scale, reverse proxying multiple services, need extreme performance.
- Setup: VPS, config files, manage certs yourself (or letsencrypt).
- Cost: Free software, but operator cost is high. You're managing it.
- Best for: APIs, web apps serving thousands, teams with ops experience.

**Docker:**

- Use when: You want reproducible deployment, isolation, cloud-native thinking.
- Setup: Write Dockerfile, push to registry, orchestrate with Compose or Kubernetes.
- Cost: Free runtime, but registry/compute costs are real.
- Best for: Startups, teams shipping fast, anything you'll deploy to multiple clouds.

**Caddy:**

- Use when: You want "it just works," automatic HTTPS, simple config.
- Setup: Single binary, JSON or text config, built-in reverse proxy.
- Cost: Free, tiny footprint, minimal operational overhead.
- Best for: Single-server deployments, hobby projects, MVP phase, new teams.

**Decision tree:**

- Do you have DevOps people? → Kubernetes + Docker
- Do you have a team? → Docker + Compose
- Are you solo? → Caddy or static hosting
- Do you already run Nginx? → Keep it, it's fine
- Are you at "how do we even deploy this?" stage? → Caddy + VPS is your answer

## Post-Release Verification: Users Will Find Bugs You Didn't

**Install path works:**

- Try installing from scratch. Not from your repo, from published artifacts.
- `npm install @yourorg/package` from a clean directory.
- `docker run yourimage:latest` with nothing pre-loaded.
- Follow your own README. If you get lost, users will too.

**Docs resolve:**

- All links in your docs should work. Check them.
- API docs generated? Rebuild them. Broken examples are reputation damage.
- Quickstart example: Run it cold. If it fails, fix it or update it.

**Brand coherence check:**

- Does the product look like a product or like a repo?
- Is there a representation surface (./presence/, landing page, or equivalent)?
- Do all public surfaces use consistent palette, fonts, tone?
- Does the install experience match the product's visual identity?
- If the product appears in another product's navbar (like loctree), does it visually belong?

**Users can actually onboard:**

- One person outside your team: ask them to use your product cold.
- Where do they get stuck? That's your fix list.
- Friction = support load.

## Go-to-Market: Code Alone Ships Nothing

**Launch announcements:**

- Twitter/X: Short hook, link to release notes.
- Hacker News: If it's novel enough. Follow the guidelines.
- Reddit: Relevant communities only. Spam kills trust.
- Product Hunt: Coordinate for day-of launch. Requires prep.
- Email: If you have a list, use it.

**Community outreach:**

- Changelog.com will link you if it's interesting.
- Lobsters accepts substantive posts about new tech.
- Indie Hackers: Good audience for indie projects.
- GitHub Trending: Happens naturally if people star your repo.

**Documentation site deploy:**

- Static site: Vercel, Netlify, GitHub Pages. Free, fast, reliable.
- Build from README: Use mdbook, docusaurus, or mkdocs.
- Deploy automatically: CI/CD on every docs change.
- Custom domain: ~$12/year, worth it for credibility.

**Key metric: Can a stranger find your code, understand what it does, and use it in 5 minutes?** If no, you haven't
shipped. You've just uploaded files.

## The Shipping Mindset

Release is not the end. It's the beginning of learning from real users. But the mechanics above—tags, changelogs, legal
clarity, deployment reality—separate projects that sustain from projects that die.

Ship it clean. Ship it documented. Ship it with a plan for what comes next.

## Anti-Patterns

- Publishing without running `vc-dou` first (shipping an incomplete product surface)
- Skipping `vc-hydrate` artifacts (no install path, no SEO, no onboarding)
- Tagging without a changelog (users cannot assess the upgrade)
- Deploying without post-release verification (install path test is mandatory)
- Treating release as a one-time event (it is a repeatable process)
- Running release on a chaotic tree or unmerged branch without explicit user approval

---

_"The code is done. The packaging is done. Now ship it to people."_

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_
