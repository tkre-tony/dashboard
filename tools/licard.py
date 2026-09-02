#!/usr/bin/env python3
"""licard.py - PropertyAtlas LinkedIn branded card, 1200x630.

THE ONLY LICARD. Do not create licard2.py, licard_225.py, licard_229.py or any
other numbered snapshot. Four of those accumulated in Project Knowledge, where
the session-open sequence cannot fetch them, and each new drop silently forked
the renderer again (L-DEPLOY-13). Article content lives in a JSON file, never in
this module. If a drop needs different copy, write a new JSON, not a new .py.

    python3 tools/licard.py card_229.json

JSON SCHEMA
    {
      "id":         229,                     int or str, used to name the output
      "kicker":     "Oxley Holdings * SGX:5UX * FY2026 results",
      "headline":   "One provision on a hotel that has never opened ...",
      "stat_pairs": [["33.2%", "gross margin as reported"],
                     ["43.5%", "before the provision"],
                     ["S$16.8m", "the provision"],
                     ["S$51.3m", "loss before tax"]],
      "credit":     "... Credit: Oxley Holdings.",
      "photo":      "news_229_oxley_towers_klcc.jpg",   optional
      "out":        "linkedin_card_229.jpg"             optional, derived from id
    }

BRAND GEOMETRY is rebuilt from the masthead SVG in the deployed
newsroom/index.html, never from a stored asset:
    <rect width=32 height=32 rx=5 fill=#0B2B5C/>
    <rect x=2.5 y=2.5 w=27 h=27 rx=3.5 stroke=#C99B5A stroke-width=0.7 fill=none/>
    <text x=11 y=22 Georgia 17 bold fill=#F7F3EB anchor=middle>P</text>
    <g transform="translate(22 16)"> four kites #C99B5A, top solid, other three at 0.55 </g>

Colour census on the live file confirms #0B2B5C x23, #C99B5A x25, #F7F3EB x21.
pa_mark.py remains wrong three ways (#0B1A2D, inverted tile/glyph, #C6AD76 - the
last appears NOWHERE in the deployed file). Do not use it.

The mark is drawn at 4x supersample so the 0.7-unit stroke survives downscaling.
L-SOCIAL-2:  the photo-source credit line is stamped on the card itself.
L-SOCIAL-17: the credit wrap widens until it fits, then ASSERTS the attribution
             survived. A card that attributes nothing must never ship.
L-IMG-1:     all text sits inside a 56px margin (floor is 45px).

PROVENANCE
    S348. Generic form of licard_229.py, whose __main__ held the id:229 values
    now shown as the worked example above. licard_229.py carried the
    L-SOCIAL-17 credit fix over licard_225.py; licard.py (the old one) and
    licard2.py predate it. All four are superseded by this file.
"""
from PIL import Image, ImageDraw, ImageFont
import textwrap, sys, os, json

W, H = 1200, 630
NAVY = (0x0B, 0x2B, 0x5C)
GOLD = (0xC9, 0x9B, 0x5A)
CREAM = (0xF7, 0xF3, 0xEB)
MARGIN = 56
SS = 4  # supersample factor for the mark


def font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


SERIF = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
SERIF_B = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]
SANS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
SANS_B = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def draw_mark(size):
    """Rebuild the 32x32 masthead mark at `size` px, supersampled."""
    s = size * SS
    k = s / 32.0
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(5 * k), fill=NAVY)
    d.rounded_rectangle([2.5 * k, 2.5 * k, 29.5 * k, 29.5 * k],
                        radius=3.5 * k, outline=GOLD, width=max(1, int(round(0.7 * k))))
    f = font(SERIF_B, int(17 * k))
    d.text((11 * k, 22 * k), "P", font=f, fill=CREAM, anchor="ms")

    cx, cy = 22 * k, 16 * k

    def kite(pts, alpha):
        lay = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(lay).polygon([(cx + x * k, cy + y * k) for x, y in pts],
                                    fill=GOLD + (alpha,))
        img.alpha_composite(lay)
    kite([(0, -7), (2, -1), (0, 0), (-2, -1)], 255)
    kite([(0, 7), (-2, 1), (0, 0), (2, 1)], 140)
    kite([(-7, 0), (-1, -2), (0, 0), (-1, 2)], 140)
    kite([(7, 0), (1, 2), (0, 0), (1, -2)], 140)
    return img.resize((size, size), Image.LANCZOS)


def build(headline, kicker, stat_pairs, credit, out, photo=None):
    if photo and os.path.exists(photo):
        # L-SOCIAL-2: the credit line names a photograph, so the photograph must be ON the card.
        base = Image.open(photo).convert("RGB")
        sc = max(W / base.width, H / base.height)
        base = base.resize((int(base.width * sc), int(base.height * sc)), Image.LANCZOS)
        base = base.crop(((base.width - W) // 2, 0, (base.width - W) // 2 + W, H))
        scrim = Image.new("RGB", (W, H), NAVY)
        img = Image.blend(base, scrim, 0.88)
        # extra weight down the left so the headline never fights the image
        grad = Image.new("L", (W, 1))
        for x in range(W):
            grad.putpixel((x, 0), int(215 * max(0.0, 1.0 - x / (W * 0.78))))
        img = Image.composite(Image.new("RGB", (W, H), NAVY), img, grad.resize((W, H)))
    else:
        img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # hairline inner rule, echoing the mark's inset stroke
    d.rounded_rectangle([26, 26, W - 27, H - 27], radius=10, outline=(0x1A, 0x3E, 0x74), width=1)

    # lockup
    mark = draw_mark(52)
    img.paste(mark, (MARGIN, MARGIN), mark)
    d.text((MARGIN + 68, MARGIN + 8), "PropertyAtlas", font=font(SERIF_B, 30), fill=CREAM)
    d.text((MARGIN + 69, MARGIN + 44), "propertyatlas.sg", font=font(SANS, 15), fill=GOLD)

    # kicker
    y = 186
    d.text((MARGIN, y), kicker.upper(), font=font(SANS_B, 16), fill=GOLD)

    # headline
    y += 40
    fh = font(SERIF_B, 44)
    for line in textwrap.wrap(headline, width=32)[:4]:
        d.text((MARGIN, y), line, font=fh, fill=CREAM)
        y += 56

    # stat strip
    y = H - 168
    d.line([MARGIN, y - 26, W - MARGIN, y - 26], fill=(0x1A, 0x3E, 0x74), width=1)
    colw = (W - 2 * MARGIN) // len(stat_pairs)
    for i, (val, lab) in enumerate(stat_pairs):
        x = MARGIN + i * colw
        d.text((x, y), val, font=font(SERIF_B, 34), fill=GOLD)
        d.text((x, y + 44), lab, font=font(SANS, 14), fill=(0xB8, 0xC6, 0xDB))

    # credit line, L-SOCIAL-2, inside the L-IMG-1 margin floor
    fc = font(SANS, 13)
    # L-SOCIAL-17: the fixed width=118 wrap silently dropped the trailing
    # "Credit: <owner>." on long landing_credit values, because [:2] truncates.
    # Widen until the credit fits two lines inside the margin; fail loudly if
    # it cannot, rather than shipping a card that attributes nothing.
    avail = W - 2 * MARGIN
    lines = None
    for _w in range(118, 181, 2):
        cand = textwrap.wrap(credit, width=_w)
        if len(cand) <= 2 and max(fc.getbbox(l)[2] for l in cand) <= avail:
            lines = cand
            break
    if lines is None:
        raise SystemExit("L-SOCIAL-17: credit will not fit two lines; shorten landing_credit")
    joined = " ".join(lines)
    if ("Credit:" not in joined) and (not joined.startswith(("Photo:", "Illustration:"))):
        raise SystemExit("L-SOCIAL-17: rendered credit attributes nothing")
    if joined.rstrip() != " ".join(credit.split()):
        raise SystemExit("L-SOCIAL-17: credit was truncated during wrap")
    cy = H - MARGIN - (len(lines) * 17) + 4
    for ln in lines:
        d.text((MARGIN, cy), ln, font=fc, fill=(0x7E, 0x8C, 0xA6))
        cy += 17

    img.save(out, "JPEG", quality=92, subsampling=0, optimize=True)
    return out


# --------------------------------------------------------------- spec layer --

REQUIRED = ("id", "kicker", "headline", "stat_pairs", "credit")


def load_spec(path):
    """Read and validate a card JSON. Every failure is loud and names the key."""
    if not os.path.exists(path):
        raise SystemExit(f"licard: no such spec file: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            spec = json.load(fh)
    except json.JSONDecodeError as e:
        raise SystemExit(f"licard: {path} is not valid JSON: {e}")
    if not isinstance(spec, dict):
        raise SystemExit(f"licard: {path} must contain a JSON object, got {type(spec).__name__}")

    missing = [k for k in REQUIRED if k not in spec or spec[k] in (None, "", [])]
    if missing:
        raise SystemExit(f"licard: {path} missing required key(s): {', '.join(missing)}")

    pairs = spec["stat_pairs"]
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 4:
        raise SystemExit("licard: stat_pairs must be a list of 1 to 4 pairs "
                         f"(got {len(pairs) if isinstance(pairs, list) else type(pairs).__name__})")
    for i, p in enumerate(pairs):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise SystemExit(f"licard: stat_pairs[{i}] must be [value, label], got {p!r}")
    spec["stat_pairs"] = [tuple(p) for p in pairs]

    # The credit is the whole point of L-SOCIAL-2/-17. Refuse before rendering.
    if ("Credit:" not in spec["credit"]) and (not spec["credit"].startswith(("Photo:", "Illustration:"))):
        raise SystemExit("licard: credit must contain 'Credit:' or start with "
                         "'Photo:' / 'Illustration:' - an unattributed card must never ship")

    # A photo named but absent would silently fall back to a plain navy card.
    photo = spec.get("photo") or None
    if photo and not os.path.exists(photo):
        raise SystemExit(f"licard: photo named in spec but not found on disk: {photo}\n"
                         "        fix the path, or drop the key for a photo-less card")

    spec["photo"] = photo
    spec["out"] = spec.get("out") or f"linkedin_card_{spec['id']}.jpg"
    return spec


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        raise SystemExit(__doc__)
    spec = load_spec(argv[1])
    out = build(headline=spec["headline"],
                kicker=spec["kicker"],
                stat_pairs=spec["stat_pairs"],
                credit=spec["credit"],
                out=argv[2] if len(argv) > 2 else spec["out"],
                photo=spec["photo"])
    kb = os.path.getsize(out) / 1024
    with Image.open(out) as im:
        dims = im.size
    print(f"wrote {out}  {dims[0]}x{dims[1]}  {kb:.0f} KB"
          f"  photo={'yes' if spec['photo'] else 'no'}")
    return out


if __name__ == "__main__":
    main(sys.argv)
