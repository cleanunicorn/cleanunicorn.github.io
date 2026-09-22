#!/usr/bin/env python3
"""Assert the built site's search and social metadata is still correct.

check_positioning.py reads the sources; this reads what Hugo rendered, because
the defects it guards against live in templates and config and only show in
the output. It runs after a build: `make build` and the deploy workflow call it
on public/, so a template edit or a theme update cannot quietly bring one back.

What it asserts, per rendered HTML page:

    robots meta       never `noodp`
    og:locale         en_US
    description       present, non-empty, at most 160 characters
    article:*         none on og:type website pages; times are RFC 3339;
                      every post (posts/<slug>/) has article:published_time
    og:image          present, equal to twitter:image, not the bare site root;
                      declared width/height are 1200x630 and match the file
    JSON-LD           no empty "keywords"; a BlogPosting image equals og:image

and for the site: robots.txt has a `Sitemap:` line with the absolute URL of a
sitemap.xml that exists in the build.

Skipped: alias redirect stubs (a meta refresh and nothing else) and files that
are copies of static/ (the presentations are hand-written HTML, not templates).

Standard library only, like check_positioning.py, so the deploy job needs
nothing installed. It imports nothing from this directory.

Usage:
    python3 scripts/check_built_meta.py [PUBLIC_DIR] [--static STATIC_DIR]
"""

import argparse
import json
import re
import struct
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

MAX_DESCRIPTION = 160  # the same limit as check_positioning.py's Rule 9
OG_SIZE = (1200, 630)
OG_SIZE_TEXT = "{}x{}".format(*OG_SIZE)
LOCALE = "en_US"
RFC3339 = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)$")
POST_PAGE = re.compile(r"^posts/(?!page/)[^/]+/index\.html$")
SITEMAP_LINE = re.compile(r"^Sitemap:\s*(\S+)\s*$", re.MULTILINE)


class Head(HTMLParser):
    """The meta tags and JSON-LD blocks of one page. Survives minified HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.refresh = False
        self.jsonld: list[str] = []
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key:
                self.meta.setdefault(key.lower(), []).append(a.get("content", ""))
            if a.get("http-equiv", "").lower() == "refresh":
                self.refresh = True
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_jsonld = True
            self.jsonld.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_jsonld = False

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld[-1] += data

    def one(self, key: str) -> str | None:
        values = self.meta.get(key)
        return values[0] if values else None


def image_size(path: Path) -> tuple[int, int] | None:
    """Pixel size of a PNG, GIF or JPEG file, or None for another format."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return width, height
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def jsonld_objects(documents: list):
    """Every JSON object in the parsed JSON-LD documents, nested ones included."""
    stack = list(documents)
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            yield item
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


def og_image_violations(head, local_file) -> list[str]:
    """What is wrong with the page's og:image and its declared size."""
    og_image = head.one("og:image")
    if not og_image:
        return ["has no og:image"]
    found = []
    if og_image != head.one("twitter:image"):
        found.append(f"twitter:image {head.one('twitter:image')!r} differs from og:image")
    if urlparse(og_image).path in ("", "/"):
        found.append(f"og:image {og_image!r} is the site root, not an image")
    width, height = head.one("og:image:width"), head.one("og:image:height")
    if not (width or height):
        return found
    if (width, height) != tuple(str(n) for n in OG_SIZE):
        return found + [f"og:image is declared {width}x{height}, expected {OG_SIZE_TEXT}"]
    if not local_file:
        return found
    path = local_file(og_image)
    if path is None or not path.is_file():
        return found + [f"og:image {og_image!r} is not in the build"]
    size = image_size(path)
    if size and size != OG_SIZE:
        found.append(f"og:image file is {size[0]}x{size[1]}, declared {OG_SIZE_TEXT}")
    return found


def page_violations(rel: str, html: str, local_file=None) -> list[str]:
    """Every metadata defect in one rendered page.

    Pure apart from `local_file`, which maps an image URL to a file in the
    build (or None when it is not local), so the fixtures below run this exact
    function.
    """
    head = Head()
    head.feed(html)
    if head.refresh and "og:locale" not in head.meta:
        return []  # an alias redirect stub
    found = []
    meta = head.meta

    if any("noodp" in v.lower() for v in meta.get("robots", [])):
        found.append("robots meta says noodp")
    if head.one("og:locale") != LOCALE:
        found.append(f"og:locale is {head.one('og:locale')!r}, expected {LOCALE!r}")

    desc = head.one("description")
    if not desc or not desc.strip():
        found.append("has no meta description")
    elif len(desc) > MAX_DESCRIPTION:
        found.append(f"description is {len(desc)} characters (max {MAX_DESCRIPTION})")

    articles = {k: v for k, v in meta.items() if k.startswith("article:")}
    if head.one("og:type") != "article" and articles:
        found.append(f"og:type {head.one('og:type')!r} page emits {sorted(articles)}")
    for key in ("article:published_time", "article:modified_time"):
        for value in meta.get(key, []):
            if not RFC3339.match(value):
                found.append(f"{key} {value!r} is not RFC 3339")
    if POST_PAGE.match(rel) and "article:published_time" not in meta:
        found.append("post has no article:published_time")

    og_image = head.one("og:image")
    found += og_image_violations(head, local_file)

    documents = []
    for block in head.jsonld:
        try:
            documents.append(json.loads(block))
        except ValueError:
            found.append(f"JSON-LD does not parse: {block[:60]!r}")
    for obj in jsonld_objects(documents):
        if obj.get("keywords") == "":
            found.append(f'JSON-LD {obj.get("@type")} has "keywords":""')
        if obj.get("@type") == "BlogPosting" and og_image and obj.get("image") != og_image:
            found.append(f"BlogPosting image {obj.get('image')!r} differs from og:image")
    return found


def robots_violations(robots: str | None, has_file) -> list[str]:
    """What is wrong with robots.txt; `has_file` says whether a URL is in the build."""
    if robots is None:
        return ["robots.txt: missing"]
    match = SITEMAP_LINE.search(robots)
    if not match:
        return ["robots.txt: no Sitemap: line"]
    url = match.group(1)
    parsed = urlparse(url)
    if not (parsed.scheme and parsed.netloc and parsed.path.endswith("sitemap.xml")):
        return [f"robots.txt: Sitemap {url!r} is not an absolute sitemap.xml URL"]
    if not has_file(url):
        return [f"robots.txt: Sitemap {url!r} is not in the build"]
    return []


# Run on every invocation through the same functions the real pages use, so
# the check cannot rot into a no-op if a rule is loosened.
_GOOD_HEAD = (
    '<meta name=description content="A page.">'
    '<meta property=og:locale content=en_US><meta property=og:type content={type}>'
    '<meta property=og:image content=https://x.test/a.png>'
    '<meta name=twitter:image content=https://x.test/a.png>{extra}'
)
PAGE_FIXTURES = [
    # (name, path, head, the words a violation must contain, or None for none)
    ("a clean list page", "posts/index.html",
     _GOOD_HEAD.format(type="website", extra=""), None),
    ("a clean post", "posts/p/index.html", _GOOD_HEAD.format(type="article", extra=(
        '<meta property=article:published_time content="2024-06-13T14:44:47&#43;01:00">')), None),
    ("noodp", "a/index.html", _GOOD_HEAD.format(
        type="website", extra='<meta name=robots content=noodp>'), "noodp"),
    ("article on a list page", "posts/index.html", _GOOD_HEAD.format(
        type="website", extra='<meta property=article:published_time content=2024-06-13T14:44:47Z>'),
     "emits"),
    ("Go's default time format", "posts/p/index.html", _GOOD_HEAD.format(
        type="article", extra='<meta property=article:published_time content="2024-09-24 14:55:44 +0100 +0100">'),
     "RFC 3339"),
    ("a post with no publish time", "posts/p/index.html",
     _GOOD_HEAD.format(type="article", extra=""), "no article:published_time"),
    ("locale en", "a/index.html",
     _GOOD_HEAD.format(type="website", extra="").replace("en_US", "en"), "og:locale"),
    ("empty description", "a/index.html",
     _GOOD_HEAD.format(type="website", extra="").replace("A page.", ""), "no meta description"),
    ("161-character description", "a/index.html",
     _GOOD_HEAD.format(type="website", extra="").replace("A page.", "x" * 161), "161 characters"),
    ("og:image is the site root", "a/index.html",
     _GOOD_HEAD.format(type="website", extra="").replace("x.test/a.png", "x.test/"), "site root"),
    ("wrong declared size", "a/index.html", _GOOD_HEAD.format(type="website", extra=(
        '<meta property=og:image:width content=800><meta property=og:image:height content=630>')),
     "declared 800x630"),
    ("empty JSON-LD keywords", "a/index.html", _GOOD_HEAD.format(type="website", extra=(
        '<script type="application/ld+json">{"@type":"BlogPosting","image":"https://x.test/a.png",'
        '"keywords":""}</script>')), '"keywords":""'),
    ("JSON-LD image differs", "a/index.html", _GOOD_HEAD.format(type="website", extra=(
        '<script type="application/ld+json">{"@type":"BlogPosting","image":"https://x.test/b.png"}'
        '</script>')), "differs from og:image"),
    ("an alias redirect stub", "posts/page/1/index.html",
     '<meta http-equiv="refresh" content="0; url=/posts/">', None),
]
ROBOTS_FIXTURES = [
    ("User-agent: *\nSitemap: https://x.test/sitemap.xml\n", None),
    ("User-agent: *\n", "no Sitemap"),
    ("Sitemap: /sitemap.xml\n", "not an absolute"),
    (None, "missing"),
]


def fixture_violations() -> list[str]:
    found = []
    for name, rel, head, expected in PAGE_FIXTURES:
        got = page_violations(rel, f"<html><head>{head}</head></html>")
        ok = not got if expected is None else any(expected in v for v in got)
        if not ok:
            found.append(f"self-check: {name}: got {got!r}, expected {expected or 'none'!r}")
    for robots, expected in ROBOTS_FIXTURES:
        got = robots_violations(robots, lambda url: True)
        ok = not got if expected is None else any(expected in v for v in got)
        if not ok:
            found.append(f"self-check: robots {robots!r}: got {got!r}, expected {expected or 'none'!r}")
    return found


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("public", nargs="?", type=Path, default=repo / "public",
                        help="built site to check (default: public/)")
    parser.add_argument("--static", type=Path, default=repo / "static",
                        help="static dir whose copied files are skipped (default: static/)")
    args = parser.parse_args()
    root = args.public
    if not (root / "index.html").is_file():
        print(f"check_built_meta: {root} has no index.html; build the site first", file=sys.stderr)
        return 1

    def local_file(url: str) -> Path | None:
        path = urlparse(url).path.lstrip("/")
        return root / path if path else None

    violations = fixture_violations()
    pages = 0
    for path in sorted(root.rglob("*.html")):
        rel = path.relative_to(root).as_posix()
        if (args.static / rel).is_file():
            continue
        pages += 1
        for problem in page_violations(rel, path.read_text(encoding="utf-8"), local_file):
            violations.append(f"{rel}: {problem}")

    robots = root / "robots.txt"
    violations += robots_violations(
        robots.read_text(encoding="utf-8") if robots.is_file() else None,
        lambda url: bool(local_file(url)) and local_file(url).is_file(),
    )

    if violations:
        print("check_built_meta: the built site's metadata is wrong", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1
    print(f"check_built_meta: {pages} pages, {len(PAGE_FIXTURES) + len(ROBOTS_FIXTURES)} fixtures, 0 violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
