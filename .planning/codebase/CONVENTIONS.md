# Coding Conventions

**Analysis Date:** 2026-05-09

This is a Hugo static site, so "code" mostly means Markdown content, TOML configuration, Hugo HTML templates, CSS, and a single Python script (`scripts/generate_cv.py`). Conventions are inferred from the existing files rather than enforced by linters — there are no lint or format tools configured in the repository.

## Naming Patterns

**Files:**
- Markdown content uses lowercase, hyphenated slugs that mirror post titles. Examples: `content/posts/an-extension-of-the-self/index.md`, `content/posts/the-right-way-to-use-transient-storage-(eip-1153)/index.md`.
- Each post is a Hugo page bundle: a directory named after the slug containing `index.md` plus colocated assets (e.g. `image.png`, `image 1.png`).
- Top-level singletons live as flat markdown files: `content/_index.md`, `content/previous-work.md`, `content/about/about.md`.
- Hugo layout files use lowercase with underscores: `layouts/partials/extend_head.html`, `layouts/partials/extended_head.html`, `layouts/partials/math.html`, `layouts/shortcodes/x.html`.
- Static assets are grouped by type under `static/`: `static/css/custom.css`, `static/css/cv.css`, `static/css/syntax.css`, `static/images/`, `static/presentations/`.
- Python scripts are snake_case: `scripts/generate_cv.py`.
- Data files use lowercase TOML: `data/skills.toml`, `hugo.toml`.
- The Make target convention is kebab-case (`serve-drafts`, `build-drafts`, `update-theme`, `cv-pdf`).

**Functions (Python):**
- snake_case throughout `scripts/generate_cv.py`. Examples: `strip_frontmatter`, `md_to_html`, `inline_md`, `parse_config`, `extract_section`, `parse_about`, `parse_work`, `parse_skills`, `build_skills_html`, `build_projects_html`, `build_work_html`, `generate_html`, `main`.
- Internal/private helpers are prefixed with a leading underscore: `_parse_skills_fallback`.

**Variables (Python):**
- snake_case for locals (`in_ul`, `links_md`, `talks_md`, `bio_match`, `html_doc`).
- UPPER_SNAKE_CASE for module-level path constants at the top of `scripts/generate_cv.py`: `ROOT`, `CONTENT`, `ABOUT_MD`, `WORK_MD`, `CONFIG`, `CSS_PATH`, `SKILLS_PATH`.

**Types (Python):**
- Built-in generics with PEP 604 union syntax (`str | None`, `list[str]`, `list[tuple[str, list[str]]]`, `dict`). The codebase targets Python 3.10+ in practice and explicitly opts into `tomllib` on 3.11+.

**Hugo content frontmatter:**
- TOML frontmatter delimited by `+++ ... +++` (not YAML `---`). Defined by `archetypes/default.md`.
- Keys are lowercase camelCase: `title`, `date`, `draft`, `authorTwitter`, `cover`, `keywords`, `description`, `showFullContent`, `readingTime`, `slug`.
- Dates are ISO 8601 with timezone offset: `"2026-01-28T12:52:43+02:00"`.

**TOML data keys (`data/skills.toml`):**
- Section names use TitleCase, with underscores for multi-word names that need a friendly label override: `[Security]`, `[Blockchain]`, `[Languages]`, `[AI]`, `[Infrastructure]`, `[Venture_Capital]` (the latter sets `label = "Venture Capital"`).
- Each section has an `items = [...]` array; an optional `label = "..."` overrides the rendered category name.

## Code Style

**Formatting:**
- No formatter is configured (no `.prettierrc`, `pyproject.toml`, `ruff.toml`, `.editorconfig`, etc. exist).
- Python code in `scripts/generate_cv.py` follows PEP 8 visually: 4-space indent, two blank lines between top-level functions, dashed comment banners (`# ----...`) to separate logical sections (markdown helpers, content extractors, HTML generation, CLI).
- Markdown uses standard CommonMark; lists use `-` bullets; emphasis uses `**bold**` and `*italic*`.
- HTML in layouts uses Hugo template syntax (`{{ ... }}`, `{{- ... -}}`) with leading-dash whitespace stripping inside conditionals — see `layouts/partials/extend_head.html`.
- CSS uses 2- or 4-space indentation depending on file (`static/css/cv.css` uses 2 spaces, `static/css/custom.css` uses 4 spaces). CSS custom properties grouped under `:root` in `static/css/cv.css`.

**Linting:**
- None configured. Treat the existing files as the style reference when adding new content or scripts.

## Import Organization

**Python (`scripts/generate_cv.py`):**
1. Stdlib only, alphabetical: `argparse`, `html`, `re`, `sys`, then `from pathlib import Path`.
2. Optional/conditional imports are deferred inside the function that uses them — `tomllib` (3.11+) and the `tomli` fallback are imported lazily inside `parse_skills()` so the script runs on older Python without the dependency present.
3. The script intentionally has zero third-party dependencies: "No external dependencies beyond Python 3 stdlib." — the module docstring states this as a contract.

**Path Aliases:**
- Not applicable. Hugo handles asset resolution via its own conventions (page bundles, `static/`, `assets/`).

## Error Handling

**Patterns:**
- `scripts/generate_cv.py` uses optimistic file reads (`Path.read_text()`) without try/except. The script is expected to fail loudly via stack traces if content files go missing — appropriate for a CI build step (the workflow runs `make cv-pdf` and a non-zero exit will fail the build).
- The one defensive check is `SKILLS_PATH.exists()` in `parse_skills()`, which returns an empty list rather than raising when the data file is absent.
- Optional dependency loading uses nested `try/except ImportError` with a regex fallback (`_parse_skills_fallback`) so the script degrades gracefully on Python < 3.11 without `tomli`.
- Regex extractions (`re.match`, `re.search`) check for `None` before dereferencing the match (`m.group(...) if m else ""` / `m.end()`).
- Output directory is created defensively: `output.parent.mkdir(parents=True, exist_ok=True)` before `output.write_text(html_doc)`.

## Logging

**Framework:** None. Plain `print()` in `scripts/generate_cv.py` (e.g. `print(f"CV written to {output}")`).

**Patterns:**
- Single success line at the end of `generate_html()` confirming the output path. No verbose/debug levels.
- The Makefile echoes status lines for the PDF target (`echo "PDF written to $(STATIC_DIR)/cv.pdf"`).
- The GitHub Actions workflow uses `echo` and `ls -R public/` for build-time diagnostics (`Verify installations`, `List public directory (Debug)` steps).

## Comments

**When to Comment:**
- Python functions all carry one-line docstrings describing purpose and, where relevant, edge cases (e.g. `"""Render projects section as a compact list instead of individual headings."""`).
- The script module starts with a docstring that documents purpose **and** usage examples:
  ```
  """Generate a CV from the website content files.
  ...
  Usage:
      python3 scripts/generate_cv.py                  # writes to public/cv.html
      python3 scripts/generate_cv.py -o resume.html   # custom output path
  """
  ```
- Inline comments explain non-obvious regex intent (`# skip empty lines`, `# Hugo relref shortcodes — replace with #`, `# Remove --- separators`, `# escape HTML entities first (but preserve existing tags from processing)`).
- Banner comments (`# --- ... ---`) separate the file into named regions: "Markdown / frontmatter helpers", "Content extractors", "HTML generation", "CLI".
- TOML files use `#` comments to explain intent (`# Skills displayed in the CV, grouped by category.` in `data/skills.toml`; `# Generated CV (built by 'make cv-pdf' before Hugo build)` in `.gitignore`).

**JSDoc/TSDoc:**
- Not applicable — no JS/TS code in the repo.

## Function Design

**Size:**
- Functions in `scripts/generate_cv.py` are short and single-purpose; the longest is `generate_html()` (~60 lines) which orchestrates the others. Most helpers are 5–25 lines.

**Parameters:**
- Positional, with explicit type hints on every public helper (`def md_to_html(md: str) -> str:`, `def extract_section(md: str, heading: str) -> str:`, `def generate_html(output: Path) -> None:`).
- The CLI uses `argparse` with a single `-o/--output` flag defaulting to `ROOT / "public" / "cv.html"`. (Note: the Makefile overrides this to `static/cv.html`; the in-script default is stale relative to the Makefile contract — see CONCERNS.)

**Return Values:**
- Pure functions return strings (HTML/markdown) or structured `dict` / `list[tuple[...]]` payloads.
- I/O functions (`generate_html`) return `None` and side-effect to disk.
- Empty results are returned as empty strings or empty lists rather than `None`, so callers can compose without null checks.

## Module Design

**Exports:**
- The Python script is a single-file module run as `__main__`. No package, no `__init__.py`, no public API beyond `main()`.
- Module-level constants (paths) are uppercase and intended to be read-only.

**Barrel Files:**
- Not applicable.

## Hugo / Content Conventions

- New posts are scaffolded with `make new POST="My Post Title"`, which slugifies the title (`tr ' ' '-' | tr '[:upper:]' '[:lower:]'`) and runs `hugo new posts/<slug>/index.md`. Always use this target so the archetype frontmatter is applied.
- Posts default to `draft = true`; flip to `false` before publishing.
- Use page bundles (post-as-directory with `index.md`) so images and other assets can live next to the markdown and be referenced relatively (`![image.png](./image.png)`).
- Math support is opt-in per page via `math = true` in frontmatter, which triggers `layouts/partials/math.html` from `extend_head.html`.
- Inline TeX uses `$...$` and block TeX uses `$$...$$` (Goldmark passthrough is enabled in `hugo.toml`).
- Twitter/X embeds use the custom shortcode `{{< x user="handle" id="tweet-id" >}}` defined in `layouts/shortcodes/x.html`.
- Theme overrides go through `assets/css/extended/` (compiled by Hugo) for theme-aware styles, or `static/css/` for plain static stylesheets loaded by the layout.
- The terminal theme is a git submodule pinned in `.gitmodules` (`themes/terminal` → `hugo-theme-terminal`); update with `make update-theme`, never edit the submodule directly.

---

*Convention analysis: 2026-05-09*
