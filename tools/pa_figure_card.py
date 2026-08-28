#!/usr/bin/env python3
"""
pa_figure_card.py — PropertyAtlas typographic hero card (1200x630).

Reconstructed to match images/news_164_landed_district19_record.jpg, measured
off the live file: left margin 92, right extent 1108, kicker band y120-140,
figure band y198-367, rule y404, body bands y441-466 / y483-508 / y517-537,
credit band y561-583. Palette sampled from the same file.

⚠ FONTS ARE SUBSTITUTES. The original was not made in this container and the
house faces are not present here. If the real generator exists locally, use it
and take only the copy deck from this file.

WIDTH GUARD (S343, re-added S344 after container loss)
------------------------------------------------------
Every band was previously fitted on HEIGHT ONLY. `fit()` binary-searched a font
size whose cap-to-baseline height matched the band, then drew at x=L with no
check that the rendered run ended before the right margin R. Anything too wide
ran off the canvas silently — no exception, no warning, just a clipped JPEG.
Measured reproductions on the pre-guard build:

    figure 'S$63.0m' + unit 'freehold industrial land'  right=1423  OVERFLOW +315
    figure 'S$38.10m' + unit 'Lucky Plaza YTD'          right=1205  OVERFLOW +97
    figure 'S$258,141,464' alone                        right=1111  OVERFLOW +3

The guard has two parts and they are not interchangeable:

1. SHRINK — `fit()` now takes `max_w` and accepts a size only when BOTH the
   height and the advance width fit. Height and width both grow monotonically
   with point size, so the binary search stays valid. The figure and unit are
   budgeted jointly: the unit is capped at UNIT_W_SHARE of the inner width and
   the figure gets whatever is left after the 22px gap.

2. ASSERT — after every band is drawn, `build()` re-measures the right extent
   of each and raises ValueError if any exceeds R. The shrink handles the
   ordinary case; the assert is what makes a case the shrink cannot rescue
   fail LOUDLY instead of shipping a clipped card.

The guard is a no-op on copy that already fits: cards whose bands are inside
the margin render byte-identical to the pre-guard build.
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np, sys, json

F = "/mnt/skills/examples/canvas-design/canvas-fonts/"
SERIF      = F + "Lora-Regular.ttf"
SANS_BOLD  = F + "InstrumentSans-Bold.ttf"
SANS       = F + "InstrumentSans-Regular.ttf"

W, H = 1200, 630
L, R = 92, 1108

INNER_W      = R - L          # 1016 — every band draws inside this
UNIT_GAP     = 22             # gap between figure and unit
UNIT_W_SHARE = 0.40           # unit may claim at most this much of INNER_W
MIN_PT       = 20             # floor of the binary search; below this we raise

BG_TL   = (11, 26, 45)
BG_BR   = (17, 41, 67)
GOLD    = (196, 180, 134)
CREAM   = (245, 241, 232)
NEARW   = (243, 244, 246)
MUTED   = (137, 159, 182)
CREDIT  = (120, 141, 168)
RULE    = (118, 121, 110)

_MEASURE = ImageDraw.Draw(Image.new("RGB", (W, H)))


def background():
    """Diagonal gradient, top-left dark to bottom-right lighter."""
    y, x = np.mgrid[0:H, 0:W]
    t = ((x / W) * 0.55 + (y / H) * 0.45)
    t = np.clip(t, 0, 1)[..., None]
    a = np.array(BG_TL, float)
    b = np.array(BG_BR, float)
    return Image.fromarray((a + (b - a) * t).astype(np.uint8), "RGB")


def track(draw, xy, text, font, fill, spacing=0.0):
    """Draw with letter-spacing. Returns advance width."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing
    return x - xy[0]


def advance(text, font, spacing=0.0):
    """Rendered advance width, including letter-spacing if tracked."""
    w = _MEASURE.textlength(text, font=font)
    if spacing:
        w += spacing * max(len(text) - 1, 0)
    return w


def fit(text, path, target_h, lo=MIN_PT, hi=400, max_w=None, spacing=0.0):
    """Binary-search a font size that fits the band height AND, if max_w is
    given, the available width. Both grow monotonically with point size, so a
    single search over the conjunction is sound.

    Returns the largest acceptable font. If even `lo` will not fit the width,
    returns the `lo` font — the caller's assert is what rejects it, so the
    failure is visible rather than silently clipped."""
    best = ImageFont.truetype(path, lo)
    _lo = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(path, mid)
        bb = f.getbbox(text)
        ok = (bb[3] - bb[1]) <= target_h
        if ok and max_w is not None:
            ok = advance(text, f, spacing) <= max_w
        if ok:
            best = f; lo = mid + 1
        else:
            hi = mid - 1
    return best


def build(spec, out, verbose=False):
    img = background()
    d = ImageDraw.Draw(img)
    extents = []   # (band, right_edge) — checked against R before saving

    # ---- kicker: band y120-140, bold sans, tracked, gold ----
    kf = fit(spec["kicker"], SANS_BOLD, 20, max_w=INNER_W, spacing=1.6)
    kb = kf.getbbox(spec["kicker"])
    kw = track(d, (L, 120 - kb[1]), spec["kicker"], kf, GOLD, spacing=1.6)
    extents.append(("kicker", L + kw))

    # ---- figure + unit: budgeted jointly against INNER_W ----
    # The unit is sized first against its capped share; the figure then takes
    # the remainder less the gap. Pre-guard this was two independent height
    # fits and their sum was never checked.
    unit = spec.get("unit")
    if unit:
        uf = fit(unit, SERIF, 46, max_w=INNER_W * UNIT_W_SHARE)
        uw = advance(unit, uf)
        fig_max_w = INNER_W - UNIT_GAP - uw
    else:
        uf = uw = None
        fig_max_w = INNER_W

    # ---- figure: band y198-367 (169px), serif, cream ----
    ff = fit(spec["figure"], SERIF, 169, max_w=fig_max_w)
    fb = ff.getbbox(spec["figure"])
    d.text((L, 198 - fb[1]), spec["figure"], font=ff, fill=CREAM)
    fw = advance(spec["figure"], ff)
    extents.append(("figure", L + fw))

    # ---- unit: serif, gold, baseline sits ~28px above the figure baseline ----
    if unit:
        ub = uf.getbbox(unit)
        d.text((L + fw + UNIT_GAP, 321 - ub[1]), unit, font=uf, fill=GOLD)
        extents.append(("unit", L + fw + UNIT_GAP + uw))

    # ---- rule at y404 ----
    d.line([(L, 404), (R, 404)], fill=RULE, width=2)

    # ---- lead line: band y441-466 ----
    lf = fit(spec["lead"], SERIF, 25, max_w=INNER_W)
    lb = lf.getbbox(spec["lead"])
    d.text((L, 441 - lb[1]), spec["lead"], font=lf, fill=NEARW)
    extents.append(("lead", L + advance(spec["lead"], lf)))

    # ---- body: bands y483-508 and y517-537 ----
    # Point size comes from the FIXED gauge string "Previous best", unchanged
    # from the pre-guard build — body typography must stay consistent card to
    # card, so it is deliberately not derived from this card's own copy. The
    # gauge is width-bounded (a no-op at this length) and each drawn line is
    # measured into `extents`, so an over-long body line trips the assert
    # rather than running off the edge.
    body = spec["body"][:2]
    bf = fit("Previous best", SERIF, 25, max_w=INNER_W)
    for i, line in enumerate(body):
        top = 483 if i == 0 else 517
        bb = bf.getbbox(line)
        d.text((L, top - bb[1]), line, font=bf, fill=MUTED)
        extents.append((f"body{i}", L + advance(line, bf)))

    # ---- credit: gold dash then sans, band y561-583 ----
    d.line([(L, 570), (L + 34, 570)], fill=GOLD, width=3)
    cf = fit(spec["credit"], SANS, 18, max_w=R - (L + 48))
    cb = cf.getbbox(spec["credit"])
    d.text((L + 48, 563 - cb[1]), spec["credit"], font=cf, fill=CREDIT)
    extents.append(("credit", L + 48 + advance(spec["credit"], cf)))

    # ---- HARD MARGIN ASSERT — the loud half of the guard ----
    over = [(b, e) for b, e in extents if e > R + 0.5]
    if verbose:
        for b, e in extents:
            print(f"  {b:8} right={e:8.1f}  headroom={R - e:7.1f}"
                  f"{'  <<< OVERFLOW' if e > R + 0.5 else ''}")
    if over:
        detail = "; ".join(f"{b} right={e:.0f} (+{e - R:.0f}px past R={R})"
                           for b, e in over)
        raise ValueError(
            f"pa_figure_card width guard: copy will not fit the card — {detail}. "
            f"Shorten the copy; the shrink already bottomed out at {MIN_PT}pt.")

    img.save(out, "JPEG", quality=90, progressive=True, optimize=True)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--verbose"]
    spec = json.load(open(args[0]))
    print(build(spec, args[1], verbose="--verbose" in sys.argv))
