import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("article_audio", ROOT / "scripts/generate_article_audio.py")
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


def article(key="posts/example/index.md", html="<p>Hello world.</p>"):
    item = {"key": key, "title": "Example", "html": html}
    item["fingerprint"] = audio.fingerprint(item)
    return item


class ExtractionTests(unittest.TestCase):
    def test_narrates_prose_not_code_embeds_or_heading_links(self):
        html = '''<h2>Section<a class="hanchor" href="#section">#</a></h2>
        <p>Hello <strong>world</strong>, <a href="https://example.org">read this</a>.
        More prose &amp; detail.<sup class="footnote-ref">1</sup></p>
        <pre><code>dangerous raw code</code></pre>
        <div class="mermaid">raw diagram markup</div>
        <img src="image.png" alt="A useful diagram"><img src="decoration.png" alt="">
        <script>embedded script</script><iframe>embedded UI</iframe>
        <div class="footnotes"><p>Footnote navigation</p></div>'''
        text = audio.narration_text("Title", html)
        self.assertTrue(text.startswith("Title\n\nSection\n\n"))
        self.assertIn("Hello world, read this. More prose & detail.", text)
        self.assertIn("Code block omitted.", text)
        self.assertIn("Image: A useful diagram.", text)
        for unwanted in ("#", "dangerous", "markup", "embedded", "Footnote", "example.org", "decoration"):
            self.assertNotIn(unwanted, text)

    def test_omits_tex_but_keeps_inline_code_and_paragraphs(self):
        text = audio.narration_text("Title", r'<p>Use <code>foo()</code>.</p><p>$$\sum_i x_i$$</p><p>$x^2$ and \(y\).</p>')
        self.assertIn("Use foo().\n\n", text)
        self.assertEqual(text.count("Equation omitted."), 3)
        self.assertNotIn("sum", text)

    def test_handles_void_tags_inside_skipped_blocks(self):
        text = audio.narration_text("Title", '<pre>skip<br>still skip</pre><p>Keep<br>this.</p>')
        self.assertNotIn("still skip", text)
        self.assertIn("Keep\n\nthis.", text)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires ffmpeg and ffprobe")
class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixture_dir.name) / "tone.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.1", "-y", str(cls.fixture)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.settings = audio.load_settings()
        self.real_run = subprocess.run
        self.calls = []

    def synthesize(self, command, **kwargs):
        if command[0] != "cathy":
            return self.real_run(command, **kwargs)
        self.calls.append(command)
        self.assertIn("Hello world.", Path(command[1]).read_text())
        shutil.copyfile(self.fixture, command[command.index("-o") + 1])
        return subprocess.CompletedProcess(command, 0)

    def test_generates_playable_mp3_and_reuses_cache(self):
        item = article()
        with patch.object(audio.subprocess, "run", side_effect=self.synthesize):
            manifest = audio.generate([item], self.settings, self.root)
            audio.generate([item], self.settings, self.root)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("--all", self.calls[0])
        saved = json.loads((self.root / "data/article_audio.json").read_text())
        self.assertEqual(saved, manifest)
        self.assertTrue(audio.valid_audio(self.root / "static" / manifest[item["key"]]["url"].lstrip("/")))

    def test_changed_text_or_settings_invalidates_cache(self):
        item = article()
        digest = audio.cache_key(item, self.settings)
        self.assertNotEqual(digest, audio.cache_key(article(html="<p>Changed.</p>"), self.settings))
        self.assertNotEqual(digest, audio.cache_key(item, {**self.settings, "voice": "am_adam"}))

    def test_plan_does_not_write_or_synthesize(self):
        with patch.object(audio.subprocess, "run") as run:
            audio.generate([article()], self.settings, self.root, plan=True)
        run.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_failure_preserves_manifest_and_never_caches_partial_audio(self):
        with patch.object(audio.subprocess, "run", side_effect=self.synthesize):
            audio.generate([article()], self.settings, self.root)
        previous = (self.root / "data/article_audio.json").read_bytes()
        def fail(command, **kwargs):
            if command[0] == "cathy":
                Path(command[command.index("-o") + 1]).write_bytes(b"partial")
                raise subprocess.CalledProcessError(1, command)
            return self.real_run(command, **kwargs)
        changed = article(html="<p>Updated content.</p>")
        with patch.object(audio.subprocess, "run", side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                audio.generate([changed], self.settings, self.root)
        self.assertEqual(previous, (self.root / "data/article_audio.json").read_bytes())
        self.assertFalse((self.root / ".cache/article-audio" / (audio.cache_key(changed, self.settings) + ".mp3")).exists())

    def test_corrupt_cache_is_regenerated_and_removed_posts_are_pruned(self):
        item = article()
        cache = self.root / ".cache/article-audio"
        cache.mkdir(parents=True)
        (cache / (audio.cache_key(item, self.settings) + ".mp3")).write_bytes(b"broken")
        with patch.object(audio.subprocess, "run", side_effect=self.synthesize):
            audio.generate([item], self.settings, self.root)
            audio.generate([], self.settings, self.root)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(list((self.root / "static/audio").glob("*.mp3")), [])
        self.assertEqual(json.loads((self.root / "data/article_audio.json").read_text()), {})

    def test_rejects_duplicate_or_bad_export_before_generation(self):
        for items in ([article(), article()], [{**article(), "fingerprint": "bad"}]):
            with self.assertRaises(ValueError):
                audio.generate(items, self.settings, self.root)
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
