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
* heading links have accessible names, and time elements have machine dates (#51)

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

try:
    import tomllib
except ModuleNotFoundError as exc:  # Python < 3.11
    raise SystemExit("check_build: needs Python 3.11+ for tomllib") from exc


RFC3339 = re.compile(
    r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)
HEADING_LABEL = "Link to this section"


class HtmlSemantics(HTMLParser):
    """Check heading links and time elements, including minified HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.failures: list[str] = []
        self.heading_links = 0

    def handle_starttag(self, tag, attrs):
        self._check_tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._check_tag(tag, attrs)

    def _check_tag(self, tag, attrs):
        attributes = dict(attrs)
        if "arialabel" in attributes:
            self.failures.append("invalid arialabel attribute")

        if tag == "a" and "hanchor" in (attributes.get("class") or "").split():
            self.heading_links += 1
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
    """The home feed is posts only, and no feed is empty."""
    failures = []
    home_feed = public / "index.xml"
    for feed in sorted(public.rglob("index.xml")):
        rel = feed.relative_to(public).as_posix()
        item_links = re.findall(r"<item>.*?<link>([^<]*)</link>", feed.read_text(), re.S)
        if not item_links:
            failures.append(f"{rel}: feed has no items")
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
    )
    for line in failures:
        print(f"check_build: {line}", file=sys.stderr)
    print(f"check_build: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
