# GlobeOptimiser on Cloudflare Workers

Cloudflare serves the website's pre-rendered pages, images and scripts. The build
renders the same Jinja templates used by the existing FastAPI deployment, so the
shared styles, navigation, metadata, tools and blog pages stay consistent.

## What runs where

| Component | Runtime |
| --- | --- |
| Website pages, SEO pages, blog, logos and favicon | Cloudflare static assets |
| Routing, legacy redirects, health check and same-origin API bridge | Cloudflare Worker |
| Image/video compression, resizing, watermarking and conversion | Existing Python backend |

**This is a hybrid migration, not a port of FFmpeg to Workers.** The configured
processing origin is `https://globeoptimiser.vercel.app`, verified to answer its
health endpoint during preparation. Keep that deployment running. Cloudflare
does not execute `backend/main.py`, Pillow, NumPy or MoviePy in this configuration.
Changing DNS does not move those processing operations into Workers.

The Worker forwards only the five known POST endpoints and returns the original
download bytes, filenames, validation errors and status codes. It does not forward
browser cookies, authentication headers or visitor IP headers. Processing responses
are never cached. No R2 buckets or paid image-processing bindings are required for
this migration. Current backend upload and processing limits remain in place.

## Requirements and local verification

- Node.js 22 or newer (the `.nvmrc` selects Node 22)
- Python 3.10 or newer, with `venv` and `pip`

```sh
npm ci
npm run build
npm test
npx wrangler deploy --dry-run
npm run dev
```

Open the local URL printed by Wrangler. The build creates an isolated
`.build-venv` containing only pinned Jinja2/MarkupSafe dependencies. It does not
install the media backend. Generated `dist/` files and the old `dist.zip` are not
tracked; always build from source rather than uploading the obsolete HTML in
`frontend/`. Those legacy files are retained only for informational page content
and historical reference.

## Connect this repository to the existing Cloudflare Worker

In Cloudflare Workers & Pages, select the existing **globeoptimiser** Worker and
connect the copied repository under **dochaseops-sys** through its Git build
configuration. Use:

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Root directory | repository root |
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy` |
| Worker name | `globeoptimiser` |
| Static assets directory | `./dist`, already set in `wrangler.jsonc` |

The build environment needs Python; Workers Builds supplies it. No Cloudflare
credentials belong in the repository when using Cloudflare's Git integration.
For an authenticated local CLI deployment, run `npm run deploy`.

`wrangler.jsonc` is the source of truth for the Worker name, assets, and
`API_ORIGIN`. If the dashboard Worker has a different name, change the config
before deploying. Deployment replaces that Worker's code: verify a local preview
and the build first. Custom domains are deliberately not declared in the config,
so deployment does not attempt to claim or move domains automatically.

### Processing origin

`API_ORIGIN` must be an HTTPS origin with no path, credentials or query string.
Never set it to `globeoptimiser.com`, `www.globeoptimiser.com`, or the Worker's
own address: that would send processing requests back to the same Worker.
If the origin is missing, recursive or unavailable, the API returns a clear error
instead of a broken HTML download. To remove the Vercel dependency later, port
supported operations to the browser/Cloudflare Images or replace the Python
origin with another compatible service and repeat processing tests.

### Domains

Keep `globeoptimiser.com` attached to this Worker. Attach `www.globeoptimiser.com`
to the same Worker if you want the included 308 redirect from `www` to the root
domain. A redirect in code cannot work until DNS and domain routing reach it.
The `workers.dev` address remains usable for verification.

## Deployment acceptance checks

1. `/health` returns `{"status":"ok","runtime":"cloudflare-workers"}`.
2. `/`, `/resize-image`, `/convert-image`, `/blog` and `/about` are styled.
3. Direct visits and refreshes on nested blog/SEO routes work; unknown URLs give 404.
4. Both theme modes and mobile layouts work; sidebar ads remain removed.
5. Upload a small PNG, resize it and download a valid image with the requested dimensions.
6. Exercise compression, conversion and watermarking with representative small files.
7. Confirm oversized uploads return 413 and failed processing is not reported as success.
8. Check Worker logs without logging uploaded files, request bodies or credentials.

The existing contact backend only logs submissions; it does not deliver email.
This migration preserves that behaviour rather than adding an email service.
Standard Workers rate limiting/access controls can be configured separately when
needed. Origin checks are a browser safeguard, not authentication or a rate limiter.

## Optional Python backend development

The original backend and `vercel.json` are retained for continuity:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload
.venv/bin/pytest
```

Native video processing requires FFmpeg. Do not raise the current media limits
without memory/CPU measurements, bounded uploads and concurrency control.
