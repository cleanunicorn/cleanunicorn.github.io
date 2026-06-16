# Codebase Concerns

**Analysis Date:** 2026-05-09

## Tech Debt

**Outdated theme submodule:**
- Issue: `themes/terminal` submodule pinned to commit `5a2b4c0` (tag `v4.2.3`, dated 2025-05-10) — roughly one year stale as of the analysis date. `make update-theme` exists but is run manually; nothing in CI surfaces drift. No `git fetch` was run during analysis (offline), so unknown upstream commits and security/UX fixes may be missing.
- Files: `.gitmodules`, `themes/terminal/`, `Makefile` (target `update-theme`)
- Impact: Bug fixes, accessibility improvements, and SEO partials (e.g., `head.html`) shipped upstream are not picked up. The pinned `head.html` already references third-party CDN assets that the upstream may have replaced.
- Fix approach: Add a scheduled GitHub Actions workflow (e.g., monthly cron) that runs `git submodule update --remote --merge themes/terminal`, opens a PR, and runs the build to verify nothing breaks. Document a manual review step before merging because the theme is template-heavy and breakage is easy to miss.

**Custom regex-based Markdown parser in CV generator:**
- Issue: `scripts/generate_cv.py` ships its own minimalist Markdown engine (`md_to_html`, `inline_md`, `_parse_skills_fallback`). It handles only the small subset of constructs currently used in `content/about/_index.md` and `content/previous-work.md` (headings, lists, links, bold/italic/code, the `relref` shortcode). Anything outside that subset (tables, nested lists, fenced code blocks, footnotes, images, multi-line links, escaped pipes) silently produces malformed HTML.
- Files: `scripts/generate_cv.py:32-114`, `scripts/generate_cv.py:166-198`
- Impact: Adding a new construct to either source file (e.g., a code block or table) breaks the generated CV without any visible error. The generator runs in CI (`make cv-pdf`) and feeds Chromium, so a broken CV PDF will silently ship.
- Fix approach: Either (a) restrict the CV source to a documented subset and add a CI check that fails on disallowed Markdown constructs, or (b) reuse Hugo itself by rendering a dedicated `/cv/` template and printing it (eliminates the parser entirely).

**Self-rolled TOML fallback parser:**
- Issue: `_parse_skills_fallback` (`scripts/generate_cv.py:201-220`) only covers a single-line `items = [...]` shape. Multi-line arrays, comments mid-array, or nested tables in `data/skills.toml` will silently lose entries when running on Python <3.11 without `tomli` installed.
- Files: `scripts/generate_cv.py`, `data/skills.toml`
- Impact: CV silently drops skills if the runtime is older than Python 3.11.
- Fix approach: Pin a minimum Python version (3.11) in the workflow and the Makefile, or list `tomli` as an explicit dependency, then delete the regex fallback.

**Hand-rolled help/`make new` slug logic:**
- Issue: The `new` target in `Makefile` only replaces spaces with dashes and lowercases — it does not strip non-ASCII characters, colons, parentheses, or apostrophes. Existing posts already show the cost: directories like `content/posts/eip-7514:-balancing-urgency-with-long-term-vision/` and `the-right-way-to-use-transient-storage-(eip-1153)/` contain `:` and `()`, which are valid on Linux/macOS but cause friction on Windows checkouts and several static-site link checkers.
- Files: `Makefile` (`new` target), `content/posts/`
- Impact: Inconsistent URL slugs, fragile filenames, headaches for any external tooling that doesn't tolerate `:` in path segments.
- Fix approach: Replace the inline shell with a small Python helper (or a stricter `tr`/`sed` pipeline) that produces ASCII-safe kebab-case slugs and rejects anything else.

**Verbose CI debug step kept in production workflow:**
- Issue: `.github/workflows/hugo.yml` ships a `List public directory (Debug)` step that runs `ls -R public/` on every build.
- Files: `.github/workflows/hugo.yml`
- Impact: Adds noise (and a small cost) to every deploy log; signals "still debugging" rather than a maintained pipeline.
- Fix approach: Delete the step, or guard it behind `if: failure()`.

**Double-slash link in `_index.md`:**
- Issue: `[BlockchainHackers IV - Mastering Ethereum CTFs](/presentations//blockchainhackers-iv/...)` has a stray `//` between segments.
- Files: `content/about/_index.md:43`
- Impact: Browsers normalize this, but external link checkers and OG-scraping bots may flag or mishandle it; canonical URLs become inconsistent.
- Fix approach: Drop the duplicate slash.

**Misspelled `.nojekyll` marker:**
- Issue: The repo contains an empty file named `.nojeckyll` (note: `eckyll`). GitHub Pages looks for `.nojekyll`. The current file does nothing.
- Files: `/.nojeckyll`
- Impact: Today this is harmless because the build is the GitHub Actions Pages workflow (not legacy Jekyll), so Jekyll never runs. If the deploy mechanism is ever switched to "Deploy from a branch", Jekyll will preprocess the `public/` output and likely break paths that start with underscores or contain Liquid-like syntax.
- Fix approach: Rename to `.nojekyll` (or delete entirely — the Pages Action doesn't read it).

## Known Bugs

**Future-dated, mostly-empty post on production:**
- Symptoms: `content/posts/an-extension-of-the-self/index.md` is dated `2026-01-28` (in the future relative to several timezones depending on UTC offset, and authored before that date). It is not marked `draft = true`, so it ships once the date passes. Frontmatter has empty `description = ""` and `cover = ""`, and the `tags` line is commented out.
- Files: `content/posts/an-extension-of-the-self/index.md:1-12`
- Trigger: Any user visiting `/posts/an-extension-of-the-self/` after the post date passes.
- Workaround: Either set `draft = true`, fill in `description`/`tags`, or fix the date. The current state means the post will appear in feeds with an empty description and broken Twitter/OG previews.

**Draft post sitting in `content/posts/`:**
- Symptoms: `content/posts/making-ais-think-before-they-speak/index.md` has `draft = true` and `title = 'Making Ais Think Before They Speak'` (broken capitalization for "AIs"). It will accidentally publish if anyone runs `hugo -D` for a deploy or flips the flag.
- Files: `content/posts/making-ais-think-before-they-speak/index.md:1-7`
- Trigger: Setting `draft = false` or building with `-D`.
- Workaround: Either finish and publish, move out of `content/posts/`, or store in a branch — leaving long-lived drafts in `main` invites accidents.

**`_index.md` Talks list contains a truncated entry (post-edit):**
- Symptoms: After the most recent edit to `content/about/_index.md` the first ETHCluj entry reads "Beyond \"Trust me, bro\" Engineering LLM reliability" — verify this is the intended title; the previous version cut off at "LLM" and the bracketing has unmatched-quote risk for any downstream Markdown linter.
- Files: `content/about/_index.md:33`
- Trigger: Markdown linters that escape on unmatched quotes inside link text.
- Workaround: Confirm the talk title is complete and consider replacing the literal `"…"` with smart quotes or escaping to avoid future linter trips.

## Security Considerations

**Third-party CDN assets loaded without Subresource Integrity in math partial:**
- Risk: `layouts/partials/math.html` loads KaTeX 0.16.25 from `cdn.jsdelivr.net`. The `integrity=` hashes are present (good), but the `onload="renderMathInElement(document.body)"` runs against the entire DOM, including post content authored in markdown. Combined with `markup.goldmark.renderer.unsafe = true` (`hugo.toml:7`), an attacker who can land malicious markdown (e.g., a future contributor) could inject HTML/JS that KaTeX's auto-render then evaluates expression-side.
- Files: `layouts/partials/math.html`, `hugo.toml:6-12`
- Current mitigation: Single-author repo limits the threat model; SRI on KaTeX scripts; KaTeX `throwOnError: false` keeps rendering robust.
- Recommendations: Document that `unsafe: true` is intentional and audit any inbound PR that touches Markdown content for raw HTML/script tags. Consider a CSP `<meta http-equiv="Content-Security-Policy" …>` partial that locks `script-src` to `self` + `cdn.jsdelivr.net` + `platform.twitter.com`.

**Twitter widget loaded without SRI:**
- Risk: `layouts/shortcodes/x.html` injects `https://platform.twitter.com/widgets.js` via plain `<script async src=…>` with no integrity hash and no fallback. Any post using `{{< x user="…" id="…" >}}` will load whatever Twitter (now X) ships at that URL.
- Files: `layouts/shortcodes/x.html`
- Current mitigation: None — this is the standard Twitter embed pattern.
- Recommendations: Switch to a static "blockquote-only" embed (no JS) for archival posts, or accept the trust dependency and document it.

**`unsafe: true` in goldmark renderer:**
- Risk: `hugo.toml:7` enables raw HTML in Markdown (needed for the `<!-- ... -->` comments and inline HTML used in posts/about). With a single author this is fine; a future contributor's PR could land XSS.
- Files: `hugo.toml`
- Current mitigation: Single-author repo; PR review.
- Recommendations: Add a CI step that greps PR-diff Markdown for `<script`, `<iframe>`, or `on*=` attributes and fails the build if present without an explicit allow-list comment.

**Generated CV inlines all CSS, but is built from user-controlled markdown:**
- Risk: `scripts/generate_cv.py` wraps `cv.css` inside `<style>…</style>` and writes the resulting HTML to `static/cv.html` (then to `cv.pdf` via headless Chromium). The Markdown source it reads is escaped via `inline_md`, but the order of operations escapes `&<>` *before* applying the link/bold/code regexes — meaning a value like `**a<>b**` becomes `<strong>a&lt;&gt;b</strong>` (correct), but a malformed regex match could still emit unbalanced tags. More importantly, anything an attacker can land in `_index.md` ends up in a PDF that is then served on the live site.
- Files: `scripts/generate_cv.py:90-114`, `static/cv.html`, `static/cv.pdf`
- Current mitigation: Single-author repo; HTML escaping in `inline_md`.
- Recommendations: Move CV generation to Hugo templates (eliminates the homemade escape pipeline) or add a small unit test that round-trips a known-malicious Markdown snippet through the generator and asserts safe output.

## Performance Bottlenecks

**Inline web-font import in CV CSS blocks first paint:**
- Problem: `static/css/cv.css:3` does `@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:…&family=Space+Grotesk:…');` from inside an inlined `<style>` block. `@import` inside a `<style>` is the worst-case waterfall — the CSS is downloaded, the `@import` discovered, then the font CSS fetched, then the actual font files. For Chromium PDF generation this introduces an avoidable network round-trip.
- Files: `static/css/cv.css:3`, `scripts/generate_cv.py:280-286`
- Cause: Convenience — keeps the CV self-contained.
- Improvement path: Either move the fonts to local `static/fonts/` and reference them with `@font-face`, or replace `@import` with a `<link rel="preload" as="style" …>` injected by `generate_cv.py` before the `<style>` block. For PDF rendering specifically, embedding the font binary as base64 yields a fully offline build.

**Per-build full Hugo cache rotation:**
- Problem: `.github/workflows/hugo.yml` keys the cache on `${{ github.run_id }}` (line: `key: hugo-${{ github.run_id }}`). Because the run id is unique per run, the *primary* key never hits — only the `restore-keys: hugo-` prefix match falls through. This means the workflow always saves a brand new cache entry on every push, growing the GitHub Actions cache quickly until the 10 GB ceiling evicts useful entries.
- Files: `.github/workflows/hugo.yml`
- Cause: Cache key copy-pasted without parameterizing on inputs that actually invalidate (Hugo version, content hash).
- Improvement path: Key on something stable like `hugo-${HUGO_VERSION}-${{ hashFiles('content/**', 'assets/**', 'static/**', 'themes/**', 'hugo.toml') }}`, with `restore-keys: hugo-${HUGO_VERSION}-`.

**Apt update + Chromium install on every CI run:**
- Problem: The `Install Chromium` step runs `sudo apt-get update && sudo apt-get install -y chromium-browser` on every push. This is ~30 seconds of avoidable work and is the slowest step besides the Hugo build itself.
- Files: `.github/workflows/hugo.yml`
- Cause: Headless Chromium is needed to print the CV to PDF.
- Improvement path: Either (a) cache `/var/cache/apt/archives/*.deb`, (b) use a docker image with Chromium pre-installed, or (c) replace Chromium with `weasyprint` / `wkhtmltopdf` (single Python install, no apt needed).

## Fragile Areas

**CV PDF generation toolchain:**
- Files: `Makefile` (`cv-pdf` target), `scripts/generate_cv.py`, `static/css/cv.css`
- Why fragile:
  1. Detects browser at runtime with `which chromium … || CHROME=google-chrome` — silently picks `google-chrome` even if it's not installed, then the PDF output step fails *but* the script then unconditionally `echo "PDF written to …"`, so the user sees a success message even when no PDF was generated.
  2. `--no-margins` and `--no-pdf-header-footer` are non-portable flags that exist on recent Chromium/Chrome but were renamed in earlier versions (`--print-to-pdf-no-header`).
  3. `2>/dev/null` swallows all error output, so a broken build produces zero diagnostic information.
  4. The CV PDF inlines Google-hosted fonts; if Chromium runs in a sandbox without network egress (common in some CI environments), the font fetch hangs until timeout, producing an unstyled PDF.
- Safe modification: Before changing, run `make cv-pdf` locally and confirm `static/cv.pdf` actually changes (check `mtime` and file size). Add `set -e` and remove the `2>/dev/null` redirect for at least one diagnostic build.
- Test coverage: Zero. There is no test that the CV builds, that it contains expected sections, or that the PDF is non-empty.

**Theme submodule + heavy reliance on theme partials:**
- Files: `themes/terminal/`, `layouts/partials/extended_head.html`, `layouts/partials/head.html`
- Why fragile: The site extends the theme's `<head>` through `layouts/partials/extended_head.html`, which conditionally includes `math.html` (KaTeX), `structured_data.html`, and `analytics.html`. The theme's own `head.html` is what invokes `extended_head.html`; any rename or refactor upstream would silently drop math rendering, structured data, and analytics.
- Safe modification: When bumping the theme, confirm `themes/terminal/layouts/partials/head.html` still calls `partial "extended_head"`; otherwise the override chain breaks.
- Test coverage: None — math rendering breakage would only be caught by visiting a `math = true` post manually.

**`hugo.toml` + theme params are minimal:**
- Files: `hugo.toml`
- Why fragile: There is no `[params.twitter]` block, but `themes/terminal/layouts/partials/head.html:38` references `$.Site.Params.Twitter.site`. Hugo evaluates this lazily inside `{{ if (isset $.Site.Params "twitter") }}`, so it short-circuits, but adding any new `[params]` key without re-checking which theme partials use it can silently produce empty `<meta>` tags.
- Safe modification: Run `hugo --printPathWarnings --printUnusedTemplates` after every config change.

## Scaling Limits

**Local `public/` directory is 19 GB:**
- Current capacity: A single dev machine. The committed lockfile and CI artifacts make this irrelevant for production (it's gitignored), but local `make clean` is the only mechanism to reclaim disk.
- Limit: Disk space; this directory will keep growing as Hugo writes intermediate `_gen/` resources.
- Scaling path: Add `make clean` to a pre-build hook, or document the size in the README. Verify nothing in `public/` is accidentally tracked: `git ls-files public/` should be empty (confirmed during analysis).

## Dependencies at Risk

**Theme `hugo-theme-terminal` upstream activity:**
- Risk: The theme is at v4.2.3; the repo's recent activity history (per local submodule log) shows mostly cosmetic fixes for over a year. No public commitment to security maintenance.
- Impact: If the upstream goes unmaintained, any Hugo breaking change will require a fork or a theme migration.
- Migration plan: Hugo themes that are currently maintained and visually similar include `hugo-paper`, `PaperMod`, or `hugo-coder`. Forking `terminal` into the org is also viable since the customization surface is small (`extended_head.html`, `math.html`, `x.html`, `_markup/render-link.html`, `static/css/cv.css`, `assets/css/z-*.css`).

**Twitter/X embed script (`platform.twitter.com/widgets.js`):**
- Risk: X frequently changes embed behavior, sometimes breaking embeds for unauthenticated viewers.
- Impact: Any post using `{{< x >}}` may render as a bare blockquote on visitor browsers without an X session.
- Migration plan: Render a static screenshot + link to the tweet, or use an archive service (e.g., `nitter`) that has stable HTML output.

**KaTeX CDN pin (`@0.16.25`):**
- Risk: Pinned version with SRI, so it cannot be silently swapped — but it also cannot pick up security fixes.
- Impact: Low; KaTeX is mature.
- Migration plan: Bump quarterly and refresh SRI hashes. Better: move KaTeX to local `static/vendor/` so the site has zero JS-CDN dependencies.

## Missing Critical Features

**No link checker in CI:**
- Problem: Outbound link rot is silent. `content/about/_index.md` already contains a noticeably-stale link surface (Discord URL `discordapp.com` → now `discord.com`, `consensys/mythril-classic` deprecated, `dapptools-template` archived) and the project lists a GitLab project (`gitlab.com/cleanunicorn/eth-tipper` for Midas) that should be verified.
- Blocks: Reader trust; SEO. Search engines downweigh sites with broken outbound links.
- Fix approach: Add `lychee-action` (or `markdown-link-check`) as a non-blocking nightly cron workflow. Filter to `content/**` and `static/**` (skip social URLs that 403 to bots).

**No HTML validation / accessibility check:**
- Problem: There is no axe/pa11y/htmlproofer step. The theme's `head.html` emits `<meta name="twitter:creator" content="…">` only when `authortwitter` is set; for posts that lack it (most), the tag is rendered with `content=""` if `Params.Author` is unset (typical) — minor SEO debt. The site has no `lang` attribute audit, no skip-link, no contrast verification.
- Blocks: Accessibility compliance; potential lawsuit risk for commercial sites (low priority for a personal blog).
- Fix approach: Add `pa11y-ci` against the local `hugo server` in CI, with a results comment posted on PRs. At minimum, run `htmltest` (Hugo-aware) to validate generated `public/`.

**No Hugo version pinning at the project level:**
- Problem: `hugo.toml` does not declare `module.hugoVersion = "0.152.2"`. The version is only pinned in `.github/workflows/hugo.yml`. Local developers running an older or newer Hugo can introduce subtle template breakage (the `markup.goldmark.extensions.passthrough` block requires Hugo 0.122+; Hugo 0.146+ deprecated several rendering hook APIs the theme might use).
- Blocks: Reproducible local builds.
- Fix approach: Add a `[module]` block with `hugoVersion = { min = "0.146.0" }` and document the pinned version in the README.

**No README / CONTRIBUTING / dev setup docs:**
- Problem: Newcomers (or future-self) have to read `Makefile` to discover commands. The CV pipeline's chromium dependency is undocumented anywhere except inline in the Makefile.
- Blocks: Onboarding; reproducing builds.
- Fix approach: Add a top-level `README.md` describing prerequisites (Hugo extended ≥ 0.152, Python 3.11+, Chromium for CV), and the `make help` target.

**No favicon at the path the theme expects:**
- Problem: `themes/terminal/layouts/partials/head.html:31` emits `<link rel="shortcut icon" href="{{ "favicon.png" | absURL }}">` and line 32 references `apple-touch-icon.png`. Neither file exists in `static/`. The site only ships `static/images/favicon-16x16.png` and `static/images/favicon-32x32.png`.
- Blocks: Browser tab icon; iOS bookmark icon; SEO image preview when `cover` is unset (the OG fallback is `og-image.png`, also missing).
- Fix approach: Add `static/favicon.png`, `static/apple-touch-icon.png`, and `static/og-image.png` (1200×627 per the `og:image:width`/`height` metadata).

**No `og-image.png` for default Open Graph previews:**
- Problem: The theme falls back to `static/og-image.png` for any page that lacks a `cover` param. The file does not exist, so every link share on Twitter/Slack/Discord shows a broken/blank preview.
- Blocks: Social-share appeal; click-through rate from socials.
- Fix approach: Generate a 1200×627 default OG image and place it at `static/og-image.png`. Optionally add per-post `cover` images.

## Test Coverage Gaps

**No tests of any kind:**
- What's not tested: Everything. There is no `pytest`/`unittest` suite for `scripts/generate_cv.py`, no Hugo template tests, no link tests, no visual regression tests, no a11y tests.
- Files: Project root (no `tests/`, `test/`, or `*_test.*` files).
- Risk: Silent breakage in the CV generator (the regex Markdown engine), in theme upgrades, and in content links. Because the CV PDF is generated and published in CI without any verification step, a malformed CV could ship undetected.
- Priority: High for `scripts/generate_cv.py` (mission-critical: it's the document hiring partners read), medium for content link health, low for visual regressions.

**No CI verification that generated CV actually contains expected sections:**
- What's not tested: Whether `make cv-pdf` produces a non-empty PDF, whether the PDF contains all expected `<section>` blocks (Bio, Contact, Skills, Experience, Talks, Podcasts, Projects), whether the PDF size is sane.
- Files: `.github/workflows/hugo.yml` step `Generate CV (HTML + PDF)`.
- Risk: The pipeline's only check is "the script exited 0", and the script always exits 0 even when Chromium fails (because the chained `&&` is followed by an unconditional `echo`).
- Priority: High. Suggested check: `python3 -c "import sys, pathlib; p=pathlib.Path('static/cv.pdf'); sys.exit(0 if p.exists() and p.stat().st_size > 50_000 else 1)"`.

**No content lint rules:**
- What's not tested: Front-matter completeness (description, tags, draft flag, date sanity). 8 of 10 posts have empty or missing `description`. Only 1 of 10 has any `tags` block (and it's commented out in `an-extension-of-the-self/index.md`). Future-dated posts are not flagged.
- Files: `content/posts/*/index.md`.
- Risk: SEO degradation (search snippets fall back to the first paragraph), inconsistent RSS, broken social previews.
- Priority: Medium. Suggested fix: a small Python script in `scripts/lint_content.py` invoked from CI that asserts each post has a non-empty `description`, valid `date <= today + 1 day`, and either `tags` or `keywords`.

---

*Concerns audit: 2026-05-09*
