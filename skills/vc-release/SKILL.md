---
name: vc-release
version: 0.2.0
description: >
  Final outward ship skill. Turns "done in the repo" into "safe, visible, deployable,
  discoverable, and launchable in the world." Covers release mechanics, deployment
  topology, reverse-proxy defaults, Semgrep-gated security hygiene, domain and DNS
  wiring, SEO/indexability, verification challenges, onboarding truth, and post-release
  smoke checks. Trigger phrases: "release", "ship to market", "publish",
  "deploy to production", "vc-release", "go live", "launch", "wypuść wersję",
  "deploy", "release prep", "launch path", "launch checklist", "production checklist".
---

# vc-release: Ship It Without Lying

## Operator Entry

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start vibecrafted
```

Then launch this workflow through the command deck, not raw `skills/.../*.sh` paths:

```bash
vibecrafted <workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --file '/path/to/plan.md'
```

```bash
vc-<workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --prompt '<prompt>'
```

If `vc-<workflow> <agent>` is invoked outside Zellij, the framework will attach
or create the operator session and run that workflow in a new tab. Replace
`<workflow>` with this skill's name. Prefer `--file` for an existing plan or
artifact and `--prompt` for inline intent.

### Concrete dispatch examples

```bash
vibecrafted release codex --prompt 'Prepare v1.2.1 release'
vc-release claude --prompt 'Ship the web surface safely behind Caddy'
vibecrafted release gemini --file /path/to/release-checklist.md
```

This is where "done in the repo" meets "done in the world."
Release is not ceremony. Release is an operational, security, visibility, and
adoption contract.

## Pipeline Position

```
scaffold → init → workflow → followup → marbles → dou → decorate → hydrate → [RELEASE]
                                                                             ^^^^^^^^^
```

Release is the final skill in the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. pipeline. It executes after:

- `vc-dou` has verified the product surface is complete
- `vc-decorate` has ensured visual coherence
- `vc-hydrate` has packaged distribution artifacts, SEO, and onboarding

Release takes those hydrated artifacts and makes them real:

- tags and changelogs
- registry or binary publication
- deployment topology selection
- proxy and TLS configuration
- domain / DNS / verification wiring
- indexability and public visibility
- release-gated security checks
- post-release smoke verification

## Core Rule

**If the release canon below is not satisfied, release is a no-op.**

Do not confuse "I can deploy it" with "it is safe, visible, and ready to meet strangers."

## The Release Canon

Every release should be checked against these planes:

1. **Artifact truth** — versions, tags, changelog, published outputs
2. **Deployment truth** — topology, proxying, healthchecks, restart behavior
3. **Security truth** — Semgrep, exposed surfaces, headers, auth, secret handling
4. **Domain truth** — DNS, canonical host, TLS, redirects, verification challenges
5. **Visibility truth** — SEO, indexability, social cards, sitemap, robots, public metadata
6. **Onboarding truth** — install path, first run, docs, screenshots, quickstart, buyer path

If any plane is missing, call it out explicitly and block release unless the
user knowingly accepts the risk.

## Artifact Canon

**Git and versioning**

- Tag the exact commit: `git tag -a v1.2.3 -m "Release 1.2.3"`
- Push the tag: `git push origin v1.2.3`
- Changelog is mandatory
- Published version must match repo version, badges, docs, and website references

**Published outputs**

- npm: `npm publish` only after version bump and package sanity checks
- crates.io: `cargo publish` only after package metadata and README sanity checks
- PyPI: build wheel + sdist, then publish
- GitHub Release: attach exact artifacts, with boring and descriptive filenames
- Docker: tag exact version and optionally `latest`, but do not ship `latest` alone as identity

**Artifact naming**

- Good: `myapp-v1.2.3-linux-x86_64.tar.gz`
- Bad: `release.zip`

## Deployment Topology Matrix

Choose one topology intentionally.

### Caddy

Use when:

- solo operator or small team
- one app or a few simple upstreams
- automatic HTTPS is desired
- minimal operator burden matters

Best default for:

- MVP web apps
- landing pages + app proxy
- internal tools made public carefully

### Nginx

Use when:

- you already operate Nginx confidently
- you need advanced reverse-proxy behavior
- you are handling many upstreams or more specialized tuning

Best for:

- established ops stacks
- larger web/API estates

### Docker

Use when:

- reproducibility matters
- deployment environment is heterogeneous
- you want a portable unit for preview/staging/prod

Best for:

- startups
- multi-env deployments
- teams that need parity between local and prod

### Safe recommendation ladder

- simplest real launch: static hosting or Caddy
- app + worker + db: Docker + reverse proxy
- existing mature infra: Nginx or current platform standard

Do not choose a stack because it sounds impressive. Choose the smallest stack
that is honest for the product.

## Deployment Safety Defaults

These defaults should be assumed unless there is a specific reason not to.

- Bind app services to `127.0.0.1` by default
- Do not expose app processes directly on `0.0.0.0` unless they are intentionally public
- Terminate TLS at a deliberate proxy or ingress
- Prefer reverse proxy to raw app port exposure
- Prefer internal Docker network over host-published ports for private services
- Use environment injection at runtime, not secrets baked into images
- Require `/health` or equivalent health endpoint for deployed services
- Require graceful shutdown / restart handling
- Require non-root containers where possible
- Require `.dockerignore` and no secret files in image context

**Red flags**

- admin/debug panel bound publicly by accident
- public service on `:3000` / `:5173` / `:8000` without proxy and TLS
- CORS set to `*` on authenticated APIs
- stacktraces or framework banners exposed publicly
- `.env` or backup files web-accessible

## Reverse Proxy and Exposure Doctrine

Release must explicitly answer:

- what hostname is canonical
- what process is public
- what process is private
- where TLS terminates
- how HTTP redirects to HTTPS
- how websockets and forwarded headers are handled

Minimum reverse-proxy expectations:

- `Host` and forwarding headers preserved intentionally
- websocket upgrade support if the app needs it
- sane timeout and body-size settings
- redirect `www`/apex according to canonical decision
- 80 -> 443 redirect when public HTTPS is intended

Public internet exposure is a decision, not a default.

## Semgrep Release Gate

Semgrep should be part of the release canon, not an optional extra.

Before release:

- run Semgrep against the app surface
- record critical and high findings
- block release on unresolved critical findings unless the user explicitly overrides

Minimum classes to care about:

- auth / authorization bypasses
- insecure secret handling
- shell / command injection seams
- SSRF
- path traversal
- unsafe file serving
- weak input validation on dangerous sinks
- insecure deserialization or eval-like behavior
- framework debug/dev endpoints left enabled

If Semgrep is unavailable in the environment, say so explicitly and run the
closest safe equivalent. But the release report must say that the Semgrep gate
was not actually satisfied.

## Domain and DNS Canon

If the product has any public surface, release should verify:

- domain is registered and intended
- DNS points to the correct target
- canonical host is chosen (`www` vs apex)
- redirects match the canonical host
- TLS certificate resolves cleanly
- staging and prod domains are not confused

Also check:

- no stale preview domains still advertised as primary
- no mismatched favicon / title / og:image leaking old product identity
- no broken `/.well-known/*` paths needed by verifiers or app clients

## Verification Challenges and Ownership Proofs

Public products often need ownership proofs. Release should verify or prepare:

- Search Console verification
- Bing Webmaster verification
- domain verification challenge files or TXT records
- Apple/Google/other ecosystem well-known verification endpoints
- any "monkey challenge" / challenge-response proof files required by infra or platforms

If a product depends on domain ownership proof and the challenge path is missing,
the release is not done.

## SEO and Visibility Canon

Release should treat visibility as a hard checklist, not a nice-to-have.

### Minimum page-level requirements

- descriptive `<title>`
- meta description
- one real `<h1>`
- crawlable content in initial HTML or a truthful fallback
- canonical URL
- Open Graph tags
- Twitter card tags
- correct status code
- noindex only when intentional

### Minimum site-level requirements

- `robots.txt`
- `sitemap.xml`
- canonical host strategy
- consistent internal linking
- no broken docs or marketing links
- favicon and social preview assets

### Indexability checks

- `curl` the page and verify meaningful content exists without relying purely on JS
- confirm the route is not accidentally blocked by `robots.txt`
- confirm meta robots is not `noindex` unless intentional
- confirm canonical points to the intended public URL

### Domain visibility checks

- docs site resolves
- landing page resolves
- primary CTA resolves
- install instructions point to real public artifacts
- social share preview is not broken

If a stranger cannot discover, understand, and try the product quickly, release
is still incomplete.

## Onboarding Truth

Release must verify the first-user path:

- install from published artifacts, not from the repo
- follow the public quickstart cold
- verify screenshots and demos match reality
- ensure the app or CLI starts without dev-only assumptions
- ensure errors are human-readable

The path from stranger -> installer -> first successful use is part of release.

## Post-Release Smoke Verification

After release, verify:

- public URL resolves
- TLS is valid
- health endpoint passes
- core action works
- install path works from scratch
- docs and CTA links resolve
- published version matches the running/released one

If possible, verify with one cold environment, not the warmed-up dev machine.

## Financial and Legal Reality

Release also means reality:

- hosting and bandwidth costs are understood
- registry or CDN limits are known
- LICENSE is correct
- SECURITY.md exists
- privacy policy / terms exist if user data is involved

Do not market proprietary behavior as open source, and do not collect data
without saying so.

## Anti-Patterns

- Publishing without `vc-dou`
- Skipping hydration and assuming people will "figure it out"
- Releasing with no Semgrep or equivalent security gate
- Exposing services publicly on `0.0.0.0` without deliberate proxy/TLS design
- Shipping with broken canonical domain or redirect logic
- Forgetting verification challenge files / TXT records
- Shipping a JS-only empty shell that crawlers cannot understand
- Tagging without a changelog
- Deploying without post-release smoke checks
- Treating release as a one-time ceremony instead of a repeatable operational discipline

## Final Principle

Release is the phase where technical debt becomes public truth.

Ship it only when:

- it is safe enough
- it is visible enough
- it is installable enough
- it is understandable enough
- and the deployment story is boring enough to trust

If not, the honest result of `vc-release` is not "done."
It is "blocked, for these exact reasons."

---

_"Done in the repo" is not "done in the world."_

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_
