#!/usr/bin/env python3
"""Assert the site's identity copy still leads with what he builds.

This repository has no test suite; this is its one assertion-running check and
the regression net behind the builder-first positioning. It fails when a
protected field starts describing him as a partner or an investor before it
describes him as someone who builds things, and when static/llms.txt — the
file agents read — drifts away from the pages it restates.

Three deliberate choices, all load-bearing:

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

What it reads, so the next editor does not have to infer it:

    data/home.toml            whoami, whoamiLink, the [[stats]] count
    hugo.toml                 subtitle, keywords, jobTitle, personDescription
    content/**/*.md           every front-matter description and lede
    static/humans.txt         the Role line
    static/js/terminal.js     the whoami greeting, about.md, work.md
    scripts/generate_og_image.py   sub_text, the social card's role line
    static/llms.txt           the summary line, and the facts it mirrors

Deliberately NOT read, each for a reason that survives asking twice:

    content/contact.md's body — prose; its front matter is read like any page's
    hugo.toml knowsAbout      — a topic list, not a sentence with an opening
    data/cv.toml              — the CV's own strings are derived from the pages
    the About lede, the role bodies — prose, reviewed by a human
    static/og-image.png       — a binary; sub_text above is its source

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

# Markdown, quoting and dashes a value may legitimately start with, stripped
# before the opening word is read. The en and em dashes are in the class
# because they are the ones this site's copy actually uses.
LEADING_MARKUP = re.compile(r"""^[\s>*_#\-–—\["'(«“‘]+""")

# generate_cv.py:174 tests `"subtitle =" in line` — an unanchored substring,
# so a commented-out or prefixed line counts for it too. Rule 3 exists to
# mirror that scan, so it matches what the generator matches, not what TOML
# means.
SUBTITLE_LINE = re.compile(r"^.*subtitle\s*=.*$", re.MULTILINE)
HUMANS_ROLE = re.compile(r"^\s*Role:\s*(.+?)\s*$", re.MULTILINE)
# `(?!")` rejects a triple-quote opener instead of capturing the middle
# quote as the value, and the body cannot span lines — either way the value
# goes missing and the presence rule fires, which is what this file promises.
OG_SUB_TEXT = re.compile(r'^\s*sub_text\s*=\s*"(?!")((?:[^"\\\n]|\\.)*)"\s*$', re.MULTILINE)
LLMS_SUMMARY = re.compile(r"^>\s*(.+?)\s*$", re.MULTILINE)
# The hero terminal's identity strings. Each is a one-line literal in a fixed
# position: the console greeting after `cleanunicorn — `, and the first entry
# of the about.md / work.md arrays that is not a markdown heading. A reworded
# anchor makes the value go missing, which the presence rule reports, so the
# guard never silently stops looking.
TERMINAL_GREETING = re.compile(r'"%c~\$ whoami%c\\ncleanunicorn — ([^"]*?)\.?"')
TERMINAL_ARRAY = '"%s": ['
TERMINAL_STRING = re.compile(r'^\s*"([^"]*)",?\s*$', re.MULTILINE)
FRONT_MATTER = re.compile(r"\A\+\+\+\s*\n(.*?)\n\+\+\+\s*\n", re.DOTALL)

# Every file this check reads, named once.
WORK_MD = "content/previous-work.md"
ABOUT_MD = "content/about/_index.md"
HOME_TOML = "data/home.toml"
HUGO_TOML = "hugo.toml"
LLMS_TXT = "static/llms.txt"
HUMANS_TXT = "static/humans.txt"
TERMINAL_JS = "static/js/terminal.js"
OG_SCRIPT = "scripts/generate_og_image.py"

# Which TOML file holds which protected values.
CONFIG_FIELDS = (
    (HOME_TOML, ("whoami",)),
    (HUGO_TOML, ("subtitle", "keywords", "jobTitle", "personDescription")),
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
    ("— Investor and builder", "investor"),
    ("– Technical Partner @ Eden Block", "technical partner"),
    ("“Investor first”, they said", "investor"),
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

# A file that still exists but holds nothing must count as a violation, not as
# nothing to check.
BLANK_FIXTURES = [("", True), ("\n  \n", True), ('x = "builder"', False)]

# Rule 6's own fixture - the ways a token-containment mirror passes on a
# page that no longer says what llms.txt claims.
MIRROR_FIXTURES = [
    ("a renamed role heading", "## CEO, Akira Tech",
     "## Founder, Security Researcher, Akira Tech"),
    ("a date in prose, not on a date line", "Since August 2026 things changed.",
     "*August 2026 – Present*"),
    ("the word without the project", "and then he drove home",
     "### [drove](https://github.com/cleanunicorn/drove)"),
]

# Rule 3's own fixture: the generator's line scan, and what Rule 3 must see.
SUBTITLE_SCAN_FIXTURES = [
    # (name, a hugo.toml fragment, how many lines Rule 3 must count,
    #  whether that count is a violation)
    ("a commented-out line below the live one",
     '      subtitle = "Builder | Hacker"\n      # subtitle = "Investor | Builder"\n', 2, True),
    ("the one live line", '      subtitle = "Builder | Hacker"\n', 1, False),
    ("no subtitle at all", '      title = "Daniel Luca"\n', 0, True),
]


# Rule 6 — static/llms.txt restates, by hand, facts that live on the pages. A
# token that merely occurs somewhere in both files proves nothing: "drove" is
# also an ordinary English verb, and a role can be renamed while its
# organisation and start date stay put. So each row pins the *line* the fact
# lives on — the About page's card heading, the Work page's `## ` heading and
# its italic date line, which is the shape parse_roles() reads.
MIRRORED_PROJECTS = [
    # (name in llms.txt, the About card heading that must still exist)
    ("Earheart", "### [Earheart](https://github.com/cleanunicorn/earheart)"),
    ("Agents Library", "### [Agents Library](https://github.com/cleanunicorn/agents-library)"),
    ("drove", "### [drove](https://github.com/cleanunicorn/drove)"),
    ("Karl", "### [Karl](https://github.com/cleanunicorn/karl)"),
    ("RL-Swarm", "### [RL-Swarm Smart Contracts](https://github.com/gensyn-ai/rl-swarm-contracts)"),
]

MIRRORED_ROLES = [
    # (organisation as llms.txt writes it, what to match the Work heading by,
    #  its date line, the start date llms.txt states)
    #
    # The second field pins the whole `## Title, Organisation` heading where
    # llms.txt restates that title, so renaming the role fails. Where llms.txt
    # states no title — it describes the role instead — the field is the
    # heading's `, Organisation` tail: there is no title to mirror, and pinning
    # one would mean retyping a job title this branch may not add.
    ("stealth startup", "## CTO, Stealth Startup", "*August 2026 \u2013 Present*", "August 2026"),
    ("Eden Block", "## Technical Partner, Eden Block", "*November 2022 \u2013 Present*", "November 2022"),
    ("FiatDAO", "## Co-Founder, FiatDAO", "*November 2021 \u00b7 Deployed April 2022*", "November 2021"),
    ("Akira Tech", "## Founder, Security Researcher, Akira Tech", "*October 2020 \u2013 Present*", "October 2020"),
    ("ConsenSys Diligence", "## Security Researcher, ConsenSys Diligence", "*November 2018 \u2013 August 2020*", "November 2018"),
    ("Alethio", ", Alethio", "*February 2017 \u2013 November 2018 \u00b7 ConsenSys*", "February 2017"),
]

LLMS_ROLES_SECTION = re.compile(r"^## Roles\s*$(.*?)^## ", re.MULTILINE | re.DOTALL)


def opens_on_forbidden(value: str) -> str | None:
    """The forbidden term a value opens on, or None."""
    stripped = LEADING_MARKUP.sub("", value).lower()
    for term in FORBIDDEN:
        if re.match(re.escape(term) + r"\b", stripped):
            return term
    return None


def lines_of(text: str) -> list[str]:
    """The file's lines, stripped, so a fact can be pinned to a whole line."""
    return [line.strip() for line in text.split("\n")]


def subtitle_violation(matches: list[str]) -> str | None:
    """Why this many `subtitle =` lines is wrong, or None when it is one.

    Zero is as much a violation as two: generate_cv.py:171-176 starts with an
    empty subtitle and writes an empty CV header rather than failing.
    """
    if len(matches) == 1:
        return None
    problem = (
        f"{len(matches)} lines contain `subtitle =` (including comments, which "
        f"generate_cv.py:174 counts too)"
    )
    if not matches:
        return f"{problem}; the CV header would be blank"
    return f"{problem}; it silently uses the last one: {matches[-1].strip()!r}"


def heading_matches(lines: list[str], pattern: str) -> bool:
    """Whether a `## ` heading matches — the whole line, or its `, Org` tail."""
    if pattern.startswith("## "):
        return pattern in lines
    return any(line.startswith("## ") and line.endswith(pattern) for line in lines)


def is_blank(text: str) -> bool:
    """Whether a file's contents hold nothing for this check to read."""
    return not text.strip()


def toml_strings(data, key: str) -> list[str]:
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
        self.contents: dict[str, str] = {}
        self.fields_checked = 0

    def fail(self, where: str, problem: str) -> None:
        self.violations.append(f"{where}: {problem}")

    def read(self, rel: str) -> str:
        """File contents, or "" with a violation recorded.

        An empty file is a violation too. Every rule below treats falsy text as
        "nothing to check and nothing to say", so without this a checked file
        truncated to zero bytes would disable its rules in silence — the one
        way to lose a field that deleting the file does not give you.
        """
        if rel in self.contents:
            return self.contents[rel]
        path = self.root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.fail(rel, f"cannot be read ({exc.strerror})")
            text = ""
        else:
            if is_blank(text):
                self.fail(rel, "is empty; it should hold the values this check reads")
                text = ""
        self.contents[rel] = text
        return text

    def check_opening(self, where: str, value: str) -> None:
        self.fields_checked += 1
        term = opens_on_forbidden(value)
        if term:
            self.fail(where, f'"{value[:60]}" opens on "{term}"')

    def parse_toml(self, rel: str, text: str | None = None) -> dict | None:
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

    def values(self, rel: str, data, key: str, required: bool = True) -> list[str]:
        """Every non-empty string under `key`, with the presence rule applied."""
        found = [v.strip() for v in toml_strings(data, key)]
        if not found and required:
            self.fail(f"{rel}: {key}", "missing")
        if any(not v for v in found):
            self.fail(f"{rel}: {key}", "is empty")
        return [v for v in found if v]

    # -- rules ---------------------------------------------------------------

    def rule_fixtures(self) -> None:
        """Rule 7 — every predicate this check leans on still does its job.

        Each table below is a defect that once got through. They run on every
        invocation rather than behind a flag, because a flag nobody passes is a
        check nobody runs.
        """
        self.check_opening_fixtures()
        self.check_blank_fixtures()
        self.check_mirror_fixtures()
        self.check_subtitle_scan_fixtures()
        self.check_toml_fixtures()

    def self_check_failed(self, problem: str) -> None:
        self.fail("check_positioning.py: self-check", problem)

    def check_opening_fixtures(self) -> None:
        """The opening rule still rejects a forbidden term, dressed however."""
        for value, expected in FIXTURES:
            actual = opens_on_forbidden(value)
            if actual != expected:
                self.self_check_failed(f'"{value}" → {actual!r}, expected {expected!r}')

    def check_blank_fixtures(self) -> None:
        """A file that holds nothing is still nothing to read, not nothing to check."""
        for text, expected_blank in BLANK_FIXTURES:
            if is_blank(text) != expected_blank:
                self.self_check_failed(
                    f"{text!r} read as blank={not expected_blank}, expected {expected_blank}"
                )

    def check_mirror_fixtures(self) -> None:
        """The mirror still refuses the near-misses a token search accepted."""
        for name, decoy, required_line in MIRROR_FIXTURES:
            if required_line.strip() in lines_of(decoy):
                self.self_check_failed(f"{name}: the mirror would still accept {decoy!r}")

    def check_subtitle_scan_fixtures(self) -> None:
        """Rule 3 still counts the lines generate_cv.py counts, and still reports."""
        for name, document, expected_lines, expect_violation in SUBTITLE_SCAN_FIXTURES:
            matches = SUBTITLE_LINE.findall(document)
            if len(matches) != expected_lines:
                self.self_check_failed(
                    f"{name}: counted {len(matches)} `subtitle =` lines, expected {expected_lines}"
                )
            problem = subtitle_violation(matches)
            if bool(problem) != expect_violation:
                self.self_check_failed(
                    f"{name}: reported {problem!r}, expected "
                    f"{'a violation' if expect_violation else 'none'}"
                )

    def check_toml_fixtures(self) -> None:
        """Every TOML quoting form still yields the value Rule 1 then tests."""
        for name, document, expected in TOML_FIXTURES:
            try:
                actual = toml_strings(tomllib.loads(document), "x")
            except tomllib.TOMLDecodeError as exc:
                self.self_check_failed(f"{name} fixture: {exc}")
                continue
            if actual != [expected]:
                self.self_check_failed(
                    f"{name} value read as {actual!r}, expected {[expected]!r}"
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
        config = self.read(HUGO_TOML)
        if not config:
            return
        problem = subtitle_violation(SUBTITLE_LINE.findall(config))
        if problem:
            self.fail(f"{HUGO_TOML}: subtitle", problem)

    def rule_single_link(self) -> None:
        """Rule 4 — layouts/index.html:24 replaces EVERY match of whoamiLink."""
        data = self.parse_toml(HOME_TOML)
        if data is None:
            return
        whoami = next(iter(self.values(HOME_TOML, data, "whoami")), "")
        link = next(iter(self.values(HOME_TOML, data, "whoamiLink")), "")
        if not whoami or not link:
            return
        hits = whoami.count(link)
        if hits != 1:
            self.fail(
                f"{HOME_TOML}: whoamiLink",
                f'"{link}" occurs {hits}x in whoami; the hero would render {hits} links',
            )
        stray = sorted(set(link) & REGEX_METACHARACTERS)
        if stray:
            self.fail(
                f"{HOME_TOML}: whoamiLink",
                f"contains regex metacharacters {''.join(stray)!r}; it is used as a pattern",
            )

    def rule_secondary_surfaces(self) -> None:
        """Rules 1 and 2 over the other copies of the role line.

        The terminal's three strings are one-line literals at fixed positions,
        the same shape as the card script's sub_text, so they are read rather
        than hand-reviewed — they were two of the four stale copies this branch
        had to clean up by hand, which is the argument for watching them.

        content/contact.md's body stays hand-reviewed: its opening is a
        shortcode and a heading, and "the prose leads with what he builds" is a
        judgement, not a field. Its front matter is covered by Rule 1 like every
        other page's.
        """
        self.check_humans_role()
        self.check_terminal_strings()
        self.check_card_sub_text()

    def check_only_match(self, pattern, text: str, where: str, noun: str) -> None:
        """Check the one value `pattern` should find, and say so if it is not one."""
        found = pattern.findall(text)
        if len(found) != 1:
            self.fail(where, f"{len(found)} {noun}, expected 1")
        for value in found:
            self.check_opening(where, value)

    def check_humans_role(self) -> None:
        humans = self.read(HUMANS_TXT)
        if humans:
            self.check_only_match(HUMANS_ROLE, humans, f"{HUMANS_TXT}: Role", "`Role:` lines")

    def check_card_sub_text(self) -> None:
        """The committed og-image.png cannot be asserted on; its source string can."""
        card = self.read(OG_SCRIPT)
        if card:
            self.check_only_match(OG_SUB_TEXT, card, f"{OG_SCRIPT}: sub_text", "assignments")

    def check_terminal_strings(self) -> None:
        terminal = self.read(TERMINAL_JS)
        if not terminal:
            return
        greeting = TERMINAL_GREETING.search(terminal)
        if not greeting:
            self.fail(TERMINAL_JS, "the `~$ whoami` greeting is no longer where this check looks")
        else:
            self.check_opening(f"{TERMINAL_JS}: whoami greeting", greeting.group(1))
        for name in ("about.md", "work.md"):
            start = terminal.find(TERMINAL_ARRAY % name)
            end = terminal.find("],", start) if start != -1 else -1
            if start == -1 or end == -1:
                self.fail(TERMINAL_JS, f'the virtual "{name}" array is no longer where this check looks')
                continue
            said = [v for v in TERMINAL_STRING.findall(terminal[start:end]) if not v.startswith("#")]
            if not said:
                self.fail(TERMINAL_JS, f'the virtual "{name}" says nothing')
                continue
            self.check_opening(f"{TERMINAL_JS}: {name}", said[0])

    def rule_llms_mirror(self) -> None:
        """Rules 1, 2 and 6 over the agent-readable surface."""
        llms = self.read(LLMS_TXT)
        if not llms:
            return
        summary = LLMS_SUMMARY.search(llms)
        if not summary:
            self.fail(LLMS_TXT, "has no `>` summary line")
        else:
            self.check_opening("static/llms.txt: summary", summary.group(1))

        about = lines_of(self.read(ABOUT_MD))
        for name, heading in MIRRORED_PROJECTS:
            if heading not in about:
                self.fail(ABOUT_MD, f"no longer has the card `{heading}`, which static/llms.txt lists")
            if heading.split("(", 1)[1].rstrip(")") not in llms:
                self.fail(LLMS_TXT, f'no longer links the project "{name}"')

        work = lines_of(self.read(WORK_MD))
        roles = LLMS_ROLES_SECTION.search(llms)
        role_lines = lines_of(roles.group(1)) if roles else []
        if not role_lines:
            self.fail(LLMS_TXT, "has no `## Roles` section")
        for org, heading, dates, start in MIRRORED_ROLES:
            if not heading_matches(work, heading):
                self.fail(WORK_MD, f"no longer has the role heading `{heading}`, which static/llms.txt states")
            if dates not in work:
                self.fail(WORK_MD, f"no longer has the date line `{dates}` for `{heading}`")
            stated = [line for line in role_lines if org.lower() in line.lower()]
            if not stated:
                self.fail(LLMS_TXT, f'its Roles section no longer states "{org}"')
                continue
            if not any(start in line for line in stated):
                self.fail(LLMS_TXT, f'states "{org}" without its start date "{start}"')
            # The table may only pin a title that llms.txt itself states, so a
            # row can never carry a job title this file has no business naming.
            titled = not stated[0].lstrip("- ").lower().startswith(org.lower())
            if titled != heading.startswith("## "):
                self.fail(
                    "check_positioning.py: MIRRORED_ROLES",
                    f'the row for "{org}" pins {"a title" if not titled else "no title"} '
                    f"while static/llms.txt states {'one' if titled else 'none'}",
                )

    def rule_four_stats(self) -> None:
        """Rule 5 — .stats is grid-template-columns: repeat(4, 1fr)."""
        data = self.parse_toml(HOME_TOML)
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
        print(f"check_positioning: {self.fields_checked} fields, {len(rules)} rules, 0 violations")
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
