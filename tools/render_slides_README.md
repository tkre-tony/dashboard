# render_slides_dark_light.py — weekly caveat carousel renderer

Recovered S352 from Tony's local copy (`render_slides_dark_light_S329.py`).
Committed **verbatim**, md5 `7e6e1897ce7edc11c8708505c30b6b3f`, 533 lines.
Proven to run end to end in the S352 container: 13 PNGs plus the PDF.

Lost at S181, S196, S349 and S351. Carousel SOP §8 said to keep it in Project
Knowledge; that remedy failed three times. It lives in `tools/` now.

---

## Dependencies

- **Pillow** only (tested against 12.1.1)
- `fonts/DMSans.ttf` — the **variable** build. The script calls
  `set_variation_by_axes([opsz, wght])`; a static DM Sans silently falls back to
  a single weight via the bare `except`, so the deck renders but loses its
  weight hierarchy. Source: google/fonts `ofl/dmsans/DMSans[opsz,wght].ttf`
- `fonts/SpaceMono-Regular.ttf`, `fonts/SpaceMono-Bold.ttf`
- `TK_REAL_ESTATE_WHITE.png`, `TK_REAL_ESTATE_BLACK.png` **in the working
  directory**, not in `fonts/`

## THE WHITE LOGO — read this before rendering

The `TK_REAL_ESTATE_WHITE.png` in Project Knowledge is **blank**. All
1092×1092 pixels are pure white, luminance extrema (255, 255). There is no mark
in the file.

`_load_logo()` rebuilds a missing alpha channel from luminance, but it cannot
key an image that has no content. The result is a **solid white square** pasted
top-right on slides 1–12. Every dark slide. This is not a renderer bug and no
rebuild of the renderer would have fixed it.

The copy in this directory is **rebuilt from the intact black asset**: alpha
keyed off the mark, RGB forced to white. Mark bbox (168, 144, 928, 920),
identical geometry to the black file. Use this one.

`TK_REAL_ESTATE_BLACK.png` is intact — luminance (0, 255) — and recovers
correctly through the same luminance path. Slide 13 was never affected.

---

## Deck structure — 13 slides, not 11

The docstring is correct. The **Carousel SOP is wrong in three places** and
the S351 starter was also wrong (it said 12). Real structure, read off
`SLIDES` at line 521:

| # | fn | slide |
|---|-----|-------|
| 1 | `s01` | Cover — total value, caveat count, matched resales, split bar |
| 2 | `s02` | Week in numbers — 4 tiles + resale/new-sale rows |
| 3 | `s03` | Industrial — top 5 by value |
| 4 | `s04` | Industrial — top 5 by PSF |
| 5 | `s05` | Commercial — top 5 by value |
| 6 | `s05b` | Commercial — top 5 by PSF |
| 7 | `s06` | GATE+ / new launch tracker |
| 8 | `s07` | Commercial P&L — gains |
| 9 | `s07b` | Commercial P&L — losses |
| 10 | `s08` | Industrial P&L — gains |
| 11 | `s09` | Industrial P&L — losses |
| 12 | `s10` | Tenure distribution + feature callout |
| 13 | `s11` | Outro flip (light, cream) — PA left, TKRE right |

Slides 1–12 dark navy with the **white** mark at 70px. Slide 13 cream with the
**black** mark at 220px.

Note `s05b` and `s07b` — the commercial value/PSF split and the commercial
gains/losses split are what the SOP's 11-slide list collapses. This is why a
rebuild from the SOP produces the wrong deck.

---

## Running next week

Everything week-specific is in the **DATA block, lines 199–262**, opened by a
`# ===== DATA` banner comment. It is a run of module-level constants, not a
dict named `DATA` — grepping for `^DATA` finds nothing and the block looks
absent. It is not.

Fields: `WEEK`, `LODGED`, `SALE_ROWS`, `S02_NOTE`, `IND_VALUE`, `IND_PSF`,
`COM_VALUE`, `COM_PSF`, `COM_GAIN`, `COM_LOSS`, `IND_GAIN`, `IND_LOSS`, `GATE`,
`GATE_HEAD`, `GATE_BULLETS`, `TENURE`, `TENURE_HEAD`, `FEATURE`, and the six
`_SUB` / `_FOOT` caption strings.

**Second edit point:** the output filename at **line 531** is hardcoded to
`Week_of_18Aug2026_LinkedIn_Carousel.pdf`. Not parameterised. Change it or you
overwrite last week's deck.

Left unparameterised deliberately — this copy is committed byte-identical to
the one proven working, so the commit carries no untested change.

---

## Carousel SOP corrections outstanding

- **§1** deliverables table: "11 slides" → 13
- **§4** heading "Slide structure (11)" and the 11-item list → the 13 above
- **§8** correct on the DATA block. Add the white-logo warning, and change
  "keep the renderer in project knowledge" to point at `tools/`
- **§7** impressions review still pending — baseline PA page 110 on 213
  followers vs 1,189 for a normal personal post the same week; now 285 followers
