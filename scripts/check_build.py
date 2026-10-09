#!/usr/bin/env python3
"""Assert facts about the built site that no template error would catch.

check_positioning.py reads source files; this reads the Hugo output, so it
runs after `hugo`. Each check guards a fix that would otherwise regress
silently, because Hugo builds green either way:

* the home feed lists posts only (#50: layouts/_default/rss.xml)
* no taxonomy pages, no about feed, none in sitemap.xml (#50: disableKinds,
  the about section's outputs)
* the footer and the Posts header link the feed (#50)
* cv.css is not published (#61: it lives in scripts/)
* the footer's profile links, the JSON-LD sameAs and the terminal's
  data-book-url match data/home.toml, and the footer location matches
  data/cv.toml (#60)
* heading links have accessible names, one per heading, and time elements have machine dates (#51)
* feeds carry no heading permalinks (render-heading.rss.xml)
* each math page has one configured KaTeX render pass (#62)
* X embeds carry their tweet text, attribution and a named status link, and
  embed pages load widgets.js once, async (#52)
* primary navigation links and the mobile disclosure's source contract (#45)
* posts link their older/newer published neighbour and end with the closing
  CTA (X, RSS, contact); no other page has either block (#55)
* GA4 consent is denied by default before config and the gtag.js request, and
  every page carries the hidden consent banner and a Cookie settings control (#44)
* every featured project in data/projects.toml is on the homepage band and
  has its own section on /projects/, each linking its repository

It needs a clean build: a stale file from an older build fails it. `make build`
passes hugo --cleanDestinationDir for that; after a bare `hugo`, run
`make clean` first.

Usage:
    python3 scripts/check_build.py [--root PATH] [--public DIR]
"""

import argparse
import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError as exc:  # Python < 3.11
    raise SystemExit("check_build: needs Python 3.11+ for tomllib") from exc


RFC3339 = re.compile(
    r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)
HEADING_LABEL = "Link to this section"
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
X_STATUS_URL = re.compile(r"^https://(?:twitter|x)\.com/[A-Za-z0-9_]{1,15}/status/\d+(?:[?#].*)?$")
X_ATTRIBUTION = re.compile(r"\(@[A-Za-z0-9_]{1,15}\)")
X_WIDGETS = re.compile(r"^(?:https:)?//platform\.twitter\.com/widgets\.js$")


class HtmlSemantics(HTMLParser):
    """Check heading links and time elements, including minified HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.failures: list[str] = []
        self.heading_links = 0
        self.heading = None  # open h1-h6 tag and the permalinks inside it
        self.heading_anchors = 0

    def handle_starttag(self, tag, attrs):
        if tag in HEADINGS:
            self.heading, self.heading_anchors = tag, 0
        self._check_tag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == self.heading:
            if self.heading_anchors > 1:
                self.failures.append(f"{tag} has {self.heading_anchors} heading links")
            self.heading = None

    def handle_startendtag(self, tag, attrs):
        self._check_tag(tag, attrs)

    def _check_tag(self, tag, attrs):
        attributes = dict(attrs)
        if "arialabel" in attributes:
            self.failures.append("invalid arialabel attribute")

        if tag == "a" and "hanchor" in (attributes.get("class") or "").split():
            self.heading_links += 1
            if self.heading:
                self.heading_anchors += 1
            if attributes.get("aria-label") != HEADING_LABEL:
                self.failures.append(f"heading link aria-label must be {HEADING_LABEL!r}")

        if tag == "time":
            value = attributes.get("datetime")
            if not value or not RFC3339.fullmatch(value):
                self.failures.append(f"time datetime is missing or invalid: {value!r}")
            else:
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    self.failures.append(f"time datetime is invalid: {value!r}")


def check_html_semantics(markup: str) -> list[str]:
    """Return semantic failures in one HTML document."""
    checker = HtmlSemantics()
    checker.feed(markup)
    checker.close()
    return checker.failures


class XEmbeds(HTMLParser):
    """Collect each twitter-tweet blockquote and every widgets.js loader."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards: list[dict] = []
        self.loaders: list[bool] = []  # one async flag per widgets.js script
        self.is_post = False
        self._card = None
        self._depth = 0
        self._in_p = False
        self._link = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "article" and "post" in classes:
            self.is_post = True
        if tag == "script" and X_WIDGETS.match(attributes.get("src") or ""):
            self.loaders.append("async" in attributes)
        if self._card is None:
            if tag == "blockquote" and "twitter-tweet" in classes:
                self._card = {"text": "", "attribution": "", "links": []}
                self._depth = 1
            return
        if tag == "blockquote":
            self._depth += 1
        elif tag == "p" and not self._in_p:
            self._in_p = True
        elif tag == "a" and not self._in_p:
            self._link = {"href": attributes.get("href") or "", "text": ""}

    def handle_endtag(self, tag):
        if self._card is None:
            return
        if tag == "p":
            self._in_p = False
        elif tag == "a" and self._link is not None:
            self._card["links"].append(self._link)
            self._link = None
        elif tag == "blockquote":
            self._depth -= 1
            if not self._depth:
                self.cards.append(self._card)
                self._card = None

    def handle_data(self, data):
        if self._card is None:
            return
        if self._in_p:
            self._card["text"] += data
        elif self._link is not None:
            self._link["text"] += data
        else:
            self._card["attribution"] += data


def check_x_embed_markup(markup: str) -> list[str]:
    """Return X embed failures in one HTML document.

    widgets.js may never load (blockers, no JS), so the blockquote itself must
    read as a quote: text, author, and a status link with a visible name.
    """
    parser = XEmbeds()
    parser.feed(markup)
    parser.close()
    failures = []
    for number, card in enumerate(parser.cards, 1):
        if not card["text"].strip():
            failures.append(f"X embed {number} has no tweet text")
        if not X_ATTRIBUTION.search(card["attribution"]):
            failures.append(f"X embed {number} has no (@handle) attribution")
        if not any(X_STATUS_URL.match(link["href"]) and link["text"].strip()
                   for link in card["links"]):
            failures.append(f"X embed {number} has no named link to the tweet")
    if len(parser.loaders) > 1:
        failures.append(f"widgets.js loaded {len(parser.loaders)} times")
    if not all(parser.loaders):
        failures.append("widgets.js loaded without async")
    # Lists with showFullContent may show a card without the page-level loader;
    # the card still reads fine there, so only post pages must load it.
    if parser.cards and parser.is_post and not parser.loaders:
        failures.append("X embed page does not load widgets.js")
    return failures


def check_x_embeds(public: Path) -> list[str]:
    """Check X embeds on every rendered page."""
    failures = []
    for page in sorted(public.rglob("*.html")):
        rel = page.relative_to(public).as_posix()
        failures.extend(f"{rel}: {failure}" for failure in check_x_embed_markup(page.read_text()))
    return failures


GA_ID = "G-42RTQLDG4M"
CONSENT_SIGNALS = ("analytics_storage", "ad_storage", "ad_user_data", "ad_personalization")


class ConsentMarkup(HTMLParser):
    """Collect script order, the consent banner and the reopen control."""

    def __init__(self):
        super().__init__()
        self.events = []  # ("inline", text) / ("loader", src) in document order
        self.ids = set()
        self.banner = None
        self.banner_buttons = 0
        self.opener = False
        self._script = None
        self._in_banner = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag == "script":
            src = attributes.get("src") or ""
            if "googletagmanager.com/gtag/js" in src:
                self.events.append(("loader", src))
            elif not src:
                self._script = []
        elif attributes.get("id") == "consent-banner":
            self.banner = attributes
            self._in_banner = True
        elif tag == "button" and self._in_banner:
            self.banner_buttons += 1
        elif tag == "button" and attributes.get("id") == "consent-open":
            self.opener = True

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.events.append(("inline", "".join(self._script)))
            self._script = None
        elif tag == "section":
            self._in_banner = False

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)


def consent_violations(markup: str) -> list[str]:
    """Return consent failures in one HTML document.

    Hugo builds green whether or not the default-denied call precedes the
    config call and the gtag.js request, so the order is asserted here.
    """
    parser = ConsentMarkup()
    parser.feed(markup)
    parser.close()
    failures = []
    default = config = loader = None  # (script position, offset) in document order
    for position, (kind, text) in enumerate(parser.events):
        if kind == "loader" and loader is None:
            loader = (position, 0)
        elif kind == "inline":
            found = re.search(r"gtag\(\s*['\"]consent['\"]\s*,\s*['\"]default['\"]", text)
            if found and default is None:
                default = (position, found.start())
            found = re.search(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]" + GA_ID, text)
            if found and config is None:
                config = (position, found.start())
    configs = sum(len(re.findall(r"gtag\(\s*['\"]config['\"]", text))
                  for kind, text in parser.events if kind == "inline")
    if configs != 1:
        failures.append(f"expected exactly one gtag config, found {configs}")
    if default is None:
        failures.append("no gtag consent default")
    else:
        call = re.search(r"\{(.*?)\}", parser.events[default[0]][1][default[1]:], re.S)
        text = call.group(1) if call else ""
        for signal in CONSENT_SIGNALS:
            if not re.search(signal + r"\s*:\s*['\"]denied['\"]", text):
                failures.append(f"consent default does not deny {signal}")
        if re.search(r"['\"]granted['\"]", text):
            failures.append("consent default grants a signal")
        if config is not None and default > config:
            failures.append("gtag config runs before the consent default")
        if loader is not None and default > loader:
            failures.append("gtag.js is requested before the consent default")
    if loader is None:
        failures.append("gtag.js loader missing")
    if parser.banner is None:
        failures.append("no #consent-banner")
    else:
        if "hidden" not in parser.banner:
            failures.append("consent banner is not hidden by default")
        if parser.banner.get("aria-labelledby") not in parser.ids:
            failures.append("consent banner aria-labelledby does not name an element")
        if parser.banner_buttons != 2:
            failures.append(f"consent banner has {parser.banner_buttons} buttons, expected 2")
    if not parser.opener:
        failures.append("no Cookie settings button")
    return failures


def check_consent(public: Path) -> list[str]:
    """Check analytics consent on every rendered page."""
    failures = []
    for page in sorted(public.rglob("*.html")):
        markup = page.read_text()
        if re.search(r"http-equiv=[\"']?refresh", markup):
            continue  # Hugo's redirect stubs render no page
        rel = page.relative_to(public).as_posix()
        failures.extend(f"{rel}: {failure}" for failure in consent_violations(markup))
    return failures


def check_html_pages(public: Path) -> list[str]:
    """Check every rendered page and require at least one heading link."""
    failures = []
    heading_links = 0
    for page in sorted(public.rglob("*.html")):
        checker = HtmlSemantics()
        checker.feed(page.read_text())
        checker.close()
        heading_links += checker.heading_links
        rel = page.relative_to(public).as_posix()
        failures.extend(f"{rel}: {failure}" for failure in checker.failures)
    if not heading_links:
        failures.append("no .hanchor heading links in built HTML")
    return failures


def check_feeds(public: Path) -> list[str]:
    """The home feed is posts only, no feed is empty, and none has heading links."""
    failures = []
    home_feed = public / "index.xml"
    for feed in sorted(public.rglob("index.xml")):
        rel = feed.relative_to(public).as_posix()
        text = feed.read_text()
        item_links = re.findall(r"<item>.*?<link>([^<]*)</link>", text, re.S)
        if not item_links:
            failures.append(f"{rel}: feed has no items")
        if "hanchor" in text:
            failures.append(f"{rel}: heading permalinks leaked into the feed")
        if feed == home_feed:
            strays = [link for link in item_links if "/posts/" not in link]
            if strays:
                failures.append(f"{rel}: non-post items in the home feed: {strays}")
    if not home_feed.is_file():
        failures.append("index.xml: home feed missing")
    return failures


def check_removed_outputs(public: Path) -> list[str]:
    """No taxonomy pages, no about feed, no cv.css, and the sitemap agrees."""
    failures = []
    for rel in ("tags", "categories", "about/index.xml", "css/cv.css"):
        if (public / rel).exists():
            failures.append(f"{rel}: should not be in the built site")
    sitemap = (public / "sitemap.xml").read_text()
    for kind in ("/tags/", "/categories/"):
        if kind in sitemap:
            failures.append(f"sitemap.xml: lists {kind}")
    return failures


def check_feed_links(public: Path) -> list[str]:
    """The home feed is linked from the footer and the Posts header."""
    failures = []
    # Patterns allow unquoted attributes: CI builds with --minify.
    feed_link = r'<a href="?[^"\s>]*/index\.xml"? type="?application/rss\+xml"?>'
    page = (public / "index.html").read_text()
    footer = page[page.find("connect-footer__links"):]
    if not re.search(feed_link + "RSS</a>", footer):
        failures.append("index.html footer: no RSS feed link")
    posts = (public / "posts" / "index.html").read_text()
    if not re.search(r'class="?page-feed"?>' + feed_link, posts):
        failures.append("posts/index.html: no page-feed RSS link in the header")
    return failures


def check_profile_data(root: Path, public: Path) -> list[str]:
    """Footer links, footer location, JSON-LD sameAs and the terminal's booking
    URL come from data."""
    failures = []
    home = tomllib.loads((root / "data" / "home.toml").read_text())
    by_net = {link["net"]: link for link in home["connect"]["links"]}
    profiles = [by_net[net] for net in home["connect"]["profiles"]]
    location = tomllib.loads((root / "data" / "cv.toml").read_text())["location"]
    page = (public / "index.html").read_text()

    # Patterns allow unquoted attributes: CI builds with --minify.
    footer = page[page.find("connect-footer__links"):]
    found = re.findall(r'<a href="?([^"\s>]+)"? target="?_blank"? rel="me noopener">([^<]*)</a>', footer)
    want = [(p["url"], p["label"]) for p in profiles]
    if found != want:
        failures.append(f"index.html footer: profile links {found} != data {want}")
    if f"<span>{location}</span>" not in page:
        failures.append(f"index.html footer: location {location!r} not rendered")

    same_as = None
    for block in re.findall(r'<script type="?application/ld\+json"?>(.*?)</script>', page, re.S):
        ld = json.loads(block)
        person = ld.get("author") or ld.get("mainEntity") or {}
        same_as = person.get("sameAs", same_as)
    urls = [p["url"] for p in profiles]
    if not same_as or same_as[: len(urls)] != urls:
        failures.append(f"index.html JSON-LD: sameAs {same_as} does not start with data {urls}")

    book_url = by_net["calendar"]["url"]
    if not re.search(r'class="?poster__eyebrow"? data-book-url="?' + re.escape(book_url) + r'[">\s]', page):
        failures.append(f"index.html: poster__eyebrow has no data-book-url={book_url!r}")
    return failures


def check_featured_projects(root: Path, public: Path) -> list[str]:
    """The homepage band and /projects/ both render every featured project.

    Both pages read data/projects.toml, so a typo in a slug or a template that
    silently drops an entry builds green. Pin each project to the markup that
    carries it: the card id on the homepage, the section id on /projects/, and
    on each a link to its repository.
    """
    failures = []
    projects = tomllib.loads((root / "data" / "projects.toml").read_text())["featured"]
    home = (public / "index.html").read_text()
    page_path = public / "projects" / "index.html"
    if not page_path.is_file():
        return ["projects/index.html: missing — content/projects.md should render it"]
    page = page_path.read_text()
    for project in projects:
        slug, repo = project["slug"], project["repo"]
        failures += featured_project_violations(slug, repo, home, page)
    return failures


def featured_project_violations(slug: str, repo: str, home: str, page: str) -> list[str]:
    """Where one featured project is missing from the two pages that show it."""
    found = []
    card = element_with_id(home, f"featured-{slug}", "article")
    if card is None:
        found.append(f"index.html: no featured card for {slug!r}")
    elif f'href="{repo}"' not in card and f"href={repo}" not in card:
        found.append(f"index.html: featured card for {slug!r} does not link {repo}")
    section = element_with_id(page, slug, "section")
    if section is None:
        found.append(f"projects/index.html: no section #{slug}")
    elif f'href="{repo}"' not in section and f"href={repo}" not in section:
        found.append(f"projects/index.html: section #{slug} does not link {repo}")
    return found


def element_with_id(markup: str, element_id: str, tag: str) -> str | None:
    """The markup from `id=<element_id>` to the next closing `tag`, or None.

    Scoped on purpose: a repo URL elsewhere on the page — Quill's install
    block clones its own repository — must not count as the card's link.
    Patterns allow unquoted attributes: CI builds with --minify.
    """
    match = re.search(r'id="?' + re.escape(element_id) + r'[">\s]', markup)
    if not match:
        return None
    end = markup.find(f"</{tag}>", match.start())
    return markup[match.start():end if end != -1 else None]


def check_math_rendering(public: Path) -> list[str]:
    """Math pages have exactly one render pass with the expected options."""
    failures = []
    math_pages = []
    delimiters = (
        ("$$", "$$", "true"),
        ("$", "$", "false"),
        (r"\\[", r"\\]", "true"),
        (r"\\(", r"\\)", "false"),
    )
    boolean = {"true": r"(?:true|!0)", "false": r"(?:false|!1)"}
    for path in sorted(public.rglob("*.html")):
        page = path.read_text()
        if not re.search(r'<meta\s+name="?math-enabled"?\s+content="?true"?>', page):
            continue
        math_pages.append(path)
        rel = path.relative_to(public).as_posix()
        if "contrib/auto-render.min.js" not in page:
            failures.append(f"{rel}: missing KaTeX auto-render loader")
        calls = re.findall(r"renderMathInElement\s*\(", page)
        if len(calls) != 1:
            failures.append(f"{rel}: expected one KaTeX render call, found {len(calls)}")
        render_call = re.search(
            r"renderMathInElement\s*\(\s*document\.body\s*,\s*\{.*?\}\s*\)", page, re.S
        )
        if not render_call:
            failures.append(f"{rel}: missing configured body render call")
            continue
        options = render_call.group()
        for left, right, display in delimiters:
            pattern = (r"\{\s*left:\s*['\"]" + re.escape(left) + r"['\"]\s*,\s*right:\s*['\"]"
                       + re.escape(right) + r"['\"]\s*,\s*display:\s*" + boolean[display] + r"\s*\}")
            if not re.search(pattern, options):
                failures.append(f"{rel}: missing KaTeX delimiter {left!r}/{right!r}")
        if not re.search(r"throwOnError\s*:\s*(?:false|!1)(?=\s*[,}])", options):
            failures.append(f"{rel}: missing KaTeX throwOnError: false")
    if not math_pages:
        failures.append("no math-enabled page marker in built site")
    return failures


class NavParser(HTMLParser):
    """Collect navigation semantics without depending on HTML minifier quoting."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.navs = []
        self.current_nav = None
        self.lists = []
        self.anchor = None
        self.bad_trigger = False
        self.refresh = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "meta" and (attributes.get("http-equiv") or "").lower() == "refresh":
            self.refresh = True
        if tag == "li" and "menu__trigger" in classes:
            self.bad_trigger = True
        if tag == "nav":
            self.current_nav = {"classes": classes, "buttons": [], "lists": [], "links": []}
            self.navs.append(self.current_nav)
        if self.current_nav is None:
            return
        if tag == "button":
            self.current_nav["buttons"].append(attributes)
        elif tag == "ul":
            item = {"attrs": attributes, "links": []}
            self.current_nav["lists"].append(item)
            self.lists.append(item)
        elif tag == "a":
            self.anchor = {"href": attributes.get("href"), "text": ""}

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None and self.current_nav is not None:
            link = (self.anchor["href"], self.anchor["text"].strip())
            self.current_nav["links"].append(link)
            if self.lists:
                self.lists[-1]["links"].append(link)
            self.anchor = None
        elif tag == "ul" and self.lists:
            self.lists.pop()
        elif tag == "nav":
            self.current_nav = None
            self.lists.clear()


def check_nav(root: Path, public: Path) -> list[str]:
    """Every rendered page has configured links and a safe mobile fallback."""
    menu = tomllib.loads((root / "hugo.toml").read_text())["languages"]["en"]["menu"]["main"]
    expected = [(item["url"], item["name"]) for item in sorted(menu, key=lambda item: item["weight"])]
    failures = []
    for path in sorted(public.rglob("*.html")):
        rel = path.relative_to(public)
        if (root / "static" / rel).is_file():
            continue  # Hugo copies static HTML (for example, the generated CV) unchanged.
        parser = NavParser()
        parser.feed(path.read_text())
        if parser.refresh:
            continue
        mobile = [nav for nav in parser.navs if "navigation-menu--mobile" in nav["classes"]]
        desktop = [nav for nav in parser.navs if "navigation-menu" in nav["classes"] and "navigation-menu--mobile" not in nav["classes"]]
        if len(mobile) != 1 or len(desktop) != 1:
            failures.append(f"{rel}: expected one mobile and one desktop primary nav, got {len(mobile)} and {len(desktop)}")
            continue
        if parser.bad_trigger:
            failures.append(f"{rel}: unfocusable li.menu__trigger remains")
        if desktop[0]["links"] != expected:
            failures.append(f"{rel}: desktop links {desktop[0]['links']} != {expected}")
        if mobile[0]["links"] != expected:
            failures.append(f"{rel}: mobile links {mobile[0]['links']} != {expected}")
        buttons = mobile[0]["buttons"]
        if len(buttons) != 1:
            failures.append(f"{rel}: expected one mobile menu button, got {len(buttons)}")
            continue
        button = buttons[0]
        targets = [lst for lst in mobile[0]["lists"] if lst["attrs"].get("id") == button.get("aria-controls")]
        if button.get("type") != "button" or button.get("aria-expanded") != "true" or "hidden" not in button:
            failures.append(f"{rel}: mobile button must start hidden with type=button and aria-expanded=true")
        if not button.get("aria-controls") or len(targets) != 1 or "hidden" in targets[0]["attrs"] or targets[0]["links"] != expected:
            failures.append(f"{rel}: mobile button must control one initially visible full link list")
    return failures


class PostEndParser(HTMLParser):
    """Collect a page's post date and its post-nav / post-cta blocks.

    Link text skips aria-hidden glyphs, so it is the text a screen reader reads."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refresh = False
        self.article = False
        self.date = None
        self.ids = set()
        self.navs = []
        self.ctas = []
        self.markers = 0
        self.block = None
        self.anchor = None
        self.hidden = []  # open tags inside a link that are aria-hidden

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if self.anchor is not None and (self.hidden or attributes.get("aria-hidden") == "true"):
            self.hidden.append(tag)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag == "meta" and (attributes.get("http-equiv") or "").lower() == "refresh":
            self.refresh = True
        if tag == "article" and "post--article" in classes:
            self.article = True
        if tag == "time" and "post-date" in classes and self.date is None:
            self.date = attributes.get("datetime")
        if classes & {"post-nav", "post-cta"}:
            self.markers += 1
        if tag == "nav" and "post-nav" in classes:
            self.block = {"tag": tag, "label": attributes.get("aria-labelledby"), "links": []}
            self.navs.append(self.block)
        elif tag == "aside" and "post-cta" in classes:
            self.block = {"tag": tag, "label": attributes.get("aria-labelledby"), "links": []}
            self.ctas.append(self.block)
        elif tag == "a" and self.block is not None:
            self.anchor = {key: attributes.get(key) for key in ("href", "type", "data-direction")}
            self.anchor["text"] = ""

    def handle_data(self, data):
        if self.anchor is not None and not self.hidden:
            self.anchor["text"] += data

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()
        elif tag == "a" and self.anchor is not None:
            self.anchor["text"] = " ".join(self.anchor["text"].split())
            self.block["links"].append(self.anchor)
            self.anchor = None
        elif self.block is not None and tag == self.block["tag"]:
            self.block = None


def check_post_navigation(root: Path, public: Path) -> list[str]:
    """Posts link their older/newer neighbour and end with the CTA; no other page does (#55)."""
    home = tomllib.loads((root / "data" / "home.toml").read_text())
    x_url = next(link["url"] for link in home["connect"]["links"] if link["net"] == "x")
    host = urlparse(tomllib.loads((root / "hugo.toml").read_text())["baseURL"]).netloc
    failures = []
    posts = {}
    for path in sorted(public.rglob("*.html")):
        rel = path.relative_to(public)
        if (root / "static" / rel).is_file():
            continue  # Hugo copies static HTML unchanged.
        parser = PostEndParser()
        parser.feed(path.read_text())
        parser.close()
        if parser.refresh:
            continue
        is_post = len(rel.parts) == 3 and rel.parts[0] == "posts" and rel.parts[1] != "page" and rel.name == "index.html"
        if not is_post:
            if parser.markers:
                failures.append(f"{rel}: post-nav/post-cta outside a post")
            continue
        if not parser.article:
            failures.append(f"{rel}: no article.post--article")
        try:
            date = datetime.fromisoformat((parser.date or "").replace("Z", "+00:00"))
        except ValueError:
            failures.append(f"{rel}: post date missing or invalid: {parser.date!r}")
            continue
        posts[f"/{rel.parent.as_posix()}/"] = (date, rel, parser)

    if len(posts) < 2:
        failures.append(f"expected at least 2 post pages under posts/, found {len(posts)}")

    def internal(href):
        url = urlparse(href or "")
        return url.netloc in ("", host), url.path

    def resolves(path):
        target = public / path.lstrip("/")
        return (target / "index.html").is_file() if path.endswith("/") else target.is_file()

    order = sorted(posts, key=lambda key: (posts[key][0], key))
    for i, key in enumerate(order):
        _, rel, parser = posts[key]
        want = {}
        if i > 0:
            want["older"] = order[i - 1]
        if i < len(order) - 1:
            want["newer"] = order[i + 1]
        if len(parser.navs) != (1 if want else 0):
            failures.append(f"{rel}: expected {1 if want else 0} nav.post-nav, got {len(parser.navs)}")
        got = {}
        for nav in parser.navs:
            if not nav["label"] or nav["label"] not in parser.ids:
                failures.append(f"{rel}: nav.post-nav needs aria-labelledby pointing at a heading")
            for link in nav["links"]:
                direction = link["data-direction"]
                label = {"older": "Older post", "newer": "Newer post"}.get(direction)
                if direction in got or label is None:
                    failures.append(f"{rel}: unexpected or duplicate post-nav link {link}")
                    continue
                got[direction] = internal(link["href"])[1]
                if not link["text"].startswith(label) or link["text"] == label:
                    failures.append(f"{rel}: {direction} link text {link['text']!r} needs {label!r} and a title")
        if got != want:
            failures.append(f"{rel}: post-nav links {got} != chronological neighbours {want}")

        if len(parser.ctas) != 1:
            failures.append(f"{rel}: expected one aside.post-cta, got {len(parser.ctas)}")
            continue
        cta = parser.ctas[0]
        if not cta["label"] or cta["label"] not in parser.ids:
            failures.append(f"{rel}: aside.post-cta needs aria-labelledby pointing at a heading")
        links = cta["links"]
        checks = {
            "X": any(link["href"] == x_url for link in links),
            "RSS": any(internal(link["href"]) == (True, "/index.xml") and link["type"] == "application/rss+xml" for link in links),
            "contact": any(internal(link["href"]) == (True, "/contact/") for link in links),
        }
        failures.extend(f"{rel}: post-cta has no {name} link" for name, ok in checks.items() if not ok)
        for link in [link for nav in parser.navs for link in nav["links"]] + links:
            local, path = internal(link["href"])
            if not link["text"]:
                failures.append(f"{rel}: post end link {link['href']!r} has no text")
            if local and not resolves(path):
                failures.append(f"{rel}: post end link {link['href']!r} does not resolve in the build")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--public", type=Path, help="built site (default: ROOT/public)")
    args = parser.parse_args()
    public = args.public or args.root / "public"

    if not (public / "index.html").is_file():
        print(f"check_build: no built site at {public} — run hugo first", file=sys.stderr)
        return 1

    failures = (
        check_feeds(public)
        + check_feed_links(public)
        + check_removed_outputs(public)
        + check_profile_data(args.root, public)
        + check_html_pages(public)
        + check_x_embeds(public)
        + check_consent(public)
        + check_math_rendering(public)
        + check_nav(args.root, public)
        + check_post_navigation(args.root, public)
        + check_featured_projects(args.root, public)
    )
    for line in failures:
        print(f"check_build: {line}", file=sys.stderr)
    print(f"check_build: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
