#!/usr/bin/env python3
"""licard_225.py — PropertyAtlas LinkedIn branded card, 1200x630.

SUPERSEDES licard_224.py, which was never committed (third renderer loss — see
S330 carry-forward and the S339 handoff). COMMIT THIS FILE TO tools/.

Brand geometry is rebuilt from the masthead SVG in the deployed newsroom/index.html,
never from a stored asset:
    <rect width=32 height=32 rx=5 fill=#0B2B5C/>
    <rect x=2.5 y=2.5 w=27 h=27 rx=3.5 stroke=#C99B5A stroke-width=0.7 fill=none/>
    <text x=11 y=22 Georgia 17 bold fill=#F7F3EB anchor=middle>P</text>
    <g transform="translate(22 16)"> four kites #C99B5A, top solid, other three at 0.55 </g>

Colour census on the live file confirms #0B2B5C x23, #C99B5A x25, #F7F3EB x21.
pa_mark.py remains wrong three ways (#0B1A2D, inverted tile/glyph, #C6AD76 — the
last appears NOWHERE in the deployed file). Do not use it.

The mark is drawn at 4x supersample so the 0.7-unit stroke survives downscaling.
L-SOCIAL-2: the photo-source credit line is stamped on the card itself.
L-IMG-1: all text sits inside a 56px margin (floor is 45px).
"""
from PIL import Image, ImageDraw, ImageFont
import textwrap, sys, os

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
    lines = textwrap.wrap(credit, width=118)[:2]
    cy = H - MARGIN - (len(lines) * 17) + 4
    for ln in lines:
        d.text((MARGIN, cy), ln, font=fc, fill=(0x7E, 0x8C, 0xA6))
        cy += 17

    img.save(out, "JPEG", quality=92, subsampling=0, optimize=True)
    return out


if __name__ == "__main__":
    out = build(
        headline="Every unopened Coliwoo room is already inside the 3,568 headline",
        kicker="LHN Limited · Coliwoo Holdings · 3QFY2026",
        stat_pairs=[("3,568", "rooms reported"),
                    ("1,021", "under renovation"),
                    ("2,547", "actually open"),
                    ("28.6%", "not open")],
        credit="Coliwoo Resort Changi, 159 Jalan Loyang Besar. Credit: Coliwoo Holdings Limited. "
               "Figures from the companies' 3QFY2026 filings; operational room count derived by PropertyAtlas.",
        out=sys.argv[1] if len(sys.argv) > 1 else "li_card_225.jpg",
        photo=sys.argv[2] if len(sys.argv) > 2 else "images/news_225_coliwoo_resort_changi.jpg")
    print("wrote", out)
