"""Unit tests for scripts/check_positioning.py.

The guard runs its own fixture tables on every invocation (Rule 7). These tests
add what an in-process self-check cannot: cases written independently of those
tables, so loosening a predicate and its table together still fails here, and
end-to-end runs against a copy of the repository with one regression injected.

Run with `make test`.
"""

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_positioning as cp  # noqa: E402

# Everything Check.run() reads, relative to the repository root.
CHECKED_PATHS = (
    "content",
    cp.HOME_TOML,
    cp.HUGO_TOML,
    cp.LLMS_TXT,
    cp.HUMANS_TXT,
    cp.TERMINAL_JS,
    cp.OG_SCRIPT,
)


class OpeningRuleTest(unittest.TestCase):
    def test_fixture_table(self):
        for value, expected in cp.FIXTURES:
            with self.subTest(value=value):
                self.assertEqual(cp.opens_on_forbidden(value), expected)

    def test_opening_on_a_forbidden_term(self):
        self.assertEqual(cp.opens_on_forbidden("INVESTOR, then builder"), "investor")
        self.assertEqual(cp.opens_on_forbidden("> *Technical partner* first"), "technical partner")

    def test_forbidden_term_later_in_the_line(self):
        self.assertIsNone(cp.opens_on_forbidden("Builder, and an investor too"))

    def test_a_longer_word_is_not_the_term(self):
        self.assertIsNone(cp.opens_on_forbidden("Investors read this page"))


class WhoLineRuleTest(unittest.TestCase):
    def test_fixture_table(self):
        for value, expected in cp.WHO_FIXTURES:
            with self.subTest(value=value):
                self.assertEqual(cp.names_a_role(value), expected)

    def test_role_anywhere_in_the_line(self):
        self.assertEqual(cp.names_a_role("hacker · extropian · engineer"), "engineer")
        self.assertEqual(cp.names_a_role("builder · CTO"), "cto")

    def test_at_sign_is_a_role_marker(self):
        self.assertEqual(cp.names_a_role("builder@home"), "@")

    def test_traits_only(self):
        self.assertIsNone(cp.names_a_role("builder · hacker · extropian"))


class TomlAndBlankTest(unittest.TestCase):
    def test_toml_fixture_table(self):
        for name, document, expected in cp.TOML_FIXTURES:
            with self.subTest(name=name):
                self.assertEqual(cp.toml_strings(cp.tomllib.loads(document), "x"), [expected])

    def test_toml_strings_walks_lists_and_tables(self):
        data = cp.tomllib.loads('x = "top"\n[[a]]\nx = "one"\n[[a]]\nx = "two"\ny = "no"')
        self.assertEqual(cp.toml_strings(data, "x"), ["top", "one", "two"])

    def test_non_string_values_are_ignored(self):
        self.assertEqual(cp.toml_strings({"x": 3}, "x"), [])

    def test_blank_fixture_table(self):
        for text, expected in cp.BLANK_FIXTURES:
            with self.subTest(text=text):
                self.assertEqual(cp.is_blank(text), expected)


class MirrorRuleTest(unittest.TestCase):
    def test_fixture_table(self):
        for name, llms, about, work, expect_violation in cp.MIRROR_FIXTURES:
            with self.subTest(name=name):
                reported = cp.mirror_violations(
                    llms, about, work, cp._FIXTURE_PROJECTS, cp._FIXTURE_ROLES
                )
                self.assertEqual(bool(reported), expect_violation, reported)

    def test_missing_roles_section(self):
        reported = cp.mirror_violations(
            "> Builder.\n", cp._FIXTURE_ABOUT, cp._FIXTURE_WORK, [], cp._FIXTURE_ROLES
        )
        self.assertIn((cp.LLMS_TXT, "has no `## Roles` section"), reported)

    def test_heading_matches_whole_line_or_org_tail(self):
        lines = ["## Founder, Akira Tech", "prose, Akira Tech"]
        self.assertTrue(cp.heading_matches(lines, "## Founder, Akira Tech"))
        self.assertFalse(cp.heading_matches(lines, "## Founder"))
        self.assertTrue(cp.heading_matches(lines, ", Akira Tech"))
        self.assertFalse(cp.heading_matches(["prose, Akira Tech"], ", Akira Tech"))


class EndToEndTest(unittest.TestCase):
    """Check.run() over the repository, and over a copy with one regression."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for rel in CHECKED_PATHS:
            src, dst = ROOT / rel, self.tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    def run_check(self, root=None):
        check = cp.Check(root or self.tmp)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = check.run()
        return code, check.violations

    def edit(self, rel, old, new):
        path = self.tmp / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"{rel} no longer contains {old!r}; update this test")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assertFailsWith(self, fragment):
        code, violations = self.run_check()
        self.assertEqual(code, 1)
        self.assertTrue(
            any(fragment in v for v in violations),
            f"no violation mentions {fragment!r}: {violations}",
        )

    def test_repository_passes(self):
        self.assertEqual(self.run_check(ROOT), (0, []))

    def test_the_copy_passes_unchanged(self):
        self.assertEqual(self.run_check(), (0, []))

    def test_role_in_whoami_fails(self):
        self.edit(cp.HOME_TOML, 'whoami = "builder', 'whoami = "CTO · builder')
        self.assertFailsWith('names a role ("cto")')

    def test_subtitle_opening_on_partner_fails(self):
        self.edit(cp.HUGO_TOML, 'subtitle = "', 'subtitle = "Technical Partner · ')
        self.assertFailsWith('opens on "technical partner"')

    def test_missing_subtitle_fails(self):
        self.edit(cp.HUGO_TOML, "      subtitle = ", "      # subtitle = ")
        self.assertFailsWith("hugo.toml: subtitle: missing")

    def test_a_fifth_stat_fails(self):
        self.edit(cp.HOME_TOML, "[[stats]]", '[[stats]]\nvalue = "1"\nlabel = "extra"\n\n[[stats]]')
        self.assertFailsWith("5 entries")

    def test_empty_file_fails(self):
        (self.tmp / cp.HUMANS_TXT).write_text("", encoding="utf-8")
        self.assertFailsWith(f"{cp.HUMANS_TXT}: is empty")


if __name__ == "__main__":
    unittest.main()
