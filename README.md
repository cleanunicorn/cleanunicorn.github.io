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

Generate narration locally with `make audio`, using an OpenAI-compatible speech
API such as your self-hosted [drove](https://github.com/cleanunicorn/drove) server.
GitHub Actions builds and deploys the committed MP3s; it never synthesizes speech,
installs speech models, or calls the API. No audio credentials are needed in CI.

Install Hugo extended (the version in `.hugo-version`), Python 3.11+, and
`ffmpeg`/`ffprobe` locally. The Python client uses only the standard library.

```sh
cp .env.example .env
# Edit .env with your endpoint, model, voice, and optional API key.
make audio-plan                 # preview published articles and chunk counts; no API calls
make audio                      # export articles, request audio, rebuild with players
# Review/listen locally, then publish the generated files with your post changes:
git add -A static/audio data/article_audio.json
git commit -m "Update article narration"
```

`make audio` exports Hugo's published articles to `public/narration.json`, sends
narration text to the configured API, then rebuilds with native players and MP3
download links. Existing published posts are included in the same command, so it
also backfills the catalog. Drafts and future posts follow Hugo's normal
publication rules. Run it again after changing or publishing an article. An
article with missing or stale narration hides its player until you regenerate it.

Configuration lives in the ignored `.env`; shell environment variables take
precedence. `.env.example` documents every setting:

| Setting | Purpose |
|---|---|
| `AUDIO_API_URL` | Full speech URL, e.g. `http://localhost:8000/v1/audio/speech`; no path is appended |
| `AUDIO_API_KEY` | Optional bearer token; leave empty for an unauthenticated self-hosted server |
| `AUDIO_MODEL` | Model identifier supported by the server |
| `AUDIO_VOICE` | Voice identifier supported by the model |
| `AUDIO_SPEED` | Speaking speed, default `1.0` |
| `AUDIO_MAX_INPUT_CHARS` | Maximum characters per request, default `3500`; lower it for stricter server limits |
| `AUDIO_TIMEOUT_SECONDS` | Timeout per request, default `300` |
| `AUDIO_EXTRA_PARAMS` | Single-quoted JSON object for additional model/provider options, e.g. instructions or language |

Requests use `POST` with JSON containing `model`, `voice`, `input`, `speed`, and
`response_format: "mp3"`, plus any extra parameters. The server must return MP3
bytes. Reserved request fields cannot be overridden through extra parameters.
The client is independent of drove's implementation; select the endpoint, model,
and voice supported by drove once its speech API is available. No server or model
is started by the Make command. For hosted OpenAI, use
`https://api.openai.com/v1/audio/speech` and an appropriate model, voice, and key.

Dotenv supports `KEY=value`, quoted values, comments, and optional `export`
prefixes. It does not evaluate shell commands or expand variables. Single-quote
JSON values as shown in the example. Keep `.env` out of Git; the generated public
metadata contains article fingerprints and audio URLs, with no credentials.

Long articles are split at paragraph, sentence, or word boundaries to stay within
the configured request length. Valid MP3 chunks are cached and joined with ffmpeg
without re-encoding. The generator validates both chunks and finished files with
ffprobe. If a request fails, rerun the command: completed chunks are reused, and
published files/metadata are updated only after all articles succeed. Requests
are not automatically retried, which avoids duplicate charges after a timeout.

Local caches live in `.cache/article-audio/`. Audio keys include article content,
title, endpoint, model, voice, speed, extra parameters, request length, and
generator code. Changing credentials or timeout does not invalidate narration.
Committed MP3s are reusable on a fresh checkout without the cache. Obsolete
generated MP3s are pruned when the full generation run completes; review their
removal along with additions in Git. Cache files and `.env` remain local, while
`static/audio/*.mp3` and `data/article_audio.json` are committed and deployed.

Narration keeps prose, headings, link labels, inline code, image descriptions, and
captions. It omits code blocks, TeX equations, diagrams, scripts, embedded media
UI, and footnote navigation. Code/equation omissions are announced. Players never
autoplay or preload the audio.

Tests use local HTTP fixtures and short fixture MP3s to check the API contract,
authentication, errors, chunking/resume, caching, and both Hugo build passes. They
do not call a paid API or download speech models.

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

