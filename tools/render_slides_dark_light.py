#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PropertyAtlas — Weekly Caveat Wrap carousel renderer
1920x1080 · 13 slides · slides 1-12 dark navy, slide 13 light outro flip.
Standing format ratified S181, rebuilt S203 to match carousel #1 house style.
Fonts: DM Sans (variable) + Space Mono.  Deps: Pillow.
"""
import os, re
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
OUT, FD = "slides", "fonts"

NAVY      = (10, 22, 42)
NAVY_DEEP = (6, 14, 28)
CARD      = (22, 38, 64)
CARD_BRD  = (40, 58, 88)
GOLD      = (222, 178, 74)
PERI      = (128, 148, 226)
GREEN     = (74, 214, 138)
CORAL     = (240, 116, 96)
WHITE     = (255, 255, 255)
MUTE      = (128, 146, 178)
DIM       = (96, 112, 142)

CREAM     = (250, 246, 238)
INK       = (18, 26, 44)
INK_MUT   = (108, 100, 86)
GOLD_DK   = (170, 130, 40)

FOOT_L = "@propertyatlassg  ·  propertyatlas.sg"
FOOT_R = "TK Real Estate Pte Ltd | Estate Agent Licence No : L3011027G"

def _load_logo(path, dark_mark):
    """Project-knowledge copies lost their alpha channel; rebuild it from
    luminance so the mark keys out instead of pasting a solid square."""
    im = Image.open(path)
    if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] < 255:
        return im
    rgb = im.convert("RGB")
    lum = rgb.convert("L")
    a = lum.point(lambda v: 255 - v) if dark_mark else lum
    out = rgb.convert("RGBA"); out.putalpha(a)
    return out

_lw = _load_logo("TK_REAL_ESTATE_WHITE.png", dark_mark=False)
_lb = _load_logo("TK_REAL_ESTATE_BLACK.png", dark_mark=True)
_lw = _lw.crop(_lw.getchannel("A").getbbox())
_lb = _lb.crop(_lb.getchannel("A").getbbox())


def dm(size, weight=400):
    f = ImageFont.truetype(os.path.join(FD, "DMSans.ttf"), size)
    try:
        f.set_variation_by_axes([min(40, max(9, size / 3)), weight])
    except Exception:
        pass
    return f


def mono(size, bold=False):
    return ImageFont.truetype(
        os.path.join(FD, "SpaceMono-Bold.ttf" if bold else "SpaceMono-Regular.ttf"), size)


def tw(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def track(d, xy, text, font, fill, sp=0):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += tw(d, ch, font) + sp
    return x


def track_w(d, text, font, sp=0):
    return sum(tw(d, c, font) + sp for c in text) - sp if text else 0


# ------------------------------------------------------------------ address
UNIT_RE = re.compile(r"#\d+-\w+")
NUM_RE = re.compile(r"^\d+[A-Za-z]?\s+")


def mask(addr):
    """Strata (has unit): keep street no., mask unit -> 140 Paya Lebar Road #09-XX
       No unit (whole building / land): mask street no. -> XX Gul Avenue"""
    if "#" in addr:
        return UNIT_RE.sub(lambda m: m.group(0).rsplit("-", 1)[0] + "-XX", addr)
    return NUM_RE.sub("XX ", addr)


SMALL = {"of", "the", "at"}


def tc(s):
    out = []
    for w in s.split():
        if w.startswith("#") or w.upper() in ("XX", "E9", "II", "AZ", "SBF", "PSF"):
            out.append(w if not w.islower() else w.upper())
        elif re.match(r"^\d+[A-Za-z]$", w):
            out.append(w[:-1] + w[-1].upper())
        elif w.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append(w[0].upper() + w[1:].lower())
    return " ".join(out)


def disp(addr):
    return tc(mask(addr))


def money(n):
    return "S$" + format(int(round(float(n))), ",")


def sgd(n):
    n = float(n)
    if abs(n) >= 1_000_000:
        return "S$%.2fM" % (n / 1_000_000)
    if abs(n) >= 1_000:
        return "S$%dK" % round(n / 1000)
    return "S$%d" % n


# ------------------------------------------------------------------ chrome
def base_dark():
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = (y / H) ** 1.2
        d.line([(0, y), (W, y)], fill=tuple(
            int(NAVY[i] + (NAVY_DEEP[i] - NAVY[i]) * t) for i in range(3)))
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for x in range(0, W, 64):
        gd.line([(x, 0), (x, H)], fill=(255, 255, 255, 7))
    for y in range(0, H, 64):
        gd.line([(0, y), (W, y)], fill=(255, 255, 255, 7))
    img = Image.alpha_composite(img.convert("RGBA"), g)
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(v)
    for i in range(80):
        vd.rectangle([i * 3, i * 2, W - i * 3, H - i * 2],
                     outline=(0, 0, 0, int(60 * (i / 80) ** 2.4)))
    return Image.alpha_composite(img, v).convert("RGB")


def chrome(img, light=False):
    d = ImageDraw.Draw(img)
    mut = (168, 156, 138) if light else DIM
    bf = dm(24, 700)
    box = [68, 50, 68 + 68, 50 + 42]
    d.rounded_rectangle(box, 5, outline=GOLD_DK if light else GOLD, width=2)
    t = "P|A"
    d.text((box[0] + (68 - tw(d, t, bf)) / 2, box[1] + 6), t,
           font=bf, fill=GOLD_DK if light else GOLD)
    lg = (_lb if light else _lw)
    hh = 70
    lg = lg.resize((int(lg.width * hh / lg.height), hh), Image.LANCZOS)
    img.paste(lg, (W - 68 - lg.width, 44), lg)
    ff = mono(15)
    d = ImageDraw.Draw(img)
    track(d, (68, H - 58), FOOT_L, ff, mut, 1.2)
    track(d, (W - 68 - track_w(d, FOOT_R, ff, 1.2), H - 58), FOOT_R, ff, mut, 1.2)
    return img


def header(d, kicker, headline, sub=None):
    kf = mono(17)
    track(d, (68, 118), kicker.upper(), kf, GOLD, 5)
    d.text((66, 152), headline.upper(), font=dm(56, 700), fill=WHITE)
    if sub:
        track(d, (68, 228), sub.upper(), mono(17), MUTE, 4)


def rank_card(img, d, y, rank, name, meta, right_big, right_sml, col=GOLD, h=92):
    x0, x1 = 68, W - 68
    d.rounded_rectangle([x0, y, x1, y + h], 10, fill=CARD, outline=CARD_BRD, width=1)
    rf = dm(38, 700)
    d.text((x0 + 34, y + h / 2 - 28), str(rank), font=rf, fill=GOLD)
    d.text((x0 + 96, y + 18), name, font=dm(30, 700), fill=WHITE)
    track(d, (x0 + 98, y + 58), meta, mono(17), MUTE, 1.4)
    bf = dm(38, 700)
    d.text((x1 - 34 - tw(d, right_big, bf), y + 16), right_big, font=bf, fill=col)
    sf = mono(17)
    track(d, (x1 - 34 - track_w(d, right_sml, sf, 1.2), y + 62), right_sml, sf, MUTE, 1.2)


def note(d, text):
    track(d, (68, H - 106), text.upper(), mono(16), DIM, 2)


def head_meta(proj, addr, typ, tenure, area, extra=""):
    """Head line and meta line for one row.

    Shipped format: [address ·] type · tenure · area [· hold · ann].
    With no project name the address becomes the head and is not repeated
    in the meta.
    """
    head = proj if proj else disp(addr)
    parts = ([disp(addr)] if proj else []) + [typ, tenure, "%s sq ft" % format(int(area), ",")]
    return head, "  ·  ".join(parts) + extra


# ================================================================== DATA
WEEK = "Week of 31st August 2026"
LODGED = "URA REALIS caveats lodged 1 and 4 September"
TOTAL, N_CAV, N_PAIR = "S$203.34M", 61, 41
IND_N, IND_V, COM_N, COM_V = 39, 60.93, 22, 142.41
N_GAIN, N_LOSS = 35, 6
SALE_ROWS = [("RESALE", 53, 118814448, WHITE),
             ("NEW SALE  \u00b7  7 OF 8 CECIL PLACE", 8, 84529596, GOLD)]
S02_NOTE = "41 of 61 caveats matched a prior transaction  \u00b7  20 unmatched  \u00b7  net realised +S$44,921,643"

IND_VALUE = [('', '58 TUAS BASIN LINK', 'Single-User', '30-yr from 2023', 58974, 10800000, 183, 'land'),
             ('Hillview Industrial Estate', '28 HILLVIEW TERRACE', 'Single-User', '999-yr from 1885', 5672, 8500000, 1499, 'land'),
             ('Space 18', '18 LORONG AMPAS #02-05', 'Multiple-User', 'Freehold', 1787, 2600000, 1455, 'strata'),
             ('Tong Lee Building', '37 KALLANG PUDDING ROAD #05-02', 'Multiple-User', 'Freehold', 2982, 2266320, 760, 'strata'),
             ('West Spring', '71B TUAS BAY DRIVE', 'Multiple-User', '60-yr from 2006', 5457, 1948000, 357, 'strata')]
IND_PSF = [('Space 18', '18 LORONG AMPAS #02-05', 'Multiple-User', 'Freehold', 1787, 2600000, 1455, 'strata'),
             ('Solstice Business Center', '23 NEW INDUSTRIAL ROAD #04-03', 'Multiple-User', 'Freehold', 1518, 1750000, 1153, 'strata'),
             ('M-Space', '6D MANDAI ESTATE #08-09', 'Multiple-User', 'Freehold', 1259, 1300000, 1032, 'strata'),
             ('Perfect One', '1 GENTING LINK #03-06', 'Warehouse', 'Freehold', 1335, 1161450, 870, 'strata'),
             ('E-Centre @ Redhill', '3791 JALAN BUKIT MERAH #09-06', 'Multiple-User', '99-yr from 1962', 1012, 780000, 771, 'strata')]
COM_VALUE = [('Telok Ayer Conservation Area', '261 SOUTH BRIDGE ROAD', 'Shop House', '999-yr from 1823', 1352, 16800000, 12426, 'land'),
             ('Boat Quay Conservation Area', '85 CIRCULAR ROAD', 'Shop House', '999-yr from 1831', 1075, 16200000, 15065, 'land'),
             ('Cecil Place', '137 CECIL STREET #08-01', 'Office', 'Freehold', 3918, 15437314, 3940, 'strata'),
             ('Cecil Place', '137 CECIL STREET #14-01', 'Office', 'Freehold', 3638, 15098659, 4150, 'strata'),
             ('Cecil Place', '137 CECIL STREET #14-02', 'Office', 'Freehold', 2551, 10586940, 4150, 'strata')]
COM_PSF = [('The Bencoolen', '180 BENCOOLEN STREET #01-70', 'Retail', '99-yr from 1995', 183, 1188000, 6492, 'strata'),
             ('VisionCrest', '103 PENANG ROAD #04-03', 'Office', 'Freehold', 1744, 7600000, 4358, 'strata'),
             ('Far East Shopping Centre', '545 ORCHARD ROAD #05-41', 'Office', '999-yr from 1871', 205, 850000, 4156, 'strata'),
             ('Cecil Place', '137 CECIL STREET #14-01', 'Office', 'Freehold', 3638, 15098659, 4150, 'strata'),
             ('Cecil Place', '137 CECIL STREET #14-02', 'Office', 'Freehold', 2551, 10586940, 4150, 'strata')]
COM_GAIN = [('Telok Ayer Conservation Area', '261 SOUTH BRIDGE ROAD', 'Shop House', '999-yr from 1823', 1352, 14200000, 546.2, 19.5, 10.1, ''),
             ('Boat Quay Conservation Area', '85 CIRCULAR ROAD', 'Shop House', '999-yr from 1831', 1075, 13550000, 511.3, 19.3, 9.8, ''),
             ('', '463 BALESTIER ROAD', 'Shop House', 'Freehold', 1068, 3000000, 352.9, 17.7, 8.9, ''),
             ('The Bencoolen', '180 BENCOOLEN STREET #01-70', 'Retail', '99-yr from 1995', 183, 653000, 122.1, 26.0, 3.1, ''),
             ('Paya Lebar Square', '60 PAYA LEBAR ROAD #11-18', 'Office', '99-yr from 2011', 1324, 646820, 26.5, 14.3, 1.7, '')]
COM_LOSS = [('NEWest', '1 WEST COAST DRIVE #01-36', 'Retail', '956-yr from 1928', 280, -1084000, -61.5, 13.2, -7.0, ''),
             ('Centropod @ Changi', '80 CHANGI ROAD #05-19', 'Office', 'Freehold', 764, -508813, -34.9, 13.6, -3.1, ''),
             ('East Village', '430 UPPER CHANGI ROAD #01-92', 'Retail', 'Freehold', 183, -303377, -31.4, 14.4, -2.6, ''),
             ('Hexacube', '160 CHANGI ROAD #04-10', 'Office', 'Freehold', 506, -123000, -11.3, 12.4, -1.0, '')]
IND_GAIN = [('', '58 TUAS BASIN LINK', 'Single-User', '30-yr from 2023', 58974, 3700000, 52.1, 15.4, 2.8, ' *'),
             ('Hillview Industrial Estate', '28 HILLVIEW TERRACE', 'Single-User', '999-yr from 1885', 5672, 3500000, 70.0, 14.0, 3.9, ''),
             ('Frontier', '52 UBI AVENUE 3 #05-45', 'Multiple-User', '60-yr from 1999', 4435, 1195510, 263.0, 20.3, 6.6, ' *'),
             ('North Link Building', '10 ADMIRALTY STREET #02-83', 'Multiple-User', '60-yr from 1999', 5188, 832000, 124.6, 21.4, 3.8, ''),
             ('North Link Building', '10 ADMIRALTY STREET #01-41', 'Multiple-User', '60-yr from 1999', 5188, 720000, 61.0, 15.2, 3.2, '')]
IND_LOSS = [('T99', '9 TUAS SOUTH AVENUE 10 #03-22', 'Multiple-User', '30-yr from 2013', 2659, -554000, -46.4, 10.7, -5.7, ''),
             ('North View Bizhub', '6 YISHUN INDUSTRIAL STREET 1 #04-02', 'Multiple-User', '30-yr from 2012', 1755, -15000, -3.0, 5.8, -0.5, '')]

GATE = dict(n=7, value=81929596, med=3920, lo=3860, hi=4150)
GATE_HEAD = "Nine months in one release"
GATE_SUB = "Cecil Place  \u00b7  D01"
NOTE_S03 = "Whole-building PSF is land-basis \u2014 not comparable to strata PSF"
NOTE_S04 = "Strata per-unit basis  \u00b7  land-basis deals excluded"
NOTE_S05 = "Rows 1 and 2 are shophouses  \u00b7  PSF is land-basis, not strata"
NOTE_S05B = "Strata basis  \u00b7  land-basis deals excluded"
GATE_BULLETS = [("7 caveats", "  \u00b7  S$81.93M  \u2014  40.3% of the week by value"),
                ("", "Sales dated 5 Dec 2025 to 22 May 2026  \u00b7  floors 6 to 14"),
                ("", "Both fourteenth-floor units cleared at exactly S$4,150 psf"),
                ("", "7 of the week's 8 new sales  \u00b7  everything else is resale")]

TENURE = [("FH / 999 yrs", 24), ("55-60 yrs", 23), ("30-33 yrs", 7), ("99 yrs", 5), ("20-26 yrs", 2)]
TENURE_HEAD = "24 of 61 are freehold or 999-year"
FEATURE = ("Cecil Place  \u00b7  137 Cecil Street",
           "S$81.93M  \u00b7  S$3,860\u20134,150 PSF  \u00b7  20,613 SQFT ACROSS 7 UNITS  \u00b7  FREEHOLD STRATA OFFICE")

COM_GAIN_SUB = "Top 5 of 9 gains (9 of 13 commercial pairs profitable)"
COM_LOSS_SUB = "All 4 losses (of 13 commercial pairs)"
IND_GAIN_SUB = "Top 5 of 26 gains (26 of 28 industrial pairs profitable)"
IND_LOSS_SUB = "All 2 losses (of 28 industrial pairs)"
COM_GAIN_FOOT = "Three shophouses carried S$30.75M of the S$44.92M in gains"
COM_LOSS_FOOT = "Three of four commercial losses sit on Changi Road"
IND_GAIN_FOOT = "* area or lease changed between buy and sell  \u00b7  not like-for-like"
IND_LOSS_FOOT = "Only 2 of 28 industrial pairs lost money this week"


# ================================================================== SLIDES
def s01():
    img = base_dark()
    d = ImageDraw.Draw(img)
    f = mono(21)
    t = "WEEKLY CAVEAT WRAP"
    track(d, ((W - track_w(d, t, f, 9)) / 2, 200), t, f, GOLD, 9)
    hf = dm(64, 700)
    d.text(((W - tw(d, WEEK, hf)) / 2, 252), WEEK, font=hf, fill=WHITE)
    bf = dm(186, 700)
    d.text(((W - tw(d, TOTAL, bf)) / 2, 352), TOTAL, font=bf, fill=GOLD)
    sf = mono(26)
    s = "%d CAVEATS   ·   %d MATCHED RESALES" % (N_CAV, N_PAIR)
    track(d, ((W - track_w(d, s, sf, 4)) / 2, 604), s, sf, WHITE, 4)
    bx, bw, by, bh = 500, W - 1000, 690, 18
    iw = int(bw * IND_N / N_CAV)
    d.rounded_rectangle([bx, by, bx + bw, by + bh], 9, fill=GOLD)
    d.rounded_rectangle([bx, by, bx + iw, by + bh], 9, fill=PERI)
    lf = mono(18)
    track(d, (bx, by + 38), "INDUSTRIAL %d" % IND_N, lf, PERI, 3)
    r = "COMMERCIAL %d" % COM_N
    track(d, (bx + bw - track_w(d, r, lf, 3), by + 38), r, lf, GOLD, 3)
    vf = mono(18)
    v = "S$%.2fM INDUSTRIAL   ·   S$%.2fM COMMERCIAL" % (IND_V, COM_V)
    track(d, ((W - track_w(d, v, vf, 2)) / 2, by + 82), v, vf, DIM, 2)
    return chrome(img)


def s02():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "The week in numbers",
           LODGED)
    tiles = [(TOTAL, "TOTAL VALUE", GOLD), (str(N_CAV), "CAVEATS", WHITE),
             (str(N_PAIR), "MATCHED RESALES", PERI),
             ("%d / %d" % (N_GAIN, N_LOSS), "GAINS / LOSSES", GREEN)]
    bw, gap = 404, 32
    x = (W - (bw * 4 + gap * 3)) / 2
    for val, lab, col in tiles:
        d.rounded_rectangle([x, 300, x + bw, 520], 12, fill=CARD, outline=CARD_BRD)
        vf = dm(62, 700)
        d.text((x + (bw - tw(d, val, vf)) / 2, 350), val, font=vf, fill=col)
        lf = mono(16)
        track(d, (x + (bw - track_w(d, lab, lf, 3)) / 2, 452), lab, lf, MUTE, 3)
        x += bw + gap
    y = 580
    for lab, n, v, col in SALE_ROWS:
        d.rounded_rectangle([68, y, W - 68, y + 92], 10, fill=CARD, outline=CARD_BRD)
        track(d, (102, y + 34), lab, mono(21), MUTE, 3)
        nf = dm(34, 700)
        d.text((W - 102 - tw(d, money(v), nf), y + 26), money(v), font=nf, fill=col)
        cf = mono(19)
        track(d, (W - 420 - track_w(d, "%d CAVEATS" % n, cf, 2), y + 36),
              "%d CAVEATS" % n, cf, MUTE, 2)
        y += 108
    note(d, S02_NOTE)
    return chrome(img)


def s03():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "Top 5 — highest value", "Industrial")
    y = 292
    for i, (proj, addr, typ, tenure, area, price, psf, basis) in enumerate(IND_VALUE, 1):
        hd, mt = head_meta(proj, addr, typ, tenure, area)
        rank_card(img, d, y, i, hd, mt, sgd(price),
                  "S$%s psf%s" % (format(psf, ","), " (land)" if basis == "land" else ""))
        y += 104
    note(d, NOTE_S03)
    return chrome(img)


def s04():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "Top 5 — price PSF", "Industrial")
    y = 292
    for i, (proj, addr, typ, tenure, area, price, psf, basis) in enumerate(IND_PSF, 1):
        hd, mt = head_meta(proj, addr, typ, tenure, area)
        rank_card(img, d, y, i, hd, mt, "S$%s%s" % (format(psf, ","),
                  " (land)" if basis == "land" else ""), sgd(price))
        y += 104
    note(d, NOTE_S04)
    return chrome(img)


def s05():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "Top 5 — highest value", "Commercial")
    y = 292
    for i, (proj, addr, typ, tenure, area, price, psf, basis) in enumerate(COM_VALUE, 1):
        hd, mt = head_meta(proj, addr, typ, tenure, area)
        rank_card(img, d, y, i, hd, mt,
                  sgd(price), "S$%s psf%s" % (format(psf, ","),
                  " (land)" if basis == "land" else ""))
        y += 104
    note(d, NOTE_S05)
    return chrome(img)


def s05b():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "Top 5 — price PSF", "Commercial")
    y = 292
    for i, (proj, addr, typ, tenure, area, price, psf, basis) in enumerate(COM_PSF, 1):
        hd, mt = head_meta(proj, addr, typ, tenure, area)
        rank_card(img, d, y, i, hd, mt,
                  "S$%s%s" % (format(psf, ","), " (land)" if basis == "land" else ""),
                  sgd(price))
        y += 104
    note(d, NOTE_S05B)
    return chrome(img)


def s06():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK + "  ·  New launch", GATE_HEAD, GATE_SUB)
    tiles = [(str(GATE["n"]), "NEW-SALE CAVEATS", WHITE),
             (sgd(GATE["value"]), "TOTAL LODGED", GOLD),
             ("S$%s" % format(GATE["med"], ","), "MEDIAN PSF", WHITE),
             ("S$%s–%s" % (format(GATE["lo"], ","), format(GATE["hi"], ",")), "PSF RANGE", WHITE)]
    bw, gap = 404, 32
    x = (W - (bw * 4 + gap * 3)) / 2
    for val, lab, col in tiles:
        d.rounded_rectangle([x, 300, x + bw, 520], 12, fill=CARD, outline=CARD_BRD)
        vf = dm(56, 700)
        d.text((x + (bw - tw(d, val, vf)) / 2, 356), val, font=vf, fill=col)
        lf = mono(16)
        track(d, (x + (bw - track_w(d, lab, lf, 3)) / 2, 452), lab, lf, MUTE, 3)
        x += bw + gap
    bullets = GATE_BULLETS
    y = 580
    for hi, rest in bullets:
        d.text((72, y), "▪", font=dm(20, 700), fill=GOLD)
        x = 110
        if hi:
            f = mono(22, True)
            d.text((x, y), hi, font=f, fill=GOLD)
            x += tw(d, hi, f)
        d.text((x, y), rest, font=mono(22), fill=WHITE)
        y += 48
    return chrome(img)


def pnl_slide(kicker, head, sub, rows, col, foot):
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, kicker, head, sub)
    y = 292
    for i, r in enumerate(rows, 1):
        proj, addr, typ, tenure, area = r[0], r[1], r[2], r[3], r[4]
        profit, pct, yrs, ann = r[5], r[6], r[7], r[8]
        flag = r[9] if len(r) > 9 else ""
        hd, meta = head_meta(proj, addr, typ, tenure, area,
                             "  ·  %.1f-yr hold  ·  %+.1f%%/yr%s" % (yrs, ann, flag))
        rank_card(img, d, y, i, hd, meta,
                  "%+.0f%%" % pct if abs(pct) >= 1 else "%+.1f%%" % pct,
                  ("+" if profit > 0 else "−") + sgd(abs(profit))[2:].join(["S$", ""]),
                  col=col)
        y += 104
    note(d, foot)
    return chrome(img)


def s07():
    return pnl_slide(WEEK, "Commercial — P & L", COM_GAIN_SUB,
                     COM_GAIN, GREEN, COM_GAIN_FOOT)


def s07b():
    return pnl_slide(WEEK, "Commercial — P & L", COM_LOSS_SUB,
                     COM_LOSS, CORAL, COM_LOSS_FOOT)


def s08():
    return pnl_slide(WEEK, "Industrial — P & L", IND_GAIN_SUB,
                     IND_GAIN, GREEN, IND_GAIN_FOOT)


def s09():
    return pnl_slide(WEEK, "Industrial — P & L", IND_LOSS_SUB,
                     IND_LOSS, CORAL, IND_LOSS_FOOT)


def s10():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK + "  ·  Lease tenure",
           TENURE_HEAD, "Remaining tenure at point of sale")
    y = 300
    mx = max(n for _, n in TENURE)
    for lab, n in TENURE:
        track(d, (72, y + 8), lab.upper(), mono(21), WHITE, 2)
        bx = 400
        bw = int((W - 260 - bx) * n / mx)
        col = GOLD if "FH" in lab else (CORAL if lab[:2] in ("30", "33") else PERI)
        d.rounded_rectangle([bx, y, bx + max(bw, 8), y + 40], 6, fill=col)
        d.text((bx + max(bw, 8) + 20, y + 4), str(n), font=dm(28, 700), fill=MUTE)
        y += 60
    d.rounded_rectangle([68, y + 26, W - 68, y + 168], 12, fill=CARD, outline=CARD_BRD)
    d.text((104, y + 54), FEATURE[0], font=dm(32, 700), fill=WHITE)
    track(d, (106, y + 104), FEATURE[1], mono(19), GOLD, 1.4)
    return chrome(img)


def s11():
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=GOLD_DK)
    d.line([(W / 2, 180), (W / 2, H - 160)], fill=(220, 210, 192), width=1)
    cx = W / 4 + 20
    bf = dm(42, 700)
    box = [cx - 82, 190, cx + 82, 190 + 100]
    d.rounded_rectangle(box, 8, outline=GOLD_DK, width=3)
    t = "P|A"
    d.text((cx - tw(d, t, bf) / 2, 218), t, font=bf, fill=GOLD_DK)
    hf = dm(62, 700)
    d.text((cx - tw(d, "PROPERTYATLAS", hf) / 2, 330), "PROPERTYATLAS", font=hf, fill=INK)
    sf = dm(28, 400)
    for i, ln in enumerate(["Singapore Commercial & Industrial", "Real Estate Intelligence"]):
        d.text((cx - tw(d, ln, sf) / 2, 424 + i * 42), ln, font=sf, fill=INK_MUT)
    d.line([(cx - 70, 528), (cx + 70, 528)], fill=GOLD_DK, width=3)
    uf = mono(30)
    u = "propertyatlas.sg"
    track(d, (cx - track_w(d, u, uf, 3) / 2, 566), u, uf, GOLD_DK, 3)

    rx = W * 3 / 4
    hh = 220
    lg = _lb.resize((int(_lb.width * hh / _lb.height), hh), Image.LANCZOS)
    img.paste(lg, (int(rx - lg.width / 2), 176), lg)
    d = ImageDraw.Draw(img)
    qf = dm(31, 700)
    for i, ln in enumerate(["Looking to buy, sell or lease",
                            "commercial & industrial space?"]):
        d.text((rx - tw(d, ln, qf) / 2, 430 + i * 44), ln, font=qf, fill=INK)
    d.line([(rx - 70, 534), (rx + 70, 534)], fill=GOLD_DK, width=3)
    cf = mono(23)
    c = "TK REAL ESTATE PTE LTD"
    track(d, (rx - track_w(d, c, cf, 4) / 2, 568), c, cf, INK, 4)
    nf = dm(36, 700)
    d.text((rx - tw(d, "Tony Koe", nf) / 2, 608), "Tony Koe", font=nf, fill=INK)
    rf = mono(21)
    r = "Founder, Key Executive Officer"
    track(d, (rx - track_w(d, r, rf, 2) / 2, 662), r, rf, INK_MUT, 2)
    lf = mono(21)
    l = "CEA Licence R003757I"
    track(d, (rx - track_w(d, l, lf, 2) / 2, 706), l, lf, INK_MUT, 2)
    ef = mono(21)
    e = "Mobile : (+65) 9797 1118  |  Email : tony@tkre.sg"
    track(d, (rx - track_w(d, e, ef, 2) / 2, 758), e, ef, GOLD_DK, 2)

    ff = mono(15)
    track(d, (68, H - 58), FOOT_L, ff, (172, 160, 142), 1.2)
    track(d, (W - 68 - track_w(d, FOOT_R, ff, 1.2), H - 58), FOOT_R, ff, (172, 160, 142), 1.2)
    return img


SLIDES = [s01, s02, s03, s04, s05, s05b, s06, s07, s07b, s08, s09, s10, s11]

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    imgs = []
    for i, fn in enumerate(SLIDES, 1):
        im = fn()
        im.save(os.path.join(OUT, "slide_%02d.png" % i))
        imgs.append(im.convert("RGB"))
        print("rendered slide_%02d.png" % i)
    imgs[0].save("Week_of_31Aug2026_LinkedIn_Carousel.pdf",
                 save_all=True, append_images=imgs[1:], resolution=150)
    print("PDF written")
