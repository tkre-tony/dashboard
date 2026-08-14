#!/usr/bin/env python3
"""
mkcard.py — PropertyAtlas / TK Real Estate social card renderer.

Committed to tools/ per L-TOOL-1 so it survives container resets. Fetch fresh
each session:

    curl -sO https://raw.githubusercontent.com/tkre-tony/dashboard/main/tools/mkcard.py

Usage
-----
    python3 mkcard.py spec.json
    python3 mkcard.py -            # read spec from stdin
    python3 mkcard.py spec.json --out override.jpg

Three modes, one grid. See MODES below and mkcard_README.md for the schema.

Bindings honoured
-----------------
L-SOCIAL-2  1200x630 branded card is a mandatory named deliverable; carries a
            bottom-edge credit line.
L-SOCIAL-4  Where a card carries no photograph the credit takes the form
            "Illustration: PropertyAtlas" plus the data source.
L-FONT-1    Never fall back to ImageFont.load_default(). Assert the font path
            and fail loudly. Poppins ships Bold/Medium/Light/Regular/Italic.
L-SOCIAL-11 PropertyAtlas-published cards carry the PropertyAtlas mark, never
            the TKRE mark. TKRE is opt-in via "brand": "tkre".
L-SOCIAL-12 The photo credit mirrors the front-end treatment: italic,
            right-aligned, muted, in the form "<Subject>. Credit: <owner>."
"""

import json
import os
import sys
import textwrap
import urllib.request

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# Design tokens — locked to L-SOCIAL-2 (First REIT / Wee Hur / URA cards)
# --------------------------------------------------------------------------

W, H = 1200, 630

NAVY        = (15, 25, 45)
WASH_ALPHA  = 172
GOLD        = (200, 180, 140)
GOLD_SOLID  = (180, 155, 100)
WHITE       = (255, 255, 255)
MUTED       = (168, 178, 196)

# L-SOCIAL-13 — the credit line must stay legible at LinkedIn feed width, where
# a 1200x630 card renders around 550px across. 13px in MUTED failed that test on
# the published id:196 card (14 Aug 2026) and read as a grey smear. The credit is
# the only attribution the card carries, so it is sized to be read, not inferred.
CREDIT_SIZE = 17
CREDIT_MIN  = 14
CREDIT_INK  = (226, 232, 242)
CREDIT_SCRIM_ALPHA = 150

PAD_X       = 56
PAD_TOP     = 44
PAD_BOTTOM  = 40

FONT_DIR    = "/usr/share/fonts/truetype/google-fonts"
FONTS = {
    "bold":    f"{FONT_DIR}/Poppins-Bold.ttf",
    "medium":  f"{FONT_DIR}/Poppins-Medium.ttf",
    "regular": f"{FONT_DIR}/Poppins-Regular.ttf",
    "light":   f"{FONT_DIR}/Poppins-Light.ttf",
    "italic":  f"{FONT_DIR}/Poppins-Italic.ttf",
}

REPO_RAW = "https://raw.githubusercontent.com/tkre-tony/dashboard/main"
LOGO_URLS = {
    "pa_white":   f"{REPO_RAW}/assets/pa_logo_white.png",
    "pa_tile":    f"{REPO_RAW}/assets/pa_logo_tile.png",
    "tkre_white": f"{REPO_RAW}/assets/tkre_logo_white.png",
    "tkre_black": f"{REPO_RAW}/assets/tkre_logo_black.png",
}

# L-SOCIAL-11 — PropertyAtlas-published cards carry the PropertyAtlas mark.
# The TKRE mark is reserved for cards published by TK Real Estate (the weekly
# `summary` card, eyebrow "TK Real Estate"). Default is PropertyAtlas; the
# TKRE mark is opt-in via "brand": "tkre".
DEFAULT_BRAND = "propertyatlas"

MODES = ("article", "number", "summary")


# --------------------------------------------------------------------------
# Font loading — L-FONT-1: assert, never fall back
# --------------------------------------------------------------------------

def font(weight, size):
    """Load a Poppins face at `size`. Fails loudly if the file is absent."""
    path = FONTS.get(weight)
    if path is None:
        raise SystemExit(
            f"mkcard: unknown font weight {weight!r}; have {sorted(FONTS)}"
        )
    if not os.path.exists(path):
        raise SystemExit(
            f"mkcard: FONT MISSING {path}\n"
            f"  L-FONT-1 forbids silently falling back to load_default().\n"
            f"  Install the google-fonts package or correct FONT_DIR."
        )
    return ImageFont.truetype(path, size)


def preflight_fonts():
    missing = [p for p in FONTS.values() if not os.path.exists(p)]
    if missing:
        raise SystemExit(
            "mkcard: required Poppins faces not found:\n  "
            + "\n  ".join(missing)
        )


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

def text_w(draw, s, f):
    return draw.textbbox((0, 0), s, font=f)[2]


def wrap_to_width(draw, s, f, max_w):
    """Greedy wrap on whitespace. Returns a list of lines."""
    words, lines, cur = s.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if text_w(draw, trial, f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_lines(draw, s, weight, max_w, max_lines, size_hi, size_lo):
    """
    Shrink the face until the string wraps into <= max_lines.
    Returns (font, lines, size). Raises if it will not fit at size_lo.
    """
    for size in range(size_hi, size_lo - 1, -1):
        f = font(weight, size)
        lines = wrap_to_width(draw, s, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
    raise SystemExit(
        f"mkcard: text will not fit in {max_lines} lines at {size_lo}px:\n"
        f"  {s[:90]}...\n"
        f"  Shorten the string or raise max_lines."
    )


def draw_lines(draw, lines, f, x, y, fill, leading):
    for line in lines:
        draw.text((x, y), line, font=f, fill=fill)
        y += leading
    return y


# --------------------------------------------------------------------------
# Background
# --------------------------------------------------------------------------

def cover_fit(img, w, h):
    """Scale to fill and centre-crop. Never distorts."""
    src_w, src_h = img.size
    scale = max(w / src_w, h / src_h)
    new = img.resize((max(1, round(src_w * scale)), max(1, round(src_h * scale))),
                     Image.LANCZOS)
    left = (new.width - w) // 2
    top = (new.height - h) // 2
    return new.crop((left, top, left + w, top + h))


def build_background(spec):
    """
    Photo cover-fit under a navy wash, or flat navy when no photo is given.
    Returns (image, had_photo).
    """
    photo = spec.get("photo")
    if photo:
        if not os.path.exists(photo):
            raise SystemExit(f"mkcard: photo not found: {photo}")
        base = cover_fit(Image.open(photo).convert("RGB"), W, H)
        wash = Image.new("RGBA", (W, H), NAVY + (int(spec.get("wash", WASH_ALPHA)),))
        base = Image.alpha_composite(base.convert("RGBA"), wash).convert("RGB")
        return base, True
    return Image.new("RGB", (W, H), NAVY), False


# --------------------------------------------------------------------------
# Logo
# --------------------------------------------------------------------------

def load_logo(spec):
    """
    Resolve the TKRE mark. Local path wins; otherwise fetch from the repo so
    the script carries its own assets and cannot be orphaned again.
    """
    brand = (spec.get("brand") or DEFAULT_BRAND).strip().lower()
    if brand in ("pa", "propertyatlas"):
        key = "pa_tile" if spec.get("logo_ink") == "tile" else "pa_white"
    elif brand == "tkre":
        key = "tkre_black" if spec.get("logo_ink") == "black" else "tkre_white"
    else:
        raise SystemExit(
            f"mkcard: unknown brand {brand!r}; use \"propertyatlas\" or \"tkre\"."
        )
    local = spec.get("logo")
    if local:
        if not os.path.exists(local):
            raise SystemExit(f"mkcard: logo not found: {local}")
        return Image.open(local).convert("RGBA")
    cache = f"/tmp/mkcard_{key}.png"
    if not os.path.exists(cache):
        try:
            urllib.request.urlretrieve(LOGO_URLS[key], cache)
        except Exception as exc:
            raise SystemExit(
                f"mkcard: could not fetch {LOGO_URLS[key]} ({exc}).\n"
                f"  Pass \"logo\": \"<path>\" in the spec to use a local file."
            )
    return Image.open(cache).convert("RGBA")


def paste_logo(card, spec, box_h, xy):
    logo = load_logo(spec)
    ratio = logo.width / logo.height
    size = (max(1, round(box_h * ratio)), box_h)
    logo = logo.resize(size, Image.LANCZOS)
    card.paste(logo, xy, logo)
    return size


# --------------------------------------------------------------------------
# Shared chrome
# --------------------------------------------------------------------------

def draw_eyebrow(draw, spec):
    label = spec.get("eyebrow", "PROPERTYATLAS NEWSROOM").upper()
    f = font("bold", 15)
    draw.text((PAD_X, PAD_TOP), label, font=f, fill=GOLD)


def draw_pill(draw, label, x, y):
    """Gold rounded rect with navy text. Returns its width."""
    f = font("bold", 14)
    tw = text_w(draw, label.upper(), f)
    pad_x, pad_y = 16, 9
    w = tw + pad_x * 2
    h = 32
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=GOLD)
    draw.text((x + pad_x, y + pad_y - 1), label.upper(), font=f, fill=NAVY)
    return w


def draw_credit(draw, spec, had_photo):
    """
    Bottom-edge credit. Mandatory (L-SOCIAL-2). Where the card carries no
    photograph the wording must be the L-SOCIAL-4 illustration form.
    """
    credit = (spec.get("credit") or "").strip()
    if not credit:
        raise SystemExit(
            "mkcard: \"credit\" is required.\n"
            "  L-SOCIAL-2 — every card carries a bottom-edge credit line.\n"
            "  L-SOCIAL-4 — with no photograph use "
            "\"Illustration: PropertyAtlas \u00b7 Source: <data source>\"."
        )
    if not had_photo and not credit.lower().startswith("illustration"):
        raise SystemExit(
            "mkcard: card has no photograph, so L-SOCIAL-4 requires the credit "
            "to begin \"Illustration:\" and name the data source.\n"
            f"  got: {credit!r}"
        )
    if had_photo and not (
        credit.lower().startswith("photo:") or "credit:" in credit.lower()
    ):
        raise SystemExit(
            "mkcard: card carries a photograph, so the credit must attribute it "
            "— either the front-end form \"<Subject>. Credit: <owner>.\" "
            "(L-SOCIAL-12, preferred) or \"Photo: <owner>\".\n"
            f"  got: {credit!r}"
        )
    # L-SOCIAL-12 — mirror the front-end photo-credit treatment:
    # italic, right-aligned, sitting directly under the frame.
    # L-SOCIAL-13 — sized and backed so it survives feed-width downscaling.
    size = CREDIT_SIZE
    f = font("italic", size)
    max_w = W - PAD_X * 2
    while size > CREDIT_MIN and draw.textlength(credit, font=f) > max_w:
        size -= 1
        f = font("italic", size)

    tw = draw.textlength(credit, font=f)
    if tw > max_w:
        raise SystemExit(
            f"mkcard: credit line is too long to render legibly at {CREDIT_MIN}px.\n"
            f"  {len(credit)} chars, needs {tw:.0f}px of {max_w}px available.\n"
            "  Shorten it — the card credit is a caption, not the article's."
        )

    asc, desc = f.getmetrics()
    line_h = asc + desc
    x = W - PAD_X - tw
    y = H - 8 - line_h

    # Scrim: the credit sits over photography whose brightness we do not control.
    draw.rectangle(
        [x - 14, y - 5, W - PAD_X + 14, y + line_h + 3],
        fill=NAVY + (CREDIT_SCRIM_ALPHA,),
    )
    draw.text((x, y), credit, font=f, fill=CREDIT_INK)


def draw_footer(draw, spec):
    label = spec.get("footer", "propertyatlas.sg")
    f = font("medium", 14)
    tw = text_w(draw, label, f)
    draw.text((W - PAD_X - tw, H - PAD_BOTTOM - 22), label, font=f, fill=GOLD)


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------

def render_article(card, draw, spec, had_photo):
    """Headline card. The L-SOCIAL-2 template."""
    draw_eyebrow(draw, spec)
    paste_logo(card, spec, 44, (W - PAD_X - 44, PAD_TOP - 6))

    headline = spec.get("headline")
    if not headline:
        raise SystemExit("mkcard: article mode requires \"headline\".")

    f, lines, size = fit_lines(
        draw, headline, "bold", W - PAD_X * 2 - 40,
        max_lines=spec.get("max_lines", 5), size_hi=34, size_lo=22,
    )
    leading = round(size * 1.30)
    block_h = leading * len(lines)
    y = 150 + max(0, (250 - block_h) // 2)
    draw_lines(draw, lines, f, PAD_X, y, WHITE, leading)

    if spec.get("category"):
        draw_pill(draw, spec["category"], PAD_X, H - PAD_BOTTOM - 74)

    draw_footer(draw, spec)
    draw_credit(draw, spec, had_photo)


def render_number(card, draw, spec, had_photo):
    """Big-figure card. One number does the work."""
    draw_eyebrow(draw, spec)
    paste_logo(card, spec, 44, (W - PAD_X - 44, PAD_TOP - 6))

    figure = spec.get("figure")
    if not figure:
        raise SystemExit("mkcard: number mode requires \"figure\".")

    if spec.get("kicker"):
        fk = font("bold", 17)
        draw.text((PAD_X, 132), spec["kicker"].upper(), font=fk, fill=GOLD)

    ff, flines, fsize = fit_lines(
        draw, figure, "bold", W - PAD_X * 2, max_lines=1,
        size_hi=118, size_lo=54,
    )
    draw.text((PAD_X, 172), flines[0], font=ff, fill=WHITE)
    y = 172 + round(fsize * 1.10)

    if spec.get("unit"):
        fu = font("medium", 22)
        draw.text((PAD_X, y), spec["unit"], font=fu, fill=GOLD)
        y += 40

    if spec.get("subline"):
        fs, slines, ssize = fit_lines(
            draw, spec["subline"], "regular", W - PAD_X * 2 - 60,
            max_lines=3, size_hi=20, size_lo=15,
        )
        draw_lines(draw, slines, fs, PAD_X, y + 8, MUTED, round(ssize * 1.45))

    draw_footer(draw, spec)
    draw_credit(draw, spec, had_photo)


def render_summary(card, draw, spec, had_photo):
    """TKRE weekly summary — label/value rows on a rule grid."""
    draw_eyebrow(draw, spec)
    paste_logo(card, spec, 46, (W - PAD_X - 46, PAD_TOP - 8))

    title = spec.get("title")
    if not title:
        raise SystemExit("mkcard: summary mode requires \"title\".")
    ft, tlines, tsize = fit_lines(
        draw, title, "bold", W - PAD_X * 2 - 120, max_lines=2,
        size_hi=38, size_lo=26,
    )
    y = draw_lines(draw, tlines, ft, PAD_X, 96, WHITE, round(tsize * 1.28))

    rows = spec.get("rows") or []
    if not rows:
        raise SystemExit("mkcard: summary mode requires a non-empty \"rows\".")
    if len(rows) > 5:
        raise SystemExit(
            f"mkcard: summary mode fits at most 5 rows, got {len(rows)}. "
            f"Split across two cards."
        )

    fl = font("regular", 19)
    fv = font("bold", 30)
    y += 26
    row_h = min(64, (H - PAD_BOTTOM - 70 - y) // len(rows))
    for label, value in rows:
        draw.line([(PAD_X, y), (W - PAD_X, y)], fill=(255, 255, 255, 40), width=1)
        draw.text((PAD_X, y + 14), str(label), font=fl, fill=MUTED)
        vw = text_w(draw, str(value), fv)
        draw.text((W - PAD_X - vw, y + 6), str(value), font=fv, fill=WHITE)
        y += row_h

    draw_footer(draw, spec)
    draw_credit(draw, spec, had_photo)


RENDERERS = {
    "article": render_article,
    "number": render_number,
    "summary": render_summary,
}


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def build(spec):
    mode = spec.get("mode")
    if mode not in MODES:
        raise SystemExit(f"mkcard: \"mode\" must be one of {MODES}, got {mode!r}")

    out = spec.get("out")
    if not out:
        raise SystemExit("mkcard: \"out\" is required (e.g. linkedin_card_164.jpg)")

    card, had_photo = build_background(spec)
    draw = ImageDraw.Draw(card, "RGBA")
    RENDERERS[mode](card, draw, spec, had_photo)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    card.save(out, "JPEG", quality=int(spec.get("quality", 92)), optimize=True)

    size_kb = os.path.getsize(out) / 1024
    print(f"mkcard: {mode} -> {out}  {W}x{H}  {size_kb:.0f} KB"
          f"  photo={'yes' if had_photo else 'no'}")
    if size_kb > 400:
        print(f"mkcard: WARNING {size_kb:.0f} KB is large for a LinkedIn card "
              f"(expect 150-250 KB); consider lowering \"quality\".")
    return out


def main(argv):
    preflight_fonts()
    if len(argv) < 2:
        raise SystemExit(__doc__.strip())

    src = argv[1]
    raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    spec = json.loads(raw)

    if "--out" in argv:
        spec["out"] = argv[argv.index("--out") + 1]

    specs = spec if isinstance(spec, list) else [spec]
    for s in specs:
        build(s)


if __name__ == "__main__":
    main(sys.argv)
