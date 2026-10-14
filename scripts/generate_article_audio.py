#!/usr/bin/env python3
"""Generate article MP3s from Hugo's published-content export using Cathy."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts/article_audio.toml"
BLOCKS = {"p", "div", "blockquote", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "figcaption"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP = {"pre", "script", "style", "svg", "math", "sup", "audio", "video", "iframe"}


class NarrationParser(HTMLParser):
    """Keep prose and link labels, with paragraph pauses and no embedded UI."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []

    @property
    def skipping(self):
        return bool(self.stack and self.stack[-1][1])

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        skip = self.skipping or tag in SKIP or attrs.get("aria-hidden") == "true" or bool(
            classes & {"hanchor", "heading-anchor", "footnotes", "footnote-ref", "footnote-backref", "mermaid"}
        )
        if not self.skipping and tag == "pre":
            self.parts.append("\n\nCode block omitted.\n\n")
        if not skip:
            if tag in BLOCKS or tag in {"br", "hr"}:
                self.parts.append("\n\n")
            elif tag in {"td", "th"}:
                self.parts.append(" ")
            elif tag == "img" and attrs.get("alt", "").strip():
                self.parts.append("\n\nImage: " + attrs["alt"] + ".\n\n")
        if tag not in VOID:
            self.stack.append((tag, skip))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        was_skipping = self.skipping
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if not was_skipping and tag in BLOCKS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.skipping:
            # HTML source line wrapping is not a paragraph boundary.
            self.parts.append(re.sub(r"\s+", " ", data))


def narration_text(title, html):
    parser = NarrationParser()
    # Goldmark passthrough leaves TeX delimiters in the rendered HTML.
    html = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]", " Equation omitted. ", html, flags=re.S)
    html = re.sub(r"(?<!\\)\$[^$\n]+\$|\\\(.*?\\\)", " Equation omitted. ", html)
    parser.feed(html)
    parser.close()
    paragraphs = [re.sub(r"[ \t]+", " ", p).strip() for p in "".join(parser.parts).split("\n\n")]
    return title.strip() + "\n\n" + "\n\n".join(p for p in paragraphs if p) + "\n"


def load_settings(path=CONFIG):
    settings = tomllib.loads(path.read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", settings["cathy_ref"]):
        raise ValueError("cathy_ref must be a full commit SHA")
    if settings["engine"] != "kokoro" or not settings["voice"].strip() or settings["speed"] <= 0:
        raise ValueError("Expected Kokoro, a voice, and a positive speed")
    return settings


def fingerprint(article):
    return hashlib.sha256((article["title"] + "\n" + article["html"]).encode()).hexdigest()


def cache_key(article, settings):
    payload = {
        "source": fingerprint(article),
        "settings": settings,
        "generator": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def valid_audio(path):
    if not path.is_file() or not path.stat().st_size:
        return False
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return False
    try:
        info = json.loads(result.stdout)
        return info["streams"][0]["codec_name"] == "mp3" and float(info["format"]["duration"]) > 0
    except (KeyError, IndexError, ValueError, TypeError):
        return False


def generate(articles, settings, root=ROOT, plan=False):
    cache = root / ".cache/article-audio"
    manifest = {}
    pending = []
    seen = set()
    # Validate the complete export before spending time synthesizing.
    for article in articles:
        key = article["key"]
        if key in seen or article["fingerprint"] != fingerprint(article):
            raise ValueError(f"Duplicate key or invalid fingerprint: {key}")
        seen.add(key)
        digest = cache_key(article, settings)
        path = cache / (digest + ".mp3")
        cached = valid_audio(path)
        print(f"{'Reuse' if cached else 'Generate'}: {article['title']}", flush=True)
        pending.append((article, path, cached))
        manifest[key] = {"fingerprint": article["fingerprint"], "url": "/audio/" + path.name}
    if plan:
        return manifest
    cache.mkdir(parents=True, exist_ok=True)
    for article, path, cached in pending:
        if cached:
            continue
        # A failed Cathy run never becomes a reusable cache entry.
        with tempfile.TemporaryDirectory(dir=cache) as work:
            text = Path(work) / "article.txt"
            audio = Path(work) / "article.mp3"
            text.write_text(narration_text(article["title"], article["html"]), encoding="utf-8")
            subprocess.run([
                "cathy", str(text), "-o", str(audio), "-e", settings["engine"],
                "-v", settings["voice"], "-s", str(settings["speed"]), "--all",
            ], check=True)
            if not valid_audio(audio):
                raise ValueError(f"Cathy did not produce a valid MP3 for {article['key']}")
            audio.replace(path)
    # Publish metadata only after every article succeeded. Files are content-addressed.
    output = root / "static/audio"
    output.mkdir(parents=True, exist_ok=True)
    for _, path, _ in pending:
        shutil.copyfile(path, output / path.name)
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    temporary = data / "article_audio.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(data / "article_audio.json")
    # Only generated MP3s are pruned, after the complete manifest is written.
    current = {path.name for _, path, _ in pending}
    for path in output.glob("*.mp3"):
        if re.fullmatch(r"[0-9a-f]{64}\.mp3", path.name) and path.name not in current:
            path.unlink()
    print(f"Audio ready for {len(manifest)} published articles.")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "public/narration.json")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--plan", action="store_true", help="report cache hits without generating or writing files")
    parser.add_argument("--print-cathy-source", action="store_true")
    args = parser.parse_args()
    try:
        settings = load_settings(args.config)
        if args.print_cathy_source:
            print("git+https://github.com/cleanunicorn/cathy@" + settings["cathy_ref"])
            return 0
        articles = json.loads(args.input.read_text(encoding="utf-8"))["articles"]
        generate(articles, settings, plan=args.plan)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"article-audio: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
