#!/usr/bin/env python3
"""Generate a CV from the website content files.

Reads markdown content from the Hugo site and produces a standalone,
print-ready HTML file. No external dependencies beyond Python 3 stdlib.

Content comes from the site (content/about/_index.md, content/previous-work.md,
data/skills.toml); data/cv.toml holds the CV-only bits — the location and how
work history splits into Experience / earlier / Education.

Usage:
    python3 scripts/generate_cv.py                  # writes to public/cv.html
    python3 scripts/generate_cv.py -o resume.html   # custom output path
"""

import argparse
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
ABOUT_MD = CONTENT / "about" / "_index.md"
WORK_MD = CONTENT / "previous-work.md"
CONFIG = ROOT / "hugo.toml"
CSS_PATH = ROOT / "static" / "css" / "cv.css"
SKILLS_PATH = ROOT / "data" / "skills.toml"
CV_CONFIG_PATH = ROOT / "data" / "cv.toml"

SITE_URL = "https://cleanunicorn.github.io"

# Feather-style stroke icons for the contact row, keyed by the link text we
# expect from the About intro.
ICONS = {
    "globe": (
        '<circle cx="12" cy="12" r="10"></circle>'
        '<line x1="2" y1="12" x2="22" y2="12"></line>'
        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 '
        '15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>'
    ),
    "github": (
        '<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 '
        '6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 '
        '2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 '
        '5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>'
    ),
    "linkedin": (
        '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4V8h4v1.5A6 '
        '6 0 0 1 16 8z"></path><rect x="2" y="9" width="4" height="12"></rect>'
        '<circle cx="4" cy="4" r="2"></circle>'
    ),
    "twitter": (
        '<path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 '
        '0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 '
        '7.72 0 0 0 23 3z"></path>'
    ),
    "map-pin": (
        '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>'
        '<circle cx="12" cy="10" r="3"></circle>'
    ),
}


def icon(name: str) -> str:
    """Render a 12x12 inline stroke icon, or nothing if the name is unknown."""
    path = ICONS.get(name)
    if not path:
        return ""
    return (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{path}</svg>'
    )


def icon_for(text: str, url: str) -> str:
    """Pick a contact icon from a link's text and target."""
    haystack = f"{text} {url}".lower()
    for key in ("github", "linkedin"):
        if key in haystack:
            return key
    if "x.com" in haystack or "twitter" in haystack:
        return "twitter"
    return "globe"


# ---------------------------------------------------------------------------
# TOML
# ---------------------------------------------------------------------------

def load_toml(path: Path) -> dict:
    """Parse a TOML file, or return {} if it is missing or tomllib is absent."""
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return {}
    return tomllib.loads(text)


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    """Strip Hugo TOML frontmatter (the leading `+++ … +++` block). Does not
    handle `+++` appearing inside the body."""
    m = re.match(r"^\+\+\+.*?\+\+\+\s*", text, re.DOTALL)
    return text[m.end():] if m else text


def inline_md(text: str) -> str:
    """Convert inline markdown (bold, italic, links, code) to HTML."""
    # escape HTML entities first (but preserve existing tags from processing)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # links [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # bold **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    # italic *text*
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    # inline code `text`
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)

    # Hugo relref shortcodes — replace with #
    text = re.sub(r'\{\{&lt;\s*relref\s+"[^"]*"\s*&gt;\}\}', "#", text)

    return text


def paragraphs_html(md: str, class_attr: str = "") -> str:
    """Render blank-line-separated markdown paragraphs as <p> elements."""
    cls = f' class="{class_attr}"' if class_attr else ""
    md = re.sub(r"^---+\s*$", "", md, flags=re.MULTILINE)  # horizontal rules
    blocks = [b.strip() for b in re.split(r"\n\s*\n", md) if b.strip()]
    return "\n".join(
        f"<p{cls}>{inline_md(' '.join(b.split(chr(10))))}</p>" for b in blocks
    )


def extract_section(md: str, heading: str) -> str:
    """Extract a section from markdown by heading name (## level)."""
    pattern = rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def list_items(md: str) -> list[str]:
    """Return the top-level `- ` bullet lines in a markdown block."""
    return re.findall(r"^-\s+(.*)$", md, re.MULTILINE)


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


def parse_about() -> dict:
    """Parse about.md into structured sections."""
    body = strip_frontmatter(ABOUT_MD.read_text())

    # Bio is everything before the first ## heading
    bio_match = re.match(r"^(.*?)(?=^##\s)", body, re.MULTILINE | re.DOTALL)
    bio = bio_match.group(1).strip() if bio_match else ""

    # The intro carries a one-line "Download my CV — or find me on …" row.
    # Pull the social links out of it for the header, and drop the line from
    # the bio (a "download this CV" link is meaningless inside the CV itself).
    contact: list[tuple[str, str]] = []
    cv_line_re = re.compile(r"^.*Download (?:my )?CV.*$", re.MULTILINE)
    cv_line = cv_line_re.search(bio)
    if cv_line:
        for text, url in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", cv_line.group(0)):
            if "cv.pdf" in url.lower() or "download" in text.lower():
                continue
            contact.append((text, url))
        bio = cv_line_re.sub("", bio).strip()

    return {
        "bio": bio,
        "contact": contact,
        "talks": extract_section(body, "Talks"),
        "podcasts": extract_section(body, "Podcasts"),
        "projects": extract_section(body, "Projects"),
    }


def parse_roles() -> list[dict]:
    """Parse previous-work.md into structured role entries.

    Each `## Title, Organisation` block carries an italic date line, a
    description, and optionally a lead-in line ending in `:` followed by a
    bullet list (portfolio companies, selected audits).
    """
    body = strip_frontmatter(WORK_MD.read_text())
    roles: list[dict] = []

    for m in re.finditer(r"^##\s+(.*?)\s*$(.*?)(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL):
        heading = m.group(1).strip()
        rest = re.sub(r"\n---+\s*", "\n", m.group(2)).strip()

        # "Founder, Security Researcher, Akira Tech" -> title + org
        if "," in heading:
            title, org = heading.rsplit(",", 1)
            title, org = title.strip(), org.strip()
        else:
            title, org = heading, ""

        # Italic date line, optionally with a "· Parent Company" suffix.
        dates = ""
        date_m = re.match(r"^\*(.+?)\*\s*$", rest, re.MULTILINE)
        if date_m:
            dates = date_m.group(1).strip()
            rest = rest[date_m.end():].strip()
            if "·" in dates:
                head, tail = dates.rsplit("·", 1)
                # A trailing "· ConsenSys" names the parent, not another date.
                if not re.search(r"\d{4}", tail):
                    dates = head.strip()
                    org = f"{org} ({tail.strip()})" if org else tail.strip()

        # A bullet list at the end, introduced by a "Something:" line.
        items = list_items(rest)
        list_label = ""
        if items:
            rest = re.sub(r"^-\s+.*$", "", rest, flags=re.MULTILINE)
            label_m = re.search(r"^([^\n]*?):\s*$", rest.strip(), re.MULTILINE)
            if label_m:
                list_label = label_m.group(1).strip().lower()
                rest = rest[: label_m.start()].strip()

        roles.append({
            "title": title,
            "org": org,
            "dates": dates,
            "desc": re.sub(r"\n\s*\n\s*\n+", "\n\n", rest).strip(),
            "list_label": list_label,
            "list": items,
        })

    return roles


def parse_skills() -> list[tuple[str, list[str]]]:
    """Parse data/skills.toml into ordered (category, items) pairs."""
    data = load_toml(SKILLS_PATH) or _parse_skills_fallback(
        SKILLS_PATH.read_text() if SKILLS_PATH.exists() else ""
    )

    results: list[tuple[str, list[str]]] = []
    for key, val in data.items():
        if not isinstance(val, dict):
            continue
        results.append((val.get("label", key.replace("_", " ")), val.get("items", [])))
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


def split_media(entry: str, with_venue: bool) -> tuple[str, str, str]:
    """Split a talk/podcast bullet into (year, venue, title_html).

    Entries read "[2025 ETHCluj - Beyond …](url)"; the year and venue are both
    optional ("[BlockchainHackers IV - Mastering …]", "[2022 Onchain games]").
    """
    m = re.match(r"^\[([^\]]+)\]\(([^)]+)\)\s*$", entry.strip())
    label, url = (m.group(1), m.group(2)) if m else (entry.strip(), "")

    year = ""
    ym = re.match(r"^(\d{4})\s+(.*)$", label)
    if ym:
        year, label = ym.group(1), ym.group(2)

    venue = ""
    if with_venue:
        vm = re.match(r"^(.*?)\s+[-–]\s+(.*)$", label)
        if vm:
            venue, label = vm.group(1).strip(), vm.group(2).strip()

    title = html.escape(label)
    if url:
        title = f'<a href="{html.escape(url)}">{title}</a>'
    return year, html.escape(venue), title


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def short_label(label: str, overrides: dict) -> str:
    """Shorten a list lead-in ("Worked closely with portfolio companies such
    as:") into a run-in tag ("portfolio:"). Lead-ins with no override are kept
    only if they are already short enough to read as a tag."""
    for needle, short in overrides.items():
        if needle.lower() in label.lower():
            return short
    return label if len(label) <= 24 else ""


def build_entry(role: dict, label_overrides: dict) -> str:
    org = (
        f' <span class="entry-org">· {inline_md(role["org"])}</span>'
        if role["org"] else ""
    )
    parts = [
        '<div class="entry">',
        '<div class="entry-head">',
        f'<div class="entry-title">{inline_md(role["title"])}{org}</div>',
        f'<div class="entry-dates">{html.escape(role["dates"])}</div>',
        '</div>',
    ]
    if role["desc"]:
        parts.append(paragraphs_html(role["desc"]))
    if role["list"]:
        tag = short_label(role["list_label"], label_overrides)
        label = (
            f'<span class="entry-list-label">{html.escape(tag)}:</span> ' if tag else ""
        )
        items = " · ".join(inline_md(i) for i in role["list"])
        parts.append(f'<p class="entry-list">{label}{items}</p>')
    parts.append("</div>")
    return "\n".join(parts)


def role_summary(desc: str, org: str) -> str:
    """Trim a role description down to what the person actually did.

    Older entries open by introducing the company ("Lendia was a company
    aggregating lending offers…"); in a one-line summary that sentence spends
    the whole line on context. Drop it when something else remains.
    """
    sentences = [s.strip() for s in re.split(r"(?<=\.)\s+", desc) if s.strip()]
    if org:
        first_word = org.split()[0].lower()
        kept = [s for s in sentences if not s.lower().startswith(first_word)]
        if kept:
            sentences = kept
    return " ".join(sentences)


def build_earlier(roles: list[dict]) -> str:
    if not roles:
        return ""
    rows = []
    for r in roles:
        org = f' · {inline_md(r["org"])}' if r["org"] else ""
        # One line each: these roles predate the work the CV is really about,
        # so keep what he did and drop the sentence introducing the company.
        desc = role_summary(r["desc"].split("\n\n")[0] if r["desc"] else "", r["org"])
        desc = f" — {inline_md(desc)}" if desc else ""
        rows.append(
            f'<div class="earlier-entry">'
            f'<div><strong>{inline_md(r["title"])}</strong>{org}{desc}</div>'
            f'<div class="earlier-dates">{html.escape(r["dates"])}</div>'
            f'</div>'
        )
    return (
        '<div class="earlier">\n<div class="earlier-label">// earlier</div>\n'
        + "\n".join(rows)
        + "\n</div>"
    )


def build_skills(skills: list[tuple[str, list[str]]]) -> str:
    groups = []
    for category, items in skills:
        tags = "".join(
            f'<span class="skill-tag">{html.escape(item)}</span>' for item in items
        )
        groups.append(
            f'<div class="skill-group">'
            f'<span class="skill-category">{html.escape(category)}</span>'
            f'<div class="skill-tags">{tags}</div>'
            f'</div>'
        )
    return "\n".join(groups)


def build_projects(projects_md: str) -> str:
    """Render the About page's `### [Name](url)` project blocks as cards."""
    entries = []
    for m in re.finditer(
        r"###\s+\[([^\]]+)\]\(([^)]+)\)\s*\n(.+?)(?=###|\Z)", projects_md, re.DOTALL
    ):
        name, url = m.group(1), m.group(2)
        desc = re.sub(r"\n---+\s*$", "", m.group(3)).strip().replace("\n", " ")
        entries.append(
            f'<li><a href="{html.escape(url)}">{html.escape(name)}</a> &mdash; '
            f"{inline_md(desc)}</li>"
        )
    return "<ul>\n" + "\n".join(entries) + "\n</ul>" if entries else ""


def build_media(md: str, with_venue: bool) -> str:
    rows = []
    for entry in list_items(md):
        # Drop indented sub-items like "  - [Slides](...)" — handled by the
        # top-level-only regex in list_items, but skip empties defensively.
        if not entry.strip():
            continue
        year, venue, title = split_media(entry, with_venue)
        venue_html = f'<span class="media-venue">{venue}</span> &mdash; ' if venue else ""
        rows.append(
            f'<div class="media-entry">'
            f'<div class="media-year">{html.escape(year)}</div>'
            f'<div>{venue_html}{title}</div>'
            f'</div>'
        )
    return "\n".join(rows)


def build_education(notes: list[dict], roles: list[dict]) -> str:
    parts = []
    for note in notes:
        parts.append(
            f'<p><strong>{html.escape(str(note.get("title", "")))}</strong> &mdash; '
            f'{inline_md(str(note.get("body", "")))}</p>'
        )
    for r in roles:
        heading = f'{r["title"]}, {r["org"]}' if r["org"] else r["title"]
        dates = f' <em>({html.escape(r["dates"])})</em>' if r["dates"] else ""
        desc = r["desc"].split("\n\n")[0] if r["desc"] else ""
        parts.append(
            f'<p><strong>{inline_md(heading)}</strong>{dates} &mdash; {inline_md(desc)}</p>'
        )
    return "\n".join(parts)


def section(class_name: str, heading: str, content: str) -> str:
    """Wrap content in a titled <section>, or return nothing if it is empty."""
    if not content:
        return ""
    return f'<section class="{class_name}">\n<h2>{heading}</h2>\n{content}\n</section>'


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def generate_html(output: Path) -> None:
    """Assemble and write the CV HTML file."""
    config = parse_config()
    about = parse_about()
    roles = parse_roles()
    cv_config = load_toml(CV_CONFIG_PATH)
    exp_config = cv_config.get("experience", {})

    def bucket(role: dict) -> str:
        """Route a role to experience / earlier / education by organisation."""
        haystack = f'{role["title"]} {role["org"]}'
        for name in exp_config.get("education", []):
            if name.lower() in haystack.lower():
                return "education"
        for name in exp_config.get("earlier", []):
            if name.lower() in haystack.lower():
                return "earlier"
        return "experience"

    main_roles = [r for r in roles if bucket(r) == "experience"]
    earlier_roles = [r for r in roles if bucket(r) == "earlier"]
    edu_roles = [r for r in roles if bucket(r) == "education"]

    css = CSS_PATH.read_text() if CSS_PATH.exists() else ""

    # Header contact row — social links from the About intro, plus the site
    # and the location from data/cv.toml.
    contact_bits = []
    for text, url in [*about["contact"], ("cleanunicorn.github.io", SITE_URL)]:
        contact_bits.append(
            f'<a href="{html.escape(url)}">{icon(icon_for(text, url))}'
            f'{html.escape(text)}</a>'
        )
    if cv_config.get("location"):
        contact_bits.append(
            f'<span>{icon("map-pin")}{html.escape(cv_config["location"])}</span>'
        )

    label_overrides = cv_config.get("list_labels", {})
    experience = "\n".join(build_entry(r, label_overrides) for r in main_roles)
    if earlier_roles:
        experience += "\n" + build_earlier(earlier_roles)

    sections = [
        f'<section class="bio">\n{paragraphs_html(about["bio"])}\n</section>'
        if about["bio"] else "",
        section("work", "Experience", experience),
        section("skills", "Skills", build_skills(parse_skills())),
        section("projects", "Selected Projects", build_projects(about["projects"])),
        section("talks", "Talks &amp; Presentations",
                build_media(about["talks"], with_venue=True)),
        section("podcasts", "Podcasts",
                build_media(about["podcasts"], with_venue=False)),
        section("education", "Education &amp; Community",
                build_education(cv_config.get("education_notes", []), edu_roles)),
    ]
    body = "\n\n".join(s for s in sections if s)

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
  <div class="sheet">
    <header>
      <h1>{html.escape(config["name"])}</h1>
      <p class="subtitle">{html.escape(config["subtitle"])}</p>
      <nav class="contact">{"".join(contact_bits)}</nav>
    </header>

    <main>
{body}
    </main>
  </div>
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
