"""KaTeX build checks must accept both regular and Hugo-minified output."""

import tempfile
import unittest
from pathlib import Path

from scripts.check_build import check_math_rendering


class MathBuildCheckTest(unittest.TestCase):
    def render_call(self, quote: str, yes: str, no: str) -> str:
        pairs = (("$$", "$$", yes), ("$", "$", no),
                 (r"\\[", r"\\]", yes), (r"\\(", r"\\)", no))
        options = ",".join(
            f"{{left:{quote}{left}{quote},right:{quote}{right}{quote},display:{display}}}"
            for left, right, display in pairs
        )
        return ("renderMathInElement(document.body,{delimiters:["
                + options + f"],throwOnError:{no}}})")

    def check_page(self, script: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text('<meta name="math-enabled" content="true">'
                            '<script src="contrib/auto-render.min.js"></script><script>'
                            + script + '</script>')
            return check_math_rendering(Path(directory))

    def test_regular_and_minified_pages(self):
        for quote, yes, no in (("'", "true", "false"), ('"', "!0", "!1")):
            with self.subTest(quote=quote, yes=yes):
                call = self.render_call(quote, yes, no)
                self.assertEqual([], self.check_page(call))
                self.assertTrue(any("expected one KaTeX render call" in failure
                                    for failure in self.check_page(call + ";" + call)))
                self.assertTrue(any("missing KaTeX throwOnError" in failure
                                    for failure in self.check_page(call.replace("throwOnError", "unused"))))
                self.assertTrue(any("missing KaTeX delimiter" in failure
                                    for failure in self.check_page(call.replace("left:", "unused:", 1))))

    def test_a_math_page_missing_the_loader_among_valid_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            (public / "valid.html").write_text(
                '<meta name="math-enabled" content="true">'
                '<script src="contrib/auto-render.min.js"></script><script>'
                + self.render_call("'", "true", "false") + '</script>')
            (public / "missing.html").write_text('<meta name="math-enabled" content="true">')
            self.assertTrue(any("missing.html" in failure for failure in check_math_rendering(public)))

    def test_options_outside_the_render_call_do_not_count(self):
        for quote, yes, no in (("'", "true", "false"), ('"', "!0", "!1")):
            with self.subTest(quote=quote, yes=yes):
                call = self.render_call(quote, yes, no)
                unrelated = (f"</script><script>const unrelated={{throwOnError:{no},"
                             f"delimiters:[{{left:{quote}$${quote},right:{quote}$${quote},"
                             f"display:{yes}}}]}}")
                wrong_error = call.replace(f"throwOnError:{no}", f"throwOnError:{yes}")
                self.assertTrue(any("missing KaTeX throwOnError" in failure
                                    for failure in self.check_page(wrong_error + unrelated)))
                wrong_delimiter = call.replace(f"left:{quote}$${quote}", f"left:{quote}nope{quote}")
                self.assertTrue(any("missing KaTeX delimiter" in failure
                                    for failure in self.check_page(wrong_delimiter + unrelated)))


if __name__ == "__main__":
    unittest.main()
