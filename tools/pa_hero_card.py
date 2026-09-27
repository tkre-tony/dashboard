"""pa_hero_card.py — S385 article hero figure card.
Usage: python3 tools/pa_hero_card.py spec.json out.jpg
Spec keys: eyebrow, figure, tail, lead, body[2], stats[3]{value,label}, credit.

Originally: S385 hero figure card — reproduces the id:257 layout measured off the live
news_257 image (no logo lockup, gold eyebrow, large serif figure + gold tail,
lead + two body lines, three-stat row, right-aligned illustration credit).
Fonts: tools/fonts (Gelasio, DMSans) — the house faces used by pa_linkedin_card.py.
Every band is width-checked against R and the script raises rather than clip."""
import sys, json
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
L, R = 64, 1136
import os
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
NAVY_TOP, NAVY_BOT = (11, 26, 45), (19, 39, 64)
CREAM, GOLD = (247, 243, 235), (201, 162, 100)
BODY, LABEL, CREDIT = (150, 166, 191), (122, 139, 164), (159, 172, 193)
RULE = (255, 255, 255, 46)

def serif(sz, bold=False):
    f = ImageFont.truetype(f"{FD}/Gelasio[wght].ttf", sz)
    f.set_variation_by_axes([700 if bold else 400]); return f
def sans(sz, w=400):
    f = ImageFont.truetype(f"{FD}/DMSans.ttf", sz)
    f.set_variation_by_axes([min(max(sz * 0.7, 9), 40), w]); return f

def track(d, x, y, t, f, fill, sp):
    for ch in t:
        d.text((x, y), ch, font=f, fill=fill, anchor="ls"); x += d.textlength(ch, font=f) + sp
    return x

def render(spec, out):
    img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img, "RGBA")
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOT)))
    ext = []
    ext.append(("eyebrow", track(d, L, 96, spec["eyebrow"].upper(), sans(20, 700), GOLD, 1.8)))
    # figure + tail, jointly fitted
    tf = serif(40); tw = d.textlength(spec["tail"], font=tf)
    sz = 200
    while sz > 80 and d.textlength(spec["figure"], font=serif(sz)) + 22 + tw > R - L: sz -= 4
    ff = serif(sz); fw = d.textlength(spec["figure"], font=ff)
    d.text((L, 268), spec["figure"], font=ff, fill=CREAM, anchor="ls")
    d.text((L + fw + 22, 260), spec["tail"], font=tf, fill=GOLD, anchor="ls")
    ext.append(("figure+tail", L + fw + 22 + tw))
    d.line([(L, 322), (R, 322)], fill=RULE, width=1)
    lf = serif(25, bold=True)
    d.text((L, 368), spec["lead"], font=lf, fill=(246, 250, 254), anchor="ls")
    ext.append(("lead", L + d.textlength(spec["lead"], font=lf)))
    bf = serif(23)
    for i, ln in enumerate(spec["body"][:2]):
        d.text((L, 412 + i * 34), ln, font=bf, fill=BODY, anchor="ls")
        ext.append((f"body{i}", L + d.textlength(ln, font=bf)))
    d.line([(L, 486), (R, 486)], fill=RULE, width=1)
    vf, lbf = serif(32), sans(17)
    col = (R - L) / 3
    for i, st in enumerate(spec["stats"]):
        x = L + round(i * col)
        d.text((x, 537), st["value"], font=vf, fill=(232, 242, 254), anchor="ls")
        e = track(d, x, 568, st["label"], lbf, LABEL, 0.5)
        if e > x + col - 16 and i < 2: raise ValueError(f"stat {i} label overruns its column")
        ext.append((f"stat{i}", e))
    cf = sans(17); cw = d.textlength(spec["credit"], font=cf)
    d.text((R - cw, 609), spec["credit"], font=cf, fill=CREDIT, anchor="ls")
    ext.append(("credit-left", R - cw))
    for band, x in ext:
        if band == "credit-left":
            if x < L: raise ValueError("credit wider than inner width")
        elif x > R: raise ValueError(f"{band} overruns right margin: {x:.0f} > {R}")
    img.save(out, quality=92)
    print(out, img.size, "figure size", sz, {b: round(x) for b, x in ext})

if __name__ == "__main__":
    render(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])
