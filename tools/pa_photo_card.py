#!/usr/bin/env python3
"""pa_photo_card.py — S390. PropertyAtlas branded PHOTO card for LinkedIn (square, 1200x1200).

Use when a real hero photo (or an issuer render) is available from the source
announcement, press release, issuer website or our own shoot. When no usable
photo exists, keep using pa_linkedin_card.py (the figure card).

Usage (run from tools/ so fonts/ and the lockup resolve):
    python3 pa_photo_card.py spec.json out.jpg

Spec keys:
  photo        path to the source image (REQUIRED)
  credit       REQUIRED. "Photo: <owner>" for a photograph, "Artist's Impression: <owner>"
               for a render. Printed bottom-right on the card itself.
  title        list of 1-3 short lines, set in gold serif capitals (e.g. ["VALLEY","POINT"])
  sub          list of 1-4 lines, cream serif — the news in one sentence
  detail       list of 0-2 lines, gold spaced capitals — the key figures
  button       outlined call-to-action text (default "READ THE ANALYSIS")
  focal_x      0..1, horizontal position of the subject in the SOURCE photo (default 0.6).
               The crop places this point at ~70% across the card, clear of the text panel.
  focal_y      0..1, vertical focus for portrait or tall sources (default 0.5)
  darken       0..1 overall photo dimming (default 0.82)
  brand        "pa" (default: PropertyAtlas lockup, bottom-left) or "tkre"
               ("TK REAL ESTATE" + licence line, for listings/mandates)
  licence      licence line for brand "tkre"

Gates (non-zero exit on FAIL):
  * credit present and starts "Photo:" / "Artist's Impression" / "Image:"
  * source short side >= 700 px (FAIL); < 1200 px prints a SOFT warning (upscaled)
  * every text line stays inside the left panel (x <= 56% of width) and 40 px margins
  * text block fits vertically between the top margin and the footer
"""
import json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W = 1200
NAVY = (12, 22, 40)
GOLD = (217, 187, 128)
CREAM = (244, 238, 226)
MUTED = (205, 205, 205)
PANEL_MAX = int(W * 0.56)
MARGIN = 40
LEFT = 84


def serif(sz, wght=400):
    f = ImageFont.truetype("fonts/Gelasio[wght].ttf", sz)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def sans(sz):
    return ImageFont.truetype("fonts/DMSans.ttf", sz)


def tracked_width(d, text, font, track):
    return sum(d.textlength(c, font=font) + track for c in text) - track if text else 0


def draw_tracked(d, xy, text, font, fill, track):
    x, y = xy
    for c in text:
        d.text((x, y), c, font=font, fill=fill)
        x += d.textlength(c, font=font) + track
    return x


def fit(d, lines, make_font, start, floor, track, limit):
    """Largest size from start down to floor at which every line fits within limit."""
    for sz in range(start, floor - 1, -2):
        f = make_font(sz)
        if all(LEFT + tracked_width(d, ln, f, track(sz)) <= limit for ln in lines):
            return sz, f
    return floor, make_font(floor)


def main(spec_path, out_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    fails, warns = [], []

    credit = (spec.get("credit") or "").strip()
    if not credit.startswith(("Photo:", "Artist's Impression", "Artist’s Impression", "Image:")):
        fails.append("credit missing or not 'Photo: …' / 'Artist's Impression …' / 'Image: …'")

    src = Image.open(spec["photo"]).convert("RGB")
    short = min(src.size)
    if short < 700:
        fails.append(f"source short side {short}px < 700px — too small")
    elif short < 1200:
        warns.append(f"source short side {short}px < 1200px — will be upscaled (soft)")

    # ---- cover crop: subject (focal_x, focal_y) lands at ~70% across, centred vertically
    fx, fy = float(spec.get("focal_x", 0.6)), float(spec.get("focal_y", 0.5))
    s = max(W / src.width, W / src.height)
    im = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    x0 = int(fx * im.width - 0.70 * W)
    y0 = int(fy * im.height - 0.5 * W)
    x0 = max(0, min(x0, im.width - W))
    y0 = max(0, min(y0, im.height - W))
    im = im.crop((x0, y0, x0 + W, y0 + W))

    a = np.asarray(im).astype(float) * float(spec.get("darken", 0.82))
    a[..., 2] *= 1.05
    im = Image.fromarray(np.clip(a, 0, 255).astype("uint8")).convert("RGBA")

    # ---- navy gradient (left panel) + bottom fade for the footer
    g = np.zeros((W, W, 4), dtype="uint8")
    g[..., 0], g[..., 1], g[..., 2] = NAVY
    xs = np.arange(W) / W
    alpha_x = (np.clip((0.78 - xs) / 0.45, 0, 1) ** 1.2) * 0.94 * 255
    alpha_y = (np.linspace(0, 1, W) ** 3) * 120
    g[..., 3] = np.maximum(alpha_x[None, :], alpha_y[:, None]).astype("uint8")
    im = Image.alpha_composite(im, Image.fromarray(g, "RGBA"))
    d = ImageDraw.Draw(im)

    d.line([(42, 0), (42, W)], fill=GOLD + (110,), width=2)

    title = spec.get("title", [])
    sub = spec.get("sub", [])
    detail = spec.get("detail", [])
    button = spec.get("button", "READ THE ANALYSIS")

    tsz, tf = fit(d, title, lambda z: serif(z), 116, 64, lambda z: max(4, z // 12), PANEL_MAX)
    ssz, sf = fit(d, sub, lambda z: serif(z), 56, 36, lambda z: 0, PANEL_MAX)
    dsz, df = fit(d, detail, lambda z: sans(z), 24, 18, lambda z: 5, PANEL_MAX)
    bf = sans(24)

    # ---- vertical layout, centred in the band between 110 and the footer (W-150)
    t_lh, s_lh, d_lh = int(tsz * 1.09), int(ssz * 1.25), int(dsz * 1.7)
    block = (len(title) * t_lh + 26 + 2 + 48 + len(sub) * s_lh
             + (44 + len(detail) * d_lh if detail else 0) + (46 + 74 if button else 0))
    top, bottom = 110, W - 150
    if block > bottom - top:
        fails.append(f"text block {block}px taller than the {bottom - top}px band — shorten lines")
    y = top + max(0, (bottom - top - block) // 2)

    rights = []
    for ln in title:
        rights.append(draw_tracked(d, (LEFT, y), ln, tf, GOLD, max(4, tsz // 12)))
        y += t_lh
    y += 26
    d.line([(LEFT + 2, y), (LEFT + 164, y)], fill=GOLD, width=2)
    y += 48
    for ln in sub:
        d.text((LEFT, y), ln, font=sf, fill=CREAM)
        rights.append(LEFT + d.textlength(ln, font=sf))
        y += s_lh
    if detail:
        y += 44
        for ln in detail:
            rights.append(draw_tracked(d, (LEFT + 2, y), ln, df, GOLD, 5))
            y += d_lh
    if button:
        y += 46
        bw = int(tracked_width(d, button, bf, 6)) + 96
        d.rectangle([LEFT, y, LEFT + bw, y + 74], outline=GOLD, width=2)
        draw_tracked(d, (LEFT + 48, y + 22), button, bf, CREAM, 6)
        rights.append(LEFT + bw)

    for r in rights:
        if r > PANEL_MAX:
            fails.append(f"text runs to x={int(r)} past the left panel ({PANEL_MAX}) — shorten the line")

    # ---- footer: brand bottom-left, credit bottom-right
    brand = spec.get("brand", "pa")
    if brand == "pa":
        logo = Image.open("PROPERTYATLAS_LOCKUP.png").convert("RGBA")
        lw = 250
        logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
        im.alpha_composite(logo, (LEFT - 4, W - 62 - logo.height // 2))
        left_edge = LEFT - 4 + lw
    else:
        left_edge = draw_tracked(d, (LEFT, W - 84), "TK REAL ESTATE", sans(22), GOLD, 5)
        lic = spec.get("licence", "")
        if lic:
            d.text((LEFT, W - 52), lic, font=sans(16), fill=MUTED)
            left_edge = max(left_edge, LEFT + d.textlength(lic, font=sans(16)))
    cf = sans(20)
    cw = d.textlength(credit, font=cf)
    cx = W - MARGIN - cw
    d.text((cx, W - 74), credit, font=cf, fill=MUTED)
    if cx < left_edge + 30:
        fails.append("credit collides with the footer brand — shorten the credit")

    im.convert("RGB").save(out_path, quality=92)
    print(f"{out_path}  {W}x{W}  title {tsz}px · sub {ssz}px · detail {dsz}px · source {src.size[0]}x{src.size[1]}")
    for w in warns:
        print("  SOFT  " + w)
    for f in fails:
        print("  FAIL  " + f)
    if fails:
        sys.exit(1)
    print("CLEAN: photo card passes credit, resolution, panel and footer gates.")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
