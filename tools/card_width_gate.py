#!/usr/bin/env python3
"""card_width_gate.py — S384. Fail any rendered card whose text runs into the side margins.

Usage:  python3 tools/card_width_gate.py <card.jpg|png> [...] [--margin 40]

Why on the image and not the text: every card renderer's fit() sizes type on HEIGHT
only, so a line can fit vertically and still run off the 1200px canvas. The id:250
kicker did exactly that at 1,173px (S379). Checking the rendered pixels covers every
renderer — mkcard.py (pad 56), pa_figure_card.py, hero scripts (pad 64) — without
re-implementing their layout.

Method: in each side band (default the outer 40px), estimate each row's background as
the band's median, then count pixels that differ from it by more than a luminance
threshold. Legitimate content ends at the renderer padding (>= 56px in), so anything
inked inside the outer band is overflow. Photos are out of scope: run this on cards.
"""
import sys
from PIL import Image

def check(path, margin=40, thresh=45, min_px=12):
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    out = []
    for side, xs in (("right", range(w - margin, w)), ("left", range(0, margin))):
        inked, cols = 0, set()
        for y in range(h):
            row = sorted(px[x, y] for x in xs)
            bg = row[len(row) // 2]
            for x in xs:
                if abs(px[x, y] - bg) > thresh:
                    inked += 1; cols.add(x)
        if inked >= min_px:
            extent = (max(cols) if side == "right" else min(cols))
            out.append((side, inked, extent))
    return (w, h), out

def main(argv):
    margin = 40
    if "--margin" in argv:
        i = argv.index("--margin"); margin = int(argv[i + 1]); del argv[i:i + 2]
    if not argv:
        print(__doc__); return 2
    fails = 0
    for p in argv:
        (w, h), hits = check(p, margin)
        if hits:
            fails += 1
            for side, n, ext in hits:
                print(f"FAIL  {p}  {w}x{h}  text in the {side} {margin}px margin — {n} px inked, reaching x={ext}")
        else:
            print(f"ok    {p}  {w}x{h}  both {margin}px side margins clear")
    print(f"\n=== card width gate: {len(argv)} card(s) · {fails} failure(s)")
    print("FAIL" if fails else "CLEAN: no card text reaches the side margins.")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
