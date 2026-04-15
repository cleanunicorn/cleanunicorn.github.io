#!/usr/bin/env python3
"""Generate a CV from the website content files.

Reads markdown content from the Hugo site and produces a standalone,
print-ready HTML file. No external dependencies beyond Python 3 stdlib.

Usage:
    python3 scripts/generate_cv.py                  # writes to public/cv.html
    python3 scripts/generate_cv.py -o resume.html   # custom output path
"""

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
ABOUT_MD = CONTENT / "about" / "about.md"
WORK_MD = CONTENT / "previous-work.md"
CONFIG = ROOT / "hugo.toml"
CSS_PATH = ROOT / "static" / "css" / "cv.css"
SKILLS_PATH = ROOT / "data" / "skills.toml"


# ---------------------------------------------------------------------------
# Markdown / frontmatter helpers
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    """Remove TOML (+++) frontmatter from markdown."""
    m = re.match(r"^\+\+\+.*?\+\+\+\s*", text, re.DOTALL)
    return text[m.end():] if m else text


def md_to_html(md: str) -> str:
    """Minimal markdown-to-HTML converter (covers what we need)."""
    lines = md.split("\n")
    out: list[str] = []
    in_ul = False

    for line in lines:
        stripped = line.strip()

        # skip empty lines
        if not stripped:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append("")
            continue

        # headings
        hm = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if hm:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            level = len(hm.group(1))
            content = inline_md(hm.group(2))
            out.append(f"<h{level}>{content}</h{level}>")
            continue

        # horizontal rule
        if re.match(r"^---+\s*$", stripped):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            continue  # skip hrs in CV

        # unordered list (- or *)
        lm = re.match(r"^[-*]\s+(.*)", stripped)
        if lm:
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"  <li>{inline_md(lm.group(1))}</li>")
            continue

        # paragraph
        if in_ul:
            out.append("</ul>")
            in_ul = False
        out.append(f"<p>{inline_md(stripped)}</p>")

    if in_ul:
        out.append("</ul>")

    return "\n".join(out)


def inline_md(text: str) -> str:
    """Convert inline markdown (bold, italic, links, code) to HTML."""
    # escape HTML entities first (but preserve existing tags from processing)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # links [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )

    # bold **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    # italic *text*
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    # inline code `text`
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)

    # Hugo relref shortcodes — replace with #
    text = re.sub(r'\{\{&lt;\s*relref\s+"[^"]*"\s*&gt;\}\}', "#", text)

    return text


# ---------------------------------------------------------------------------
# Content extractors
# ---------------------------------------------------------------------------

def parse_config() -> dict:
    """Extract name and subtitle from hugo.toml."""
    text = CONFIG.read_text()
    name = ""
    subtitle = ""
    for line in text.split("\n"):
        if "title =" in line and not name:
            name = line.split("=", 1)[1].strip().strip('"')
        if "subtitle =" in line:
            subtitle = line.split("=", 1)[1].strip().strip('"')
    return {"name": name, "subtitle": subtitle}


def extract_section(md: str, heading: str) -> str:
    """Extract a section from markdown by heading name (## level)."""
    pattern = rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_about() -> dict:
    """Parse about.md into structured sections."""
    raw = ABOUT_MD.read_text()
    body = strip_frontmatter(raw)

    # Bio is everything before the first ## heading
    bio_match = re.match(r"^(.*?)(?=^##\s)", body, re.MULTILINE | re.DOTALL)
    bio = bio_match.group(1).strip() if bio_match else ""

    return {
        "bio": bio,
        "talks": extract_section(body, "Talks"),
        "podcasts": extract_section(body, "Podcasts"),
        "projects": extract_section(body, "Projects"),
        "links": extract_section(body, "Links"),
    }


def parse_work() -> str:
    """Parse previous-work.md and return the body."""
    raw = WORK_MD.read_text()
    return strip_frontmatter(raw)


def parse_skills() -> list[tuple[str, list[str]]]:
    """Parse data/skills.toml into ordered (category, items) pairs.

    Uses a minimal TOML parser (stdlib tomllib in 3.11+, fallback regex).
    """
    if not SKILLS_PATH.exists():
        return []

    text = SKILLS_PATH.read_text()

    # Try stdlib tomllib (Python 3.11+)
    try:
        import tomllib
        data = tomllib.loads(text)
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
            data = tomllib.loads(text)
        except ImportError:
            # Fallback: simple regex parser for our known format
            data = _parse_skills_fallback(text)

    results: list[tuple[str, list[str]]] = []
    for key, val in data.items():
        if isinstance(val, dict):
            label = val.get("label", key.replace("_", " "))
            items = val.get("items", [])
        else:
            continue
        results.append((label, items))
    return results


def _parse_skills_fallback(text: str) -> dict:
    """Regex-based TOML parser for simple [Section] + items = [...] format."""
    data: dict = {}
    current: str | None = None
    for line in text.split("\n"):
        line = line.strip()
        hm = re.match(r"^\[(\w+)\]", line)
        if hm:
            current = hm.group(1)
            data[current] = {"items": []}
            continue
        if current and line.startswith("label"):
            m = re.match(r'label\s*=\s*"([^"]*)"', line)
            if m:
                data[current]["label"] = m.group(1)
        if current and '"' in line and "items" not in line and "label" not in line:
            for m in re.finditer(r'"([^"]+)"', line):
                data[current]["items"].append(m.group(1))
    return data


def build_skills_html(skills: list[tuple[str, list[str]]]) -> str:
    """Render skills as grouped pill/tag lists."""
    if not skills:
        return ""
    groups: list[str] = []
    for category, items in skills:
        tags = "".join(
            f'<span class="skill-tag">{html.escape(item)}</span>'
            for item in items
        )
        groups.append(
            f'<div class="skill-group">'
            f'<span class="skill-category">{html.escape(category)}</span>'
            f'<div class="skill-tags">{tags}</div>'
            f'</div>'
        )
    return "\n".join(groups)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def build_projects_html(projects_md: str) -> str:
    """Render projects section as a compact list instead of individual headings."""
    entries: list[str] = []
    for m in re.finditer(
        r"###\s+\[([^\]]+)\]\(([^)]+)\)\s*\n(.+?)(?=###|\Z)",
        projects_md,
        re.DOTALL,
    ):
        name, url = m.group(1), m.group(2)
        desc = re.sub(r"\n---+\s*$", "", m.group(3)).strip()
        entries.append(
            f'<li><a href="{html.escape(url)}">'
            f"<strong>{html.escape(name)}</strong></a> &mdash; "
            f"{inline_md(desc)}</li>"
        )
    if entries:
        return "<ul>\n" + "\n".join(entries) + "\n</ul>"
    return md_to_html(projects_md)


def build_work_html(work_md: str) -> str:
    """Render work history with clean formatting."""
    # Split into individual job sections by ## headings
    sections = re.split(r"(?=^##\s)", work_md, flags=re.MULTILINE)
    parts: list[str] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Remove --- separators
        section = re.sub(r"\n---+\s*", "", section)

        parts.append(md_to_html(section))

    return "\n".join(parts)


def generate_html(output: Path) -> None:
    """Assemble and write the CV HTML file."""
    config = parse_config()
    about = parse_about()
    work_md = parse_work()

    # Read CSS
    css = CSS_PATH.read_text() if CSS_PATH.exists() else ""

    sections = []

    # Bio
    if about["bio"]:
        sections.append(f'<section class="bio">\n{md_to_html(about["bio"])}\n</section>')

    # Contact / Links — strip the "Download CV" entry (self-referential in the CV)
    if about["links"]:
        links_md = re.sub(r"^- \[Download CV.*\n?", "", about["links"], flags=re.MULTILINE)
        sections.append(
            f'<section class="links">\n<h2>Contact</h2>\n{md_to_html(links_md)}\n</section>'
        )

    # Skills
    skills = parse_skills()
    if skills:
        sections.append(
            f'<section class="skills">\n<h2>Skills</h2>\n{build_skills_html(skills)}\n</section>'
        )

    # Work experience
    if work_md:
        sections.append(
            f'<section class="work">\n<h2>Experience</h2>\n{build_work_html(work_md)}\n</section>'
        )

    # Talks
    if about["talks"]:
        # Remove the intro sentence if present
        talks_md = re.sub(r"^Sometimes.*?\n\n", "", about["talks"], flags=re.DOTALL)
        # Remove indented sub-items (e.g. "  - [Slides](...)")
        talks_md = re.sub(r"\n\s+-\s+\[Slides\].*", "", talks_md)
        sections.append(
            f'<section class="talks">\n<h2>Talks &amp; Presentations</h2>\n{md_to_html(talks_md)}\n</section>'
        )

    # Podcasts
    if about["podcasts"]:
        podcasts_md = re.sub(r"^Or I am.*?\n\n", "", about["podcasts"], flags=re.DOTALL)
        sections.append(
            f'<section class="podcasts">\n<h2>Podcasts</h2>\n{md_to_html(podcasts_md)}\n</section>'
        )

    # Projects
    if about["projects"]:
        sections.append(
            f'<section class="projects">\n<h2>Projects</h2>\n{build_projects_html(about["projects"])}\n</section>'
        )

    body = "\n\n".join(sections)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CV &mdash; {html.escape(config["name"])}</title>
  <style>
{css}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(config["name"])}</h1>
    <p class="subtitle">{html.escape(config["subtitle"])}</p>
  </header>

  <main>
{body}
  </main>

  <footer>
    <p>Generated from <a href="https://cleanunicorn.github.io">cleanunicorn.github.io</a></p>
  </footer>
</body>
</html>
"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc)
    print(f"CV written to {output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CV from website content")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "public" / "cv.html",
        help="Output HTML file path (default: public/cv.html)",
    )
    args = parser.parse_args()
    generate_html(args.output)


if __name__ == "__main__":
    main()
