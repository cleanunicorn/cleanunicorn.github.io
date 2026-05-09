# External Integrations

**Analysis Date:** 2026-05-09

## APIs & External Services

**Content Delivery Networks (CDN):**
- jsDelivr - Serves KaTeX assets
  - Endpoint: `https://cdn.jsdelivr.net/npm/katex@0.16.25/dist/...`
  - Files loaded: `katex.min.css`, `katex.min.js`, `contrib/auto-render.min.js`
  - Loaded by: `layouts/partials/math.html` (only when frontmatter `math: true` is set, gated in `layouts/partials/extend_head.html` and `layouts/partials/extended_head.html`)
  - Subresource Integrity (SRI) hashes pinned for all three assets
  - Auth: None (public CDN)

**Social / Embeds:**
- Twitter / X widgets - Tweet embeds via shortcode `{{< x user="..." id="..." >}}`
  - Endpoint: `https://platform.twitter.com/widgets.js`
  - Implementation: `layouts/shortcodes/x.html` (renders blockquote + async script tag)
  - Auth: None

**Theme Source:**
- GitHub - Theme submodule fetched from `https://github.com/panr/hugo-theme-terminal.git`
  - Defined in `.gitmodules`
  - Pulled at build time via `actions/checkout@v5` with `submodules: recursive`

**Tooling Downloads (CI only):**
- GitHub Releases - Hugo and Dart Sass binaries fetched at CI runtime
  - `https://github.com/gohugoio/hugo/releases/download/v0.152.2/hugo_extended_0.152.2_linux-amd64.tar.gz`
  - `https://github.com/sass/dart-sass/releases/download/1.93.2/dart-sass-1.93.2-linux-x64.tar.gz`
  - Defined in `.github/workflows/hugo.yml`

**External Content Links (referenced but not integrated):**
- YouTube - Talk and podcast videos linked from `content/about/about.md`
- IMDb - Documentary reference (`Code Is Law (2025)`) in `content/about/about.md`
- LinkedIn / X / GitHub - Profile links in `content/about/about.md`

## Data Storage

**Databases:**
- None - Pure static site, no database

**File Storage:**
- Local filesystem only
  - Site content: `content/`
  - Static assets (images, presentations, generated CV): `static/`, including `static/images/`, `static/presentations/`, `static/cv.html`, `static/cv.pdf`
  - Hugo build output: `public/` (gitignored)
  - Hugo cache: `resources/_gen/` (gitignored)

**Caching:**
- Hugo build cache - `${{ runner.temp }}/hugo_cache` cached across CI runs via `actions/cache/restore@v4` and `actions/cache/save@v4`
  - Cache key: `hugo-${{ github.run_id }}`, restore prefix: `hugo-`

## Authentication & Identity

**Auth Provider:**
- None - Static site has no authentication layer
- Site visitors are anonymous; no user accounts, no login flow

## Monitoring & Observability

**Error Tracking:**
- None - No Sentry, Rollbar, or similar tooling detected

**Analytics:**
- None active - The bundled `themes/terminal/layouts/partials/head.html` references Hugo's internal `_internal/google_analytics.html` template, but `hugo.toml` does not define `googleAnalytics`, so no tracking code is emitted
- No `params` overrides for analytics in `hugo.toml`

**Logs:**
- CI logs only - GitHub Actions captures workflow output (e.g. `ls -R public/` debug step in `hugo.yml`)
- No runtime logging (static site)

## CI/CD & Deployment

**Hosting:**
- GitHub Pages - Custom domain not detected; `baseURL = 'https://cleanunicorn.github.io/'` in `hugo.toml`
- Deploy environment: `github-pages`

**CI Pipeline:**
- GitHub Actions - `.github/workflows/hugo.yml`
  - Triggers: `push` to `main`, manual `workflow_dispatch`
  - Permissions: `contents: read`, `pages: write`, `id-token: write`
  - Concurrency group: `pages` (serialized, no cancel-in-progress)
  - Jobs:
    1. `build` (ubuntu-latest) - Checkout with submodules, install Go/Node/Hugo/Dart Sass/Chromium, generate CV, build Hugo site, upload artifact
    2. `deploy` (ubuntu-latest) - Uses `actions/deploy-pages@v4` to publish the `github-pages` artifact
  - Third-party actions: `actions/checkout@v5`, `actions/setup-go@v5`, `actions/setup-node@v4`, `actions/configure-pages@v5`, `actions/cache/restore@v4`, `actions/cache/save@v4`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`

## Environment Configuration

**Required env vars:**
- None at runtime (static site, no secrets consumed by site code)
- CI workflow injects build-time vars only: `DART_SASS_VERSION`, `GO_VERSION`, `HUGO_VERSION`, `NODE_VERSION`, `TZ`

**Secrets location:**
- None used - No GitHub Actions `secrets.*` references found in `.github/workflows/hugo.yml`
- Pages deployment authenticated via OIDC (`id-token: write` permission), no long-lived tokens

## Webhooks & Callbacks

**Incoming:**
- GitHub push events - Trigger CI build/deploy via `on.push.branches: [main]` in `.github/workflows/hugo.yml`
- Manual `workflow_dispatch` - Allows manual re-runs from the Actions UI

**Outgoing:**
- None - No outbound webhooks, no server-side callbacks (static site)

## Comments / Disqus

- Theme references `_internal/disqus.html` in `themes/terminal/layouts/partials/comments.html`, but `hugo.toml` does not configure `disqusShortname`, so comments are disabled in the rendered output

---

*Integration audit: 2026-05-09*
