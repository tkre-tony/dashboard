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
# Week of 21st September 2026 · URA REALIS release 22 Sep 2026 · ids 83,179–83,247 · built S388 from the same
# Tab A/B CSVs and row selection as weekly_caveat_reel_25Sep2026.html (gate-checked row-for-row against the reel DATA).
# Flagged rows carry " *": Fook Hai area_caveat; Tuas Ave 6 / Loyang St lease extended; Ascent @ Gambas tenure restated.
# TENURE is remaining lease at sale date (the slide subtitle), not original term.
WEEK = 'Week of 21st September 2026'
LODGED = 'URA REALIS caveats released 22nd September 2026'
TOTAL, N_CAV, N_PAIR = 'S$155.40M', 69, 43
IND_N, IND_V, COM_N, COM_V = 47, 106.66, 22, 48.74
N_GAIN, N_LOSS = 36, 6
SALE_ROWS = [('RESALE', 67, 151805961, WHITE),
             ('NEW SALE  ·  SPACE 18, GATE+', 2, 3596823, GOLD)]
S02_NOTE = '43 of 69 caveats matched a prior transaction  ·  26 unmatched  ·  1 flat  ·  net realised +S$21,684,249'

IND_VALUE = [('Cityneon Building', '25 TAI SENG AVENUE', 'Single-User', '30+29-yr from 2007', 27679, 28000000, 1012, 'land'), ('', '9 TUAS AVENUE 6', 'Single-User', '30+30-yr from 1990', 56376, 10500000, 186, 'land'), ('', '459 MACPHERSON ROAD', 'Single-User', '99-yr from 1965', 6490, 9500000, 1464, 'land'), ('', '20 LOYANG STREET', 'Single-User', '30+27-yr from 1995', 34256, 7180000, 210, 'land'), ('Woodlands Bizhub', '276 WOODLANDS INDUSTRIAL PARK E5', 'Multiple-User', '57-yr from 2011', 6103, 4050000, 664, 'strata')]
IND_PSF = [('Space 18', '18 LORONG AMPAS #04-10', 'Multiple-User', 'Freehold', 1787, 2594023, 1452, 'strata'), ('Perfect One', '1 GENTING LINK #01-07', 'Multiple-User', 'Freehold', 1281, 1580000, 1233, 'strata'), ('ArcSphere', '124 LORONG 23 GEYLANG #03-02', 'Multiple-User', 'Freehold', 1130, 1288888, 1140, 'strata'), ('M-Space', '6D MANDAI ESTATE #04-09', 'Multiple-User', 'Freehold', 1313, 1420000, 1081, 'strata'), ('Novelty Bizcentre', '18 HOWARD ROAD #11-04', 'Multiple-User', 'Freehold', 1658, 1780000, 1074, 'strata')]
COM_VALUE = [('Little India', '164 SERANGOON ROAD', 'Shop House', 'Freehold', 1228, 9800000, 7979, 'land'), ('Orchard Plaza', '150 ORCHARD ROAD #01-XX/XX/XX', 'Retail', '99-yr from 1977', 818, 4680000, 5721, 'strata'), ('Desker Road', '91 ROWELL ROAD', 'Shop House', '199-yr from 2013', 1107, 4600000, 4157, 'land'), ('', '375 BALESTIER ROAD', 'Shop House', 'Freehold', 1675, 2970000, 1773, 'land'), ('The Adelphi', '1 COLEMAN STREET #01-20', 'Retail', '999-yr from 1828', 398, 2399000, 6024, 'strata')]
COM_PSF = [('The Adelphi', '1 COLEMAN STREET #01-20', 'Retail', '999-yr from 1828', 398, 2399000, 6024, 'strata'), ('Orchard Plaza', '150 ORCHARD ROAD #01-XX/XX/XX', 'Retail', '99-yr from 1977', 818, 4680000, 5721, 'strata'), ('EON Shenton', '70 SHENTON WAY #01-05', 'Retail', '99-yr from 2011', 172, 606666, 3523, 'strata'), ('Arc 380', '380 JALAN BESAR #10-XX/XX/XX', 'Office', 'Freehold', 2196, 6451800, 2938, 'strata'), ('Balestier Plaza', '400 BALESTIER ROAD #01-04', 'Office', 'Freehold', 506, 1175000, 2323, 'strata')]
COM_GAIN = [('Fook Hai Building', '150 SOUTH BRIDGE ROAD #01-01', 'Retail', '99-yr from 1972', 1012, 1505000, 268.8, 25.2, 5.3, ' *'), ('Desker Road', '91 ROWELL ROAD', 'Shop House', '199-yr from 2013', 1107, 1175000, 34.3, 4.4, 6.9, ''), ('The Adelphi', '1 COLEMAN STREET #01-20', 'Retail', '999-yr from 1828', 398, 1045800, 77.3, 14.8, 4.0, ''), ('Regency Suites', '38 KIM TIAN ROAD #04-06', 'Office', 'Freehold', 1152, 887000, 63.7, 15.8, 3.2, ''), ('International Plaza', '10 ANSON ROAD #16-14', 'Office', '99-yr from 1970', 463, 462000, 110.5, 18.5, 4.1, '')]
COM_LOSS = [('EON Shenton', '70 SHENTON WAY #01-05', 'Retail', '99-yr from 2011', 172, -623334, -50.7, 13.0, -5.3, ''), ('The Commerze@Irving', '1 IRVING PLACE #02-06', 'Retail', '60-yr from 2011', 431, -101850, -17.5, 14.5, -1.3, '')]
IND_GAIN = [('', '9 TUAS AVENUE 6', 'Single-User', '30+30-yr from 1990', 56376, 5940000, 130.3, 16.1, 5.3, ' *'), ('', '20 LOYANG STREET', 'Single-User', '30+27-yr from 1995', 34256, 4080000, 131.6, 16.9, 5.1, ' *'), ('', '459 MACPHERSON ROAD', 'Single-User', '99-yr from 1965', 6490, 1000000, 11.8, 5.6, 2.0, ''), ("A'Posh Bizhub", '1 YISHUN INDUSTRIAL STREET 1 #08-18', 'Multiple-User', '60-yr from 2010', 2185, 782000, 85.2, 6.2, 10.5, ''), ('Premier @ Kaki Bukit', '8 KAKI BUKIT AVENUE 4 #02-17', 'Multiple-User', '60-yr from 2010', 3078, 542414, 52.5, 14.0, 3.1, '')]
IND_LOSS = [('Pioneer Centre', '1 SOON LEE STREET #01-33', 'Multiple-User', '30-yr from 2010', 3197, -848500, -53.1, 13.5, -5.4, ''), ('Ascent @ Gambas', '6 GAMBAS WAY #02-20', 'Multiple-User', '26-yr from 2023', 3983, -205000, -17.3, 4.1, -4.5, ' *'), ('Sing Industrial Complex', '32 ANG MO KIO INDUSTRIAL PARK 2 #04-03', 'Multiple-User', '60-yr from 1982', 1227, -93100, -25.3, 11.8, -2.4, ''), ('Pioneer Junction', '3 SOON LEE STREET #06-17', 'Multiple-User', '30-yr from 2011', 1324, -92174, -20.6, 13.5, -1.7, '')]

GATE = dict(n=26, value=28000000, med=1012, lo=0, hi=0)
GATE_KICKER = 'Feature'
GATE_HEAD = 'Biggest deal, blank P&L'
GATE_SUB = 'Cityneon Building  ·  XX Tai Seng Avenue  ·  Single-user factory'
GATE_TILES = [('26', 'NO PRIOR CAVEAT', WHITE), ('S$28.00M', 'CITYNEON BUILDING', GOLD), ('S$1,012', 'CITYNEON PSF', WHITE), ('0.9%/yr', 'ON S$25.9M EFFECTIVE COST', WHITE)]
NOTE_S03 = 'Whole-site PSF is land-basis  ·  4 single-user factories S$55.2M vs 42 strata units S$50.4M'
NOTE_S04 = 'Strata per-unit basis  ·  land-basis deals excluded  ·  Space 18 is a new sale'
NOTE_S05 = 'Rows 1, 3 and 4 are shophouses  ·  PSF is land-basis  ·  Orchard Plaza is three units in one caveat'
NOTE_S05B = 'Strata basis  ·  land-basis deals excluded  ·  Arc 380 row is three adjacent units, same day'
GATE_BULLETS = [('Dec 2017', '  ·  Cityneon bought Scorpio East Properties, the owner company, from KOP'),
                ('', 'S$2.9M equity plus a S$23M assumed loan  ·  a share sale lodges no caveat'),
                ('', 'On S$25.9M effective cost: +8% over 8.75 years, about 0.9% a year'),
                ('', 'On the S$2.9M equity alone, the same deal reads +866%')]

TENURE = [('FH / 999 yrs', 18), ('60+ yrs left', 6), ('40-59 yrs left', 20), ('20-39 yrs left', 20), ('Under 20 yrs left', 5)]
TENURE_HEAD = '3 of the 6 losses had under 20 years left'
FEATURE = ('Pioneer Centre  ·  1 Soon Lee Street', 'S$750K  ·  30-YR FROM 2010  ·  13.5 YRS LEFT AT SALE  ·  −53.1% ON A 2013 PURCHASE')

COM_GAIN_SUB = 'Top 5 of 8 gains (8 of 10 commercial pairs profitable)'
COM_LOSS_SUB = 'All 2 losses (of 10 commercial pairs)'
IND_GAIN_SUB = 'Top 5 of 28 gains (28 of 33 industrial pairs profitable)'
IND_LOSS_SUB = 'All 4 losses (of 33 industrial pairs  ·  1 flat)'
COM_GAIN_FOOT = '* Fook Hai: area 527 → 1,012 sq ft between the two sales  ·  not like-for-like'
COM_LOSS_FOOT = 'EON Shenton bought 2013 at S$7,142 psf  ·  sold at S$3,523'
IND_GAIN_FOOT = '* lease extended between buy and sell (30 yrs → 30+30, 30+27)  ·  not like-for-like'
IND_LOSS_FOOT = '* tenure restated between legs  ·  flat: Ascent @ Gambas, S$686,000 in 2021 and 2026'
PDF_NAME = 'Week_of_21st_Sep_2026_LinkedIn_Carousel.pdf'


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
