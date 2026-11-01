#!/usr/bin/env python3
"""Update the Books list on the About page from a Goodreads shelf.

Goodreads retired its public API in 2020, but per-shelf RSS feeds still work:

    https://www.goodreads.com/review/list_rss/<USER_ID>?shelf=<SHELF>

This script builds a pool from the books already curated on the About page
plus a Goodreads shelf, ranks them by your star rating and then the Goodreads
community average (popularity), and keeps the top N (default 10). Books on the
page that also appear on Goodreads pick up their ratings, so they rank fairly;
the list is rewritten in place between the markers:

    <!-- BOOKS:START ... -->
    ...
    <!-- BOOKS:END -->

Run it only when you want to refresh the list:

    make books                                  # top 10 by rating, then popularity
    python3 scripts/update_books.py --top 12
    python3 scripts/update_books.py --from-file feed.xml   # offline / behind an allowlist
    python3 scripts/update_books.py --dry-run              # preview, write nothing

No third-party dependencies — Python 3 standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ABOUT_MD = ROOT / "content" / "about" / "_index.md"

DEFAULT_USER_ID = "24370112"  # https://www.goodreads.com/user/show/24370112-daniel-luca
DEFAULT_SHELF = "read"
DEFAULT_TOP = 10
DEFAULT_MIN_RATING = 0  # 0 = no floor; rank everything and take the top N
MAX_PAGES = 10

START_RE = re.compile(r"<!--\s*BOOKS:START.*?-->", re.IGNORECASE | re.DOTALL)
END_RE = re.compile(r"<!--\s*BOOKS:END\s*-->", re.IGNORECASE)

USER_AGENT = "Mozilla/5.0 (compatible; cleanunicorn-cv/1.0; +https://cleanunicorn.github.io)"


# ---------------------------------------------------------------------------
# Book model
# ---------------------------------------------------------------------------

class Book:
    """A ranked book entry: title, author, your rating, community average and a
    read/added timestamp used for de-duplication and tie-breaking."""

    __slots__ = ("title", "author", "rating", "average", "when")

    def __init__(self, title: str, author: str = "", rating: int = 0,
                 average: float = 0.0, when: float = 0.0):
        self.title = title
        self.author = author
        self.rating = rating      # your own rating, 1–5 (0 if unknown)
        self.average = average    # Goodreads community average (popularity proxy)
        self.when = when          # read/added timestamp, for tie-breaking

    @property
    def key(self) -> str:
        """Normalised title used for de-duplication."""
        return normalise_title(self.title)

    @property
    def sort_key(self) -> tuple:
        # rating first (your favourites), then popularity, then most recent
        return (-self.rating, -self.average, -self.when)

    def to_markdown(self) -> str:
        if self.author:
            return f"* **{self.title}** by {self.author}"
        return f"* **{self.title}**"


def normalise_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\s*\([^)]*\)", "", t)        # drop "(Series, #1)" etc.
    t = re.sub(r"\s*:.*$", "", t)             # drop subtitle after a colon
    t = re.sub(r"\s+[-–—]\s+.*$", "", t)      # drop subtitle after " - " (keeps hyphenated words)
    t = re.sub(r"[^a-z0-9]+", " ", t)         # collapse punctuation
    return t.strip()


def clean_title(title: str) -> str:
    """Tidy a Goodreads title for display: drop the series parenthetical."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def parse_date(value: str) -> float:
    """RFC-822 date string -> POSIX timestamp (0.0 if unparseable)."""
    value = value.strip()
    if not value:
        return 0.0
    try:
        return parsedate_to_datetime(value).timestamp()
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Goodreads RSS
# ---------------------------------------------------------------------------

def feed_url(user_id: str, shelf: str, page: int) -> str:
    return (
        f"https://www.goodreads.com/review/list_rss/{user_id}"
        f"?shelf={shelf}&sort=rating&order=d&page={page}"
    )


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_feed(xml_bytes: bytes) -> list[Book]:
    """Parse a Goodreads list_rss payload into Book objects."""
    root = ET.fromstring(xml_bytes)
    books: list[Book] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        try:
            rating = int((item.findtext("user_rating") or "0").strip())
        except ValueError:
            rating = 0
        try:
            average = float((item.findtext("average_rating") or "0").strip())
        except ValueError:
            average = 0.0
        when = parse_date(item.findtext("user_read_at") or item.findtext("user_date_added") or "")
        books.append(
            Book(
                title=clean_title(title),
                author=(item.findtext("author_name") or "").strip(),
                rating=rating,
                average=average,
                when=when,
            )
        )
    return books


def goodreads_books(user_id: str, shelf: str) -> list[Book]:
    collected: list[Book] = []
    for page in range(1, MAX_PAGES + 1):
        url = feed_url(user_id, shelf, page)
        try:
            payload = fetch(url)
        except urllib.error.HTTPError as exc:
            raise SystemExit(
                f"Goodreads returned HTTP {exc.code} for {url}\n"
                "The shelf must be public. If you are behind a network allowlist, "
                "save the feed locally and pass --from-file."
            )
        except urllib.error.URLError as exc:
            raise SystemExit(f"Could not reach Goodreads: {exc.reason}")
        page_books = parse_feed(payload)
        if not page_books:
            break
        collected.extend(page_books)
        if len(page_books) < 50:  # last page
            break
    return collected


# ---------------------------------------------------------------------------
# About page I/O
# ---------------------------------------------------------------------------

def split_markers(text: str) -> tuple[str, str, str]:
    """Return (before, inner, after) around the BOOKS markers."""
    s = START_RE.search(text)
    e = END_RE.search(text, s.end()) if s else None
    if not s or not e:
        raise SystemExit(
            "Could not find the <!-- BOOKS:START --> / <!-- BOOKS:END --> markers "
            f"in {ABOUT_MD.relative_to(ROOT)}. Add them around the Books list first."
        )
    return text[: s.end()], text[s.end() : e.start()], text[e.start() :]


def parse_existing(inner: str) -> list[Book]:
    """Read the books already listed between the markers."""
    books: list[Book] = []
    for line in inner.splitlines():
        m = re.match(r"\s*[-*]\s+\*\*(.+?)\*\*\s*,?\s*(?:by\s+(.*))?$", line.strip())
        if m:
            books.append(Book(title=m.group(1).strip(),
                              author=(m.group(2) or "").strip().rstrip(".")))
    return books


def select_top(existing: list[Book], incoming: list[Book], top: int,
               replace: bool) -> list[Book]:
    """Merge existing + Goodreads (Goodreads wins on matches), rank, take top N."""
    pool: dict[str, Book] = {}
    if not replace:
        for b in existing:
            pool[b.key] = b
    for b in incoming:
        prev = pool.get(b.key)
        if prev is not None and not b.author:
            b.author = prev.author  # keep a nicer hand-written author if GR lacks one
        pool[b.key] = b  # Goodreads carries the rating/popularity signal
    ranked = sorted(pool.values(), key=lambda b: (b.sort_key, b.title.lower()))
    return ranked[:top] if top > 0 else ranked


def render_block(books: list[Book]) -> str:
    lines = "\n".join(b.to_markdown() for b in books)
    return f"\n\n{lines}\n\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help=f"Goodreads numeric user id (default: {DEFAULT_USER_ID})")
    parser.add_argument("--shelf", default=DEFAULT_SHELF, help=f"Shelf to pull (default: {DEFAULT_SHELF})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help=f"How many books to keep, by rating then popularity (default: {DEFAULT_TOP}; 0 = all)")
    parser.add_argument("--min-rating", type=int, default=DEFAULT_MIN_RATING, help="Drop books rated below this before ranking (default: 0 = no floor)")
    parser.add_argument("--from-file", type=Path, help="Read the RSS from a local file instead of fetching (offline mode)")
    parser.add_argument("--about", type=Path, default=ABOUT_MD, help="Path to the About page markdown")
    parser.add_argument("--replace", action="store_true", help="Ignore the existing list; rank Goodreads books only")
    parser.add_argument("--dry-run", action="store_true", help="Print the result; do not write the file")
    args = parser.parse_args()

    about_path: Path = args.about
    text = about_path.read_text()
    before, inner, after = split_markers(text)
    existing = parse_existing(inner)

    if args.from_file:
        incoming = parse_feed(args.from_file.read_bytes())
    else:
        incoming = goodreads_books(args.user_id, args.shelf)

    if args.min_rating > 0:
        incoming = [b for b in incoming if b.rating >= args.min_rating]

    if not incoming and not existing:
        raise SystemExit("No books found from Goodreads and none existing — nothing to write.")

    selected = select_top(existing, incoming, args.top, args.replace)

    block = render_block(selected)
    new_text = before + block + after

    print(
        f"existing: {len(existing)} | from Goodreads: {len(incoming)} "
        f"| kept top {args.top}: {len(selected)}",
        file=sys.stderr,
    )

    if args.dry_run:
        sys.stdout.write(block)
        return

    if new_text != text:
        about_path.write_text(new_text)
        rel = about_path.relative_to(ROOT) if about_path.is_relative_to(ROOT) else about_path
        print(f"Updated {rel}", file=sys.stderr)
    else:
        print("No changes.", file=sys.stderr)


if __name__ == "__main__":
    main()
