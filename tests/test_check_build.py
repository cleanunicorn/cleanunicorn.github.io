"""Regression tests for built HTML semantics and primary navigation."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_build  # noqa: E402


class PostDates(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "time" and "post-date" in (attributes.get("class") or "").split():
            self.values.append(attributes.get("datetime"))


class HtmlSemanticsTests(unittest.TestCase):
    def check(self, markup):
        return check_build.check_html_semantics(markup)

    def test_valid_heading_and_dates_in_minified_html(self):
        markup = ('<h2 id=x>Title<a class=hanchor href=#x '
                  'aria-label="Link to this section">#</a></h2>'
                  '<time datetime=2026-09-23T12:30:45+03:00>Sep 23</time>'
                  '<time datetime="2026-09-23T09:30:45Z">Sep 23</time>')
        self.assertEqual([], self.check(markup))

    def test_every_heading_anchor_needs_exact_label(self):
        markup = ('<a class=hanchor aria-label="Link to this section">#</a>'
                  '<a class="x hanchor" aria-label="Anchor">#</a>')
        self.assertTrue(any("aria-label" in failure for failure in self.check(markup)))

    def test_missing_heading_label(self):
        self.assertTrue(any("aria-label" in failure for failure in self.check('<a class=hanchor>#</a>')))

    def test_invalid_arialabel_attribute_even_on_other_elements(self):
        self.assertTrue(any("arialabel" in failure for failure in self.check('<span ariaLabel=wrong>Text</span>')))

    def test_time_needs_datetime(self):
        for markup in ('<time>Sep 23</time>', '<time datetime="">Sep 23</time>'):
            with self.subTest(markup=markup):
                self.assertTrue(any("datetime" in failure for failure in self.check(markup)))

    def test_rejects_malformed_and_impossible_dates(self):
        for value in ('2026-09-23', '2026-02-30T12:30:45Z', '2026-09-23T25:30:45Z',
                      '2026-09-23T12:30:45+25:00', '2026-09-23T12:30:45+03:99'):
            with self.subTest(value=value):
                self.assertTrue(any("datetime" in failure for failure in self.check(
                    f'<time datetime="{value}">Date</time>')))

    def test_html_entities_in_offset_are_decoded(self):
        self.assertEqual([], self.check('<time datetime="2026-09-23T12:30:45&#43;03:00">Date</time>'))

    def test_output_scan_requires_an_anchor_and_checks_nested_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            (public / "index.html").write_text("<main>Home</main>")
            self.assertTrue(any("no .hanchor" in failure
                                for failure in check_build.check_html_pages(public)))

            post = public / "posts" / "example" / "index.html"
            post.parent.mkdir(parents=True)
            post.write_text('<a class=hanchor aria-label="Link to this section">#</a>'
                            '<time>Sep 23</time>')
            failures = check_build.check_html_pages(public)
            self.assertEqual(1, len(failures))
            self.assertIn("posts/example/index.html: time datetime", failures[0])


@unittest.skipUnless(shutil.which("hugo") and (ROOT / "themes/terminal/layouts").is_dir(),
                     "Hugo and the theme submodule are required for the render fixture")
class HugoDateSourceTests(unittest.TestCase):
    def test_home_list_and_single_use_publication_date(self):
        published = "2024-02-29T14:23:45+01:00"
        updated = "2025-06-01T09:08:07-04:00"
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            post = temporary / "content" / "posts" / "date-source-fixture"
            post.mkdir(parents=True)
            (post / "index.md").write_text(
                f'+++\ntitle = "Date source fixture"\ndate = {published}\n'
                f'lastmod = {updated}\n+++\n\n## Fixture heading\n'
            )
            output = temporary / "public"
            subprocess.run(
                ["hugo", "--source", str(ROOT), "--contentDir", str(temporary / "content"),
                 "--destination", str(output), "--cleanDestinationDir"],
                check=True, capture_output=True, text=True,
            )
            for relative in ("index.html", "posts/index.html", "posts/date-source-fixture/index.html"):
                with self.subTest(page=relative):
                    dates = PostDates()
                    dates.feed((output / relative).read_text())
                    self.assertEqual([published], dates.values)


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
        return check_build.check_nav(self.root, self.public)

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
