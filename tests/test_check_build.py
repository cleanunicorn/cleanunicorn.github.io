"""Regression tests for built HTML semantics and primary navigation."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

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

    def test_heading_with_two_links_fails(self):
        link = '<a class=hanchor href=#x aria-label="Link to this section">#</a>'
        self.assertEqual(["h2 has 2 heading links"], self.check(f"<h2 id=x>X{link}{link}</h2>"))
        self.assertEqual([], self.check(f"<h2 id=x>X{link}</h2><h3 id=y>Y{link}</h3>"))

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


class FeedTests(unittest.TestCase):
    ITEM = "<rss><channel><item><link>https://x/posts/a/</link>{}</item></channel></rss>"

    def check(self, description):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "index.xml").write_text(self.ITEM.format(description))
            return check_build.check_feeds(Path(directory))

    def test_plain_heading_passes(self):
        self.assertEqual([], self.check("<description>&lt;h2&gt;Intro&lt;/h2&gt;</description>"))

    def test_heading_permalink_in_feed_fails(self):
        self.assertEqual(["index.xml: heading permalinks leaked into the feed"], self.check(
            '<description>&lt;a href="#intro" class="hanchor"&gt;#&lt;/a&gt;</description>'))


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


def render_fixture(directory, front_matter=None, env=None, posts=None, pages=None, args=(),
                   body="## Fixture heading\n"):
    """Build the site from fixture content and return the output directory.

    `posts` maps post slugs to front matter (default: one "fixture" post with
    `front_matter`) and Markdown `body`; `pages` maps content-relative paths
    to whole files."""
    temporary = Path(directory)
    for slug, matter in (posts or {"fixture": front_matter}).items():
        post = temporary / "content" / "posts" / slug
        post.mkdir(parents=True)
        (post / "index.md").write_text(f"+++\n{matter}+++\n\n{body}")
    for relative, text in (pages or {}).items():
        (temporary / "content" / relative).write_text(text)
    output = temporary / "public"
    subprocess.run(
        ["hugo", "--source", str(ROOT), "--contentDir", str(temporary / "content"),
         "--destination", str(output), "--cleanDestinationDir", *args],
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

    def test_markdown_headings_link_to_themselves(self):
        """Posts and section pages (like About) both get heading permalinks."""
        with tempfile.TemporaryDirectory() as directory:
            section = Path(directory) / "content" / "notes"
            section.mkdir(parents=True)
            (section / "_index.md").write_text('+++\ntitle = "Notes"\n+++\n\n## Section heading\n')
            output = render_fixture(directory, 'title = "Anchor fixture"\n')
            for relative, anchor in (("posts/fixture/index.html", "fixture-heading"),
                                     ("notes/index.html", "section-heading")):
                with self.subTest(page=relative):
                    markup = (output / relative).read_text()
                    self.assertIn(f'id="{anchor}"', markup)
                    self.assertIn(f'<a href="#{anchor}" class="hanchor" '
                                  f'aria-label="Link to this section">#</a>', markup)
            feed = (output / "posts/index.xml").read_text()
            self.assertIn("Fixture heading", feed)
            self.assertNotIn("hanchor", feed)

    def test_heading_attributes_keep_one_id(self):
        """A {#custom} id drives the permalink; other attributes pass through."""
        with tempfile.TemporaryDirectory() as directory:
            output = render_fixture(directory, 'title = "Attribute fixture"\n',
                                    body="## Custom {#my-id}\n\n## Styled {.cls #styled}\n")
            markup = (output / "posts/fixture/index.html").read_text()
            self.assertEqual(1, markup.count('id="my-id"'))
            self.assertIn('<a href="#my-id" class="hanchor"', markup)
            self.assertEqual(1, markup.count('id="styled"'))
            self.assertIn('<h2 id="styled" class="cls">', markup)

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

    def test_posts_link_chronological_neighbours_and_end_with_cta(self):
        """Slugs sort opposite to dates; drafts are skipped; non-post pages stay clean."""
        posts = {
            "a-newest": 'title = "Newest"\ndate = 2024-03-01T09:00:00-05:00\n',
            "b-draft": 'title = "Draft"\ndate = 2023-06-01T00:00:00Z\ndraft = true\n',
            "c-middle": 'title = "Middle with a very long title that has to wrap on narrow screens"\ndate = 2023-01-01T23:30:00+09:00\n',
            "d-oldest": 'title = "Oldest"\ndate = 2022-12-31T15:00:00Z\n',
        }
        pages = {
            "contact.md": '+++\ntitle = "Connect"\nslug = "contact"\n+++\nHi\n',
            "previous-work.md": '+++\ntitle = "Work"\nslug = "work"\n+++\nWork\n',
        }
        with tempfile.TemporaryDirectory() as directory:
            output = render_fixture(directory, posts=posts, pages=pages, args=("--minify",))
            self.assertEqual([], check_build.check_post_navigation(ROOT, output))
            expected = {
                "d-oldest": {"newer": "/posts/c-middle/"},
                "c-middle": {"older": "/posts/d-oldest/", "newer": "/posts/a-newest/"},
                "a-newest": {"older": "/posts/c-middle/"},
            }
            self.assertFalse((output / "posts" / "b-draft").exists())
            for slug, want in expected.items():
                with self.subTest(post=slug):
                    parser = check_build.PostEndParser()
                    parser.feed((output / "posts" / slug / "index.html").read_text())
                    got = {link["data-direction"]: urlparse(link["href"]).path for link in parser.navs[0]["links"]}
                    self.assertEqual(want, got)
                    self.assertEqual(1, len(parser.ctas))
            for relative in ("index.html", "posts/index.html", "contact/index.html", "work/index.html", "404.html"):
                with self.subTest(page=relative):
                    parser = check_build.PostEndParser()
                    parser.feed((output / relative).read_text())
                    self.assertEqual(0, parser.markers)

    def test_single_post_has_cta_and_no_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = render_fixture(directory, 'title = "Alone"\ndate = 2024-01-01T00:00:00Z\n')
            parser = check_build.PostEndParser()
            parser.feed((output / "posts" / "fixture" / "index.html").read_text())
            self.assertEqual([], parser.navs)
            self.assertEqual(1, len(parser.ctas))


def post_html(older=None, newer=None, date="2024-01-01T00:00:00Z", cta=True, x="https://x.com/cleanunicorn"):
    """A built post page in the shape of layouts/partials/post-{nav,cta}.html."""
    links = ""
    if older:
        links += f'<li><a href="{older}" data-direction="older"><span aria-hidden="true">← </span>Older post <span>Old title</span></a></li>'
    if newer:
        links += f'<li><a href="{newer}" data-direction="newer">Newer post<span aria-hidden="true"> →</span> <span>New title</span></a></li>'
    nav = f'<nav class="post-nav" aria-labelledby="post-nav-title"><h2 id="post-nav-title">Read other posts</h2><ul>{links}</ul></nav>' if links else ""
    end = (
        '<aside class="post-cta" aria-labelledby="post-cta-title"><h2 id="post-cta-title">Thanks for reading</h2><ul>'
        f'<li><a href="{x}">Follow on X</a></li>'
        '<li><a href="https://cleanunicorn.github.io/index.xml" type="application/rss+xml">Subscribe via RSS</a></li>'
        '<li><a href="https://cleanunicorn.github.io/contact/">Get in touch</a></li></ul></aside>'
    ) if cta else ""
    return f'<article class="post post--article"><time class="post-date" datetime="{date}">x</time><div class="post-content"></div>{nav}{end}</article>'


class PostNavigationGuardTests(unittest.TestCase):
    """check_post_navigation on a synthetic public/ (#55)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.public = Path(self.tmp.name)
        for relative in ("index.html", "contact/index.html", "about/index.html"):
            self.write(relative, "<main></main>")
        self.write("index.xml", "<rss></rss>")
        self.pages = {
            "posts/one/index.html": post_html(newer="/posts/two/", date="2020-01-01T00:00:00Z"),
            "posts/two/index.html": post_html(older="/posts/one/", newer="/posts/three/", date="2021-01-01T00:00:00+02:00"),
            "posts/three/index.html": post_html(older="https://cleanunicorn.github.io/posts/two/", date="2022-01-01T00:00:00-03:00"),
        }

    def write(self, relative, html):
        path = self.public / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)

    def check(self, **changes):
        for relative, html in {**self.pages, **changes}.items():
            self.write(relative, html)
        return check_build.check_post_navigation(ROOT, self.public)

    def test_valid_site(self):
        self.assertEqual([], self.check())

    def test_minified_unquoted_attributes_and_no_li_end_tags(self):
        minified = {
            path: html.replace('class="post-nav"', "class=post-nav").replace('class="post-cta"', "class=post-cta")
            .replace('data-direction="older"', "data-direction=older").replace('data-direction="newer"', "data-direction=newer")
            .replace('type="application/rss+xml"', "type=application/rss+xml").replace("</li>", "")
            for path, html in self.pages.items()
        }
        self.assertEqual([], self.check(**minified))

    def test_list_pagination_page_is_not_a_post(self):
        self.assertEqual([], self.check(**{"posts/page/2/index.html": "<main></main>"}))

    def test_rejects_broken_shapes(self):
        cases = {
            "pre-change post without either block": {"posts/two/index.html": post_html(date="2021-01-01T00:00:00+02:00", cta=False)},
            "swapped directions": {"posts/two/index.html": post_html(older="/posts/three/", newer="/posts/one/", date="2021-01-01T00:00:00+02:00")},
            "older link on the oldest post": {"posts/one/index.html": post_html(older="/posts/three/", newer="/posts/two/", date="2020-01-01T00:00:00Z")},
            "skipped neighbour": {"posts/one/index.html": post_html(newer="/posts/three/", date="2020-01-01T00:00:00Z")},
            "missing CTA": {"posts/three/index.html": post_html(older="/posts/two/", date="2022-01-01T00:00:00-03:00", cta=False)},
            "wrong X URL": {"posts/one/index.html": post_html(newer="/posts/two/", date="2020-01-01T00:00:00Z", x="https://x.com/someone")},
            "missing RSS": {"posts/one/index.html": post_html(newer="/posts/two/", date="2020-01-01T00:00:00Z").replace(' type="application/rss+xml"', "")},
            "duplicate CTA": {"posts/one/index.html": post_html(newer="/posts/two/", date="2020-01-01T00:00:00Z").replace("</article>", '<aside class="post-cta"></aside></article>')},
            "unlabelled nav": {"posts/one/index.html": post_html(newer="/posts/two/", date="2020-01-01T00:00:00Z").replace(' aria-labelledby="post-nav-title"', "")},
            "direction word missing": {"posts/one/index.html": post_html(newer="/posts/two/", date="2020-01-01T00:00:00Z").replace("Newer post", "Next")},
            "dead neighbour link": {"posts/three/index.html": post_html(older="/posts/gone/", date="2022-01-01T00:00:00-03:00")},
            "leak onto about": {"about/index.html": post_html(cta=True)},
            "invalid date": {"posts/one/index.html": post_html(newer="/posts/two/", date="soon")},
        }
        for name, changes in cases.items():
            with self.subTest(name):
                self.setUp()
                self.assertTrue(self.check(**changes))

    def test_dead_contact_target_fails(self):
        (self.public / "contact" / "index.html").unlink()
        self.assertTrue(self.check())

    def test_needs_two_posts(self):
        self.pages = {"posts/one/index.html": post_html(date="2020-01-01T00:00:00Z")}
        self.assertTrue(self.check())

    def test_refresh_alias_is_skipped(self):
        self.assertEqual([], self.check(**{"old/index.html": '<meta http-equiv=refresh content="0; url=/posts/one/"><nav class=post-nav></nav>'}))


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


CONSENT_HEAD = """<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('consent', 'default', {
    analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'
  });
  try { if (localStorage.getItem('consent.v1') === 'granted') { gtag('consent', 'update', { analytics_storage: 'granted' }); } } catch (e) {}
  gtag('js', new Date());
  gtag('config', 'G-42RTQLDG4M');
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-42RTQLDG4M"></script>"""
CONSENT_BODY = ('<section id=consent-banner class=consent role=region aria-labelledby=consent-title hidden>'
                '<h2 id=consent-title>Analytics</h2><button type=button>Accept</button>'
                '<button type=button>Reject</button></section>'
                '<button type=button id=consent-open hidden>Cookie settings</button>')


class ConsentTests(unittest.TestCase):
    def check(self, head=CONSENT_HEAD, body=CONSENT_BODY):
        return check_build.consent_violations(f"<head>{head}</head><body>{body}</body>")

    def test_good_page(self):
        self.assertEqual([], self.check())

    def test_config_before_default_fails(self):
        head = CONSENT_HEAD.replace("gtag('config', 'G-42RTQLDG4M');", "").replace(
            "gtag('consent', 'default'", "gtag('config', 'G-42RTQLDG4M');\n  gtag('consent', 'default'")
        self.assertIn("gtag config runs before the consent default", self.check(head))

    def test_loader_before_default_fails(self):
        loader = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-42RTQLDG4M"></script>'
        head = loader + CONSENT_HEAD.replace(loader, "")
        self.assertIn("gtag.js is requested before the consent default", self.check(head))

    def test_granted_default_fails(self):
        head = CONSENT_HEAD.replace("analytics_storage: 'denied'", "analytics_storage: 'granted'")
        failures = self.check(head)
        self.assertIn("consent default does not deny analytics_storage", failures)
        self.assertIn("consent default grants a signal", failures)

    def test_missing_signal_fails(self):
        head = CONSENT_HEAD.replace(" ad_user_data: 'denied',", "")
        self.assertEqual(["consent default does not deny ad_user_data"], self.check(head))

    def test_missing_default_fails(self):
        head = CONSENT_HEAD.replace("gtag('consent', 'default'", "gtag('set', 'default'")
        self.assertIn("no gtag consent default", self.check(head))

    def test_double_config_fails(self):
        self.assertIn("expected exactly one gtag config, found 2", self.check(CONSENT_HEAD + CONSENT_HEAD))

    def test_banner_contract(self):
        self.assertIn("consent banner is not hidden by default", self.check(body=CONSENT_BODY.replace(" hidden>", ">", 1)))
        self.assertIn("consent banner aria-labelledby does not name an element",
                      self.check(body=CONSENT_BODY.replace("id=consent-title", "id=other")))
        self.assertIn("consent banner has 1 buttons, expected 2",
                      self.check(body=CONSENT_BODY.replace("<button type=button>Reject</button>", "")))
        self.assertIn("no #consent-banner", self.check(body=""))

    def test_missing_cookie_settings_fails(self):
        body = CONSENT_BODY.replace("id=consent-open", "id=x")
        self.assertEqual(["no Cookie settings button"], self.check(body=body))


if __name__ == "__main__":
    unittest.main()
