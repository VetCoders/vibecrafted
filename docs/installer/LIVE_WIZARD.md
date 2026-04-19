# Live Wizard — Svelte Bundle Integration

## Intent

The browser installer is no longer inline HTML in `installer_gui.py`. It is
the same Svelte component that ships on `vibecrafted.io/install`, served by
the local HTTP server with real API endpoints. One UI, two data modes:

- **Preview** (`vibecrafted.io/en/install`): `InstallerShell.svelte` mounts
  the existing `InstallerWizard.svelte` (static manifest, educational flow,
  curl one-liner at the end).
- **Live** (`localhost:<port>/`): `InstallerShell.svelte` detects the
  localhost host and mounts `LiveInstaller.svelte`, which talks to
  `/api/preflight`, `/api/install`, `/api/install/status`, and
  `/api/open-start-here` on the local installer process.

## Components

Source lives in the `vibecrafted-io` repo:

| Path                                         | Role                                          |
| -------------------------------------------- | --------------------------------------------- |
| `site/src/components/InstallerShell.svelte`  | Mode selector (preview vs live)               |
| `site/src/components/InstallerWizard.svelte` | Existing preview/marketing wizard (unchanged) |
| `site/src/components/LiveInstaller.svelte`   | Live wizard, talks to the local API           |
| `site/src/lib/installer/api.ts`              | Typed fetch helpers + `isLiveInstallerHost()` |
| `site/src/pages/{en,pl}/install.astro`       | Route pages, now mount `InstallerShell`       |

Server-side bits live in this repo (`vibecrafted`):

| Path                                   | Role                                                                 |
| -------------------------------------- | -------------------------------------------------------------------- |
| `scripts/installer_gui.py`             | HTTP server: API + static file serving + fallback inline HTML        |
| `scripts/installer_gui.py::build_html` | Legacy inline HTML kept as fallback when no Svelte bundle is present |

## Runtime contract

`InstallController` discovers the bundle in this order:

1. CLI flag `--bundle-dir /path/to/site/dist`
2. Env var `VIBECRAFTED_SITE_BUNDLE`
3. `<source>/site/dist`
4. `<source>/dist`

If any candidate contains `en/install/index.html`, the handler serves the
prebuilt Svelte site plus its `_astro/`, `presence/`, and root static files.
Every `/api/*` route stays reserved for the live controller, so the bundle
and the API live on the same origin with zero CORS or mixed-content issues.

When no bundle is found, the server falls back to the legacy
`build_html(preflight)` template. The fallback keeps the installer usable
on any clean framework checkout that has not built the site yet.

## Developer loop

Run the wizard against a sibling `vibecrafted-io` checkout — the target
rebuilds the bundle first:

```bash
make wizard-dev
```

Pass a pre-built bundle explicitly:

```bash
make wizard BUNDLE_DIR=/path/to/vibecrafted-io/site/dist
```

Manual smoke test against a running server:

```bash
python3 scripts/installer_gui.py \
    --source . \
    --bundle-dir /path/to/vibecrafted-io/site/dist \
    --host 127.0.0.1 --port 47321 --no-open

curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:47321/
curl -s http://127.0.0.1:47321/api/preflight | python3 -m json.tool | head
```

Both `/` and `/en/install/` should return 200 with the prebuilt HTML, and
`/api/preflight` should return the controller payload (version, categories,
install plan, status).

## Release TODO

Right now the distributed tarball (`vibecrafted-v*.tar.gz`) does **not**
include the Svelte bundle, so production installers still fall back to
inline HTML. To ship the live wizard end-to-end:

1. **Build the site first** in the release pipeline. In `vibecrafted-io`
   that means `make site-build` before `make bundle-build`.
2. **Carry the bundle into the framework tarball**. Two viable shapes:
   - Drop the full `site/dist/` into `framework/site/dist/` before the
     tarball is rolled. `installer_gui.py` will find it under
     `<source>/site/dist` out of the box.
   - Or assemble a minimal subset (install pages, `_astro/`, favicons,
     relevant `presence/` assets — roughly ~1 MB) into `framework/ui/`
     and teach `_resolve_site_dist` to also look there. Smaller tarball,
     more plumbing.
3. **Stop excluding `site/dist`** in `vibecrafted-io/Makefile:bundle-build`.
4. **Re-sign and publish**. The integrity rule (rebuild + resign on version
   bump) still applies — a recycled tarball with the old inline HTML and a
   new filename remains a fake release.

Once the release carries the bundle, `curl …/install.sh | bash -s -- --gui`
will land users directly in the Svelte wizard driven by the local API.
