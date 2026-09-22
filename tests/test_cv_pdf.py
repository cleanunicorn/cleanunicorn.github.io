"""Tests for `make cv-pdf`: it must fail whenever no PDF comes out (#48).

Each case runs the real Makefile recipe with STATIC_DIR pointed at a temp
directory and a stand-in browser passed as CHROME, so nothing in the working
tree is written and no real browser is needed. Run with `make test`.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKE = shutil.which("make")

WRITES_PDF = """#!/bin/sh
for arg in "$@"; do
  case "$arg" in --print-to-pdf=*) printf '%%PDF-1.4 stand-in' > "${arg#--print-to-pdf=}" ;; esac
done
"""
WRITES_NOTHING = "#!/bin/sh\nexit 0\n"
FAILS = "#!/bin/sh\nexit 3\n"


@unittest.skipUnless(MAKE, "make is not installed")
class CvPdfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.pdf = self.tmp / "cv.pdf"

    def browser(self, script):
        path = self.tmp / "browser"
        path.write_text(script)
        path.chmod(0o755)
        return path

    def make(self, *args, path=None):
        env = {k: v for k, v in os.environ.items() if k != "CHROME"}
        if path is not None:
            env["PATH"] = path
        return subprocess.run(
            [MAKE, "-s", "-C", str(ROOT), "cv-pdf", f"STATIC_DIR={self.tmp}", *args],
            env=env, capture_output=True, text=True,
        )

    def test_writes_the_pdf(self):
        result = self.make(f"CHROME={self.browser(WRITES_PDF)}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(self.pdf.stat().st_size, 0)

    def test_fails_when_the_browser_writes_nothing(self):
        result = self.make(f"CHROME={self.browser(WRITES_NOTHING)}")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("was not produced", result.stderr)
        self.assertFalse(self.pdf.exists())

    def test_a_stale_pdf_does_not_count(self):
        self.pdf.write_text("stale")
        result = self.make(f"CHROME={self.browser(WRITES_NOTHING)}")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.pdf.exists())

    def test_fails_when_the_browser_fails(self):
        result = self.make(f"CHROME={self.browser(FAILS)}")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.pdf.exists())

    def test_fails_with_no_browser_on_path(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "python3").symlink_to(sys.executable)
        result = self.make(path=str(bin_dir))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("need chromium or google-chrome", result.stderr)
        self.assertFalse(self.pdf.exists())


if __name__ == "__main__":
    unittest.main()
