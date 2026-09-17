#!/usr/bin/env node
/* rail_sync.js — PropertyAtlas related-rail consistency gate and surgical fixer
 *
 * WHY THIS EXISTS (L-CORR-1):
 *   generate_all.js bakes each neighbour's category, headline, date and read time into
 *   every article page's "More from PropertyAtlas" rail AT GENERATION TIME. Correcting a
 *   headline in NEWS therefore leaves the old one live on every page whose rail carries it.
 *   S374 found six stale id:238 cards by UAT; S375 found a seventh (id:244 on the id:245
 *   page) carrying a withdrawn claim for six days. No existing gate opened a rail card.
 *
 * WHAT IT DOES:
 *   For every news/<slug>/index.html, every <a class="ed-art-related-card" href="/news/<slug>/">
 *   is re-derived from the CURRENT NEWS array exactly as the renderer does it:
 *     eyebrow  = category || 'PropertyAtlas'
 *     headline = display_title || title || display_headline         (edDeriveCardHeadline)
 *     meta     = edFormatDate(date) [+ ' · ' + readTime + ' min']    (edDeriveReadTime)
 *   and compared byte-for-byte. It checks CONTENT only, never MEMBERSHIP: which three
 *   neighbours a rail shows is frozen at generation and is not a defect.
 *
 * MODES:
 *   check (default)  report mismatches, exit 1 if any. Run on every drop that edits an
 *                    existing NEWS entry's category / display_title / title /
 *                    display_headline / date / word_count / read_time_min.
 *   --fix <outDir>   write patched copies of affected pages to <outDir>/news/<slug>/index.html.
 *                    Surgical: only the text inside the one card changes, each replacement
 *                    asserted count==1 within that card. Never regenerates (regeneration
 *                    reshuffles rails — S374). Source pages are never modified in place.
 *
 * USAGE
 *   node rail_sync.js <newsroom/index.html> <newsDir> [--fix <outDir>] [-v]
 *   newsDir is the folder that CONTAINS the <slug>/index.html folders (repo `news/`).
 *
 * EXIT  0 clean / fixed   1 mismatches (check mode)   2 could not run
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const argv = process.argv.slice(2);
const pos = argv.filter((a, i) => !a.startsWith('-') && argv[i - 1] !== '--fix');
const [NEWSROOM, NEWSDIR] = pos;
const fixIdx = argv.indexOf('--fix');
const FIX = fixIdx !== -1 ? argv[fixIdx + 1] : null;
const VERBOSE = argv.includes('-v');
function die(m) { console.error('RAIL SYNC ABORT: ' + m); process.exit(2); }
if (!NEWSROOM || !NEWSDIR) die('usage: node rail_sync.js <newsroom/index.html> <newsDir> [--fix <outDir>]');
if (FIX && !path.resolve(FIX).startsWith('/') ) die('bad --fix dir');
if (FIX && path.resolve(FIX) === path.resolve(path.dirname(NEWSDIR))) die('--fix outDir must not be the repo root');

/* ---------- NEWS extraction (quote-aware, same approach as news_integrity_gate) ---------- */
function matchDelim(s, start, open, close) {
  let depth = 0, instr = null, esc = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (instr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === instr) instr = null; }
    else if (c === '"' || c === "'") instr = c;
    else if (c === open) depth++;
    else if (c === close && --depth === 0) return i;
  }
  return -1;
}
const src = fs.readFileSync(NEWSROOM).toString('utf8');
const decls = [];
for (let from = 0; ;) {
  const m = src.indexOf('var NEWS', from); if (m === -1) break;
  if (/^var\s+NEWS\s*=/.test(src.slice(m, m + 40))) decls.push(m);
  from = m + 8;
}
if (decls.length !== 1) die(`expected exactly 1 live \`var NEWS =\`, found ${decls.length}`);
const open = src.indexOf('[', decls[0]);
const close = matchDelim(src, open, '[', ']');
if (close === -1) die('could not bracket-match NEWS');
let NEWS;
try { NEWS = JSON.parse(src.slice(open, close + 1)); }
catch (_) { NEWS = vm.runInNewContext('(' + src.slice(open, close + 1) + ')'); }
if (!Array.isArray(NEWS) || !NEWS.length) die('NEWS did not parse to a non-empty array');

/* ---------- renderer mirrors (edFormatDate / edDeriveCardHeadline / edDeriveReadTime) ---------- */
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
function fmtDate(d) {
  if (!d) return '';
  const p = String(d).split('-'); if (p.length !== 3) return d;
  return parseInt(p[2], 10) + ' ' + MONTHS[parseInt(p[1], 10) - 1] + ' ' + p[0];
}
function cardHeadline(a) { return a.display_title || a.title || a.display_headline || ''; }
function wordCount(a) { if (a.word_count) return a.word_count; if (!a.summary) return 0; return a.summary.split(/\s+/).filter(Boolean).length; }
function readTime(a) { if (a.read_time_min) return a.read_time_min; const w = wordCount(a); return w ? Math.max(1, Math.round(w / 220)) : null; }
function expected(a) {
  const rt = readTime(a);
  return { eyebrow: a.category || 'PropertyAtlas', headline: cardHeadline(a), meta: fmtDate(a.date) + (rt ? ' · ' + rt + ' min' : '') };
}
const bySlug = new Map();
for (const n of NEWS) if (n && n.slug) bySlug.set(n.slug, n);

/* ---------- scan ---------- */
const CARD = /<a class="ed-art-related-card" href="\/news\/([^"\/]+)\/"><div class="ed-art-related-eyebrow">([\s\S]*?)<\/div><h4 class="ed-art-related-headline">([\s\S]*?)<\/h4><div class="ed-art-related-meta">([\s\S]*?)<\/div><\/a>/g;
const pages = fs.readdirSync(NEWSDIR, { withFileTypes: true }).filter(d => d.isDirectory() && fs.existsSync(path.join(NEWSDIR, d.name, 'index.html'))).map(d => d.name).sort();
if (!pages.length) die(`no <slug>/index.html pages under ${NEWSDIR}`);

let cardsSeen = 0, mismatches = 0, unknown = 0, pagesFixed = 0, rawCardAnchors = 0;
const report = [];
for (const slug of pages) {
  const file = path.join(NEWSDIR, slug, 'index.html');
  const buf = fs.readFileSync(file);
  let html = buf.toString('utf8');
  rawCardAnchors += (html.match(/class="ed-art-related-card"/g) || []).length;
  const fixes = [];
  CARD.lastIndex = 0;
  let m;
  while ((m = CARD.exec(html))) {
    cardsSeen++;
    const [whole, target, eyebrow, headline, meta] = m;
    const n = bySlug.get(target);
    if (!n) { unknown++; report.push(`  [UNKNOWN TARGET] ${slug} -> /news/${target}/ (not in NEWS)`); continue; }
    const e = expected(n);
    const diffs = [];
    if (eyebrow !== e.eyebrow) diffs.push(['eyebrow', eyebrow, e.eyebrow]);
    if (headline !== e.headline) diffs.push(['headline', headline, e.headline]);
    if (meta !== e.meta) diffs.push(['meta', meta, e.meta]);
    if (!diffs.length) continue;
    mismatches++;
    report.push(`  [STALE] ${slug}  card -> id:${n.id} (${target})`);
    for (const [f, have, want] of diffs) report.push(`      ${f}\n        live: ${have}\n        want: ${want}`);
    const rebuilt = `<a class="ed-art-related-card" href="/news/${target}/"><div class="ed-art-related-eyebrow">${e.eyebrow}</div><h4 class="ed-art-related-headline">${e.headline}</h4><div class="ed-art-related-meta">${e.meta}</div></a>`;
    fixes.push([whole, rebuilt]);
  }
  if (FIX && fixes.length) {
    for (const [oldCard] of fixes) {
      const c = html.split(oldCard).length - 1;
      if (c !== 1) die(`${slug}: stale card occurs ${c}x, refusing to patch`);
    }
    // byte-safe, regex-free splice from the original buffer
    let out = html;
    for (const [oldCard, newCard] of fixes) {
      const at = out.indexOf(oldCard);
      out = out.slice(0, at) + newCard + out.slice(at + oldCard.length);
    }
    if (out.includes('\r') !== buf.toString('utf8').includes('\r')) die(`${slug}: line-ending drift`);
    const dest = path.join(FIX, 'news', slug, 'index.html');
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, out);
    pagesFixed++;
  }
}

console.log('=== rail sync: ' + NEWSROOM + ' vs ' + NEWSDIR + ' ===');
console.log(`NEWS ${NEWS.length} entries · pages ${pages.length} · rail cards ${cardsSeen}` + (rawCardAnchors !== cardsSeen ? ` (WARNING: ${rawCardAnchors} card anchors, ${rawCardAnchors - cardsSeen} unparsed)` : ''));
if (report.length) console.log(report.join('\n'));
if (rawCardAnchors !== cardsSeen) { console.log('\nFAIL: card markup changed shape — update the CARD pattern before trusting this gate.'); process.exit(1); }
if (FIX) {
  console.log(`\n${mismatches ? 'FIXED' : 'CLEAN'}: ${mismatches} stale card(s) across ${pagesFixed} page(s)` + (pagesFixed ? ` written to ${FIX}/news/` : '') + (unknown ? ` · ${unknown} unknown target(s)` : ''));
  process.exit(0);
}
if (mismatches || unknown) { console.log(`\nFAIL: ${mismatches} stale card(s)` + (unknown ? `, ${unknown} unknown target(s)` : '') + ' — rerun with --fix <outDir>'); process.exit(1); }
console.log('\nCLEAN: every rail card matches NEWS.');
