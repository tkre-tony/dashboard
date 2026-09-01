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


# ================================================================== DATA
WEEK = "Week of 18th August 2026"
LODGED = "URA REALIS caveats lodged 18 and 21 August"
TOTAL, N_CAV, N_PAIR = "S$215.01M", 41, 22
IND_N, IND_V, COM_N, COM_V = 29, 149.88, 12, 65.13
N_GAIN, N_LOSS = 17, 5
SALE_ROWS = [("RESALE", 38, 208_541_642, WHITE),
             ("NEW SALE  ·  ALL GATE+", 2, 1_666_000, GOLD),
             ("SUB SALE", 1, 4_800_000, PERI)]
S02_NOTE = "22 of 41 caveats matched a prior transaction  ·  19 unmatched  ·  net realised \u2212S$18,781,072"

IND_VALUE = [("Single-user Factory", "XX MANDAI ESTATE", 50_000_000, 1726, "land"),
             ("ALOG Gul LogisCentre", "XX GUL WAY", 24_200_000, 119, "land"),
             ("Multiple-user Factory", "XX CHANGI SOUTH AVENUE 2", 16_588_000, 296, "land"),
             ("SRS Building", "XX KUNG CHONG ROAD", 14_000_000, 1726, "land"),
             ("Liner", "1 TUAS BAY CLOSE #01-XX", 7_100_000, 267, "strata")]
IND_PSF = [("SRS Building", "XX KUNG CHONG ROAD", 14_000_000, 1726, "land"),
             ("Single-user Factory", "XX MANDAI ESTATE", 50_000_000, 1726, "land"),
             ("CT Hub 2", "114 LAVENDER STREET #09-XX", 1_356_600, 1400, "strata"),
             ("100 Pasir Panjang", "100 PASIR PANJANG ROAD #02-XX", 2_000_000, 1387, "strata"),
             ("Eunos Techpark", "XX KAKI BUKIT PLACE", 6_300_000, 1311, "land")]
COM_VALUE = [("Southpoint", "200 CANTONMENT ROAD #10-XX", "Office", 19_350_000, 3016, "strata"),
             ("Shop House", "XX EAST COAST ROAD", "Shop House", 9_700_000, 7215, "land"),
             ("Petain Rd/Tyrwhitt Rd Conservation Area", "XX FOCH ROAD", "Shop House", 8_550_000, 5990, "land"),
             ("Shop House", "XX JOO CHIAT ROAD", "Shop House", 7_000_000, 7373, "land"),
             ("Arc 380", "380 JALAN BESAR #14-XX", "Office", 5_320_300, 3070, "strata")]
COM_PSF = [("Shop House", "XX JOO CHIAT ROAD", "Shop House", 7_000_000, 7373, "land"),
             ("Shop House", "XX EAST COAST ROAD", "Shop House", 9_700_000, 7215, "land"),
             ("Petain Rd/Tyrwhitt Rd Conservation Area", "XX FOCH ROAD", "Shop House", 8_550_000, 5990, "land"),
             ("Lucky Plaza", "304 ORCHARD ROAD #02-XX", "Retail", 2_150_000, 5548, "strata"),
             ("Solitaire On Cecil", "148 CECIL STREET #01-XX", "Retail", 4_800_000, 5126, "strata")]
COM_GAIN = [("Shop House", "XX JOO CHIAT ROAD", "Shop House", 1_900_000, 37.3, 1.7, 20.2, ""),
             ("Shop House", "XX EAST COAST ROAD", "Shop House", 1_700_000, 21.2, 3.2, 6.3, "")]
COM_LOSS = [("Solitaire On Cecil", "148 CECIL STREET #01-XX", "Retail", -254_400, -5.0, 3.2, -1.6, "")]
IND_GAIN = [("SRS Building", "XX KUNG CHONG ROAD", "Factory", 7_300_000, 109.0, 11.2, 6.8, ""),
             ("Eunos Techpark", "XX KAKI BUKIT PLACE", "Factory", 1_320_000, 26.5, 29.7, 0.8, ""),
             ("CT Hub", "2 KALLANG AVENUE #09-XX", "Factory", 426_727, 81.5, 15.2, 4.0, ""),
             ("Pantech Business Hub", "192 PANDAN LOOP #06-XX", "Factory", 403_000, 42.2, 15.0, 2.4, ""),
             ("Vertex", "33 UBI AVENUE 3 #07-XX", "Factory", 397_000, 70.5, 18.9, 2.9, "")]
IND_LOSS = [("ALOG Gul LogisCentre", "XX GUL WAY", "Warehouse", -30_950_000, -56.1, 13.5, -5.9, ""),
             ("Factory", "XX BUKIT BATOK STREET 22", "Factory", -3_011_112, -30.1, 10.7, -3.3, " *"),
             ("Ark@Kb", "68 KAKI BUKIT AVENUE 6 #04-XX", "Factory", -143_467, -18.5, 13.1, -1.6, ""),
             ("E9 Premium", "61 WOODLANDS INDUSTRIAL PARK E9 #02-XX", "Factory", -141_234, -13.8, 9.1, -1.6, "")]

GATE = dict(n=2, value=1_666_000, med=516, lo=516, hi=516)
GATE_HEAD = "GATE+ holds at two"
GATE_BULLETS = [("2 caveats", "  ·  S$1.67M this week \u2014 down from 4 last week"),
                ("", "Both printed at exactly S$516 psf \u2014 a developer price list"),
                ("99 caveats", "  ·  S$114.17M since launch  ·  project median S$608 psf"),
                ("", "265-unit ramp-up B2  ·  33-yr leasehold from Aug 2025")]

TENURE = [("FH / 999 yrs", 15), ("60 yrs", 11), ("30 yrs", 7), ("99 yrs", 6), ("33 yrs", 2)]
TENURE_HEAD = "9 of 41 sit on 30\u201333 yr leases"
FEATURE = ("ALOG Gul LogisCentre  ·  15 Gul Way",
           "S$24.2M  ·  S$119 PSF (LAND)  ·  203,274 SQFT  ·  30-YR LEASE FROM 2003, 7.3 YRS REMAINING")

COM_GAIN_SUB = "All 2 commercial gains (of 3 commercial pairs)"
COM_LOSS_SUB = "The week's only commercial loss (of 3 commercial pairs)"
IND_GAIN_SUB = "Top 5 of 15 gains (15 of 19 industrial pairs profitable)"
IND_LOSS_SUB = "All 4 losses (of 19 industrial pairs)"
COM_GAIN_FOOT = "Both commercial gains are freehold shophouses"
COM_LOSS_FOOT = "The week's only sub sale  ·  sold before completion"
IND_GAIN_FOOT = "All nine sixty-year leasehold pairs gained"
IND_LOSS_FOOT = "All four industrial losses sit on 30-year leases  ·  * lease renewed mid-hold"


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
    for i, (proj, addr, price, psf, basis) in enumerate(IND_VALUE, 1):
        rank_card(img, d, y, i, proj, disp(addr), sgd(price),
                  "S$%s psf%s" % (format(psf, ","), " (land)" if basis == "land" else ""))
        y += 104
    note(d, "Whole-building PSF is land-basis — not comparable to strata PSF")
    return chrome(img)


def s04():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "Top 5 — price PSF", "Industrial")
    y = 292
    for i, (proj, addr, price, psf, basis) in enumerate(IND_PSF, 1):
        rank_card(img, d, y, i, proj, disp(addr), "S$%s%s" % (format(psf, ","),
                  " (land)" if basis == "land" else ""), sgd(price))
        y += 104
    note(d, "Whole-site PSF is land-basis  ·  strata PSF is per-unit")
    return chrome(img)


def s05():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "Top 5 — highest value", "Commercial")
    y = 292
    for i, (proj, addr, typ, price, psf, basis) in enumerate(COM_VALUE, 1):
        rank_card(img, d, y, i, proj, "%s  ·  %s" % (disp(addr), typ),
                  sgd(price), "S$%s psf%s" % (format(psf, ","),
                  " (land)" if basis == "land" else ""))
        y += 104
    note(d, "Whole-building PSF is land-basis — not comparable to strata PSF")
    return chrome(img)


def s05b():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK, "Top 5 — price PSF", "Commercial")
    y = 292
    for i, (proj, addr, typ, price, psf, basis) in enumerate(COM_PSF, 1):
        rank_card(img, d, y, i, proj, "%s  ·  %s" % (disp(addr), typ),
                  "S$%s%s" % (format(psf, ","), " (land)" if basis == "land" else ""),
                  sgd(price))
        y += 104
    note(d, "Top three are shophouses  ·  PSF is land-basis")
    return chrome(img)


def s06():
    img = base_dark()
    d = ImageDraw.Draw(img)
    header(d, WEEK + "  ·  New launch", GATE_HEAD,
           "9 Tukang Innovation Drive  ·  D22")
    tiles = [(str(GATE["n"]), "NEW-SALE CAVEATS", WHITE),
             (sgd(GATE["value"]), "TOTAL LODGED", GOLD),
             ("S$%d" % GATE["med"], "MEDIAN PSF", WHITE),
             ("S$%d–%d" % (GATE["lo"], GATE["hi"]), "PSF RANGE", WHITE)]
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
        proj, addr, typ, profit, pct, yrs, ann = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        flag = r[7] if len(r) > 7 else ""
        meta = "%s%s  ·  %s  ·  %.1f-yr hold  ·  %+.1f%%/yr" % (disp(addr), flag, typ, yrs, ann)
        rank_card(img, d, y, i, proj, meta,
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
    imgs[0].save("Week_of_18Aug2026_LinkedIn_Carousel.pdf",
                 save_all=True, append_images=imgs[1:], resolution=150)
    print("PDF written")
