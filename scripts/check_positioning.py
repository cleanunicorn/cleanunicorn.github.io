#!/usr/bin/env python3
"""Assert the site's identity copy still leads with what he builds.

This repository has no test suite; this is its one assertion-running check and
the regression net behind the builder-first positioning. It fails when a
protected field starts describing him as a partner or an investor before it
describes him as someone who builds things, and when static/llms.txt — the
file agents read — drifts away from the pages it restates.

Two deliberate choices, both load-bearing:

* It imports nothing from this directory. An import would write
  `scripts/__pycache__/*.pyc` into a tree whose .gitignore does not cover it,
  and this check has to keep working when the CV generator is broken.
* It reads TOML values with `tomllib`, so every form the format allows — a
  single-quoted value, a triple-quoted block, a value spread over lines — is
  read the way Hugo and the CV generator will read it. Line regexes were tried
  first and failed open two ways: a single-quoted value dropped out of the
  checked set entirely, and a triple-quoted block matched with the middle
  quote as its value.
* Rule 3 is the exception and stays a raw-line count, because it exists to
  mirror `generate_cv.py:171-175`, which scans lines rather than parsing.

Usage:
    python3 scripts/check_positioning.py [--root PATH]

`--root` points the check at a copy of the repository, so a regression can be
demonstrated without writing to the working tree.
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:  # Python < 3.11
    raise SystemExit(
        "check_positioning: needs Python 3.11+ for tomllib — refusing to run "
        "rather than pass on values it cannot read"
    ) from exc

# A field may mention these; it may not open on one. Add a term here and the
# whole check picks it up.
FORBIDDEN = ("technical partner", "investor")

# Markdown and quoting a value may legitimately start with, stripped before
# the opening word is read.
LEADING_MARKUP = re.compile(r"""^[\s>*_#\-\["'(]+""")

SUBTITLE_LINE = re.compile(r"^\s*subtitle\s*=", re.MULTILINE)
HUMANS_ROLE = re.compile(r"^\s*Role:\s*(.+?)\s*$", re.MULTILINE)
# `(?!")` rejects a triple-quote opener instead of capturing the middle
# quote as the value, and the body cannot span lines — either way the value
# goes missing and the presence rule fires, which is what this file promises.
OG_SUB_TEXT = re.compile(r'^\s*sub_text\s*=\s*"(?!")((?:[^"\\\n]|\\.)*)"\s*$', re.MULTILINE)
LLMS_SUMMARY = re.compile(r"^>\s*(.+?)\s*$", re.MULTILINE)
FRONT_MATTER = re.compile(r"\A\+\+\+\s*\n(.*?)\n\+\+\+\s*\n", re.DOTALL)

# Which TOML file holds which protected values.
CONFIG_FIELDS = (
    ("data/home.toml", ("whoami",)),
    ("hugo.toml", ("subtitle", "jobTitle", "personDescription")),
)
REGEX_METACHARACTERS = set(r".^$*+?()[]{}|\\")

# Rule 7 — run on every invocation, through the same predicate the real fields
# use, so the check cannot rot into a no-op if the rule is ever loosened.
FIXTURES = [
    ("Technical Partner @ Eden Block", "technical partner"),
    ("Investor and builder", "investor"),
    ("builder · hacker · Technical Partner @ Eden Block", None),
    ("Investors are the audience", None),
    ("**Technical Partner** at Eden Block", "technical partner"),
]

# Rule 7, second half — the TOML shapes a line regex used to miss. Each source
# must still yield the value that Rule 1 then tests.
TOML_FIXTURES = [
    # (name, a TOML document, the value the reader must return for key "x")
    ("single-quoted", "x = 'Investor and builder'", "Investor and builder"),
    # TOML trims the newline that follows the opening delimiter.
    ("triple-quoted", 'x = """\nInvestor | Builder\n"""', "Investor | Builder\n"),
    ("nested table", '[a.b]\nx = "builder"', "builder"),
]


# Rule 6 — static/llms.txt restates facts that live on the pages. Each row is
# a token that must still be in both files: rename a project, drop a role or
# change a start date on the Work page and the check fails naming the token,
# instead of leaving an agent-facing file quietly claiming something the site
# no longer says.
MIRRORED = [
    ("Earheart", "content/about/_index.md"),
    ("Agents Library", "content/about/_index.md"),
    ("drove", "content/about/_index.md"),
    ("Karl", "content/about/_index.md"),
    ("RL-Swarm", "content/about/_index.md"),
    ("Eden Block", "content/previous-work.md"),
    ("FiatDAO", "content/previous-work.md"),
    ("Akira Tech", "content/previous-work.md"),
    ("ConsenSys Diligence", "content/previous-work.md"),
    ("Alethio", "content/previous-work.md"),
    ("August 2026", "content/previous-work.md"),
    ("November 2022", "content/previous-work.md"),
    ("November 2021", "content/previous-work.md"),
    ("October 2020", "content/previous-work.md"),
    ("November 2018", "content/previous-work.md"),
    ("February 2017", "content/previous-work.md"),
]


def opens_on_forbidden(value: str):
    """The forbidden term a value opens on, or None."""
    stripped = LEADING_MARKUP.sub("", value).lower()
    for term in FORBIDDEN:
        if re.match(re.escape(term) + r"\b", stripped):
            return term
    return None


def toml_strings(data, key: str) -> list:
    """Every string stored under `key`, at any depth in a parsed TOML value."""
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key and isinstance(v, str):
                found.append(v)
            else:
                found.extend(toml_strings(v, key))
    elif isinstance(data, list):
        for item in data:
            found.extend(toml_strings(item, key))
    return found


class Check:
    def __init__(self, root: Path):
        self.root = root
        self.violations: list[str] = []
        self.fields = 0

    def fail(self, where: str, problem: str) -> None:
        self.violations.append(f"{where}: {problem}")

    def read(self, rel: str) -> str:
        """File contents, or "" with a violation recorded."""
        path = self.root / rel
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            self.fail(rel, f"cannot be read ({exc.strerror})")
            return ""

    def check_opening(self, where: str, value: str) -> None:
        self.fields += 1
        term = opens_on_forbidden(value)
        if term:
            self.fail(where, f'"{value[:60]}" opens on "{term}"')

    def parse_toml(self, rel: str, text: str = None):
        """A parsed TOML document, or None with a violation recorded."""
        if text is None:
            text = self.read(rel)
        if not text:
            return None
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            self.fail(rel, f"is not valid TOML ({exc})")
            return None

    def values(self, rel: str, data, key: str, required: bool = True) -> list:
        """Every non-empty string under `key`, with the presence rule applied."""
        found = [v.strip() for v in toml_strings(data, key)]
        if not found and required:
            self.fail(f"{rel}: {key}", "missing")
        if any(not v for v in found):
            self.fail(f"{rel}: {key}", "is empty")
        return [v for v in found if v]

    # -- rules ---------------------------------------------------------------

    def rule_fixtures(self) -> None:
        """Rule 7 — the predicate and the value reader still do their jobs."""
        for value, expected in FIXTURES:
            actual = opens_on_forbidden(value)
            if actual != expected:
                self.fail(
                    "check_positioning.py: self-check",
                    f'"{value}" → {actual!r}, expected {expected!r}',
                )
        for name, document, expected in TOML_FIXTURES:
            try:
                actual = toml_strings(tomllib.loads(document), "x")
            except tomllib.TOMLDecodeError as exc:
                self.fail("check_positioning.py: self-check", f"{name} fixture: {exc}")
                continue
            if actual != [expected]:
                self.fail(
                    "check_positioning.py: self-check",
                    f"{name} value read as {actual!r}, expected {[expected]!r}",
                )

    def rule_config_fields(self) -> None:
        """Rules 1 and 2 over the hero and the site metadata."""
        for rel, keys in CONFIG_FIELDS:
            data = self.parse_toml(rel)
            if data is None:
                continue
            for key in keys:
                for value in self.values(rel, data, key):
                    self.check_opening(f"{rel}: {key}", value)

    def rule_front_matter(self) -> None:
        """Rules 1 and 2 over every page's description and lede."""
        for path in sorted((self.root / "content").rglob("*.md")):
            rel = path.relative_to(self.root).as_posix()
            text = self.read(rel)
            if not text:
                continue
            block = FRONT_MATTER.match(text)
            if not block:
                self.fail(rel, "has no TOML (+++) front matter — cannot be checked")
                continue
            data = self.parse_toml(rel, block.group(1))
            if data is None:
                continue
            for key in ("description", "lede"):
                for value in self.values(rel, data, key, required=False):
                    self.check_opening(f"{rel}: {key}", value)

    def rule_single_subtitle(self) -> None:
        """Rule 3 — generate_cv.py takes the LAST `subtitle =` line it sees."""
        config = self.read("hugo.toml")
        if not config:
            return
        count = len(SUBTITLE_LINE.findall(config))
        if count != 1:
            self.fail(
                "hugo.toml: subtitle",
                f"{count} `subtitle =` lines; generate_cv.py:171-175 silently uses the last one",
            )

    def rule_single_link(self) -> None:
        """Rule 4 — layouts/index.html:24 replaces EVERY match of whoamiLink."""
        data = self.parse_toml("data/home.toml")
        if data is None:
            return
        whoami = next(iter(self.values("data/home.toml", data, "whoami")), "")
        link = next(iter(self.values("data/home.toml", data, "whoamiLink")), "")
        if not whoami or not link:
            return
        hits = whoami.count(link)
        if hits != 1:
            self.fail(
                "data/home.toml: whoamiLink",
                f'"{link}" occurs {hits}x in whoami; the hero would render {hits} links',
            )
        bad = sorted(set(link) & REGEX_METACHARACTERS)
        if bad:
            self.fail(
                "data/home.toml: whoamiLink",
                f"contains regex metacharacters {''.join(bad)!r}; it is used as a pattern",
            )

    def rule_secondary_surfaces(self) -> None:
        """Rules 1 and 2 over the other single-line copies of the role line.

        static/js/terminal.js and the body of content/contact.md say the same
        thing in prose and in JavaScript string literals; reading those would
        take a JS parser or a literal-text match that any legitimate rewording
        would break. They are reviewed by hand instead.
        """
        humans = self.read("static/humans.txt")
        if humans:
            found = HUMANS_ROLE.findall(humans)
            if len(found) != 1:
                self.fail("static/humans.txt: Role", f"{len(found)} `Role:` lines, expected 1")
            for value in found:
                self.check_opening("static/humans.txt: Role", value)

        # The committed static/og-image.png cannot be asserted on; the string
        # it is generated from can.
        card = self.read("scripts/generate_og_image.py")
        if card:
            found = OG_SUB_TEXT.findall(card)
            if len(found) != 1:
                self.fail("scripts/generate_og_image.py: sub_text", f"{len(found)} assignments, expected 1")
            for value in found:
                self.check_opening("scripts/generate_og_image.py: sub_text", value)

    def rule_llms_mirror(self) -> None:
        """Rules 1, 2 and 6 over the agent-readable surface."""
        llms = self.read("static/llms.txt")
        if not llms:
            return
        summary = LLMS_SUMMARY.search(llms)
        if not summary:
            self.fail("static/llms.txt", "has no `>` summary line")
        else:
            self.check_opening("static/llms.txt: summary", summary.group(1))
        for token, source in MIRRORED:
            if token not in llms:
                self.fail("static/llms.txt", f'no longer mentions "{token}"')
            text = self.read(source)
            if text and token not in text:
                self.fail(source, f'no longer mentions "{token}", which static/llms.txt states')

    def rule_four_stats(self) -> None:
        """Rule 5 — .stats is grid-template-columns: repeat(4, 1fr)."""
        data = self.parse_toml("data/home.toml")
        if data is None:
            return
        count = len(data.get("stats", []))
        if count != 4:
            self.fail(
                "data/home.toml: [[stats]]",
                f"{count} entries; the band is a 4-column grid (assets/css/z-home.css:62)",
            )

    def run(self) -> int:
        rules = [
            self.rule_fixtures,
            self.rule_config_fields,
            self.rule_front_matter,
            self.rule_single_subtitle,
            self.rule_single_link,
            self.rule_four_stats,
            self.rule_secondary_surfaces,
            self.rule_llms_mirror,
        ]
        for rule in rules:
            rule()
        if self.violations:
            print("check_positioning: the copy no longer leads builder-first", file=sys.stderr)
            for violation in self.violations:
                print(f"  {violation}", file=sys.stderr)
            return 1
        print(f"check_positioning: {self.fields} fields, {len(rules)} rules, 0 violations")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to check (default: this repository)",
    )
    return Check(parser.parse_args().root).run()


if __name__ == "__main__":
    sys.exit(main())
