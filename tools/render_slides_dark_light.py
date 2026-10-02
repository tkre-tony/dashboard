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
UNIT_RE = re.compile(r"#[A-Z]?\d+-[\w,]+")          # S371: basement units (#B1-01) and multi-unit caveats (#33-10,10A)
NUM_RE = re.compile(r"^\d[\dA-Za-z,]*\s+(?:ETC\s+)?")  # S371: "406,406A,406B JOO CHIAT ROAD", "25 ETC LOYANG CRESCENT"


def mask(addr):
    """Strata (has unit): keep street no., mask unit -> 140 Paya Lebar Road #09-XX
       No unit (whole building / land): mask street no. -> XX Gul Avenue"""
    if "#" in addr:
        return UNIT_RE.sub(lambda m: m.group(0).split("-", 1)[0] + "-XX", addr)
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
    """S388: round half-up in decimal. '%.2f' and round() are float/banker's and
    printed 1,505,000 as S$1.50M and 848,500 as S$848K against the reel's
    S$1.51M / S$849K (same DATA, different rounding)."""
    from decimal import Decimal, ROUND_HALF_UP
    q = lambda v, e: Decimal(str(v)).quantize(Decimal(e), rounding=ROUND_HALF_UP)
    n = float(n)
    if abs(n) >= 1_000_000:
        return "S$%sM" % q(n / 1_000_000, "0.01")
    if abs(n) >= 1_000:
        return "S$%dK" % int(q(n / 1000, "1"))
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
# Week of 28th September 2026 · URA REALIS releases 29 Sep (5) + 2 Oct (55) · ids 83,248–83,307 · built S390.
# Matches article id:269: 60 caveats, S$480.4M, 38 pairs (29G / 9L), median +30.3% over 11.8y.
# pnl_pairs_mv refreshed 2 Oct 2026 (29,922 pairs); the MV returns 39 batch pairs — the 39th is the E-Centre @ Redhill
# re-issued caveat (id 83275 against 83107, same price, 0.05y) and is EXCLUDED from pairs (Tony's ruling, S390):
# counted as a caveat, unpaired. 38 paired + 22 unpaired (21 no prior caveat + 1 re-issue) = 60.
# Flagged rows carry " *": North Bridge Road lease_event (new 99-yr lease after purchase); Pandan Loop area 2,067 → 2,121 sq ft.
# TENURE is remaining lease at sale date.
WEEK = 'Week of 28th September 2026'
LODGED = 'URA REALIS caveats released 29th September and 2nd October 2026'
TOTAL, N_CAV, N_PAIR = 'S$480.43M', 60, 38
IND_N, IND_V, COM_N, COM_V = 44, 428.68, 16, 51.75
N_GAIN, N_LOSS = 29, 9
SALE_ROWS = [('RESALE', 55, 468989231, WHITE),
             ('NEW SALE  ·  LENTOR GARDENS, GOLDEN MILE, SPACE 18', 5, 11437673, GOLD)]
S02_NOTE = '38 of 60 caveats matched a prior transaction  ·  21 unmatched  ·  1 re-issued  ·  net realised +S$24,494,053'

IND_VALUE = [('Advanced Display Park', 'XX TAMPINES INDUSTRIAL AVENUE 3', 'Single-User', '30+28-yr from 2001', 997340, 350000000, 351, 'land'), ('JDE Building', 'XX TUAS LINK 2', 'Single-User', '30-yr from 2011', 107713, 15000000, 139, 'land'), ('', 'XX TUAS VIEW SQUARE', 'Single-User', '60-yr from 1996', 16586, 14380000, 867, 'land'), ('Food Concept @ Pandan', '239 PANDAN LOOP #05-XX', 'Multiple-User', 'Freehold', 2121, 3100000, 1462, 'strata'), ('Citilink Warehouse Complex', '102F PASIR PANJANG ROAD #05-XX', 'Warehouse', 'Freehold', 2443, 3038000, 1243, 'strata')]
IND_PSF = [('Mapex', '37 JALAN PEMIMPIN #08-XX', 'Multiple-User', 'Freehold', 1636, 2650000, 1620, 'strata'), ('Food Concept @ Pandan', '239 PANDAN LOOP #05-XX', 'Multiple-User', 'Freehold', 2121, 3100000, 1462, 'strata'), ('Space 18', '18 LORONG AMPAS #03-XX', 'Multiple-User', 'Freehold', 1787, 2594023, 1452, 'strata'), ('HH @ Kallang', '56 KALLANG PUDDING ROAD #08-XX/XX', 'Multiple-User', 'Freehold', 1765, 2400000, 1360, 'strata'), ('Citilink Warehouse Complex', '102F PASIR PANJANG ROAD #05-XX', 'Warehouse', 'Freehold', 2443, 3038000, 1243, 'strata')]
COM_VALUE = [('GB Building', '143 CECIL STREET #11-XX/XX/XX/XX', 'Office', '99-yr from 1982', 5425, 10250000, 1889, 'strata'), ('Kampong Glam', 'XX JALAN PINANG', 'Shop House', '99-yr from 2006', 1732, 6880733, 3973, 'land'), ('Kampong Glam', 'XX NORTH BRIDGE ROAD', 'Shop House', '99-yr from 2005', 1081, 5700000, 5274, 'land'), ('The Golden Mile', '800 BEACH ROAD #10-XX', 'Office', '99-yr from 2024', 1550, 5301700, 3420, 'strata'), ('Lucky Plaza', '304 ORCHARD ROAD #05-XX', 'Retail', 'Freehold', 1098, 4995900, 4550, 'strata')]
COM_PSF = [('Grandlink Square', '511 GUILLEMARD ROAD #01-XX', 'Retail', 'Freehold', 194, 888888, 4588, 'strata'), ('Lucky Plaza', '304 ORCHARD ROAD #05-XX', 'Retail', 'Freehold', 1098, 4995900, 4550, 'strata'), ('The Golden Mile', '800 BEACH ROAD #10-XX', 'Office', '99-yr from 2024', 1550, 5301700, 3420, 'strata'), ('Goldhill Shopping Centre', 'XX THOMSON ROAD', 'Office', '999-yr from 1970', 1668, 4350000, 2607, 'strata'), ('Lentor Gardens Residences', '80 LENTOR GARDENS #B1-XX', 'Retail', '99-yr from 2025', 463, 1180650, 2551, 'strata')]
COM_GAIN = [('Kampong Glam', 'XX NORTH BRIDGE ROAD', 'Shop House', '99-yr from 2005', 1081, 5325000, 1420.0, 21.4, 13.6, ' *'), ('Kampong Glam', 'XX JALAN PINANG', 'Shop House', '99-yr from 2006', 1732, 5180733, 304.7, 18.4, 7.9, ''), ('GB Building', '143 CECIL STREET #11-XX/XX/XX/XX', 'Office', '99-yr from 1982', 5425, 1027500, 11.1, 6.8, 1.6, ''), ('Goldhill Shopping Centre', 'XX THOMSON ROAD', 'Office', '999-yr from 1970', 1668, 925000, 27.0, 9.7, 2.5, ''), ('The Modules', '387 JOO CHIAT ROAD #04-XX', 'Office', 'Freehold', 474, 258888, 30.5, 12.5, 2.1, '')]
COM_LOSS = [('The Promenade@Pelikat', '183 JALAN PELIKAT #01-XX', 'Retail', 'Freehold', 280, -349600, -35.0, 14.4, -2.9, '')]
IND_GAIN = [('', 'XX TUAS VIEW SQUARE', 'Single-User', '60-yr from 1996', 16586, 6652000, 86.1, 12.1, 5.3, ''), ('Citilink Warehouse Complex', '102F PASIR PANJANG ROAD #05-XX', 'Warehouse', 'Freehold', 2443, 1476923, 94.6, 15.6, 4.4, ''), ('Mapex', '37 JALAN PEMIMPIN #08-XX', 'Multiple-User', 'Freehold', 1636, 670000, 33.8, 6.5, 4.6, ''), ('Innovation Place', '25 MANDAI ESTATE #06-XX', 'Multiple-User', 'Freehold', 1432, 511000, 104.5, 27.0, 2.7, ''), ('Midview City', '26 SIN MING LANE #05-XX', 'Multiple-User', '60-yr from 2008', 1496, 485600, 81.1, 14.8, 4.1, '')]
IND_LOSS = [('West Star', '11 TUAS BAY CLOSE #05-XX', 'Multiple-User', '30-yr from 2013', 5673, -482000, -27.8, 9.5, -3.4, ''), ('2.8 Penjuru Tech Hub', '8 PENJURU PLACE #01-XX', 'Multiple-User', '30-yr from 2005', 5662, -395000, -35.3, 11.6, -3.7, ''), ('Food Concept @ Pandan', '239 PANDAN LOOP #05-XX', 'Multiple-User', 'Freehold', 2121, -350000, -10.1, 6.5, -1.6, ' *'), ('Eco-Tech@Sunview', '1 SUNVIEW ROAD #03-XX', 'Multiple-User', '30-yr from 2013', 2605, -214633, -33.6, 11.1, -3.6, ''), ('Eco-Tech@Sunview', '1 SUNVIEW ROAD #03-XX', 'Multiple-User', '30-yr from 2013', 2605, -210900, -32.7, 13.0, -3.0, '')]

GATE = dict(n=21, value=350000000, med=351, lo=0, hi=0)
GATE_KICKER = 'Feature'
GATE_HEAD = 'AUO plant to Western Digital'
GATE_SUB = 'Advanced Display Park  ·  XX Tampines Industrial Avenue 3  ·  Single-user factory'
GATE_TILES = [('S$350.00M', 'CAVEAT PRICE', GOLD), ('S$400M', 'FIRST ASKED, 2024', WHITE), ('−12.5%', 'VS FIRST ASK', WHITE), ('S$183', 'PSF OF GFA', WHITE)]
NOTE_S03 = 'Whole-site PSF is land-basis  ·  3 single-user factories carry S$379.4M of S$428.7M'
NOTE_S04 = 'Strata per-unit basis  ·  land-basis deals excluded  ·  Space 18 is a new sale'
NOTE_S05 = 'Rows 2 and 3 are shophouses (land-basis PSF)  ·  GB Building row is a whole floor, 4 units'
NOTE_S05B = 'Strata basis  ·  land-basis deals excluded  ·  Lentor Gardens and Golden Mile are new sales'
GATE_BULLETS = [('Dec 2023', '  ·  AUO closed production at its Singapore display plant'),
                ('', 'Asked S$400M in 2024, then S$380M from April 2025'),
                ('2 Sep 2026', '  ·  AUO announced the sale to Western Digital Singapore'),
                ('', 'Caveat 10 Sep at S$350.0M  ·  lease to 2059, about 32.7 years left')]

TENURE = [('FH / 999 yrs', 18), ('60+ yrs left', 6), ('40-59 yrs left', 16), ('20-39 yrs left', 9), ('Under 20 yrs left', 11)]
TENURE_HEAD = '7 of the 9 losses had under 20 years left'
FEATURE = ('2.8 Penjuru Tech Hub  ·  8 Penjuru Place', 'S$725K  ·  30-YR FROM 2005  ·  9.1 YRS LEFT AT SALE  ·  −35.3% ON A 2015 PURCHASE')

COM_GAIN_SUB = 'Top 5 of 8 gains (8 of 9 commercial pairs profitable)'
COM_LOSS_SUB = 'The only loss (of 9 commercial pairs)'
IND_GAIN_SUB = 'Top 5 of 21 gains (21 of 29 industrial pairs profitable)'
IND_LOSS_SUB = 'Top 5 of 8 losses (of 29 industrial pairs)'
COM_GAIN_FOOT = '* North Bridge Road: current 99-yr lease began Aug 2005, after the May 2005 purchase  ·  not like-for-like'
COM_LOSS_FOOT = 'Promenade@Pelikat bought 2012 at S$3,571 psf  ·  sold at S$2,322'
IND_GAIN_FOOT = 'Tuas View Square: +S$6.65M, the week\'s largest gain in dollars'
IND_LOSS_FOOT = '* Pandan Loop: area 2,067 → 2,121 sq ft between legs  ·  3 Eco-Tech@Sunview units sold the same day'
PDF_NAME = 'Week_of_28th_Sep_2026_LinkedIn_Carousel.pdf'


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
        track(d, (W - 420 - track_w(d, ("%d CAVEAT" % n + ("S" if n != 1 else "")), cf, 2), y + 36),
              ("%d CAVEAT" % n + ("S" if n != 1 else "")), cf, MUTE, 2)
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
    header(d, WEEK + "  ·  " + globals().get("GATE_KICKER", "New launch"), GATE_HEAD, GATE_SUB)
    tiles = globals().get("GATE_TILES") or [(str(GATE["n"]), "NEW-SALE CAVEATS", WHITE),
             (sgd(GATE["value"]), "TOTAL LODGED", GOLD),
             ("S$%s" % format(GATE["med"], ","), "MEDIAN PSF", WHITE),
             ("S$%s–%s" % (format(GATE["lo"], ","), format(GATE["hi"], ",")), "PSF RANGE", WHITE)]   # S371: GATE_TILES overrides
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
        d.rectangle([74, y + 11, 84, y + 21], fill=GOLD)   # S371: "▪" had no glyph in DM Sans (tofu box)
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
    imgs[0].save(PDF_NAME,
                 save_all=True, append_images=imgs[1:], resolution=150)
    print("PDF written")
