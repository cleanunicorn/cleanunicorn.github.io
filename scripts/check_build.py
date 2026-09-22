#!/usr/bin/env python3
"""Assert facts about the built site that no template error would catch.

check_positioning.py reads source files; this reads the Hugo output, so it
runs after `hugo`. Each check guards a fix that would otherwise regress
silently, because Hugo builds green either way:

* the home feed lists posts only (#50: layouts/_default/rss.xml)
* no taxonomy pages, no about feed, none in sitemap.xml (#50: disableKinds,
  the about section's outputs)
* cv.css is not published (#61: it lives in scripts/)
* the footer's profile links and the JSON-LD sameAs match data/home.toml, and
  the footer location matches data/cv.toml (#60)

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
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:  # Python < 3.11
    raise SystemExit("check_build: needs Python 3.11+ for tomllib") from exc

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--public", type=Path, help="built site (default: ROOT/public)")
    args = parser.parse_args()
    root = args.root
    public = args.public or root / "public"
    failures = []

    def fail(where: str, why: str) -> None:
        failures.append(f"{where}: {why}")

    if not (public / "index.html").is_file():
        print(f"check_build: no built site at {public} — run hugo first", file=sys.stderr)
        return 1

    # Feeds: the home feed is posts only, and no feed is empty.
    home_feed = public / "index.xml"
    for feed in sorted(public.rglob("index.xml")):
        rel = feed.relative_to(public).as_posix()
        item_links = re.findall(r"<item>.*?<link>([^<]*)</link>", feed.read_text(), re.S)
        if not item_links:
            fail(rel, "feed has no items")
        if feed == home_feed:
            strays = [link for link in item_links if "/posts/" not in link]
            if strays:
                fail(rel, f"non-post items in the home feed: {strays}")
    if not home_feed.is_file():
        fail("index.xml", "home feed missing")

    # No taxonomy pages and no about feed, and the sitemap agrees.
    for rel in ("tags", "categories", "about/index.xml", "css/cv.css"):
        if (public / rel).exists():
            fail(rel, "should not be in the built site")
    sitemap = (public / "sitemap.xml").read_text()
    for kind in ("/tags/", "/categories/"):
        if kind in sitemap:
            fail("sitemap.xml", f"lists {kind}")

    # Profile links and location come from data.
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
        fail("index.html footer", f"profile links {found} != data {want}")
    if f"<span>{location}</span>" not in page:
        fail("index.html footer", f"location {location!r} not rendered")

    same_as = None
    for block in re.findall(r'<script type="?application/ld\+json"?>(.*?)</script>', page, re.S):
        ld = json.loads(block)
        person = ld.get("author") or ld.get("mainEntity") or {}
        same_as = person.get("sameAs", same_as)
    urls = [p["url"] for p in profiles]
    if not same_as or same_as[: len(urls)] != urls:
        fail("index.html JSON-LD", f"sameAs {same_as} does not start with data {urls}")

    for line in failures:
        print(f"check_build: {line}", file=sys.stderr)
    print(f"check_build: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
