"""Unit tests for scripts/generate_cv.py. Run with `make test`."""

import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_cv  # noqa: E402


class ParseConfigTest(unittest.TestCase):
    def test_reads_name_and_subtitle_from_hugo_toml(self):
        en = tomllib.loads((ROOT / "hugo.toml").read_text())["languages"]["en"]
        config = generate_cv.parse_config()
        self.assertEqual(config, {"name": en["title"], "subtitle": en["params"]["subtitle"]})
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
