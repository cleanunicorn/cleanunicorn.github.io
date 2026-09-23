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
* primary navigation links and the mobile disclosure's source contract (#45)

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
from html.parser import HTMLParser
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:  # Python < 3.11
    raise SystemExit("check_build: needs Python 3.11+ for tomllib") from exc


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
        + check_nav(args.root, public)
    )
    for line in failures:
        print(f"check_build: {line}", file=sys.stderr)
    print(f"check_build: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
