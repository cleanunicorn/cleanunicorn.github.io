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
* It reads values with line regexes, the way `generate_cv.py`'s
  `parse_config()` reads hugo.toml, rather than with a TOML parser. Rule 3
  below is a property of the raw lines, and every field checked is a
  single-line `key = "value"`. If one is ever reformatted, the presence rule
  reports it as missing — the check fails loudly instead of passing on an
  empty set of fields.

Usage:
    python3 scripts/check_positioning.py [--root PATH]

`--root` points the check at a copy of the repository, so a regression can be
demonstrated without writing to the working tree.
"""

import argparse
import re
import sys
from pathlib import Path

# A field may mention these; it may not open on one. Add a term here and the
# whole check picks it up.
FORBIDDEN = ("technical partner", "investor")

# Markdown and quoting a value may legitimately start with, stripped before
# the opening word is read.
LEADING_MARKUP = re.compile(r"""^[\s>*_#\-\["'(]+""")

# Single-line `key = "value"` assignments, the shape every checked field uses.
def assignment(key: str) -> re.Pattern:
    return re.compile(r'^\s*%s\s*=\s*"(.*)"\s*$' % re.escape(key), re.MULTILINE)


SUBTITLE_LINE = re.compile(r"^\s*subtitle\s*=", re.MULTILINE)
HUMANS_ROLE = re.compile(r"^\s*Role:\s*(.+?)\s*$", re.MULTILINE)
OG_SUB_TEXT = re.compile(r'^\s*sub_text\s*=\s*"(.*)"\s*$', re.MULTILINE)
LLMS_SUMMARY = re.compile(r"^>\s*(.+?)\s*$", re.MULTILINE)
STATS_TABLE = re.compile(r"^\s*\[\[stats\]\]\s*$", re.MULTILINE)
FRONT_MATTER = re.compile(r"\A\+\+\+\s*\n(.*?)\n\+\+\+\s*\n", re.DOTALL)
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

    def one_value(self, rel: str, text: str, key: str) -> str:
        """The single value of `key`, or "" with a violation recorded."""
        found = assignment(key).findall(text)
        if not found:
            self.fail(f"{rel}: {key}", "missing, empty or no longer a single-line string")
            return ""
        if len(found) > 1:
            self.fail(f"{rel}: {key}", f"assigned {len(found)} times — which one wins is not obvious")
        value = found[0].strip()
        if not value:
            self.fail(f"{rel}: {key}", "is empty")
        return value

    # -- rules ---------------------------------------------------------------

    def rule_fixtures(self) -> None:
        """Rule 7 — the predicate still rejects what it is here to reject."""
        for value, expected in FIXTURES:
            actual = opens_on_forbidden(value)
            if actual != expected:
                self.fail(
                    "check_positioning.py: self-check",
                    f'"{value}" → {actual!r}, expected {expected!r}',
                )

    def rule_config_fields(self) -> None:
        """Rules 1 and 2 over the hero and the site metadata."""
        home = self.read("data/home.toml")
        if home:
            self.check_opening("data/home.toml: whoami", self.one_value("data/home.toml", home, "whoami"))

        config = self.read("hugo.toml")
        if config:
            for key in ("subtitle", "jobTitle", "personDescription"):
                self.check_opening(f"hugo.toml: {key}", self.one_value("hugo.toml", config, key))

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
            for key in ("description", "lede"):
                for value in assignment(key).findall(block.group(1)):
                    self.check_opening(f"{rel}: {key}", value.strip())

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
        home = self.read("data/home.toml")
        if not home:
            return
        whoami = self.one_value("data/home.toml", home, "whoami")
        link = self.one_value("data/home.toml", home, "whoamiLink")
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
        home = self.read("data/home.toml")
        if not home:
            return
        count = len(STATS_TABLE.findall(home))
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
