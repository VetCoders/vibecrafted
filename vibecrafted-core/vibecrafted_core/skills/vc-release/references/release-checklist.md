# Release Checklist: Step-by-Step Mechanics

Use this. Don't skip steps. Users will find every skip.

## Pre-Release (24h before)

- [ ] **Version number decided.** Semantic versioning: MAJOR.MINOR.PATCH. Is this a breaking change? (MAJOR) New
      feature? (MINOR) Bug fix? (PATCH)
- [ ] **Changelog written.** Include: what changed, why, breaking changes in bold, migration path if needed.
- [ ] **All tests pass.** `npm test`, `cargo test`, `pytest`, whatever your stack uses. Green across CI/CD.
- [ ] **Code reviewed.** Second pair of eyes on significant changes.
- [ ] **Dependencies updated and audited.** `npm audit`, `cargo audit`, or equivalent. Pin security-critical deps.
- [ ] **README matches reality.** Quickstart still works. Examples still run. Links don't 404.
- [ ] **LICENSE file exists and is correct.** MIT, Apache 2.0, GPL, or custom. Pick one and stick with it.
- [ ] **SECURITY.md exists.** Email for vuln reports, expected response time, disclosure timeline.
- [ ] **Docs are built and working.** All links resolve. No broken images. API docs generated.

## Release Day (1–2 hours)

- [ ] **Bump version in source files.** `package.json`, `Cargo.toml`, `setup.py`, version file, whatever your lang uses.
      Exactly one source of truth.
- [ ] **Build artifacts.** Compile, bundle, create distributable. Binary, wheel, JAR, Docker image, whatever.
- [ ] **Test artifact locally.** Install it cold from the artifact, not from source. Does it work?
- [ ] **Commit version bump.** Commit message: "Release v1.2.3" (clear, minimal).
- [ ] **Tag commit.** `git tag -a v1.2.3 -m "Release 1.2.3"` (annotated tags, not lightweight).
- [ ] **Push commit and tag.** `git push origin main && git push origin v1.2.3`

## Publish (30 minutes)

**If npm package:**

- [ ] `npm publish`
- [ ] Verify on npm registry: https://www.npmjs.com/package/@yourorg/yourpkg
- [ ] Takes ~30s to appear. Wait and check.

**If Rust crate:**

- [ ] `cargo publish`
- [ ] Verify on crates.io. Takes 1–5 minutes.

**If Python package:**

- [ ] Build: `python -m build`
- [ ] Upload: `twine upload dist/*`
- [ ] Verify on PyPI.

**If Docker image:**

- [ ] Build: `docker build -t yourorg/yourimage:v1.2.3 .`
- [ ] Tag latest: `docker tag yourorg/yourimage:v1.2.3 yourorg/yourimage:latest`
- [ ] Push: `docker push yourorg/yourimage:v1.2.3 && docker push yourorg/yourimage:latest`
- [ ] Verify on registry.

**If GitHub Release:**

- [ ] Go to Releases tab.
- [ ] Click "Draft a new release."
- [ ] Select tag: v1.2.3
- [ ] Title: "Release 1.2.3"
- [ ] Description: Copy from changelog. Include highlights, breaking changes, migration path.
- [ ] Attach binaries if needed (pre-built for common platforms).
- [ ] Publish.

## Post-Release Verification (immediately)

- [ ] **Users can install from published source.** Do it yourself, cold, from scratch:
  - `npm install @yourorg/yourpkg` from new directory
  - `cargo add yourpkg`
  - `pip install yourpkg`
  - `docker run yourimage:v1.2.3 --help`
- [ ] **Documentation site is deployed and correct.** Docs link to new version, examples use new API.
- [ ] **Quickstart in README works.** Follow it exactly. If stuck, fix the docs.
- [ ] **Release notes are visible.** GitHub Releases page shows your release with description.

## Go-to-Market (2–6 hours)

- [ ] **Changelog published.** On your site, GitHub Releases, or both.
- [ ] **Twitter/X announcement.** Hook + link to release notes. Tag relevant communities.
- [ ] **Email list notified** (if you have one). Short version bump notice with highlights.
- [ ] **Community channels.** Relevant Discord, Slack, forums, subreddits. One post, not spam.
- [ ] **Internal/team comms.** Ship post in your workspace. Celebrate the release.

## 1 Week Post-Release

- [ ] **Monitor issues/reports.** Fix critical bugs in v1.2.4 patch immediately.
- [ ] **User feedback loop.** Did anyone report problems? Did they use the feature?
- [ ] **Verify docs are accurate.** Check for feedback that docs don't match reality.
- [ ] **Plan next release.** Backlog refinement, prioritize next work.

---

## Common Mistakes (Don't Do These)

- **Forgetting to push tags.** You released locally. Nobody else can see it. `git push origin v1.2.3`
- **Publishing to wrong registry.** Paid version on free tier, or vice versa. Check your config.
- **Broken docs in release notes.** Typos, dead links, outdated examples. Users see this first.
- **No changelog.** Users don't know what changed or if it affects them. Spend 20 minutes. Worth it.
- **Releasing without testing the artifact.** You tested source code. The artifact is different. Test it.
- **Forgetting to update version everywhere.** package.json but not version.ts. Confuses everyone.
- **Not announcing it.** Shipping silently = no adoption. Tell people.

---

## Template: Release Announcement

```
Version X.Y.Z is live.

Highlights:
- Feature A: [one sentence, why it matters]
- Feature B: [one sentence, why it matters]
- Fixes: [list of major bugs fixed]

Breaking changes:
- Old API removed. Use NewAPI instead. [link to migration guide]

Thanks to [contributors]. Download from [link to release].

Feedback? Open an issue on GitHub.
```

Post this on Twitter, email, GitHub Releases, Hacker News, your blog. Adjust length per platform.
