#!/usr/bin/env python3
"""PropertyAtlas LinkedIn figure card — 1200x630.

Rebuilt in S359 by measuring the shipped 4 Sep card. The original generator
was an S358 session artefact: never committed, container gone, and
`pa_figure_card.py` in Project Knowledge is a different design (no logo
lockup, no three-stat row).

The reason it was rebuilt: the shipped card read "surfaced on Thursday" for
a Friday release. **The weekday is now derived from the release date and can
never be typed.** Pass `releases` as ISO dates; `{weekday}` in the body text
is substituted from the last one.

Usage:  python3 pa_linkedin_card.py spec.json out.png
"""
import sys, json, datetime
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
S = 1.5                                   # measurements were taken at 800x420

# palette — newsroom editorial, not the reel/carousel palette
NAVY_TOP = (11, 26, 45)                   # #0B1A2D, measured
NAVY_BOT = (19, 39, 64)                   # #132740, measured
CREAM    = (247, 243, 235)                # --ed-cream
GOLD     = (201, 162, 100)                # --ed-bronze-lt
BODY     = (150, 166, 191)
LABEL    = (122, 139, 164)
RULE     = (255, 255, 255, 46)

FD = "fonts"
def serif(sz, italic=False, bold=False):
    f = "Gelasio-Italic[wght].ttf" if italic else "Gelasio[wght].ttf"
    ft = ImageFont.truetype(f"{FD}/{f}", sz)
    try: ft.set_variation_by_axes([700 if bold else 400])
    except Exception: pass
    return ft
def sans(sz, wght=400):
    ft = ImageFont.truetype(f"{FD}/DMSans.ttf", sz)
    try: ft.set_variation_by_axes([min(max(sz * 0.7, 9), 40), wght])
    except Exception: pass
    return ft

def px(v): return int(round(v * S))

def track(d, xy, text, font, fill, sp=0.0):
    """Draw with letter-spacing. Returns the advance."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + sp
    return x - xy[0]

def track_w(d, text, font, sp=0.0):
    return sum(d.textlength(c, font=font) for c in text) + sp * max(len(text) - 1, 0)


def render(spec, out):
    # ---- weekday derived, never typed -------------------------------
    rel = [datetime.date.fromisoformat(r) for r in spec["releases"]]
    weekday = rel[-1].strftime("%A")
    body = [ln.replace("{weekday}", weekday) for ln in spec["body"]]

    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(H):                     # vertical gradient
        t = y / (H - 1)
        d.line([(0, y), (W, y)],
               fill=tuple(int(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOT)))

    L, R = px(42), px(758)

    # ---- kicker + logo ----------------------------------------------
    f = sans(px(14.5), 700)
    track(d, (L, px(31)), spec["kicker"].upper(), f, (214, 213, 216), sp=px(1.5))
    logo = Image.open(spec["logo"]).convert("RGBA")
    lw = px(114); lh = round(logo.height * lw / logo.width)
    img.paste(logo.resize((lw, lh), Image.LANCZOS), (R - lw, px(29)), logo.resize((lw, lh), Image.LANCZOS))

    # ---- gold kicker -------------------------------------------------
    f = sans(px(16.3), 700)
    track(d, (L, px(78)), spec["eyebrow"].upper(), f, GOLD, sp=px(1.2))

    # ---- headline figure + tail -------------------------------------
    ff = serif(px(76))
    d.text((L, px(98)), spec["figure"], font=ff, fill=CREAM)
    fw = d.textlength(spec["figure"], font=ff)
    ft = serif(px(38), italic=True)
    d.text((L + fw + px(14), px(148)), spec["tail"], font=ft, fill=GOLD)

    d.line([(L, px(221)), (R, px(221))], fill=RULE, width=1)

    # ---- lead + body -------------------------------------------------
    d.text((L, px(236)), spec["lead"], font=serif(px(17), bold=True), fill=(246, 250, 254))
    fb = serif(px(14))
    for i, ln in enumerate(body):
        d.text((L, px(264 + i * 23)), ln, font=fb, fill=BODY)

    d.line([(L, px(324)), (R, px(324))], fill=RULE, width=1)

    # ---- three stats --------------------------------------------------
    fn, fl = serif(px(22)), sans(px(10), 400)
    for i, st in enumerate(spec["stats"]):
        x = L + round(i * (R - L) / 3)
        d.text((x, px(336)), st["value"], font=fn, fill=(232, 242, 254))
        track(d, (x, px(369)), st["label"], fl, LABEL, sp=px(0.35))

    # ---- footer -------------------------------------------------------
    fsm = sans(px(9), 400)
    track(d, (L, px(396)), "propertyatlas.sg", fsm, GOLD, sp=px(0.5))
    def ord_(n): return f"{n}{'th' if 11 <= n <= 13 else {1:'st',2:'nd',3:'rd'}.get(n % 10, 'th')}"
    if len({(r.year, r.month) for r in rel}) == 1:
        days = " and ".join(ord_(r.day) for r in rel)
        when = f"{days} {rel[-1].strftime('%B %Y')}"
    else:
        when = " and ".join(f"{ord_(r.day)} {r.strftime('%B %Y')}" for r in rel)
    src = f'Illustration: PropertyAtlas. Source: {spec["source"]}, releases dated {when}.'
    d.text((R - track_w(d, src, fsm), px(396)), src, font=fsm, fill=(159, 172, 193))

    img.save(out, quality=96)
    print(f"{out}  {img.size[0]}x{img.size[1]}  weekday derived = {weekday}")


if __name__ == "__main__":
    render(json.load(open(sys.argv[1])), sys.argv[2])
