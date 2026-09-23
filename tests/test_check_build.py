"""Regression tests for the rendered primary navigation guard."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_build import check_nav  # noqa: E402


CONFIG = """[languages.en.menu]
[[languages.en.menu.main]]
name = "About"
url = "/about/"
weight = 10
[[languages.en.menu.main]]
name = "Work"
url = "/work/"
weight = 20
[[languages.en.menu.main]]
name = "Posts"
url = "/posts/"
weight = 30
[[languages.en.menu.main]]
name = "Contact"
url = "/contact/"
weight = 40
"""

LINKS = '<li><a href="/about/">About</a></li><li><a href="/work/">Work</a></li><li><a href="/posts/">Posts</a></li><li><a href="/contact/">Contact</a></li>'
MOBILE = '<nav class="navigation-menu--mobile" aria-label="Primary mobile"><button type="button" aria-expanded="true" aria-controls="mobile-nav-links" hidden>Menu</button><ul id="mobile-nav-links">' + LINKS + '</ul></nav>'
DESKTOP = '<nav class="navigation-menu" aria-label="Primary"><ul class="navigation-menu__inner menu--desktop">' + LINKS + '</ul></nav>'


class NavGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.public = self.root / "public"
        self.public.mkdir()
        (self.root / "hugo.toml").write_text(CONFIG)

    def check(self, html=MOBILE + DESKTOP):
        (self.public / "index.html").write_text(html)
        return check_nav(self.root, self.public)

    def test_valid_source_contract(self):
        self.assertEqual([], self.check())

    def test_minified_unquoted_attributes(self):
        html = (MOBILE + DESKTOP).replace('class="navigation-menu--mobile"', 'class=navigation-menu--mobile').replace('aria-expanded="true"', 'aria-expanded=true').replace('aria-controls="mobile-nav-links"', 'aria-controls=mobile-nav-links').replace('id="mobile-nav-links"', 'id=mobile-nav-links')
        self.assertEqual([], self.check(html))

    def test_missing_link_fails(self):
        self.assertTrue(self.check((MOBILE + DESKTOP).replace('<li><a href="/contact/">Contact</a></li>', '', 1)))

    def test_duplicate_mobile_nav_fails(self):
        self.assertTrue(self.check(MOBILE + MOBILE + DESKTOP))

    def test_unfocusable_trigger_fails(self):
        self.assertTrue(self.check((MOBILE + DESKTOP).replace('<button type="button" aria-expanded="true" aria-controls="mobile-nav-links" hidden>Menu</button>', '<li class="menu__trigger">Menu</li>')))

    def test_broken_disclosure_contract_fails(self):
        for old, new in (('aria-expanded="true"', 'aria-expanded="false"'), ('aria-controls="mobile-nav-links"', 'aria-controls="missing"'), (' id="mobile-nav-links"', ' id="mobile-nav-links" hidden'), (' hidden>Menu', '>Menu')):
            with self.subTest(old=old):
                self.assertTrue(self.check((MOBILE + DESKTOP).replace(old, new, 1)))

    def test_refresh_alias_is_skipped(self):
        (self.public / "about").mkdir()
        (self.public / "about" / "index.html").write_text('<meta http-equiv=refresh content="0; url=/about/">')
        self.assertEqual([], self.check())

    def test_static_html_copy_is_skipped(self):
        (self.root / "static").mkdir()
        (self.root / "static" / "cv.html").write_text("<h1>CV</h1>")
        (self.public / "cv.html").write_text("<h1>CV</h1>")
        self.assertEqual([], self.check())


if __name__ == "__main__":
    unittest.main()
