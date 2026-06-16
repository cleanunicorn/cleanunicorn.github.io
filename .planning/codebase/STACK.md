# Technology Stack

**Analysis Date:** 2026-05-09

## Languages

**Primary:**
- Markdown - Site content (`content/posts/`, `content/about/_index.md`, `content/previous-work.md`)
- HTML/Go templates - Hugo layouts and partials (`layouts/`, `themes/terminal/layouts/`)
- TOML - Site configuration and structured data (`hugo.toml`, `data/skills.toml`, frontmatter blocks)
- Python 3 - CV generator script (`scripts/generate_cv.py`, ~395 lines)

**Secondary:**
- CSS - Custom styling and CV print layout (`static/css/cv.css`, `static/terminal.css`, `assets/css/`)
- Make - Build orchestration (`Makefile`)
- YAML - CI/CD pipeline (`.github/workflows/hugo.yml`)
- Shell (bash) - GitHub Actions inline scripts and Make recipes

## Runtime

**Environment:**
- Hugo Extended 0.152.2 - Static site generator (pinned in `.github/workflows/hugo.yml`)
- Python 3.11+ - Required for `tomllib` stdlib import in `scripts/generate_cv.py` (lines 178-188 fall back to `tomli`, then a regex parser)
- Node.js 22.20.0 - Pinned in CI for any Hugo/JS pipeline needs (no local `package.json` consumed at runtime)
- Go 1.25.3 - Required by Hugo modules during build
- Chromium / Chromium-browser - Headless print-to-PDF for CV (`make cv-pdf` target in `Makefile`, installed in CI)

**Package Manager:**
- Git submodules - Used for theme distribution (`.gitmodules` references `themes/terminal`)
- npm - Used in CI only when `package-lock.json` exists (none in repo root); the bundled theme has its own `themes/terminal/package.json` and `yarn.lock` but they are not invoked by site builds
- Lockfile: None at repo root for npm/Python; theme submodule ships `themes/terminal/yarn.lock` and `themes/terminal/package-lock.json`

## Frameworks

**Core:**
- Hugo (extended build) 0.152.2 - Static site generator; configured by `hugo.toml`
- hugo-theme-terminal 4.2.3 - Theme submodule at `themes/terminal/` (sourced from `https://github.com/panr/hugo-theme-terminal.git`)
- Dart Sass 1.93.2 - SCSS compilation in CI (`.github/workflows/hugo.yml` line ~31)

**Testing:**
- None detected - No test files, no test runner configured

**Build/Dev:**
- Make - Task runner with targets `serve`, `serve-drafts`, `build`, `build-drafts`, `clean`, `new`, `update-theme`, `submodules`, `cv`, `cv-pdf` (`Makefile`)
- Hugo CLI - Local dev server via `hugo server -D --disableFastRender`
- Goldmark - Hugo's bundled Markdown renderer; passthrough extension enabled in `hugo.toml` for `$...$` and `$$...$$` math delimiters

## Key Dependencies

**Critical:**
- `themes/terminal` (git submodule) - Provides all base layouts, partials, and styles; site is unbuildable without it (initialized via `make submodules` or `actions/checkout@v5` with `submodules: recursive`)
- KaTeX 0.16.25 (CDN) - Math rendering loaded from `https://cdn.jsdelivr.net/npm/katex@0.16.25/...` in `layouts/partials/math.html` when a page sets `math: true` in frontmatter

**Infrastructure:**
- GitHub Pages - Hosting target (`baseURL = 'https://cleanunicorn.github.io/'` in `hugo.toml`)
- GitHub Actions - CI/CD pipeline (`.github/workflows/hugo.yml`)

## Configuration

**Environment:**
- No `.env`, no runtime secrets - Static site with no server-side configuration
- CI env vars set inline in `.github/workflows/hugo.yml`: `DART_SASS_VERSION`, `GO_VERSION`, `HUGO_VERSION`, `NODE_VERSION`, `TZ=Europe/Oslo`
- `HUGO`, `THEME`, `PUBLIC_DIR`, `STATIC_DIR`, `POSTS_DIR` overridable in `Makefile`

**Build:**
- `hugo.toml` - Site config (baseURL, theme, language, menu, params, markup pipeline)
- `Makefile` - Build commands and CV generation orchestration
- `.github/workflows/hugo.yml` - CI/CD with Hugo install, Chromium install, CV generation, Hugo build, Pages deploy
- `.gitignore` - Excludes `/public/`, `/resources/_gen/`, `/static/cv.html`, `/static/cv.pdf`, `assets/jsconfig.json`, `hugo_stats.json`
- `.gitmodules` - Pins `themes/terminal` submodule

## Platform Requirements

**Development:**
- Hugo extended binary on PATH (or set `HUGO=...` for `Makefile`)
- Python 3.11+ for `make cv` / `make cv-pdf`
- Chromium or Google Chrome on PATH for `make cv-pdf` (Makefile auto-detects via `which chromium`)
- Git with submodule support for theme initialization

**Production:**
- GitHub Pages (deploy job uses `actions/deploy-pages@v4`)
- Build output: `public/` directory uploaded as `github-pages` artifact via `actions/upload-pages-artifact@v3`
- Concurrency group `pages` ensures serialized deploys (`cancel-in-progress: false`)

---

*Stack analysis: 2026-05-09*
