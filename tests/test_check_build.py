"""Regression tests for built HTML semantics and primary navigation."""

import os
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


class FeaturedProjectsTests(unittest.TestCase):
    """A featured project must be on both pages, each linking its repo."""

    REPO = "https://github.com/cleanunicorn/earheart"
    HOME = '<article class=featured__card id=featured-earheart><a href="https://github.com/cleanunicorn/earheart">GitHub</a></article>'
    PAGE = '<section class="project" id="earheart"><a href="https://github.com/cleanunicorn/earheart">GitHub</a></section>'

    def check(self, home=HOME, page=PAGE):
        return check_build.featured_project_violations("earheart", self.REPO, home, page)

    def test_both_pages_render_the_project(self):
        self.assertEqual([], self.check())

    def test_missing_homepage_card(self):
        self.assertEqual(["index.html: no featured card for 'earheart'"], self.check(home="<main></main>"))

    def test_missing_projects_section(self):
        self.assertEqual(["projects/index.html: no section #earheart"], self.check(page="<main></main>"))

    def test_card_without_repo_link(self):
        got = self.check(home="<article id=featured-earheart></article>")
        self.assertEqual([f"index.html: featured card for 'earheart' does not link {self.REPO}"], got)

    def test_repo_link_outside_the_section_does_not_count(self):
        page = ('<section class="project" id="quill"><pre>git clone https://github.com/cleanunicorn/earheart</pre></section>'
                '<section id="earheart"></section><a href="https://github.com/cleanunicorn/earheart">x</a>')
        self.assertEqual([f"projects/index.html: section #earheart does not link {self.REPO}"], self.check(page=page))

    def test_minified_unquoted_href_counts(self):
        page = '<section id=earheart><a href=https://github.com/cleanunicorn/earheart target=_blank>GitHub</a></section>'
        self.assertEqual([], self.check(page=page))

    def test_slug_is_not_a_prefix_match(self):
        self.assertEqual(
            ["projects/index.html: no section #earheart"],
            self.check(page='<section id="earheart-legacy"></section>'),
        )


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


TWEET = ('<blockquote class="twitter-tweet x-embed"><p lang="en" dir="ltr">Be careful &lt;b&gt;'
         '<a href="https://t.co/x">https://t.co/x</a></p>&mdash; Name (@user_1) '
         '<a href="https://twitter.com/user_1/status/123">January 27, 2024 · View on X</a></blockquote>')
LOADER = '<script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>'
POST = '<article class="post post--article">{}</article>'


class XEmbedTests(unittest.TestCase):
    def check(self, markup):
        return check_build.check_x_embed_markup(markup)

    def test_valid_card_with_loader(self):
        self.assertEqual([], self.check(POST.format(TWEET) + LOADER))

    def test_original_empty_embed_fails(self):
        empty = ('<blockquote class="twitter-tweet"><a href="https://twitter.com/shadowxyz/status/'
                 '1732049145140015142"></a></blockquote>')
        failures = self.check(POST.format(empty + LOADER))
        self.assertIn("X embed 1 has no tweet text", failures)
        self.assertIn("X embed 1 has no (@handle) attribution", failures)
        self.assertIn("X embed 1 has no named link to the tweet", failures)

    def test_minified_unquoted_attributes(self):
        minified = (TWEET.replace('class="twitter-tweet x-embed"', "class=twitter-tweet")
                    .replace('href="https://twitter.com/user_1/status/123"',
                             "href=https://twitter.com/user_1/status/123"))
        loader = "<script async src=https://platform.twitter.com/widgets.js></script>"
        self.assertEqual([], self.check("<article class=post>" + minified + loader + "</article>"))

    def test_blank_text_fails(self):
        for text in ("", "  \n "):
            with self.subTest(text=text):
                card = TWEET.replace('Be careful &lt;b&gt;<a href="https://t.co/x">https://t.co/x</a>', text)
                self.assertIn("X embed 1 has no tweet text", self.check(card + LOADER))

    def test_missing_paragraph_fails(self):
        card = ('<blockquote class="twitter-tweet">&mdash; Name (@user_1) '
                '<a href="https://twitter.com/user_1/status/123">Jan 1</a></blockquote>')
        self.assertEqual(["X embed 1 has no tweet text"], self.check(card))

    def test_missing_attribution_fails(self):
        self.assertEqual(["X embed 1 has no (@handle) attribution"],
                         self.check(TWEET.replace("Name (@user_1)", "Name")))

    def test_link_inside_text_does_not_count_as_status_link(self):
        card = TWEET.replace('<a href="https://twitter.com/user_1/status/123">January 27, 2024 · View on X</a>', "")
        self.assertEqual(["X embed 1 has no named link to the tweet"], self.check(card))

    def test_blank_or_wrong_status_link_fails(self):
        for old, new in (("January 27, 2024 · View on X", " "),
                         ("https://twitter.com/user_1/status/123", "https://example.com/user_1/status/123"),
                         ("https://twitter.com/user_1/status/123", "https://twitter.com/user_1")):
            with self.subTest(new=new):
                self.assertEqual(["X embed 1 has no named link to the tweet"],
                                 self.check(TWEET.replace(old, new)))

    def test_two_cards_share_one_loader(self):
        self.assertEqual([], self.check(POST.format(TWEET + TWEET) + LOADER))

    def test_duplicate_loader_fails(self):
        self.assertEqual(["widgets.js loaded 2 times"], self.check(POST.format(TWEET + LOADER + LOADER)))

    def test_blocking_loader_fails(self):
        self.assertEqual(["widgets.js loaded without async"],
                         self.check(POST.format(TWEET) + LOADER.replace("async ", "")))

    def test_post_with_card_needs_loader(self):
        self.assertEqual(["X embed page does not load widgets.js"], self.check(POST.format(TWEET)))

    def test_list_page_card_without_loader_passes(self):
        self.assertEqual([], self.check("<main>" + TWEET + "</main>"))

    def test_page_without_embeds_passes(self):
        self.assertEqual([], self.check(POST.format("<blockquote><p>Quote</p></blockquote>")))

    def test_output_scan_names_the_page(self):
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            post = public / "posts" / "example" / "index.html"
            post.parent.mkdir(parents=True)
            post.write_text(POST.format('<blockquote class="twitter-tweet"><a href="https://twitter.com/u/status/1"></a></blockquote>') + LOADER)
            (public / "index.html").write_text("<main>Home</main>")
            failures = check_build.check_x_embeds(public)
            self.assertEqual(3, len(failures))
            self.assertTrue(all(f.startswith("posts/example/index.html: X embed 1") for f in failures))
def render_fixture(directory, front_matter, env=None):
    """Build the site with one fixture post and return the output directory."""
    temporary = Path(directory)
    post = temporary / "content" / "posts" / "fixture"
    post.mkdir(parents=True)
    (post / "index.md").write_text(f"+++\n{front_matter}+++\n\n## Fixture heading\n")
    output = temporary / "public"
    subprocess.run(
        ["hugo", "--source", str(ROOT), "--contentDir", str(temporary / "content"),
         "--destination", str(output), "--cleanDestinationDir"],
        check=True, capture_output=True, text=True,
        env=None if env is None else {**os.environ, **env},
    )
    return output


FIXTURE_PAGES = ("index.html", "posts/index.html", "posts/fixture/index.html")


@unittest.skipUnless(shutil.which("hugo") and (ROOT / "themes/terminal/layouts").is_dir(),
                     "Hugo and the theme submodule are required for the render fixture")
class HugoRenderFixtureTests(unittest.TestCase):
    def test_home_list_and_single_use_publication_date(self):
        published = "2024-02-29T14:23:45+01:00"
        updated = "2025-06-01T09:08:07-04:00"
        with tempfile.TemporaryDirectory() as directory:
            output = render_fixture(
                directory,
                f'title = "Date source fixture"\ndate = {published}\nlastmod = {updated}\n',
            )
            for relative in FIXTURE_PAGES:
                with self.subTest(page=relative):
                    dates = PostDates()
                    dates.feed((output / relative).read_text())
                    self.assertEqual([published], dates.values)

    def test_removed_theme_features_do_not_render(self):
        """Tags, TOC and the last-updated stamp stay off even when requested."""
        with tempfile.TemporaryDirectory() as directory:
            output = render_fixture(
                directory,
                'title = "Feature fixture"\ndate = 2024-02-29T14:23:45+01:00\n'
                'lastmod = 2025-06-01T09:08:07-04:00\ntags = ["fixture-tag"]\ntoc = true\n',
                env={"HUGO_PARAMS_SHOWLASTUPDATED": "true", "HUGO_PARAMS_TOC": "true"},
            )
            # Markers: the tag/TOC classes and the theme post-lastmod prefix. The theme
            # comments partial is only an HTML comment, which html/template strips.
            for relative in FIXTURE_PAGES:
                markup = (output / relative).read_text()
                for marker in ("post-tags", "table-of-contents", "Updated:"):
                    with self.subTest(page=relative, marker=marker):
                        self.assertNotIn(marker, markup)



@unittest.skipUnless(shutil.which("hugo") and (ROOT / "themes/terminal/layouts").is_dir(),
                     "Hugo and the theme submodule are required for the render fixture")
class HugoXShortcodeTests(unittest.TestCase):
    """Render the real x shortcode and loader in a throwaway content dir."""

    def build(self, posts):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        temporary = Path(directory.name)
        for slug, body in posts.items():
            post = temporary / "content" / "posts" / slug
            post.mkdir(parents=True)
            (post / "index.md").write_text(
                f'+++\ntitle = "{slug}"\ndate = 2024-01-01T00:00:00Z\n+++\n\n## Heading\n\n{body}\n')
        output = temporary / "public"
        result = subprocess.run(
            ["hugo", "--source", str(ROOT), "--contentDir", str(temporary / "content"),
             "--destination", str(output), "--cleanDestinationDir"],
            capture_output=True, text=True,
        )
        return result, output

    def embed(self, user="some_user", id="42", name="Some <Name>", date="May 1, 2024",
              text='Hi <script>alert("x")</script> & bye\n\nNext <br> line'):
        return (f'{{{{< x user="{user}" id="{id}" name="{name}" date="{date}" >}}}}\n'
                f'{text}\n{{{{< /x >}}}}')

    def test_two_embeds_escape_text_and_share_one_loader(self):
        result, output = self.build({"two": self.embed() + "\n\n" + self.embed(), "none": "Plain."})
        self.assertEqual(0, result.returncode, result.stderr)
        two = (output / "posts" / "two" / "index.html").read_text()
        self.assertEqual(2, two.count('<blockquote class="twitter-tweet x-embed">'))
        self.assertEqual(1, two.count("platform.twitter.com/widgets.js"))
        self.assertIn("<script async src=\"https://platform.twitter.com/widgets.js\"", two)
        self.assertIn("Hi &lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt; &amp; bye<br><br>Next &lt;br&gt; line</p>", two)
        self.assertIn("&mdash; Some &lt;Name&gt; (@some_user) ", two)
        self.assertIn('<a href="https://twitter.com/some_user/status/42">May 1, 2024 · View on X</a>', two)
        self.assertNotIn("<script>alert", two)
        self.assertEqual([], check_build.check_x_embed_markup(two))
        none = (output / "posts" / "none" / "index.html").read_text()
        self.assertNotIn("widgets.js", none)

    def test_invalid_or_missing_values_fail_the_build(self):
        cases = {
            "old-unpaired-call": ('{{< x user="u" id="1" >}}', 'shortcode "x" must be closed'),
            "self-closed": ('{{< x user="u" id="1" name="N" date="D" />}}', "tweet text is required"),
            "blank-text": (self.embed(text="   "), "tweet text is required"),
            "handle-with-at": (self.embed(user="@u"), "user must be an X handle"),
            "path-in-user": (self.embed(user="u/../evil"), "user must be an X handle"),
            "non-numeric-id": (self.embed(id="12a"), "id must be the numeric status id"),
            "no-name": (self.embed(name=" "), "name (the author's display name) is required"),
            "no-date": (self.embed(date=""), "date (as X shows it"),
        }
        for slug, (body, message) in cases.items():
            with self.subTest(case=slug):
                result, _ = self.build({slug: body})
                self.assertNotEqual(0, result.returncode)
                self.assertIn(message, result.stderr)


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
