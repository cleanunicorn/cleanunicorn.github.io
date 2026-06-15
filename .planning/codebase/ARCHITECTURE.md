<!-- refreshed: 2026-05-09 -->
# Architecture

**Analysis Date:** 2026-05-09

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                  Authoring & Source Inputs                   │
├──────────────────┬──────────────────┬───────────────────────┤
│  Markdown content│  Theme submodule │  Local overrides      │
│  `content/`      │  `themes/terminal│  `layouts/`,          │
│                  │  /` (git submod) │  `assets/`, `static/` │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│        Pre-build Generators (Make targets / scripts)         │
│  `scripts/generate_cv.py` → `static/cv.html` & `cv.pdf`      │
│  reads `content/about/about.md`, `content/previous-work.md`, │
│  `data/skills.toml`, `static/css/cv.css`                     │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       Hugo Build (SSG)                       │
│  config: `hugo.toml`   theme: `themes/terminal`              │
│  goldmark + KaTeX passthrough + syntax highlight             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│            Static Output → `public/` (gitignored)            │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│   GitHub Actions (`.github/workflows/hugo.yml`)              │
│   → upload-pages-artifact → GitHub Pages deployment          │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Hugo site config | Site metadata, theme selection, markup options, language menus | `hugo.toml` |
| Content (Markdown) | All posts, About page, Work history (source of truth) | `content/` |
| Theme (vendored via submodule) | Default templates, base styles, base partials | `themes/terminal/` |
| Local layout overrides | Project-specific templates, partials, render hooks, shortcodes | `layouts/` |
| Homepage & error templates | Landing page (hero typewriter, stats band, CTAs) and custom 404 | `layouts/index.html`, `layouts/404.html` |
| Structured data (SEO) | Schema.org JSON-LD (WebSite/Person/ProfilePage/BlogPosting) injected into every page `<head>` | `layouts/partials/structured_data.html` |
| Client-side enhancement | Hero role-line typewriter (progressive enhancement, reduced-motion aware) | `static/js/hero-type.js` |
| Asset pipeline (CSS) | Custom CSS picked up, minified and fingerprinted by the theme pipeline (`css/*.css`) | `assets/css/` |
| Static assets | Images, JavaScript, presentations, raw CSS, generated CV files | `static/` |
| Data files | Structured data consumed by scripts and templates | `data/` (`home.toml`, `skills.toml`) |
| CV generator | Python script that synthesizes a print-ready CV from content | `scripts/generate_cv.py` |
| Build orchestration | Developer- and CI-facing entry points (serve/build/cv/cv-pdf) | `Makefile` |
| CI/CD | Builds CV, builds Hugo, deploys to GitHub Pages | `.github/workflows/hugo.yml` |

## Pattern Overview

**Overall:** Static Site Generator (Hugo) with a vendored theme submodule and a Python pre-build step for derived artifacts (CV).

**Key Characteristics:**
- Content-as-source: all narrative content lives as Markdown files under `content/` with TOML frontmatter (`+++ ... +++`).
- Theme inheritance: `themes/terminal` is consumed as a git submodule; project-level `layouts/` and `assets/` selectively override theme files using Hugo's lookup precedence (project beats theme).
- Pre-build derivation: `make cv-pdf` runs before `hugo` in CI to regenerate `static/cv.html` / `static/cv.pdf` from the same Markdown sources, so the live site links to a CV that is always in sync with `about.md`, `previous-work.md`, and `data/skills.toml`.
- No server-side runtime: all output is fully static. Browser-side code is minimal — third-party CDN scripts (KaTeX for math, Twitter widgets for the `x` shortcode) plus one small first-party progressive-enhancement script (`static/js/hero-type.js`, the hero typewriter).

## Layers

**Content layer:**
- Purpose: Author-facing source of truth for all human-readable content.
- Location: `content/`
- Contains: Markdown files with TOML frontmatter; per-post bundles (`content/posts/<slug>/index.md` + co-located images).
- Depends on: nothing (it is the input).
- Used by: Hugo rendering pipeline and `scripts/generate_cv.py`.

**Data layer:**
- Purpose: Structured (non-prose) inputs consumed by templates and scripts.
- Location: `data/`
- Contains: `home.toml` (homepage landing content) and `skills.toml` (categorized skill lists used by the CV generator).
- Depends on: nothing.
- Used by: `layouts/index.html` via `.Site.Data.home`; `scripts/generate_cv.py` and Hugo templates via `.Site.Data.skills`.
- Principle: content that changes often or is purely declarative (hero copy, credibility stats, SEO metadata) lives in `data/` TOML or `hugo.toml` params rather than hardcoded in templates, so editors don't touch markup.

**Presentation / template layer:**
- Purpose: Convert content + data into HTML.
- Location: `layouts/` (project overrides) + `themes/terminal/layouts/` (defaults).
- Contains: Templates (`index.html` homepage, `404.html`), partials (`extend_head.html`, `extended_head.html`, `math.html`, `structured_data.html`), shortcodes (`x.html`), markup render hooks (`_default/_markup/render-link.html`).
- Depends on: theme defaults; content frontmatter (`.Params.math` toggles KaTeX include); `data/home.toml` (homepage); site params (structured data).
- Used by: Hugo at build time.

**Asset / styling layer:**
- Purpose: CSS, JavaScript, images, fonts, prebuilt static files.
- Location: `assets/css/` (Hugo asset pipeline; every `css/*.css` is minified + fingerprinted) and `static/` (copied verbatim into `public/`).
- Contains: `assets/css/z-base.css` (shared tokens/animation/`.sr-only`), `assets/css/z-home.css`, `assets/css/z-404.css`, `assets/css/extended/center-images.css`; `static/js/hero-type.js`; `static/terminal.css`, `static/css/{custom,cv,syntax}.css`, `static/images/`, `static/presentations/`.
- Depends on: theme conventions for the asset pipeline.
- Used by: theme templates and the generated CV HTML.

**Generator / scripts layer:**
- Purpose: Produce derived artifacts from content before Hugo runs.
- Location: `scripts/`
- Contains: `scripts/generate_cv.py` (stdlib-only Python).
- Depends on: `content/about/about.md`, `content/previous-work.md`, `data/skills.toml`, `static/css/cv.css`, `hugo.toml`.
- Used by: `Makefile` targets `cv` and `cv-pdf`; CI workflow.

**Build / deploy layer:**
- Purpose: Orchestrate generation, build, and deployment.
- Location: `Makefile`, `.github/workflows/hugo.yml`.
- Contains: Make targets (`serve`, `build`, `new`, `cv`, `cv-pdf`, `update-theme`, `submodules`); CI build + deploy jobs.
- Depends on: Hugo extended, Dart Sass, Node, Go, Chromium (CI only), Python 3.

## Data Flow

### Primary Request Path (production rendering)

1. Author edits Markdown under `content/` and pushes to `main`.
2. GitHub Actions checks out the repo with submodules (`.github/workflows/hugo.yml:31-35`).
3. CI installs Hugo extended, Dart Sass, Node, Go, Chromium (`.github/workflows/hugo.yml:37-66`).
4. CI runs `make cv-pdf`, which runs `python3 scripts/generate_cv.py -o static/cv.html` then headless Chromium prints to `static/cv.pdf` (`Makefile:46-50`).
5. CI runs `hugo --gc --minify --baseURL ...` (`.github/workflows/hugo.yml:88-94`).
6. Hugo loads `hugo.toml`, walks `content/`, applies theme + local `layouts/` overrides, processes `assets/css/extended/*.css` through the asset pipeline, and copies `static/` verbatim into `public/`.
7. `actions/upload-pages-artifact@v3` uploads `public/`; `actions/deploy-pages@v4` publishes it to GitHub Pages (`.github/workflows/hugo.yml:103-115`).

### Local Development Flow

1. Developer runs `make serve` (or `make serve-drafts`) → executes `hugo server -D --disableFastRender` (`Makefile:16-19`).
2. Hugo watches `content/`, `layouts/`, `assets/`, `static/`, `data/`, `hugo.toml` and rebuilds on change.
3. New posts: `make new POST="My Title"` slugifies the title and runs `hugo new posts/<slug>/index.md` using `archetypes/default.md` as the frontmatter template (`Makefile:30-37`).
4. CV regeneration: `make cv` (HTML) or `make cv-pdf` (HTML + PDF via Chromium headless print).

### CV Generation Flow

1. `scripts/generate_cv.py` reads `hugo.toml`, `content/about/about.md`, `content/previous-work.md`, `data/skills.toml`, `static/css/cv.css` (`scripts/generate_cv.py:18-24`).
2. Strips TOML frontmatter, converts a Markdown subset to HTML inline, groups skills by category.
3. Writes a single self-contained HTML file to the path passed via `-o` (defaults to `public/cv.html` per the docstring; `Makefile` overrides to `static/cv.html` so Hugo serves it at `/cv.html`).
4. `make cv-pdf` then drives headless Chromium to print that HTML to `static/cv.pdf`.

**State Management:**
- No runtime state. Build is a pure function of repo contents at the checked-out SHA.
- Submodule pin in `.gitmodules` + recorded submodule SHA defines the exact theme version.
- `static/cv.html` and `static/cv.pdf` are gitignored derived artifacts (regenerated every CI run).

## Key Abstractions

**Page Bundle:**
- Purpose: Group a piece of content with its co-located media in a single directory (Hugo "leaf bundle").
- Examples: `content/posts/an-extension-of-the-self/index.md` plus `image.png`, `image 1.png`, `image 2.png` in the same folder.
- Pattern: One post = one directory under `content/posts/<slug>/` containing `index.md` and any referenced images.

**Frontmatter (TOML):**
- Purpose: Declarative per-page metadata (title, date, tags, `math`, `cover`, `showFullContent`, etc.).
- Examples: `content/posts/*/index.md`, `content/about/about.md`, `content/previous-work.md`.
- Pattern: `+++ ... +++` TOML block at the top of every Markdown file. The `math` flag toggles KaTeX inclusion via `layouts/partials/extend_head.html`.

**Theme override:**
- Purpose: Add or replace a theme template without forking the theme.
- Examples: `layouts/partials/extend_head.html` (theme extension hook), `layouts/_default/_markup/render-link.html` (Goldmark render hook that opens external links in a new tab).
- Pattern: Place a file at the same path under project `layouts/` as it lives under `themes/terminal/layouts/`; Hugo's lookup order picks the project copy.

**Shortcode:**
- Purpose: Custom Markdown extension callable from content.
- Examples: `layouts/shortcodes/x.html` (embeds a tweet by user/id).
- Pattern: `{{< x user="cleanunicorn" id="..." >}}` inside Markdown.

**Asset pipeline extension:**
- Purpose: Inject extra CSS into the theme's compiled stylesheet without editing the theme.
- Examples: `assets/css/z-home.css`, `assets/css/z-404.css`, `assets/css/z-base.css` (shared tokens/animation/utilities); `assets/css/extended/center-images.css`.
- Pattern: Drop a `z-<name>.css` file into `assets/css/`; every `css/*.css` is picked up, minified and fingerprinted by the pipeline. The `z-` prefix groups custom additions and keeps shared primitives (`z-base.css`) reusable across them.

## Entry Points

**Hugo build:**
- Location: `hugo.toml` (config), `content/_index.md` (homepage content), `layouts/index.html` (project homepage template, overriding the theme), `layouts/404.html` (custom error page).
- Triggers: `hugo`, `hugo server`, or CI step in `.github/workflows/hugo.yml:88`.
- Responsibilities: Read config, render content, copy static, output to `public/`.

**Makefile:**
- Location: `Makefile`
- Triggers: Developer commands (`make help`, `make serve`, `make build`, `make new`, `make cv`, `make cv-pdf`, `make update-theme`, `make submodules`, `make clean`).
- Responsibilities: Single canonical interface for local and CI workflows.

**CV generator:**
- Location: `scripts/generate_cv.py`
- Triggers: `make cv`, `make cv-pdf`, and CI step "Generate CV (HTML + PDF)" in `.github/workflows/hugo.yml:71`.
- Responsibilities: Produce `static/cv.html` (and via Chromium, `static/cv.pdf`) from Markdown + TOML inputs.

**CI workflow:**
- Location: `.github/workflows/hugo.yml`
- Triggers: Push to `main`, manual `workflow_dispatch`.
- Responsibilities: Install toolchain, generate CV, build site, upload artifact, deploy to GitHub Pages.

## Architectural Constraints

- **No server runtime:** Output must be pure static files servable by GitHub Pages. No backend code runs in production.
- **Theme is a git submodule:** Editing files inside `themes/terminal/` is not a project change — it is an upstream change. Local customization MUST happen via project-level `layouts/`, `assets/css/extended/`, and `static/`. Use `make update-theme` to bump.
- **Generated artifacts are gitignored:** `public/`, `resources/_gen/`, `static/cv.html`, `static/cv.pdf` MUST NOT be committed (`.gitignore`). CI regenerates them on every build.
- **Hugo extended required:** `hugo.toml` enables Goldmark passthrough + classed syntax highlighting; CI installs `hugo_extended_*` because Dart Sass is also required.
- **Submodule init required:** Local clones MUST run `git submodule update --init --recursive` (or `make submodules`) before building, or the theme directory will be empty.
- **CV generator depends on file paths:** `scripts/generate_cv.py` hard-codes paths to `content/about/about.md`, `content/previous-work.md`, `data/skills.toml`, and `static/css/cv.css`. Renaming or moving any of these breaks `make cv`.
- **External CDN dependency for math:** KaTeX CSS/JS load from `cdn.jsdelivr.net` with SRI hashes (`layouts/partials/math.html`); offline builds will render but math will not display until the CDN is reachable in the browser.

## Anti-Patterns

### Editing the theme submodule directly

**What happens:** Modifying files under `themes/terminal/` to tweak look or behavior.
**Why it's wrong:** Changes live inside a submodule pointing at a third-party repo and are lost (or cause merge conflicts) the next time `make update-theme` runs.
**Do this instead:** Create a same-path file under `layouts/` to override a template (see `layouts/partials/extend_head.html`), or drop CSS into `assets/css/extended/` (see `assets/css/extended/center-images.css`).

### Committing generated artifacts

**What happens:** Running `make cv-pdf` or `make build` locally and committing `static/cv.html`, `static/cv.pdf`, or `public/`.
**Why it's wrong:** These are derived from sources and `.gitignore`d; CI regenerates them on every push, so committed copies just bloat history and create stale-vs-fresh confusion.
**Do this instead:** Commit only the inputs (`content/`, `data/`, `static/css/cv.css`, `scripts/generate_cv.py`). Let CI produce the artifacts.

### Bypassing the page-bundle layout for posts with images

**What happens:** Putting a post at `content/posts/my-post.md` while dropping images into `static/images/blog/...` and referencing them by absolute URL.
**Why it's wrong:** Splits a logical unit across two trees, breaks Hugo's relative image resolution, and prevents the `render-link` / image render hooks from working consistently.
**Do this instead:** Use a leaf bundle: `content/posts/my-post/index.md` with `image.png` (and friends) co-located, mirroring `content/posts/an-extension-of-the-self/`.

### Hard-coding HTML in Markdown for cross-cutting features

**What happens:** Pasting raw `<script>` / `<link>` tags into post bodies to enable math, embeds, etc.
**Why it's wrong:** Duplicates concerns across posts and bypasses the `extend_head` partial pattern.
**Do this instead:** Toggle a frontmatter flag (e.g. `math = true`) and let `layouts/partials/extend_head.html` conditionally include the relevant `<head>` partial; for embeds, add a shortcode under `layouts/shortcodes/` (see `layouts/shortcodes/x.html`).

## Error Handling

**Strategy:** Build-time failure only; no runtime error paths.

**Patterns:**
- Hugo build failures (bad frontmatter, missing template, broken shortcode) fail the CI job and block deployment.
- `scripts/generate_cv.py` is best-effort: it reads inputs and writes output; missing files will raise a Python exception and abort `make cv`, which in turn aborts CI ("Generate CV (HTML + PDF)" step) before Hugo runs.
- Chromium PDF step in `Makefile` swallows stderr (`2>/dev/null`) and unconditionally echoes success — a real failure surfaces only as a missing/zero-byte `static/cv.pdf`.

## Cross-Cutting Concerns

**Logging:** None at runtime (static output). Build-time output is whatever Hugo, Make, and Python print to stdout/stderr; CI logs are the only source of truth.

**Validation:** No explicit content validation. Hugo enforces template correctness; frontmatter typos silently fall through (e.g. an unset `math` simply skips the KaTeX include).

**SEO / structured data:** `layouts/partials/structured_data.html` emits Schema.org JSON-LD on every page (WebSite always; ProfilePage on home/about; BlogPosting on posts), sourced from site params (`hugo.toml [languages.en.params]`) and page frontmatter. `jsonify | safeJS` is required so `html/template` does not re-encode the JSON inside the `<script>` element.

**Accessibility:** Decorative terminal flourishes are hidden from assistive tech (`aria-hidden` on the hero prompt/cursor and the 404 shell art); animations honor `prefers-reduced-motion` (centralized rule in `z-base.css`). Where visual and announced content diverge, use the `.sr-only` utility (`z-base.css`) to supply a screen-reader-only string and `aria-hidden="true"` on the visual fragments — see the homepage stats band in `layouts/index.html` (`<span class="sr-only">label: value</span>`).

**Authentication:** None. Site is fully public; CI uses GitHub-provided OIDC tokens for Pages deploy (`permissions: id-token: write` in the workflow).

---

*Architecture analysis: 2026-05-09*
