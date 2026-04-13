# Release Kickoff

This is the pre-release operator sheet for 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.

Rule zero: do not let the repo, installer, portal, and marketplace copy disagree
about what the product is.

## One-line truth

- Product: 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.
- Promise: Release engine for AI-built software.
- Primary CTA: `curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui`
- Secondary CTA: `curl -fsSL https://vibecrafted.io/install.sh | bash`
- Human front door: browser-guided installer, chosen for TwinSweep-style
  effortlessness.
- Automation path: compact CLI installer, still available for scripts and CI.
- Adjacent pattern kept for inspiration, not as the public front door:
  `rmcp-memex`-style wizard/TUI.

## Positioning guardrails

- Do not pitch Vibecrafted as another code generator.
- Do not pitch it as an IDE replacement or pair-programmer shell alone.
- Do pitch it as the post-generation layer: the thing you run after agents have
  already produced the repo and before a stranger touches it.
- Adjacent tools such as Cursor, Windsurf, Cline, Devin, Lovable, and Bolt help
  write or generate software. Vibecrafted hardens, packages, verifies, and
  prepares that software to ship.

## Kickoff checklist

1. Repo truth
   Run the pre-release gates from this repo:

   ```bash
   make bundle-check
   make check
   make test
   env -u ZELLIJ -u ZELLIJ_PANE_ID -u ZELLIJ_SESSION_NAME -u VIBECRAFTED_OPERATOR_SESSION bash scripts/check-portable.sh
   ```

2. Installer truth
   Confirm every public install surface keeps the same contract:
   - guided GUI path is the first CTA for humans
   - compact path stays available for automation
   - `doctor` remains the first verification step after install

3. Portal truth
   Treat `vibecrafted-io/site/src` as the portal source of truth and its repo
   root / generated `docs/` files as the deploy mirror. Rebuild and redeploy
   that mirror before launch if any derived file still advertises the old
   direct-only install path or the older self-referential promise. The
   homepage, quickstart, FAQ, `install.sh`, and README must all match the
   release-engine narrative and the guided installer CTA.
   Because `vibecrafted-io` is a separate git root, treat its build/deploy pass
   as a separate lane from this repo commit. Minimum rebuild command:

   ```bash
   pnpm --dir ~/Libraxis/01_deployed_libraxis_vm/vibecrafted-io/site build
   ```

   Minimum drift checks before any public launch:

   ```bash
   rg -n "Interactive terminals always enter the installer TUI|curl -fsSL https://vibecrafted.io/install.sh \\| bash$" \
     ~/Libraxis/01_deployed_libraxis_vm/vibecrafted-io/README.md \
     ~/Libraxis/01_deployed_libraxis_vm/vibecrafted-io/docs/install.sh \
     ~/Libraxis/01_deployed_libraxis_vm/vibecrafted-io/docs/QUICK_START.md \
     ~/Libraxis/01_deployed_libraxis_vm/vibecrafted-io/site/src
   ```

   If that grep still finds old TUI-only or direct-only wording in the portal
   repo root / built `docs/`, the deploy mirror is stale and launch should
   pause until that separate lane is rebuilt and redeployed.

4. Asset truth
   Capture and store these before submission day:
   - guided installer screenshot
   - command deck screenshot
   - quickstart screenshot
   - marbles / convergence screenshot
   - landing-page hero screenshot
   - one short walkthrough video

5. Marketplace order
   Submit in this order:
   1. There’s An AI For That
   2. Future Tools
   3. Futurepedia
   4. Toolify
   5. TopAI.tools
   6. Uneed
   7. Product Hunt

6. Uneed dry run
   Treat Uneed as the softer rehearsal launch once AI-directory listings are
   already live:
   - use the guided installer screenshot as the hero asset
   - keep the explanation founder-readable, not taxonomy-heavy
   - watch which screenshot / blurb combination gets the cleanest conversion

7. Product Hunt day
   Do not schedule Product Hunt until:
   - the maker posting account has Product Hunt post access
   - the founder comment is prewritten
   - the portal and installer are both ready for real strangers
   - someone is available to answer comments for the full launch window

## Supporting docs

- [Quick Start](./QUICK_START.md)
- [Marketplace Listing](./MARKETPLACE_LISTING.md)
- [Submission Forms](./SUBMISSION_FORMS.md)
- [Installer Reference](./installer/REFERENCE.md)

`//𝚟𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.`
