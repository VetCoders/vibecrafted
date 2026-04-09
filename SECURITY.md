# Security Policy

## Supported Versions

| Version          | Supported   |
| ---------------- | ----------- |
| Latest on `main` | Yes         |
| Older commits    | Best effort |

## Reporting a Vulnerability

If you discover a security vulnerability in 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Skills, please report it
responsibly.

**Do not open a public issue.**

Email: **void@div0.space**

Include:

- Description of the vulnerability
- Steps to reproduce
- Impact assessment (what can an attacker do?)
- Affected skill(s) or script(s)

We will acknowledge receipt within 48 hours and provide an initial assessment
within 7 days.

## Scope

This policy covers:

- All skill definitions (`vc-*/SKILL.md`)
- Install and spawn scripts (`scripts/`, `install.sh`)
- Shell helpers installed by `install-shell.sh`
- CI workflows (`.github/workflows/`)

Out of scope:

- Runtime foundations (`aicx-mcp`, `loctree-mcp`, `prview`) — report to their respective repos
- Agent CLIs (Codex, Claude, Gemini) — report to their vendors

## Known Security Boundaries

- Spawn scripts use `zsh -ic` which loads the user's full shell environment. This is by design — agents need the real
  env. Do not run spawns in untrusted environments.
- `--dangerously-skip-permissions` flags are required for external agents. This is documented and intentional. The
  `vc-delegate` skill exists as the safe alternative.
- No secrets should ever be committed to this repo. Skills read credentials from environment variables only.
