# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. FAQ

Public-facing answers for the questions people ask before they trust the framework.

For the public HTML version, see https://vibecrafted.io/en/faq/.
For the long-form answer bank, see [FAQ-ANSWERED.md](FAQ-ANSWERED.md).

## Installation

- **Why does 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. install into `$VIBECRAFTED_ROOT/.vibecrafted/` instead of `$HOME/.agents/`?**
  `$VIBECRAFTED_ROOT/.vibecrafted/` is the central store and control plane. Agent-specific directories are only views or symlink
  targets.

- **Can I install without editing my shell config?**
  Yes. You can opt out of shell-helper installation and source
  `${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh` manually when you want the helpers in your current session.

- **Do you have a guided GUI install path?**
  Yes. Run `curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui` to stage the control plane and open the browser-based installer. It bootstraps foundations first, then runs the same compact installer truth used by automation. If you are already in the repo, use `make wizard` or its alias `make gui-install`. The default `make vibecrafted` target runs the terminal-native installer wizard.

- **What does `make doctor` check?**
  The doctor verifies the central store, helper availability, symlink health, optional foundations, and shell quietness.

- **Which install path should I use in CI?**
  Use `make install` for the direct non-interactive path, or
  `python3 scripts/vetcoders_install.py install --source "$PWD" --non-interactive` when you want full CLI control.

## Skills, Agents, Foundations

- **What is the difference between a skill and an agent?**
  An agent is the runtime. A skill is the workflow protocol that tells that runtime how to behave for a specific
  engineering phase.

- **Why not just use a single giant prompt?**
  Because 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. is trying to solve system-shaping, not only chat convenience. It adds structural awareness,
  decision retrieval, convergence loops, and shipping audits.

- **Can I use 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. without loctree or aicx?**
  Yes, but you lose structural perception and session continuity. The framework runs, but with weaker context.

- **What is Marbles?**
  Marbles is the convergence loop: implement, follow up, measure, and repeat until the important classes of findings
  reach zero.

## Workflow and Operations

- **When should I use `vc-justdo`?**
  Use it when the task is clear and you want the agent to take ownership end-to-end. Use the phase skills individually
  when you want more supervisory control.

- **Can I run 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. in CI/CD?**
  Yes. The direct install path is non-interactive, and review/followup/release flows are shaped to work as repeatable
  gates.

- **What lives in `$VIBECRAFTED_ROOT/.vibecrafted/artifacts/`?**
  Plans, reports, transcripts, and metadata from major runs. The artifact store exists so agent work leaves durable
  evidence.

- **What is Definition of Undone?**
  DoU is the audit that checks whether people can discover, understand, install, trust, and adopt the thing, not only
  whether the codebase is healthy.

## Commercial Posture

- **Is 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. open source?**
  The framework is distributed under Business Source License 1.1, so the repo is visible and usable but not pure
  permissive open source.

- **Can small teams use it in production?**
  Yes. The Additional Use Grant allows individual developers and teams smaller than five people to use it in production
  as long as they are not offering a competitive hosted or embedded product.

- **What if I need broader commercial rights?**
  Read [LICENSE](../LICENSE) for the exact terms and contact path for alternative licensing arrangements.

---

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. by VetCoders | https://vibecrafted.io/
