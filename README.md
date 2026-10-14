# cleanunicorn.github.io

Source for [cleanunicorn.github.io](https://cleanunicorn.github.io/), a
[Hugo](https://gohugo.io/) site on the
[Terminal](https://github.com/panr/hugo-theme-terminal) theme, which is
included as a git submodule in `themes/terminal`.

## Prerequisites

- **Hugo extended**, at the version in [`.hugo-version`](.hugo-version). CI
  installs exactly that version. Nothing checks your local Hugo, so match it by
  hand to see what CI builds.
- **Python 3.11+** for the scripts in `scripts/` and the tests. All of them
  except `generate_og_image.py` (`make og-image`) use only the standard library.
- **Node.js 22+** for the browser navigation check in `make build`. The build
  installs its pinned `playwright-core` package with npm.
- **Chromium or Google Chrome** on `PATH` for `make build`,
  `make check-browser-nav`, and `make cv-pdf` (`CHROME=<path>` selects a browser).
- **Pillow**, only for `make og-image`: `pip install -r requirements.txt`.

Clone with the theme:

```sh
git clone --recurse-submodules https://github.com/cleanunicorn/cleanunicorn.github.io.git
# or, in an existing clone:
make submodules
```

## Local development

```sh
make dev                        # serve with drafts and future posts on :1313
make dev HOST=192.168.1.50      # the same, reachable from another device on the LAN
make new POST="My Post Title"   # create content/posts/my-post-title/index.md
```

The homepage band and `/projects/` both read `data/projects.toml`, the
featured projects; `make check-build` fails if either page drops one. The full
project list stays in `content/about/_index.md`.

`make help` lists every target. The ones you will use most:

| Target | What it does |
|---|---|
| `make check-positioning` | Checks that the identity copy leads with what he builds, that `static/llms.txt` still matches the pages it restates, and that descriptions fit in 160 characters |
| `make test` | Runs the Python unit tests in `tests/` (including navigation, KaTeX, and built-HTML semantic guards, positioning rules, CV tools, and cv-pdf failure paths) |
| `make check-alt-text` | Fails if a post image has placeholder alt text ("Untitled", "image 2", a filename) |
| `make build` | Runs `check-positioning` and `check-alt-text`, builds the site into a clean `public/`, then runs `check-build`, `check-built-meta`, and the Chromium navigation check |
| `make check-build` | Checks the built site in `public/`: feeds, removed outputs, profile data, primary navigation markup, post older/newer links and closing CTA, one configured KaTeX render pass per math page, accessible heading links, and machine-readable dates |
| `make check-built-meta` | Checks the built site's search and social metadata: descriptions, Open Graph image, JSON-LD, robots.txt |
| `make check-browser-nav` | Uses Chromium to check the mobile Menu state, Tab order, desktop links, the no-JS fallback, and that post navigation and the closing CTA fit at 390px and 1300px against `public/`; installs the pinned `playwright-core` package with npm if needed |
| `make cv` | Writes the CV as HTML to `static/cv.html`, generated from the About and Work pages |
| `make cv-pdf` | Runs `make cv`, then prints `static/cv.pdf` with headless Chromium or Chrome (`CHROME=<path>` picks the browser) |
| `make books` | Refreshes the About page's Books list from Goodreads |
| `make og-image` | Regenerates `static/og-image.png`, the social share card (needs Pillow) |
| `make update-theme` | Moves the theme submodule to its latest upstream commit |

`static/cv.html` and `static/cv.pdf` are gitignored. CI generates them before
every build. `make cv-pdf` exits non-zero when it cannot produce the PDF, for
example with no browser on `PATH` or an empty output file.

## CI and deploy

### Article audio

Every published post gets a narrated MP3 generated with
[Cathy](https://github.com/cleanunicorn/cathy). The deployment workflow backfills
existing posts and generates audio for new or changed posts. MP3s are part of the
GitHub Pages artifact; they are not committed to Git. Article pages show a native
player and download link, with no autoplay or audio preloading.

Hugo first exports published articles to `public/narration.json`, with rendered
shortcodes and without front matter or site navigation. The generator keeps prose,
headings, link labels, inline code, image descriptions, and captions. It omits
code blocks, TeX equations, diagrams, scripts, embedded media UI, and footnote
navigation. Code and equation omissions are announced in the narration. Drafts
and future posts are excluded by Hugo's normal publication rules.

`scripts/article_audio.toml` pins the Cathy commit and selects Kokoro's `af_heart`
voice at normal speed. Change that file to choose another Kokoro voice or speed,
or upgrade Cathy. CI uses Python 3.12 and CPU PyTorch wheels; synthesis needs
`espeak-ng` and MP3 encoding/validation needs `ffmpeg` and `ffprobe`.

To generate locally, install those system dependencies and [uv](https://docs.astral.sh/uv/), then run:

```sh
uv tool install --python 3.12 "$(python3 scripts/generate_article_audio.py --print-cathy-source)"
make audio-plan                 # report which published articles need generation
make audio                      # export, generate audio, rebuild with players
```

The first run downloads Cathy's speech model and dependencies; subsequent runs
reuse them. Generated MP3s are cached in `.cache/article-audio/`, keyed by rendered
article content, title, Cathy commit, voice, speed, and generator code. CI restores
that cache plus model/dependency downloads. Cache eviction causes regeneration,
so the first deployment takes longer than later ones. The build job allows up to
120 minutes; a failed narration blocks deployment and leaves the live site intact.

The generator checks each MP3 with `ffprobe`, regenerates corrupt entries, writes
`static/audio/` plus `data/article_audio.json`, and prunes unused generated MP3s.
Players appear only when the manifest matches the current article and the MP3
exists. Run `make audio` after editing an article to update local narration.

`make test` covers extraction, cache reuse/invalidation, corrupt files, and failed
generation. PR CI also runs `python3 tests/check_article_audio_build.py`: both Hugo
passes use short fixture MP3s to check publication filtering, accessible players,
download links, asset inclusion, and stale-audio suppression, without downloading
speech models. Fixture audio is isolated in a temporary site and never deployed.
Changes to the generator, Cathy settings, or deployment workflow also run a real
CPU narration smoke test in PR CI, synthesizing and validating a short article.

### Workflows

- **Pull requests** run two workflows:
  - *Check positioning* (`.github/workflows/positioning.yml`) runs
    `make check-positioning` and `make test`.
  - *Build and link-check* (`.github/workflows/site-check.yml`) builds the site
    with `hugo --minify`, runs `make check-alt-text`, `make check-build`,
    `make check-built-meta`, and `make check-browser-nav`, then runs [lychee](https://lychee.cli.rs/) offline
    over `public/`. A dead internal link or `#anchor` fails the PR.
- **A push to `main`** runs *Build and deploy* (`.github/workflows/hugo.yml`).
  It runs the positioning guard and `make check-alt-text`, generates the CV
  (HTML and PDF), builds with Hugo, runs `make check-build`,
  `make check-built-meta`, and `make check-browser-nav`, then publishes `public/` to GitHub Pages.
- **Dependabot** (`.github/dependabot.yml`) opens weekly PRs that bump the
  GitHub Actions and the theme submodule.

To move to a new Hugo version, change `.hugo-version`. Both workflows read it.

