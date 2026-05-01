# Docker Runtime

The Docker image packages the Vibecrafted command deck as a portable operator
runtime. Source lives at `/opt/vibecrafted`; the project under audit is mounted
at `/workspace`; runtime state is written to `/workspace/.vibecrafted`.
On first run, the entrypoint seeds `/workspace/.vibecrafted/skills` from the
framework source so `vibecrafted doctor` and skill discovery work without a
host install.

## Build

```bash
docker build -t vetcoders/vibecrafted:local .
```

For a heavier image with agent CLIs and foundation tools installed at build
time:

```bash
docker build \
  --build-arg INSTALL_AGENT_CLIS=true \
  --build-arg INSTALL_FOUNDATIONS=true \
  -t vetcoders/vibecrafted:full .
```

## Run

From any repo you want Vibecrafted to inspect:

```bash
docker run --rm -it \
  -v "$PWD:/workspace" \
  -w /workspace \
  vetcoders/vibecrafted:local help
```

Common checks:

```bash
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:local version
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:local help
```

`doctor` is intentionally stricter: the light image can run the command deck,
but it will report missing foundation binaries unless you build the full image:

```bash
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:full doctor
```

Run agent-backed skills from the full image, or from a light image where you
have installed/mounted the agent CLI yourself:

```bash
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:full dou codex --prompt "Audit launch readiness"
```

If you use host-side agent auth/config, mount only the config stores you intend
the container to use:

```bash
docker run --rm -it \
  -v "$PWD:/workspace" \
  -v "$HOME/.codex:/root/.codex" \
  -v "$HOME/.claude:/root/.claude" \
  -v "$HOME/.gemini:/root/.gemini" \
  vetcoders/vibecrafted:full justdo codex --prompt "Ship the bounded fix"
```

## Shell

The entrypoint routes unknown commands through `vibecrafted`, but lets common
tools run directly:

```bash
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:local bash
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:local git status
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:local uv --version
```

## Runtime Contract

- `/opt/vibecrafted` is immutable framework source inside the image.
- `/workspace` is the mounted project being worked on.
- `/workspace/.vibecrafted` is the persistent runtime state for reports, logs,
  plans, and temporary files.
- `VIBECRAFTED_DOCKER_SEED_SKILLS=0` disables first-run skill seeding when you
  intentionally mount your own runtime store.
- Agent CLIs still need their own credentials/config. Docker isolates the
  framework; it does not invent cloud auth.
