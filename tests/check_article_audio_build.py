"""Exercise both Hugo passes with fixture MP3s; never deploy these test files."""

from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("article_audio", ROOT / "scripts/generate_article_audio.py")
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class PlayerParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.players = []
        self.sources = []
        self.downloads = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "audio":
            self.players.append(attrs)
        if tag == "source" and attrs.get("type") == "audio/mpeg":
            self.sources.append(attrs["src"])
        if tag == "a" and "download" in attrs:
            self.downloads.append(attrs["href"])


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "site"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "public", "node_modules", ".cache", "__pycache__", "article_audio.json", "audio"))
    for name, extra in (("audio-test-draft", "draft = true"), ("audio-test-future", 'date = "2999-01-01"')):
        (root / "content/posts" / (name + ".md")).write_text(f'+++\ntitle = "{name}"\n{extra}\n+++\nShould not be narrated.\n')

    def build():
        subprocess.run(["hugo", "--source", str(root), "--destination", str(root / "public"), "--minify", "--cleanDestinationDir"], check=True)

    build()
    articles = json.loads((root / "public/narration.json").read_text())["articles"]
    assert articles, "No published articles exported"
    assert all("audio-test" not in a["key"] for a in articles), "Draft/future content was exported"
    fixture = root / "fixture.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.1", "-y", str(fixture)], check=True)
    real_run = subprocess.run
    calls = []

    def synthesize(command, **kwargs):
        if command[0] != "cathy":
            return real_run(command, **kwargs)
        calls.append(command)
        shutil.copyfile(fixture, command[command.index("-o") + 1])
        return subprocess.CompletedProcess(command, 0)

    with patch.object(audio.subprocess, "run", side_effect=synthesize):
        manifest = audio.generate(articles, audio.load_settings(), root)
        audio.generate(articles, audio.load_settings(), root)
    assert len(calls) == len(articles), "Unchanged articles were regenerated"
    build()
    for item in articles:
        parser = PlayerParser()
        parser.feed((root / "public" / item["url"].strip("/") / "index.html").read_text())
        assert len(parser.players) == 1, f"Missing/duplicate player: {item['key']}"
        player = parser.players[0]
        assert "controls" in player and "autoplay" not in player and player.get("preload") == "none"
        assert player.get("aria-label"), "Player needs a label"
        url = manifest[item["key"]]["url"]
        assert parser.sources == [url] and url in parser.downloads
        assert audio.valid_audio(root / "public" / url.lstrip("/")), "MP3 missing from final build"
    for entry in manifest.values():
        entry["fingerprint"] = "stale"
    (root / "data/article_audio.json").write_text(json.dumps(manifest))
    build()
    for item in articles:
        parser = PlayerParser()
        parser.feed((root / "public" / item["url"].strip("/") / "index.html").read_text())
        assert not parser.players, "Stale narration was shown"
    print(f"Article audio build check passed for {len(articles)} published articles.")
