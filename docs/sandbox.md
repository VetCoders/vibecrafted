# Microsandbox Execution Substrate

Vibecrafted now has a supervisor-level sandbox seam: `--sandbox` routes the
agent command through microsandbox while preserving the existing control-plane
contract. The terminal choice is orthogonal. WezTerm, vc-apprt, locterm, Zellij,
and headless mode all observe the same spawn events.

## Why This Matters

The product promise is simple: the AI agent does not need write access to the
operator's working tree. It can run inside a libkrun-backed microVM against a
controlled project mount and report its result through Vibecrafted's audit log.
That is materially different from a host-bare-machine agent launcher and
stronger than a Docker-only story for developer-skeptic customers.

## Runtime Shape

```text
vc-implement --sandbox
  -> vibecrafted_core.wrappers
  -> Supervisor.spawn(... sandbox=True)
  -> SandboxAdapter
  -> MsbserverLifecycle
  -> microsandbox Python SDK
  -> msbserver
  -> libkrun microVM
```

The canonical run stream remains `$VIBECRAFTED_HOME/control/events.jsonl`.
Sandbox execution adds `spawn-update` lifecycle states and keeps exit-code
propagation in `Supervisor`.

## Policy

Default policy is intentionally restrictive:

```yaml
network: deny
filesystem_root_readonly: true
tmp_writable: true
cpu: 1.0
memory_mb: 512
```

The policy file lives at `$VIBECRAFTED_HOME/sandbox/policy.yaml`. Per-run
override:

```bash
vc-implement codex --file brief.md --sandbox --sandbox-policy /path/policy.yaml
```

The Python adapter records policy values into events. Enforcement belongs to
the microsandbox runtime because that is the isolation boundary.

Current implementation status:

- `memory_mb` and `cpu` are passed to `sandbox.start(...)`.
- `network`, `allow_hosts`, `filesystem_root_readonly`, `tmp_writable`, and
  `mounts` are parsed and recorded into the event stream, but the local Python
  adapter does not directly enforce them yet.
- Treat those values as operator intent unless the microsandbox runtime version
  in use is verified to enforce them.

The adapter must never silently fall back to host execution when `--sandbox`
was requested.

## License Matrix

| Component         | Role                               | License Boundary                  |
| ----------------- | ---------------------------------- | --------------------------------- |
| Vibecrafted       | Supervisor, wrappers, event stream | VetCoders-owned                   |
| microsandbox fork | Execution substrate and SDK        | Apache-2.0                        |
| libkrun           | MicroVM runtime                    | permissive open-source dependency |
| Terminal spines   | Visualization only                 | independent                       |

No GPL terminal code is linked into this substrate. microsandbox is treated as
a fork-and-forget Apache-2.0 runtime dependency owned operationally by
VetCoders for this lab.

## ICP Fit

For developers who do not trust AI agents with their repository, sandboxed
execution is the credibility layer. The first conversation changes from "trust
our agent" to "inspect the audit log and the sandbox boundary." That is the
right wedge against generic managed-agent surfaces.

## Failure Rule

If msbserver cannot start, Vibecrafted reports failure. It does not fall back
to host execution while claiming sandbox isolation.
