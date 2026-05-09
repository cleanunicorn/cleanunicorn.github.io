# Testing Patterns

**Analysis Date:** 2026-05-09

## Test Framework

**Runner:**
- None. This repository has **no test infrastructure**.
- No test framework is installed or configured. There is no `pytest`, `unittest`-based test suite, no `jest`/`vitest`, no `go test`, and no Hugo content-validation harness.
- Searches confirmed:
  - No `tests/` or `test/` directory anywhere in the repo.
  - No files matching `test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`.
  - No `pytest.ini`, `pyproject.toml`, `tox.ini`, `conftest.py`, `jest.config.*`, `vitest.config.*`, `.mocharc*`.
  - No `requirements.txt`, `requirements-dev.txt`, `Pipfile`, or `package.json` (so no declared test dependencies).
- Config: not applicable.

**Assertion Library:**
- Not applicable.

**Run Commands:**
- Not applicable. The Makefile (`Makefile`) exposes only build/serve/clean/scaffold targets — `serve`, `serve-drafts`, `build`, `build-drafts`, `clean`, `new`, `update-theme`, `submodules`, `cv`, `cv-pdf`. There is no `make test` target.

## Test File Organization

**Location:**
- Not applicable. No tests exist.

**Naming:**
- Not applicable.

**Structure:**
- Not applicable.

## Test Structure

**Suite Organization:**
- Not applicable.

**Patterns:**
- Not applicable.

## Mocking

**Framework:** Not applicable.

**Patterns:**
- Not applicable.

**What to Mock:**
- Not applicable.

**What NOT to Mock:**
- Not applicable.

## Fixtures and Factories

**Test Data:**
- Not applicable.

**Location:**
- Not applicable.

## Coverage

**Requirements:** None enforced. No coverage tooling is installed and no coverage targets are set in CI.

**View Coverage:**
- Not applicable.

## Test Types

**Unit Tests:**
- None.

**Integration Tests:**
- None in the conventional sense.
- The closest analog is the **CI build itself**: `.github/workflows/hugo.yml` performs a full production build on every push to `main`. If any of the following break, the workflow fails and acts as a smoke test:
  - `make cv-pdf` — runs `python3 scripts/generate_cv.py` and Chromium headless PDF rendering. A regression in `scripts/generate_cv.py` (missing content section, malformed regex, broken TOML) crashes the script and fails the build.
  - `hugo --gc --minify --baseURL ...` — Hugo will exit non-zero on template errors, broken shortcodes, or invalid frontmatter, catching content-side regressions.
- This is implicit verification, not a test suite — there are no assertions on the output, only that the commands exit 0.

**E2E Tests:**
- Not used.

## Common Patterns

**Async Testing:**
- Not applicable.

**Error Testing:**
- Not applicable.

## Manual Verification Workflow

In the absence of automated tests, the working verification flow is:

1. **Local preview:** `make serve` (or `make serve-drafts` to include drafts/futures) starts `hugo server -D --disableFastRender` and serves the site at `http://localhost:1313/` for visual inspection.
2. **Production build dry-run:** `make build` produces the full static site under `public/` so layout/template changes can be inspected without deploying.
3. **CV regeneration:** `make cv` (HTML) or `make cv-pdf` (HTML + PDF via headless Chromium) regenerates `static/cv.html` and `static/cv.pdf`. Open the HTML in a browser to verify rendering before committing.
4. **CI gate:** Pushing to `main` triggers `.github/workflows/hugo.yml`, which builds the site on a clean ubuntu-latest runner with Hugo `0.152.2`, Go `1.25.3`, Node `22.20.0`, Dart Sass `1.93.2`, and Chromium. Build failure blocks the GitHub Pages deploy.

## Recommendations (gaps)

If automated tests are ever introduced, the highest-leverage starting points would be:

- **`scripts/generate_cv.py` unit tests** — pure-function helpers (`strip_frontmatter`, `md_to_html`, `inline_md`, `extract_section`, `parse_skills`, `_parse_skills_fallback`) are deterministic, dependency-free, and currently the only Python in the repo. `pytest` with fixture markdown strings would cover the regex-heavy code paths cheaply.
- **Link-check / HTML-validate** of the built `public/` directory in CI (e.g. `lychee`, `htmltest`) to catch broken internal links and missing assets.
- **Frontmatter schema check** for `content/posts/**/index.md` to enforce required keys (`title`, `date`, `draft`) before deploy.

None of these exist today; they are listed only as future hooks for `/gsd-plan-phase` if a testing phase is requested.

---

*Testing analysis: 2026-05-09*
