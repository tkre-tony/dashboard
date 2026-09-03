#!/usr/bin/env python3
"""
font_gate.py - prove the carousel/reel fonts still resolve to distinct weights.

WHY THIS EXISTS
---------------
S355, 2 Sep 2026. render_slides_dark_light.py resolves DM Sans weights like this:

    def dm(size, weight=400):
        f = ImageFont.truetype(os.path.join(FD, "DMSans.ttf"), size)
        try:
            f.set_variation_by_axes([min(40, max(9, size / 3)), weight])
        except Exception:
            pass                      # <-- swallows everything
        return f

If DMSans.ttf is ever replaced by a STATIC (non-variable) build, or the axis
order changes, set_variation_by_axes throws, the bare except eats it, and dm()
returns a perfectly valid font object at the default weight. Every call - 400,
500, 700, 900 - then returns the same face. The deck renders flat, with no
error, no traceback and exit 0. The only way to catch it is to notice by eye,
on a Friday, after recording.

S355 proved the fonts were correct that day by rendering four weights and
getting four different widths. It did not fix the swallow. This gate makes that
one-off check repeatable, and fails on the CAUSE (axis metadata) as well as the
SYMPTOM (collapsed widths).

Deliberately a separate file, not an edit to dm(). Touching the renderer the
day before the combined C&I + landed cycle risks the deck; a gate is additive.
Matches the js_syntax_gate / html_balance_check / news_integrity_gate pattern.

USAGE
-----
    python font_gate.py               # resolves ./fonts, like the renderer
    python font_gate.py <fontdir>

Exit 0 = fonts resolve to distinct, monotonically widening weights.
Exit 1 = at least one check failed.
Exit 2 = could not run (fonts missing / Pillow absent).
MANDATORY before any weekly carousel or reel render.
"""

import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("font_gate: Pillow not installed (pip install pillow)")
    sys.exit(2)

FD = sys.argv[1] if len(sys.argv) > 1 else "fonts"

# The weights render_slides_dark_light.py actually calls dm() with.
WEIGHTS = [400, 500, 700, 900]
PROBE = "PropertyAtlas 1,234 sqft"   # mixed caps/digits/lowercase
PROBE_SIZE = 48

# Canvas for ink measurement - comfortably larger than the probe at PROBE_SIZE.
INK_W, INK_H = 900, 90
# Bold must carry meaningfully more ink than regular. Measured 1.48x on the
# committed Space Mono files; 1.15 leaves room for a future revision of the
# family without letting an identical-file copy through.
MONO_INK_MIN_RATIO = 1.15

# DM Sans variable axes, in the order dm() passes them.
EXPECTED_AXES = [
    ("Optical size", 9, 40),
    ("Weight", 100, 1000),
]

errs = []
notes = []


def fail(msg):
    errs.append(msg)


def width(font, text):
    img = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(img)
    b = d.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def ink(font, text):
    """Dark-pixel count of the rendered probe. Used where advance width cannot
    discriminate (monospaced faces): weight shows up as ink, not extent."""
    img = Image.new("L", (INK_W, INK_H), 255)
    ImageDraw.Draw(img).text((5, 5), text, font=font, fill=0)
    px = img.load()
    return sum(1 for y in range(INK_H) for x in range(INK_W) if px[x, y] < 128)


# ---------- check 1: the three faces are present and loadable ----------
REQUIRED = ["DMSans.ttf", "SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf"]
missing = [f for f in REQUIRED if not os.path.exists(os.path.join(FD, f))]
if missing:
    print("=== font gate: %s ===" % FD)
    for f in missing:
        print("  MISSING: %s" % f)
    print("\nFAIL: required font file(s) absent - cannot proceed.")
    sys.exit(2)

print("=== font gate: %s ===" % FD)
for f in REQUIRED:
    p = os.path.join(FD, f)
    print("  %-24s %8d bytes" % (f, os.path.getsize(p)))

# ---------- check 2: OFL licences travel with the fonts ----------
# The SIL Open Font Licence requires the licence to accompany redistribution.
lic = [f for f in os.listdir(FD) if "OFL" in f.upper() or "LICENSE" in f.upper()]
if not lic:
    fail("OFL licence file(s) absent from %s - SIL OFL requires the licence to "
         "travel with redistributed fonts" % FD)
else:
    notes.append("licence files present: %s" % ", ".join(sorted(lic)))

# ---------- check 3: DM Sans is a VARIABLE build with the expected axes ----------
# This is the direct cause. A static build has no axes at all, and a reordered
# axis list would make dm()'s positional [optical, weight] call silently wrong.
dms = os.path.join(FD, "DMSans.ttf")
try:
    probe = ImageFont.truetype(dms, PROBE_SIZE)
except Exception as e:
    print("\nFAIL: DMSans.ttf will not load: %s" % e)
    sys.exit(1)

try:
    axes = probe.get_variation_axes()
except Exception as e:
    axes = None
    fail("DMSans.ttf exposes no variation axes (%s) - this is a STATIC build; "
         "dm() would silently return one weight for every call" % e)

if axes is not None:
    got = []
    for a in axes:
        name = a["name"]
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        got.append((name, a["minimum"], a["maximum"]))
    if len(got) != len(EXPECTED_AXES):
        fail("DMSans.ttf has %d variation axis/axes, expected %d: %s"
             % (len(got), len(EXPECTED_AXES), got))
    else:
        for i, (exp, act) in enumerate(zip(EXPECTED_AXES, got)):
            if exp[0].lower() != act[0].lower():
                fail("axis %d is '%s', expected '%s' - dm() passes axes "
                     "POSITIONALLY, so a reordered axis list silently applies "
                     "the wrong value" % (i, act[0], exp[0]))
            elif (act[1], act[2]) != (exp[1], exp[2]):
                fail("axis '%s' range is %s-%s, expected %s-%s"
                     % (act[0], act[1], act[2], exp[1], exp[2]))
        notes.append("axes: " + " | ".join("%s %s-%s" % a for a in got))

# ---------- check 4: replicate dm() WITHOUT the swallow ----------
# dm() guards set_variation_by_axes with `except Exception: pass`. Here the
# call is unguarded on purpose: a throw must surface, not vanish.
widths = {}
for w in WEIGHTS:
    try:
        f = ImageFont.truetype(dms, PROBE_SIZE)
        f.set_variation_by_axes([min(40, max(9, PROBE_SIZE / 3)), w])
    except Exception as e:
        fail("set_variation_by_axes threw at weight %d: %s "
             "(dm()'s bare except would have hidden this)" % (w, e))
        break
    widths[w] = width(f, PROBE)

if len(widths) == len(WEIGHTS):
    print("\n  rendered width of %r at %dpx:" % (PROBE, PROBE_SIZE))
    for w in WEIGHTS:
        print("    wght %-4d -> %4d px" % (w, widths[w]))

    vals = [widths[w] for w in WEIGHTS]
    if len(set(vals)) == 1:
        fail("all %d weights render at IDENTICAL width (%d px) - the variable "
             "axis is not applying; the deck would render flat"
             % (len(WEIGHTS), vals[0]))
    elif len(set(vals)) != len(vals):
        fail("weights do not render at distinct widths: %s"
             % dict(zip(WEIGHTS, vals)))
    else:
        # Heavier must be wider. Distinctness alone would pass on a garbled
        # mapping; monotonicity is the stronger claim.
        bad = [(WEIGHTS[i], vals[i], WEIGHTS[i + 1], vals[i + 1])
               for i in range(len(vals) - 1) if vals[i] >= vals[i + 1]]
        if bad:
            for a, av, b, bv in bad:
                fail("wght %d (%dpx) is not narrower than wght %d (%dpx) - "
                     "weight axis is mapped wrongly" % (a, av, b, bv))
        else:
            notes.append("four distinct, monotonically widening weights")

# ---------- check 5: Space Mono regular and bold are different faces ----------
# Two separate static files; a copy-paste of one over the other is silent.
#
# NOTE: width is USELESS here. Space Mono is monospaced, so regular and bold
# share identical advance widths by design - both render this probe at 705px.
# The first draft of this gate compared widths and failed on correct fonts.
# Weight difference shows up as INK, not extent, so rasterise and count dark
# pixels instead. Measured on the committed files: 5,750 vs 8,508 px (1.48x).
try:
    mr = ImageFont.truetype(os.path.join(FD, "SpaceMono-Regular.ttf"), PROBE_SIZE)
    mb = ImageFont.truetype(os.path.join(FD, "SpaceMono-Bold.ttf"), PROBE_SIZE)
    ir, ib = ink(mr, PROBE), ink(mb, PROBE)
    print("\n  Space Mono ink coverage  regular -> %5d px   bold -> %5d px  (%.2fx)"
          % (ir, ib, (ib / ir) if ir else 0))
    if ir == 0 or ib == 0:
        fail("a Space Mono face rendered nothing at all (regular %d px, bold %d px)"
             % (ir, ib))
    elif ib <= ir * MONO_INK_MIN_RATIO:
        fail("SpaceMono-Bold carries only %.2fx the ink of Regular (expected "
             "> %.2fx) - one file has probably been copied over the other"
             % (ib / ir, MONO_INK_MIN_RATIO))
    else:
        notes.append("Space Mono regular/bold are distinct faces (%.2fx ink)"
                     % (ib / ir))
except Exception as e:
    fail("Space Mono faces would not load: %s" % e)

# ---------- verdict ----------
print()
for n in notes:
    print("  ok  %s" % n)

if errs:
    print("\nERRORS (%d):" % len(errs))
    for e in errs:
        print("  - %s" % e)
    print("\nFAIL")
    sys.exit(1)

print("\nCLEAN: fonts resolve to distinct weights; carousel/reel will render correctly.")
sys.exit(0)
