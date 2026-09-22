"""Unit tests for scripts/generate_cv.py. Run with `make test`."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_cv  # noqa: E402


HUGO_TOML = """\
title = "Not the name"

[languages.en]
  title = "Ada Lovelace"

  [languages.en.params]
    subtitle = "Builder | Hacker"
    # subtitle = "Investor | Builder"
"""


class ParseConfigTest(unittest.TestCase):
    """parse_config reads TOML keys, not the lines the old scanner matched."""

    def parse(self, document):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "hugo.toml"
            config.write_text(document)
            with mock.patch.object(generate_cv, "CONFIG", config):
                return generate_cv.parse_config()

    def test_reads_the_language_title_and_subtitle(self):
        self.assertEqual(
            self.parse(HUGO_TOML), {"name": "Ada Lovelace", "subtitle": "Builder | Hacker"}
        )

    def test_a_missing_subtitle_raises(self):
        with self.assertRaises(KeyError):
            self.parse(HUGO_TOML.replace('    subtitle = "Builder | Hacker"\n', ""))

    def test_a_missing_title_raises(self):
        with self.assertRaises(KeyError):
            self.parse(HUGO_TOML.replace('  title = "Ada Lovelace"\n', ""))

    def test_the_real_config_has_both_values(self):
        config = generate_cv.parse_config()
        self.assertTrue(config["name"].strip())
        self.assertTrue(config["subtitle"].strip())


class ParseSkillsTest(unittest.TestCase):
    def test_every_category_has_a_label_and_items(self):
        skills = generate_cv.parse_skills()
        self.assertTrue(skills)
        for label, items in skills:
            with self.subTest(label=label):
                self.assertTrue(label.strip())
                self.assertTrue(items)


if __name__ == "__main__":
    unittest.main()
