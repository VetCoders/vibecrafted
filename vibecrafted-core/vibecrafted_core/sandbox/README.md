# Vibecrafted Microsandbox Substrate

The sandbox package makes microsandbox an execution substrate below the
Vibecrafted supervisor. Terminal spines stay visual adapters. The control
plane, `events.jsonl`, run ids, exit codes, and report paths remain canonical.

## Operator Commands

```bash
vc-sandbox status
vc-sandbox start
vc-sandbox stop
vc-sandbox policy
vc-implement codex --file /path/to/brief.md --sandbox
vc-implement true --sandbox
```

`--sandbox` is handled by the Python wrapper before the shell command deck sees
the arguments. This keeps the existing skill prompts clean while routing the
actual command through `SandboxAdapter`.

## Lifecycle

`MsbserverLifecycle` health-checks `http://127.0.0.1:5555/api/v1/health`.
When the server is absent it starts `msbserver`, then records the child PID in:

```text
$VIBECRAFTED_HOME/sandbox/msbserver.pid
```

Logs go to:

```text
$VIBECRAFTED_HOME/sandbox/msbserver.log
```

If no server key is configured, Vibecrafted starts msbserver in development
mode so local operator smoke tests work without printing or copying secrets. If
`MSB_API_KEY` is present, the Python SDK uses it for authenticated RPC calls.

## Policy

Default policy:

```yaml
cpu: 1.0
memory_mb: 512
network: deny
filesystem_root_readonly: true
tmp_writable: true
mounts:
  - /project/root:/workspace:ro
  - /tmp:/tmp:rw
```

Operators can override with:

```text
$VIBECRAFTED_HOME/sandbox/policy.yaml
```

or per run:

```bash
vc-implement codex --file plan.md --sandbox --sandbox-policy /path/policy.yaml
```

The Python layer records policy intent in `spawn-update` events. Hard isolation
is delegated to the microsandbox/libkrun runtime so the audit trail reflects
the actual substrate rather than a local wrapper promise.

## Events

Sandbox runs emit:

```text
spawn-started
spawn-update state=launching
spawn-update state=running
spawn-update state=completed|failed
spawn-completed|spawn-failed
```

Every event includes `substrate=microsandbox` when the sandbox path owns the
execution. Existing control-plane consumers can therefore render sandboxed and
host runs from the same stream.

## Platform

microsandbox uses libkrun under the hood. That means KVM on Linux and HVF on
macOS/ARM64 are the relevant host capabilities. If the server cannot start, do
not silently fall back to host execution; report the substrate failure.
