import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
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

    def test_escaped_dollars_inside_tex_do_not_leak_markup(self):
        text = audio.narration_text("Title", r'<p>Cost is $\$1$.</p>')
        self.assertIn("Cost is Equation omitted. .", text)
        self.assertNotIn("$", text)
        self.assertNotIn("\\", text)


def settings(**overrides):
    return {
        'endpoint': 'http://127.0.0.1:8000/v1/audio/speech', 'api_key': 'test-secret',
        'model': 'drove-test-model', 'voice': 'test-voice', 'speed': 1.0,
        'timeout': 5.0, 'max_chars': 3500, 'extra': {}, **overrides,
    }


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = Path(self.directory.name) / '.env'
        self.base = 'AUDIO_API_URL=http://localhost:8000/v1/audio/speech\nAUDIO_MODEL=test\nAUDIO_VOICE=alloy\n'

    def test_reads_dotenv_and_environment_overrides(self):
        self.env.write_text(self.base + '''export AUDIO_API_KEY="secret with spaces # inside"
AUDIO_EXTRA_PARAMS='{"instructions":"Speak calmly", "language":"en"}' # comment
AUDIO_SPEED=1.2
''')
        actual = audio.load_settings(self.env, {'AUDIO_MODEL': 'overridden'})
        self.assertEqual(actual['api_key'], 'secret with spaces # inside')
        self.assertEqual(actual['extra'], {'instructions': 'Speak calmly', 'language': 'en'})
        self.assertEqual(actual['model'], 'overridden')
        self.assertEqual(actual['speed'], 1.2)

    def test_blank_key_for_self_hosted_endpoint(self):
        self.env.write_text(self.base + 'AUDIO_API_KEY=\n')
        self.assertEqual(audio.load_settings(self.env, {})['api_key'], '')

    def test_requires_explicit_endpoint_model_and_voice(self):
        for key in ('AUDIO_API_URL', 'AUDIO_MODEL', 'AUDIO_VOICE'):
            self.env.write_text('\n'.join(line for line in self.base.splitlines() if not line.startswith(key)))
            with self.subTest(key=key), self.assertRaises(ValueError):
                audio.load_settings(self.env, {})

    def test_rejects_invalid_configuration(self):
        for value in ('AUDIO_SPEED=nan', 'AUDIO_SPEED=0', 'AUDIO_MAX_INPUT_CHARS=-1',
                      'AUDIO_TIMEOUT_SECONDS=inf', "AUDIO_EXTRA_PARAMS='[]'",
                      "AUDIO_EXTRA_PARAMS='{}oops'", "AUDIO_EXTRA_PARAMS='{" + '"input":"override"' + "}'",
                      'AUDIO_API_URL=http://user:secret@localhost/speech'):
            self.env.write_text(self.base + value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                audio.load_settings(self.env, {})

    def test_no_shell_execution_or_interpolation(self):
        self.env.write_text(self.base + "AUDIO_API_KEY='$(touch should-not-exist)'\n")
        self.assertEqual(audio.load_settings(self.env, {})['api_key'], '$(touch should-not-exist)')
        self.assertFalse((self.env.parent / 'should-not-exist').exists())

    def test_credentials_and_timeout_do_not_change_audio_key(self):
        before = audio.cache_key(article(), settings())
        self.assertEqual(before, audio.cache_key(article(), settings(api_key='rotated', timeout=60)))
        for change in ({'voice': 'new'}, {'model': 'new'}, {'speed': 1.2}, {'extra': {'language': 'fr'}}, {'endpoint': 'http://new/v1/audio/speech'}):
            self.assertNotEqual(before, audio.cache_key(article(), settings(**change)))


class ChunkTests(unittest.TestCase):
    def test_respects_limit_and_preserves_words(self):
        text = 'First short paragraph.\n\nSecond paragraph has a much longer explanation. End.'
        chunks = audio.split_text(text, 30)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 30 for chunk in chunks))
        self.assertEqual(' '.join(text.split()), ' '.join(' '.join(chunks).split()))

    def test_hard_splits_only_oversized_words(self):
        self.assertEqual(audio.split_text('abcdefghij', 4), ['abcd', 'efgh', 'ij'])
        self.assertEqual(audio.split_text('Hi.', 3500), ['Hi.'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires ffmpeg and ffprobe')
class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixture_dir.name) / 'tone.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1', '-y', str(cls.fixture)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.settings = settings()
        self.calls = []

    def respond(self, text, config, output):
        self.calls.append(text)
        shutil.copyfile(self.fixture, output)

    def test_generates_playable_mp3_and_reuses_committed_output(self):
        item = article()
        with patch.object(audio, 'speech_request', side_effect=self.respond):
            manifest = audio.generate([item], self.settings, self.root)
            shutil.rmtree(self.root / '.cache')
            audio.generate([item], settings(api_key='new-key'), self.root)
        self.assertEqual(len(self.calls), 1)
        saved = (self.root / 'data/article_audio.json').read_text()
        self.assertNotIn('test-secret', saved)
        self.assertEqual(json.loads(saved), manifest)
        self.assertTrue(audio.valid_audio(self.root / 'static' / manifest[item['key']]['url'].lstrip('/')))

    def test_plan_does_not_write_or_request_audio(self):
        with patch.object(audio, 'speech_request') as request:
            audio.generate([article()], self.settings, self.root, plan=True)
        request.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_failure_preserves_published_manifest_and_files(self):
        with patch.object(audio, 'speech_request', side_effect=self.respond):
            audio.generate([article()], self.settings, self.root)
        previous = (self.root / 'data/article_audio.json').read_bytes()
        previous_files = list((self.root / 'static/audio').glob('*.mp3'))
        changed = article(html='<p>Updated content.</p>')
        with patch.object(audio, 'speech_request', side_effect=ValueError('API unavailable')):
            with self.assertRaises(ValueError):
                audio.generate([changed], self.settings, self.root)
        self.assertEqual(previous, (self.root / 'data/article_audio.json').read_bytes())
        self.assertEqual(previous_files, list((self.root / 'static/audio').glob('*.mp3')))
        self.assertFalse((self.root / '.cache/article-audio' / (audio.cache_key(changed, self.settings) + '.mp3')).exists())

    def test_resumes_chunks_and_assembles_valid_mp3(self):
        config = settings(max_chars=25)
        item = article(html='<p>First short paragraph.</p><p>Second short paragraph.</p>')
        calls = []
        def fail_second(text, config, output):
            calls.append(text)
            if len(calls) == 2:
                output.write_bytes(b'partial')
                raise ValueError('interrupted')
            shutil.copyfile(self.fixture, output)
        with patch.object(audio, 'speech_request', side_effect=fail_second):
            with self.assertRaises(ValueError):
                audio.generate([item], config, self.root)
        self.assertEqual(len(list((self.root / '.cache/article-audio/chunks').glob('*.mp3'))), 1)
        chunks = audio.split_text(audio.narration_text(item['title'], item['html']), 25)
        with patch.object(audio, 'speech_request', side_effect=self.respond):
            manifest = audio.generate([item], config, self.root)
        self.assertEqual(len(self.calls), len(chunks) - 1)
        self.assertTrue(audio.valid_audio(self.root / 'static' / manifest[item['key']]['url'].lstrip('/')))

    def test_corrupt_cache_is_regenerated_and_removed_posts_are_pruned(self):
        item = article()
        cache = self.root / '.cache/article-audio'
        cache.mkdir(parents=True)
        (cache / (audio.cache_key(item, self.settings) + '.mp3')).write_bytes(b'broken')
        with patch.object(audio, 'speech_request', side_effect=self.respond):
            audio.generate([item], self.settings, self.root)
            audio.generate([], self.settings, self.root)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(list((self.root / 'static/audio').glob('*.mp3')), [])
        self.assertEqual(json.loads((self.root / 'data/article_audio.json').read_text()), {})

    def test_rejects_duplicate_or_bad_export_before_generation(self):
        for items in ([article(), article()], [{**article(), 'fingerprint': 'bad'}]):
            with self.assertRaises(ValueError):
                audio.generate(items, self.settings, self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def serve(self, status=200, response=None, headers=None):
        received = []
        content = self.fixture.read_bytes() if response is None else response
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(status)
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(content)
            def log_message(self, *args):
                pass
        try:
            server = HTTPServer(('127.0.0.1', 0), Handler)
        except PermissionError:
            self.skipTest('this sandbox cannot open local HTTP sockets; exercised in CI')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join()
        self.addCleanup(cleanup)
        return settings(endpoint=f'http://127.0.0.1:{server.server_port}/v1/audio/speech'), received

    def test_openai_http_contract_and_optional_auth(self):
        config, received = self.serve()
        config['extra'] = {'instructions': 'Calm narration', 'language': 'en'}
        with patch.dict('os.environ', {'NO_PROXY': '127.0.0.1'}):
            audio.speech_request('Hello world.', config, self.root / 'out.mp3')
            audio.speech_request('No key.', {**config, 'api_key': ''}, self.root / 'other.mp3')
        path, headers, payload = received[0]
        self.assertEqual(path, '/v1/audio/speech')
        self.assertEqual(headers['Authorization'], 'Bearer test-secret')
        self.assertEqual(payload, {'model': config['model'], 'voice': config['voice'], 'input': 'Hello world.', 'speed': 1.0, 'response_format': 'mp3', 'instructions': 'Calm narration', 'language': 'en'})
        self.assertNotIn('Authorization', received[1][1])
        self.assertTrue(audio.valid_audio(self.root / 'out.mp3'))

    def test_http_errors_do_not_leak_server_body_or_key(self):
        config, received = self.serve(status=429, response=b'test-secret: provider error details')
        with patch.dict('os.environ', {'NO_PROXY': '127.0.0.1'}):
            with self.assertRaisesRegex(ValueError, 'HTTP 429') as error:
                audio.speech_request('Hello.', config, self.root / 'out.mp3')
        self.assertNotIn('test-secret', str(error.exception))
        self.assertEqual(len(received), 1)  # No potentially billable retries.

    def test_rejects_json_errors_returned_with_http_200(self):
        config, _ = self.serve(response=b'{"error":"not audio"}')
        with patch.dict('os.environ', {'NO_PROXY': '127.0.0.1'}):
            with self.assertRaisesRegex(ValueError, 'valid MP3'):
                audio.speech_request('Hello.', config, self.root / 'out.mp3')

    def test_does_not_forward_credentials_on_redirect(self):
        config, received = self.serve(status=302, headers={'Location': 'http://127.0.0.1:1/other'})
        with patch.dict('os.environ', {'NO_PROXY': '127.0.0.1'}):
            with self.assertRaisesRegex(ValueError, 'redirected'):
                audio.speech_request('Hello.', config, self.root / 'out.mp3')
        self.assertEqual(len(received), 1)


if __name__ == '__main__':
    unittest.main()
