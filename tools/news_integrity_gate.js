#!/usr/bin/env node
/* news_integrity_gate.js — PropertyAtlas newsroom NEWS-array field integrity gate
 *
 * WHY THIS EXISTS (L-NEWS-3):
 *   html_balance_check.js verifies that tags balance. landing_label_gate.js verifies that
 *   dates agree. NEITHER OPENS A NEWS FIELD. An article body written into `standfirst` is
 *   perfectly balanced HTML sitting in the wrong place, and every structural gate passes it.
 *   That defect (ids 116-119) shipped wrong-company copy to four public pages for six weeks
 *   and was found by the operator's eye on a rendered page, not by any gate.
 *
 * WHY IT IS BASELINE-RELATIVE (L-GATE-1):
 *   The published corpus has been verified once and must never need re-verifying. Two earlier
 *   drafts threw 85 and then 21 errors at a corpus that is fine — 59 legacy entries predate the
 *   `standfirst` field and 7 carry plain-text summaries. A gate that loud gets ignored.
 *   Accepted state is frozen into news_integrity_baseline.json; the gate fires ONLY on deviation.
 *   A CLEAN run means "nothing changed for the worse", NOT "everything is perfect".
 *
 * HONEST LIMIT:
 *   The 117/118/119 class (body in a textContent field, missing summary key) is caught with
 *   certainty by construction. The 116 class — a wrong clause sitting CONSISTENTLY in both
 *   standfirst and summary — is internally self-consistent and surfaces only as a subject
 *   mismatch WARNING. That one still needs a human eye.
 *
 * USAGE
 *   node news_integrity_gate.js <newsroom/index.html> [--baseline <path>] [--regen-baseline] [-v]
 *
 * EXIT
 *   0 = clean (warnings do not fail the gate)
 *   1 = one or more errors
 *   2 = could not run (file/parse/baseline problem)
 */

'use strict';
const fs = require('fs');
const path = require('path');

const argv = process.argv.slice(2);
const FILE = argv.find(a => !a.startsWith('-'));
const VERBOSE = argv.includes('-v') || argv.includes('--verbose');
const REGEN = argv.includes('--regen-baseline');
const bIdx = argv.indexOf('--baseline');
const BASELINE = bIdx !== -1 ? argv[bIdx + 1]
                             : path.join(path.dirname(FILE || '.'), 'news_integrity_baseline.json');

if (!FILE) {
  console.error('usage: node news_integrity_gate.js <newsroom/index.html> [--baseline <path>] [--regen-baseline]');
  process.exit(2);
}

/* ---------------------------------------------------------------- extraction */
/* Byte-mode read, quote-aware bracket matching. No regex .replace() anywhere. */

function readSource(file) {
  const buf = fs.readFileSync(file);
  return buf.toString('utf8');
}

/* Walk from `start` (which must be the opening delimiter) to its match, skipping
   over string literals so that brackets inside copy do not confuse the depth count. */
function matchDelim(s, start, open, close) {
  let depth = 0, i = start, instr = null, esc = false;
  while (i < s.length) {
    const c = s[i];
    if (instr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === instr) instr = null;
    } else {
      if (c === '"' || c === "'") instr = c;
      else if (c === open) depth++;
      else if (c === close) { depth--; if (depth === 0) return i; }
    }
    i++;
  }
  return -1;
}

function extractArray(s) {
  const decls = [];
  let from = 0;
  for (;;) {
    const m = s.indexOf('var NEWS', from);
    if (m === -1) break;
    // must be an assignment, not a mention inside a comment/version header
    const tail = s.slice(m, m + 40);
    if (/^var\s+NEWS\s*=/.test(tail)) decls.push(m);
    from = m + 8;
  }
  if (decls.length !== 1) {
    fail(`expected exactly 1 live \`var NEWS =\` assignment, found ${decls.length}`);
  }
  const open = s.indexOf('[', decls[0]);
  const close = matchDelim(s, open, '[', ']');
  if (open === -1 || close === -1) fail('could not bracket-match the NEWS array');
  return { text: s.slice(open, close + 1), offset: open };
}

/* Split the array into top-level entry objects. */
function splitEntries(arr) {
  const out = [];
  let i = 0;
  while (i < arr.length) {
    const b = arr.indexOf('{', i);
    if (b === -1) break;
    const e = matchDelim(arr, b, '{', '}');
    if (e === -1) fail(`unterminated entry object at array offset ${b}`);
    out.push({ text: arr.slice(b, e + 1), start: b });
    i = e + 1;
  }
  return out;
}

/* Top-level keys only — depth-1 colons. Nested financial_headlines keys are NOT counted. */
function topLevelKeys(entry) {
  const keys = [];
  let d = 0, i = 0, instr = null, esc = false;
  while (i < entry.length) {
    const c = entry[i];
    if (instr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === instr) instr = null;
    } else {
      if (c === '"' || c === "'") instr = c;
      else if (c === '{' || c === '[') d++;
      else if (c === '}' || c === ']') d--;
      else if (c === ':' && d === 1) {
        const m = /["']?([A-Za-z_][A-Za-z0-9_]*)["']?\s*$/.exec(entry.slice(0, i));
        if (m) keys.push(m[1]);
      }
    }
    i++;
  }
  return keys;
}

/* Read one top-level string field's RAW source (escapes intact). */
function rawField(entry, key) {
  const re = new RegExp('["\']?' + key + '["\']?\\s*:\\s*"', 'g');
  let m, best = null, d = 0, i = 0, instr = null, esc = false;
  // find the depth-1 occurrence
  const depths = [];
  while (i < entry.length) {
    const c = entry[i];
    if (instr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === instr) instr = null;
    } else {
      if (c === '"' || c === "'") instr = c;
      else if (c === '{' || c === '[') d++;
      else if (c === '}' || c === ']') d--;
    }
    depths[i] = d;
    i++;
  }
  while ((m = re.exec(entry)) !== null) {
    if (depths[m.index] === 1) { best = m; break; }
  }
  if (!best) return null;
  const vs = best.index + best[0].length;
  let j = vs, e2 = false;
  while (j < entry.length) {
    const c = entry[j];
    if (e2) e2 = false;
    else if (c === '\\') e2 = true;
    else if (c === '"') break;
    j++;
  }
  return entry.slice(vs, j);
}

function fail(msg) { console.error('GATE ABORT: ' + msg); process.exit(2); }

/* ---------------------------------------------------------------- checks */

/* Fields rendered via textContent. Raw HTML and HTML entities here are defects.
   `summary` is the ONLY field rendered via innerHTML — HTML belongs there. (L-NEWS-2) */
const TEXT_FIELDS = [
  'title', 'display_title', 'display_headline', 'landing_headline',
  'standfirst', 'display_teaser', 'imageCredit', 'landing_credit',
  'category', 'tag', 'source', 'sourceLabel', 'byline'
];

const HTML_MARKERS = ['<p ', '<p>', '</p>', '<h2', '</h2>', '<h3', '<ul', '<li', '<div', '<span', '<strong', '<em>', 'class=\\"lede\\"', 'class="lede"'];
const ENTITY_RE = /&(?:amp|lt|gt|quot|nbsp|#8212|#8217|#8211|#8230|#\d{2,5}|mdash|ndash|rsquo|hellip|middot);/;

/* A standfirst past this is almost certainly a body dump.
   Sited against the measured corpus (S264, 94 standfirsts): min 119, median 480, p90 1,073,
   max 3,749 (id:99 Manulife, legitimate). The real corruption produced 4,773 / 6,664 / 7,571.
   2,500 clears every legitimate entry except the five long May entries — which the baseline
   freezes — and sits well below the defect class. Do NOT tighten this without re-measuring;
   long analytical standfirsts are accepted schema here, not a defect. */
const STANDFIRST_HARD_MAX = 2500;

function checkEntry(id, entry, keys) {
  const errs = [], warns = [];
  const has = k => keys.indexOf(k) !== -1;

  // 1. summary key ABSENT (not empty) — the 117/118/119 signature
  if (!has('summary')) {
    errs.push({ check: 'missing-summary', msg: '`summary` key is ABSENT from the entry' });
  }

  // 2. raw HTML inside a textContent field
  for (const f of TEXT_FIELDS) {
    if (!has(f)) continue;
    const v = rawField(entry, f);
    if (v === null) continue;
    for (const mk of HTML_MARKERS) {
      if (v.indexOf(mk) !== -1) {
        errs.push({ check: 'html-in-textfield', field: f,
                    msg: `raw HTML \`${mk.trim()}\` inside textContent field \`${f}\`` });
        break;
      }
    }
  }

  // 3. HTML entities in a textContent field (L-NEWS-2)
  for (const f of TEXT_FIELDS) {
    if (!has(f)) continue;
    const v = rawField(entry, f);
    if (v === null) continue;
    const m = ENTITY_RE.exec(v);
    if (m) {
      errs.push({ check: 'entity-in-textfield', field: f,
                  msg: `HTML entity \`${m[0]}\` in textContent field \`${f}\` — use literal Unicode` });
    }
  }

  // 4. standfirst length blowout — body-dump signature
  if (has('standfirst')) {
    const v = rawField(entry, 'standfirst');
    if (v !== null && v.length > STANDFIRST_HARD_MAX) {
      errs.push({ check: 'standfirst-overlong', field: 'standfirst',
                  msg: `standfirst is ${v.length} chars (hard max ${STANDFIRST_HARD_MAX}) — body dumped into standfirst?` });
    }
  }

  // 5. WARNING — subject mismatch. The id:116 class. Self-consistent corruption; needs an eye.
  if (has('standfirst') && has('title')) {
    const sf = rawField(entry, 'standfirst') || '';
    const ti = rawField(entry, 'title') || '';
    const sl = rawField(entry, 'slug') || '';
    const lead = leadSubject(sf);
    if (lead) {
      const hay = (ti + ' ' + sl).toLowerCase();
      const tokens = lead.toLowerCase().split(/\s+/).filter(t => t.length > 2);
      const hit = tokens.some(t => hay.indexOf(t) !== -1);
      if (!hit) {
        warns.push({ check: 'subject-mismatch', field: 'standfirst',
                     msg: `standfirst opens on "${lead}" which does not appear in title or slug` });
      }
    }
  }

  return { errs, warns };
}

/* First proper-noun run at the head of the standfirst. */
function leadSubject(sf) {
  const m = /^([A-Z][A-Za-z&.'-]*(?:\s+(?:of|and|the)?\s*[A-Z][A-Za-z&.'-]*){0,3})/.exec(sf.trim());
  if (!m) return null;
  const s = m[1].trim();
  if (s.split(/\s+/).length < 2 && s.length < 4) return null;
  return s;
}

/* ---------------------------------------------------------------- run */

const src = readSource(FILE);
const { text: arrText, offset } = extractArray(src);
const entries = splitEntries(arrText);

const findings = [];   // {id, sev, check, field, msg}
const idList = [];

for (const ent of entries) {
  const idm = /["']?id["']?\s*:\s*(\d+)/.exec(ent.text);
  if (!idm) { findings.push({ id: '?', sev: 'ERROR', check: 'no-id', msg: `entry at array offset ${ent.start} has no id` }); continue; }
  const id = Number(idm[1]);
  idList.push(id);
  const keys = topLevelKeys(ent.text);
  const { errs, warns } = checkEntry(id, ent.text, keys);
  for (const e of errs) findings.push(Object.assign({ id, sev: 'ERROR' }, e));
  for (const w of warns) findings.push(Object.assign({ id, sev: 'WARN' }, w));
}

/* corpus-level */
const dupes = idList.filter((v, i) => idList.indexOf(v) !== i);
if (dupes.length) findings.push({ id: dupes.join(','), sev: 'ERROR', check: 'duplicate-id', msg: `duplicate ids: ${[...new Set(dupes)].join(', ')}` });

const key = f => `${f.id}|${f.check}|${f.field || ''}`;

/* ---------------------------------------------------------------- baseline */

if (REGEN) {
  const accepted = {};
  for (const f of findings) accepted[key(f)] = f.msg;
  const out = {
    _comment: 'ACCEPTED STATE — regenerate ONLY after deliberate review. A clean gate run means "nothing changed for the worse", not "everything is perfect".',
    generated: new Date().toISOString().slice(0, 10),
    source: path.basename(FILE),
    entry_count: entries.length,
    head_id: idList[0],
    accepted
  };
  fs.writeFileSync(BASELINE, JSON.stringify(out, null, 2) + '\n');
  console.log(`=== news integrity gate: BASELINE REGENERATED ===`);
  console.log(`  ${BASELINE}`);
  console.log(`  ${entries.length} entries · head id:${idList[0]} · ${Object.keys(accepted).length} accepted finding(s) frozen`);
  process.exit(0);
}

let base;
try { base = JSON.parse(fs.readFileSync(BASELINE, 'utf8')); }
catch (e) { fail(`cannot read baseline ${BASELINE} — run once with --regen-baseline after review`); }

const accepted = base.accepted || {};
const novel = findings.filter(f => !(key(f) in accepted));

const errors = novel.filter(f => f.sev === 'ERROR');
const warnings = novel.filter(f => f.sev === 'WARN');

console.log(`=== news integrity gate: ${path.basename(FILE)} ===`);
console.log(`NEWS at offset ${offset.toLocaleString()} · ${entries.length} entries · head id:${idList[0]} · ${dupes.length} duplicate id(s)`);
console.log(`baseline ${path.basename(BASELINE)} (${base.generated}, ${Object.keys(accepted).length} accepted) · ${findings.length} raw finding(s), ${findings.length - novel.length} suppressed\n`);

/* corpus drift is worth saying out loud even when clean */
if (base.entry_count !== undefined && base.entry_count !== entries.length) {
  console.log(`  note: entry count ${base.entry_count} -> ${entries.length}\n`);
}

if (errors.length) {
  console.log('ERRORS:');
  for (const f of errors) console.log(`  id:${f.id}  [${f.check}]  ${f.msg}`);
  console.log('');
}
if (warnings.length) {
  console.log('WARNINGS (do not fail the gate — but look at them):');
  for (const f of warnings) console.log(`  id:${f.id}  [${f.check}]  ${f.msg}`);
  console.log('');
}
if (VERBOSE) {
  console.log(`suppressed by baseline: ${findings.length - novel.length}`);
}

if (errors.length) {
  console.log(`FAIL: ${errors.length} error(s), ${warnings.length} warning(s).`);
  process.exit(1);
}
console.log(`CLEAN: no new field-level defects.${warnings.length ? ` ${warnings.length} warning(s) above.` : ''}`);
process.exit(0);
