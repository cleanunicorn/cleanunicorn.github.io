#!/usr/bin/env python3
"""Generate the Open Graph / social share card (static/og-image.png).

Produces a 1200x630 branded card matching the site's terminal palette,
using the portrait at static/images/me.png. Requires Pillow.

This is a one-off design helper — the resulting PNG is committed as a
static asset, so CI does not need to run it.

Usage:
    python3 scripts/generate_og_image.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PORTRAIT = ROOT / "static" / "images" / "me.png"
OUTPUT = ROOT / "static" / "og-image.png"

W, H = 1200, 630
BG = (26, 23, 15)          # --background #1a170f
FG = (236, 234, 229)       # --foreground #eceae5
ACCENT = (238, 195, 94)    # --accent     #eec35e
MUTED = (160, 156, 146)

FONT_CANDIDATES = {
    "bold": [
        "/mnt/skills/examples/canvas-design/canvas-fonts/JetBrainsMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ],
    "regular": [
        "/mnt/skills/examples/canvas-design/canvas-fonts/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
}


def load_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def circular(img: Image.Image, size: int) -> Image.Image:
    img = ImageOps.fit(img.convert("RGBA"), (size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    img.putalpha(mask)
    return img


def fit_font(draw, text, kind, max_size, max_width):
    """Largest font of `kind` at which `text` fits within `max_width`."""
    size = max_size
    while size > 10:
        font = load_font(kind, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(kind, 10)


def main() -> None:
    card = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(card)

    # Accent bar down the left edge
    draw.rectangle((0, 0, 12, H), fill=ACCENT)

    margin = 80
    x = margin + 20

    # Portrait, circular with an amber ring, on the right
    if PORTRAIT.exists():
        size = 300
        ring = 6
        portrait = circular(Image.open(PORTRAIT), size)
        px = W - margin - size
        py = (H - size) // 2
        draw.ellipse(
            (px - ring, py - ring, px + size + ring, py + size + ring),
            outline=ACCENT, width=ring,
        )
        card.paste(portrait, (px, py), portrait)
        text_right = px - 55
    else:
        text_right = W - margin

    avail = text_right - x

    f_eyebrow = load_font("regular", 26)
    f_name = fit_font(draw, "DANIEL LUCA", "bold", 92, avail)
    sub_text = "Security Researcher · Investor · Builder"
    f_sub = fit_font(draw, sub_text, "regular", 34, avail)

    proof_lines = [
        "Audited Uniswap · Aave · Filecoin · Polygon",
        "ConsenSys Diligence · Eden Block · DEF CON",
    ]
    f_proof = load_font("regular", 24)
    for line in proof_lines:
        f_proof = min(f_proof, fit_font(draw, line, "regular", 24, avail),
                      key=lambda f: f.size)

    # Text block
    draw.text((x, 150 - 44), "// cleanunicorn", font=f_eyebrow, fill=ACCENT)
    draw.text((x, 150), "DANIEL LUCA", font=f_name, fill=FG)
    draw.text((x, 275), sub_text, font=f_sub, fill=FG)

    yy = 365
    for line in proof_lines:
        draw.text((x, yy), line, font=f_proof, fill=MUTED)
        yy += 38

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    card.save(OUTPUT, "PNG")
    print(f"OG image written to {OUTPUT} ({W}x{H})")


if __name__ == "__main__":
    main()
