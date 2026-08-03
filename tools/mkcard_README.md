# mkcard.py — social card renderer

Lives in `tools/` so it survives container resets (**L-TOOL-1**). Fetch fresh at
session open, alongside `html_balance_check.js` and `landing_label_gate.js`:

```
curl -sO https://raw.githubusercontent.com/tkre-tony/dashboard/main/tools/mkcard.py
```

Renders 1200×630 JPEGs — LinkedIn landscape, also valid `og:image` dimensions.

## Run

```
python3 mkcard.py spec.json
python3 mkcard.py -                    # spec on stdin
python3 mkcard.py spec.json --out other.jpg
```

A spec may also be a JSON **array** of specs, rendered in order.

## Requirements

- Pillow
- Poppins at `/usr/share/fonts/truetype/google-fonts/` — Bold, Medium, Regular,
  Light. **No SemiBold exists**; do not reference one.
- Network access to `raw.githubusercontent.com` for the logo, or a local
  `"logo"` path in the spec.

Per **L-FONT-1** the script asserts every font path at startup and exits
non-zero if one is missing. It never falls back to `ImageFont.load_default()`,
which silently ignores the size argument and produces a render that looks
broken but not obviously wrong.

## Modes

### `article` — the L-SOCIAL-2 headline card

```json
{
  "mode": "article",
  "out": "linkedin_card_164.jpg",
  "headline": "Forty-Five Landed Transactions Totalling S$279.6 Million",
  "category": "Weekly Caveats",
  "photo": "images/news_164_landed_district19_record.jpg",
  "credit": "Photo: KORE US REIT"
}
```

Headline auto-shrinks 34px → 22px until it wraps within `max_lines` (default 5).
If it still will not fit, the script **fails** rather than overrunning the canvas.

### `number` — one figure does the work

```json
{
  "mode": "number",
  "out": "linkedin_card_number.jpg",
  "kicker": "District 19 record",
  "figure": "S$3,921",
  "unit": "per square foot",
  "subline": "The 17 July sale off Simon Lane is the highest ever paid for a freehold terrace house in District 19, measured against 6,524 prior sales.",
  "credit": "Illustration: PropertyAtlas · Source: URA REALIS"
}
```

`figure` shrinks 118px → 54px to fit one line.

### `summary` — TKRE weekly, label/value rows

```json
{
  "mode": "summary",
  "out": "linkedin_card_summary.jpg",
  "eyebrow": "TK Real Estate",
  "title": "Weekly Landed Caveats — Week of 27 July 2026",
  "rows": [["Transactions", "45"], ["Total value", "S$279.6M"]],
  "credit": "Illustration: PropertyAtlas · Source: URA REALIS"
}
```

Maximum **5 rows**. More than that fails with a message telling you to split
across two cards, rather than silently compressing to unreadable leading.

## Fields

| Field | Modes | Required | Notes |
|---|---|---|---|
| `mode` | all | ✅ | `article` \| `number` \| `summary` |
| `out` | all | ✅ | output path |
| `credit` | all | ✅ | bottom-edge credit — see below |
| `photo` | all | — | cover-fit under a navy wash; omit for flat navy |
| `eyebrow` | all | — | default `PROPERTYATLAS NEWSROOM` |
| `footer` | all | — | default `propertyatlas.sg` |
| `brand` | all | — | `propertyatlas` (default) or `tkre` — see below |
| `logo` | all | — | local path; otherwise fetched from `assets/` |
| `logo_ink` | all | — | PA: `white` (default) or `tile`. TKRE: `white` (default) or `black` |
| `wash` | all | — | overlay alpha, default 172 |
| `quality` | all | — | JPEG quality, default 92 |
| `headline` | article | ✅ | |
| `category` | article | — | gold pill, bottom-left |
| `max_lines` | article | — | default 5 |
| `figure` | number | ✅ | |
| `kicker`, `unit`, `subline` | number | — | |
| `title`, `rows` | summary | ✅ | |

## Which mark goes on the card (L-SOCIAL-11)

**PropertyAtlas-published cards carry the PropertyAtlas mark. This is the
default and needs no `brand` key.** The TKRE mark is reserved for cards
published by TK Real Estate — in practice the weekly `summary` card with
eyebrow `TK Real Estate` — and is opt-in:

```json
{ "brand": "tkre" }
```

An unknown `brand` is a hard failure rather than a silent fallback, because a
silent fallback is how the wrong mark shipped on a live post in the first place.

PA variants: `pa_logo_white.png` is the mark on transparency (cream `P` plus
the gold sparkle, no tile) and is the default — it composites predictably over
both flat navy and any photo under the wash. `pa_logo_tile.png` is the full
site-header lockup including the navy tile and gold hairline; it reads *darker*
than a washed photo, so reserve it for light surfaces.

## The credit rule is enforced, not advisory

**L-SOCIAL-2** — every card carries a bottom-edge credit. A missing `credit`
is a hard failure.

**L-SOCIAL-4** — where the card carries no photograph the credit must begin
`Illustration:` and name the data source. Passing `"Photo: …"` on a card with
no photo fails, because that wording would be false.

**L-SOCIAL-12** — where the card *does* carry a photograph the credit must
attribute it, and the preferred wording mirrors the front-end treatment:

```
Jem, 50 Jurong Gateway Road, Singapore. Credit: Lendlease Global Commercial REIT.
```

That is the `landing_credit` field verbatim, so the card and the site say the
same thing about the same photograph. The older `Photo: <owner>` form is still
accepted. A photo card whose credit does neither is a hard failure.

The credit is rendered **italic, right-aligned and muted**, matching the
front-end `.hero-credit` / `.card-credit` / `.ed-art-photo-credit` rules
(`font-style:italic; text-align:right;` muted ink). It sits directly beneath
`propertyatlas.sg` at the bottom-right, the way the site sets a credit
directly beneath its image.

## Design tokens (locked to L-SOCIAL-2)

| Token | Value |
|---|---|
| Canvas | 1200 × 630 |
| Navy | `(15, 25, 45)` |
| Wash alpha | 172 |
| Gold | `(200, 180, 140)` |
| Gold solid | `(180, 155, 100)` |
| Muted | `(168, 178, 196)` |
| Side margin | 56px |

## Assets

The TKRE mark is fetched from `assets/tkre_logo_white.png` (4500×4500 RGBA,
true transparency) and cached at `/tmp/`. Committing the logos to the repo is
deliberate: the script carries its own inputs and cannot be orphaned by a lost
Project Knowledge file, which is how the white mark went missing for five
sessions.

## Not in scope

The weekly carousel (`render_slides_dark_light.py`) stays separate. It needs DM
Sans and Space Mono, which are **not** installed locally and must be downloaded
from `google/fonts`. Different fonts, different canvas, different cadence.
