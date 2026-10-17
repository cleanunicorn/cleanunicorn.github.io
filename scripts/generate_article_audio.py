#!/usr/bin/env python3
"""Generate article MP3s from Hugo's published-content export using an OpenAI-compatible speech API."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
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
    html = re.sub(r"(?<!\\)\$(?:\\.|[^$\\\n])+\$|\\\(.*?\\\)", " Equation omitted. ", html)
    parser.feed(html)
    parser.close()
    paragraphs = [re.sub(r"[ \t]+", " ", p).strip() for p in "".join(parser.parts).split("\n\n")]
    return title.strip() + "\n\n" + "\n\n".join(p for p in paragraphs if p) + "\n"


def load_settings(path=ENV_FILE, environ=None):
    """Read simple dotenv assignments without evaluating shell code."""
    values = {}
    if path.is_file():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"(?:export\s+)?([A-Za-z_]\w*)\s*=(.*)", line)
            if not match:
                raise ValueError(f"{path.name}:{number}: expected KEY=value")
            values[match[1]] = " ".join(shlex.split(match[2], comments=True))
    values.update(os.environ if environ is None else environ)
    endpoint = values.get("AUDIO_API_URL", "").strip()
    url = parse.urlsplit(endpoint)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError("Set AUDIO_API_URL to a full HTTP(S) speech endpoint in .env")
    model = values.get("AUDIO_MODEL", "").strip()
    voice = values.get("AUDIO_VOICE", "").strip()
    if not model or not voice:
        raise ValueError("Set AUDIO_MODEL and AUDIO_VOICE in .env")
    speed = float(values.get("AUDIO_SPEED", "1.0"))
    timeout = float(values.get("AUDIO_TIMEOUT_SECONDS", "300"))
    max_chars = int(values.get("AUDIO_MAX_INPUT_CHARS", "3500"))
    if not math.isfinite(speed) or speed <= 0 or not math.isfinite(timeout) or timeout <= 0 or max_chars <= 0:
        raise ValueError("Audio speed, timeout, and maximum input length must be positive")
    extra = json.loads(values.get("AUDIO_EXTRA_PARAMS", "{}"))
    if not isinstance(extra, dict) or extra.keys() & {"input", "model", "voice", "speed", "response_format"}:
        raise ValueError("AUDIO_EXTRA_PARAMS must be a JSON object without reserved speech fields")
    return {
        "endpoint": endpoint, "api_key": values.get("AUDIO_API_KEY", ""),
        "model": model, "voice": voice, "speed": speed,
        "timeout": timeout, "max_chars": max_chars, "extra": extra,
    }


def fingerprint(article):
    return hashlib.sha256((article["title"] + "\n" + article["html"]).encode()).hexdigest()


def synthesis_settings(settings):
    # Rotating credentials or changing a timeout must not regenerate narration.
    return {key: settings[key] for key in ("endpoint", "model", "voice", "speed", "max_chars", "extra")}


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def cache_key(article, settings):
    return digest({
        "source": fingerprint(article), "settings": synthesis_settings(settings),
        "generator": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })


def split_text(text, limit):
    """Prefer paragraph/sentence/word boundaries; hard-split only oversized words."""
    chunks = []
    remaining = text.strip()
    while len(remaining) > limit:
        window = remaining[:limit + 1]
        cut = window.rfind("\n\n", 0, limit + 1)
        if cut < limit // 2:
            boundaries = list(re.finditer(r"(?<=[.!?])\s+", window))
            cut = boundaries[-1].start() if boundaries else -1
        if cut <= 0:
            cut = max(window.rfind(" ", 0, limit + 1), window.rfind("\n", 0, limit + 1))
        if cut <= 0:
            cut = limit
        chunk = remaining[:cut].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


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
        duration = float(info["format"]["duration"])
        return info["streams"][0]["codec_name"] == "mp3" and math.isfinite(duration) and duration > 0
    except (KeyError, IndexError, ValueError, TypeError):
        return False


class NoRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Speech API redirected the request; configure its final endpoint directly")


def speech_request(text, settings, output):
    payload = {
        **settings["extra"], "model": settings["model"], "voice": settings["voice"],
        "input": text, "speed": settings["speed"], "response_format": "mp3",
    }
    headers = {"Content-Type": "application/json", "Accept": "audio/mpeg"}
    if settings["api_key"]:
        headers["Authorization"] = "Bearer " + settings["api_key"]
    req = request.Request(settings["endpoint"], data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with request.build_opener(NoRedirects()).open(req, timeout=settings["timeout"]) as response:
            with output.open("wb") as target:
                shutil.copyfileobj(response, target)
    except error.HTTPError as failure:
        # Server error bodies and URLs can contain credentials; keep errors terse.
        raise ValueError(f"Speech API returned HTTP {failure.code}; check endpoint, credentials, model, and parameters") from None
    except (error.URLError, TimeoutError, OSError):
        raise ValueError("Speech API connection failed or timed out; check the endpoint and server") from None
    if not valid_audio(output):
        raise ValueError("Speech API did not return a valid MP3; check response_format support")


def synthesize(text, settings, destination, cache):
    chunks = split_text(text, settings["max_chars"])
    chunk_dir = cache / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, chunk in enumerate(chunks, 1):
        path = chunk_dir / (digest({"text": chunk, "settings": synthesis_settings(settings)}) + ".mp3")
        if not valid_audio(path):
            print(f"  Request chunk {index}/{len(chunks)}", flush=True)
            with tempfile.TemporaryDirectory(dir=cache) as work:
                temporary = Path(work) / "response.mp3"
                speech_request(chunk, settings, temporary)
                temporary.replace(path)
        paths.append(path)
    if len(paths) == 1:
        shutil.copyfile(paths[0], destination)
    else:
        with tempfile.TemporaryDirectory(dir=cache) as work:
            # Controlled relative filenames avoid quoting user paths in ffconcat.
            work = Path(work)
            for index, path in enumerate(paths):
                shutil.copyfile(path, work / f"{index}.mp3")
            playlist = work / "chunks.txt"
            playlist.write_text("".join(f"file '{index}.mp3'\n" for index in range(len(paths))))
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "concat", "-safe", "1", "-i", str(playlist),
                "-c:a", "copy", "-y", str(destination.resolve()),
            ], check=True)
    if not valid_audio(destination):
        raise ValueError("Could not assemble a valid article MP3")


def generate(articles, settings, root=ROOT, plan=False):
    cache = root / ".cache/article-audio"
    output = root / "static/audio"
    manifest = {}
    pending = []
    seen = set()
    for article in articles:
        key = article["key"]
        if key in seen or article["fingerprint"] != fingerprint(article):
            raise ValueError(f"Duplicate key or invalid fingerprint: {key}")
        seen.add(key)
        filename = cache_key(article, settings) + ".mp3"
        path = cache / filename
        published = output / filename
        # Committed files are reusable on a fresh checkout with no local cache.
        if valid_audio(published):
            path = published
        cached = valid_audio(path)
        text = narration_text(article["title"], article["html"])
        chunks = split_text(text, settings["max_chars"])
        print(f"{'Reuse' if cached else 'Generate'}: {article['title']} ({len(chunks)} chunks)", flush=True)
        pending.append((article, path, cached, text))
        manifest[key] = {"fingerprint": article["fingerprint"], "url": "/audio/" + filename}
    if plan:
        return manifest
    cache.mkdir(parents=True, exist_ok=True)
    for article, path, cached, text in pending:
        if cached:
            continue
        print(f"Narrating: {article['title']}", flush=True)
        with tempfile.TemporaryDirectory(dir=cache) as work:
            temporary = Path(work) / "article.mp3"
            synthesize(text, settings, temporary, cache)
            temporary.replace(path)
    # Publish metadata only after every article succeeded.
    output.mkdir(parents=True, exist_ok=True)
    for _, path, _, _ in pending:
        target = output / path.name
        if path != target:
            shutil.copyfile(path, target)
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    temporary = data / "article_audio.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(data / "article_audio.json")
    current = {path.name for _, path, _, _ in pending}
    for path in output.glob("*.mp3"):
        if re.fullmatch(r"[0-9a-f]{64}\.mp3", path.name) and path.name not in current:
            path.unlink()
    print(f"Audio ready for {len(manifest)} published articles.")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "public/narration.json")
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--plan", action="store_true", help="report cache hits without API requests or file writes")
    args = parser.parse_args()
    try:
        settings = load_settings(args.env_file)
        articles = json.loads(args.input.read_text(encoding="utf-8"))["articles"]
        generate(articles, settings, plan=args.plan)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as failure:
        print(f"article-audio: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
