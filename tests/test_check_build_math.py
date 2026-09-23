"""KaTeX build checks must accept both regular and Hugo-minified output."""

import tempfile
import unittest
from pathlib import Path

from scripts.check_build import check_math_rendering


class MathBuildCheckTest(unittest.TestCase):
    def check_page(self, script: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text('<script src="contrib/auto-render.min.js"></script><script>'
                            + script + '</script>')
            return check_math_rendering(Path(directory))

    def test_regular_and_minified_pages(self):
        for quote, yes, no in (("'", "true", "false"), ('"', "!0", "!1")):
            with self.subTest(quote=quote, yes=yes):
                pairs = (("$$", "$$", yes), ("$", "$", no),
                         (r"\\[", r"\\]", yes), (r"\\(", r"\\)", no))
                options = ",".join(
                    f"{{left:{quote}{left}{quote},right:{quote}{right}{quote},display:{display}}}"
                    for left, right, display in pairs
                )
                call = ("renderMathInElement(document.body,{delimiters:["
                        + options + f"],throwOnError:{no}}})")
                self.assertEqual([], self.check_page(call))
                self.assertTrue(any("expected one KaTeX render call" in failure
                                    for failure in self.check_page(call + ";" + call)))
                self.assertTrue(any("missing KaTeX throwOnError" in failure
                                    for failure in self.check_page(call.replace("throwOnError", "unused"))))
                self.assertTrue(any("missing KaTeX delimiter" in failure
                                    for failure in self.check_page(call.replace("left:", "unused:", 1))))


if __name__ == "__main__":
    unittest.main()
