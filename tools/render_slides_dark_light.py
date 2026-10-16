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
# Week of 12th October 2026 · URA REALIS releases 13 Oct + 16 Oct (all stamped 16 Oct; Tuesday download missed) · ids 83,342–83,389 · built S402.
# Matches article id:278: 48 caveats, S$126.56M, 36 pairs (28G / 8L), net +S$39,385,541 — reconciled to pnl_pairs_mv (sell_id > 83341).
# Flagged rows carry " *": Senoko South Road lease_event (new 30-yr lease from Mar 2021; bought 2000 on a lease from 1991);
# Shun Li #02-XX area 2,812 → 2,863 sq ft (pnl_confirmed_pairs) — not in a top-5 list this week.
# TENURE is remaining lease at sale date.
WEEK = 'Week of 12th October 2026'
LODGED = 'URA REALIS caveats released 13th and 16th October 2026'
TOTAL, N_CAV, N_PAIR = 'S$126.56M', 48, 36
IND_N, IND_V, COM_N, COM_V = 32, 75.60, 16, 50.96
N_GAIN, N_LOSS = 28, 8
SALE_ROWS = [('RESALE', 44, 120180640, WHITE),
             ('NEW SALE  ·  GATE+, THE GOLDEN MILE', 4, 6374985, GOLD)]
S02_NOTE = '36 of 48 caveats matched a prior transaction  ·  12 unmatched  ·  net realised +S$39,385,541'

IND_VALUE = [('Senoko Industrial Estate', 'XX SENOKO SOUTH ROAD', 'Single-User', '30-yr from 2021', 109724, 35100000, 320, 'land'), ('Westlink Techpark', 'XX TUAS VIEW SQUARE', 'Single-User', '60-yr from 1996', 7233, 5625000, 778, 'land'), ('Link@AMK', '3 ANG MO KIO STREET 62 #01-XX', 'Warehouse', '60-yr from 2011', 7912, 3530000, 446, 'strata'), ('Henderson Building', '221 HENDERSON ROAD #05-XX', 'Multiple-User', 'Freehold', 2454, 2352000, 958, 'strata'), ('M-Space', '6D MANDAI ESTATE #03-XX', 'Multiple-User', 'Freehold', 1668, 2016500, 1209, 'strata')]
IND_PSF = [('M-Space', '6D MANDAI ESTATE #03-XX', 'Multiple-User', 'Freehold', 1668, 2016500, 1209, 'strata'), ('Henderson Building', '221 HENDERSON ROAD #05-XX', 'Multiple-User', 'Freehold', 2454, 2352000, 958, 'strata'), ('Gate+', '9 TUKANG INNOVATION DRIVE #01-XX', 'Multiple-User', '33-yr from 2025', 2228, 1648000, 740, 'strata'), ('Woodlands 11', '11 WOODLANDS CLOSE #09-XX', 'Multiple-User', '60-yr from 2010', 1830, 1250000, 683, 'strata'), ('Woodlands Horizon', '31 WOODLANDS CLOSE #06-XX', 'Multiple-User', '60-yr from 2012', 1711, 1150000, 672, 'strata')]
COM_VALUE = [('Visioncrest', '103 PENANG ROAD #04-XX', 'Office', 'Freehold', 2809, 10814650, 3849, 'strata'), ('', 'XX MIDDLE ROAD', 'Shop House', 'Freehold', 994, 7800000, 7851, 'land'), ('Tanjong Pagar', 'XX TANJONG PAGAR ROAD', 'Shop House', '99-yr from 1988', 760, 5800000, 7632, 'land'), ('', 'XX UPPER EAST COAST ROAD', 'Shop House', 'Freehold', 2207, 5600000, 2538, 'strata'), ('Chinatown Point', '133 NEW BRIDGE ROAD #23-XX/XX', 'Office', '99-yr from 1980', 2347, 4300000, 1832, 'strata')]
COM_PSF = [('Queensway Shopping Centre', '1 QUEENSWAY #01-XX', 'Retail', 'Freehold', 301, 1450000, 4811, 'strata'), ('Rocca Balestier', '221 BALESTIER ROAD #01-XX', 'Retail', 'Freehold', 183, 810000, 4427, 'strata'), ('Soho Life', '216 JOO CHIAT ROAD #01-XX', 'Retail', 'Freehold', 355, 1376146, 3874, 'strata'), ('Katong Shopping Centre', '865 MOUNTBATTEN ROAD #01-XX', 'Retail', 'Freehold', 388, 1500000, 3871, 'strata'), ('Visioncrest', '103 PENANG ROAD #04-XX', 'Office', 'Freehold', 2809, 10814650, 3849, 'strata')]
COM_GAIN = [('Katong Shopping Centre', '865 MOUNTBATTEN ROAD #01-XX', 'Retail', 'Freehold', 388, 980000, 188.5, 20.3, 5.4, ''), ('Soho Life', '216 JOO CHIAT ROAD #01-XX', 'Retail', 'Freehold', 355, 626146, 83.5, 15.4, 4.0, ''), ('The Central', '6 EU TONG SEN STREET #10-XX', 'Office', '99-yr from 2001', 635, 320000, 24.1, 15.5, 1.4, ''), ('Paya Lebar Square', '60 PAYA LEBAR ROAD #04-XX', 'Office', '99-yr from 2011', 538, 299100, 33.2, 14.6, 2.0, ''), ('Rocca Balestier', '221 BALESTIER ROAD #01-XX', 'Retail', 'Freehold', 183, 275000, 51.4, 9.7, 4.4, '')]
COM_LOSS = [('EON Shenton', '70 SHENTON WAY #09-XX/XX/XX', 'Office', '99-yr from 2011', 1701, -252500, -6.0, 14.4, -0.4, ''), ('', 'XX UPPER EAST COAST ROAD', 'Shop House', 'Freehold', 2207, -200000, -3.4, 3.0, -1.2, ''), ('International Plaza', '10 ANSON ROAD #14-XX', 'Office', '99-yr from 1970', 474, -40000, -4.0, 12.0, -0.3, '')]
IND_GAIN = [('Senoko Industrial Estate', 'XX SENOKO SOUTH ROAD', 'Single-User', '30-yr from 2021', 109724, 28700000, 448.4, 26.5, 6.6, ' *'), ('Westlink Techpark', 'XX TUAS VIEW SQUARE', 'Single-User', '60-yr from 1996', 7233, 2625000, 87.5, 3.5, 19.4, ''), ('Eunos Technolink', '13 KAKI BUKIT ROAD 1 #B1-XX', 'Multiple-User', '60-yr from 1996', 3283, 742645, 122.3, 19.6, 4.2, ''), ('Pantech Business Hub', '196 PANDAN LOOP #07-XX', 'Multiple-User', '99-yr from 1984', 2616, 726880, 182.6, 21.2, 5.0, ''), ('Woodlands 11', '11 WOODLANDS CLOSE #09-XX', 'Multiple-User', '60-yr from 2010', 1830, 685589, 121.5, 15.4, 5.3, '')]
IND_LOSS = [('The Westcom', '1 TUAS SOUTH AVENUE 6 #04-XX', 'Multiple-User', '60-yr from 1996', 3068, -446752, -37.7, 12.9, -3.6, ''), ('ARK@KB', '68 KAKI BUKIT AVENUE 6 #03-XX', 'Multiple-User', '30-yr from 2012', 3315, -173327, -21.1, 13.2, -1.8, ''), ('Pioneer Point', '5 SOON LEE STREET #01-XX', 'Multiple-User', '30-yr from 2011', 1087, -113900, -21.3, 13.1, -1.8, ''), ('Wave9', '71 WOODLANDS INDUSTRIAL PARK E9 #04-XX', 'Multiple-User', '30-yr from 2014', 1884, -112000, -17.5, 4.1, -4.5, ''), ('Link@AMK', '3 ANG MO KIO STREET 62 #01-XX', 'Warehouse', '60-yr from 2011', 7912, -70000, -1.9, 5.1, -0.4, '')]

GATE = dict(n=1, value=35100000, med=320, lo=0, hi=0)
GATE_KICKER = 'Feature'
GATE_HEAD = 'Senoko South Road: a new lease start'
GATE_SUB = 'Senoko Industrial Estate  ·  XX Senoko South Road  ·  Single-user factory'
GATE_TILES = [('S$35.10M', 'CAVEAT PRICE', GOLD), ('S$6.40M', 'MARCH 2000', WHITE), ('S$320', 'PSF OF LAND', WHITE), ('2021', 'NEW 30-YR LEASE', WHITE)]
NOTE_S03 = 'Whole-site PSF is land-basis  ·  2 single-user factories carry S$40.7M of S$75.6M'
NOTE_S04 = 'Strata per-unit basis  ·  land-basis deals excluded  ·  Gate+ is a new sale'
NOTE_S05 = 'Rows 2 and 3 are shophouses (land-basis PSF)  ·  Visioncrest caveat dated 10 Apr, a late lodgement'
NOTE_S05B = 'Strata basis  ·  land-basis deals excluded  ·  Rocca Balestier unit is 183 sq ft'
GATE_BULLETS = [('Mar 2000', '  ·  Changed hands for S$6.40M on a 30-yr lease from 1991'),
                ('Mar 2021', '  ·  A fresh 30-yr term begins on the same site'),
                ('11 Sep 2026', '  ·  Caveat dated at S$35.10M  ·  109,724 sq ft of land'),
                ('', 'Not like-for-like: the caveat price excludes the lease top-up premium')]

TENURE = [['FH / 999 yrs', 9], ['60+ yrs left', 5], ['40-59 yrs left', 9], ['20-39 yrs left', 19], ['Under 20 yrs left', 6]]
TENURE_HEAD = '3 of the 8 losses had under 20 years left'
FEATURE = ('Pioneer Point  ·  5 Soon Lee Street', 'S$420K  ·  30-YR FROM 2011  ·  15.2 YRS LEFT AT SALE  ·  −21.3% ON A 2013 PURCHASE')

COM_GAIN_SUB = 'Top 5 of 6 gains (6 of 9 commercial pairs profitable)'
COM_LOSS_SUB = 'All 3 losses (of 9 commercial pairs)'
IND_GAIN_SUB = 'Top 5 of 22 gains (22 of 27 industrial pairs profitable)'
IND_LOSS_SUB = 'All 5 losses (of 27 industrial pairs)'
COM_GAIN_FOOT = 'Katong Shopping Centre: bought Apr 2006 at S$520,000  ·  +188.5% over 20.3 years'
COM_LOSS_FOOT = 'Upper East Coast Road: bought Sep 2023  ·  lowest price and psf on the street since 2020'
IND_GAIN_FOOT = '* Senoko South Road: new lease start for the same site (30-yr from 1991, then from 2021)  ·  not like-for-like'
IND_LOSS_FOOT = 'ARK@KB, Pioneer Point and Wave9 are on 30-yr leases, 15 to 18 years left at sale'
PDF_NAME = 'Week_of_12th_Oct_2026_LinkedIn_Carousel.pdf'


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
