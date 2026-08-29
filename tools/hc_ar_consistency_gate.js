#!/usr/bin/env node
/* hc_ar_consistency_gate.js — Human Capital consistency gate (L-HC-1)
 *
 * WHY THIS EXISTS
 * ---------------
 * S346, 29 Aug 2026. A Wendy Koh board-departure check surfaced three latent
 * defects in TALENT_DATA that no existing gate could see:
 *   1. Six MIT director records carried WRONG NAMES against correct ids and
 *      correct fee figures. Nothing flagged it because the JSON was valid.
 *   2. An AR refresh updated 12 board records to FY25/26 but left the CEO and
 *      CFO records on FY24/25, so the entity's year label rendered stale.
 *   3. entity_short read 'MINT' where the issuer's own AR uses 'MIT'.
 *
 * js_syntax_gate, html_balance_check, landing_label_gate and
 * news_integrity_gate ALL returned exit 0 on that file. None of them opens a
 * TALENT_DATA record.
 *
 * WHAT IT CHECKS (per entity)
 *   A  MIXED AR YEAR    more than one ar_year among CURRENT people, ignoring
 *                       records explicitly marked departed ("until"/"retired")
 *   B  ENTITY_SHORT     more than one entity_short value for the same entity
 *   C  DUP NAME         same person name twice within one entity
 *   D  DUP ID           any id repeated anywhere
 *   E  ORPHAN HISTORY   rem_history contains a year NEWER than ar_year
 *   F  SUM MISMATCH     rem_fixed + rem_bonus + rem_other != rem_exact
 *   G  PCT MISMATCH     rem_pct_* present and summing outside 99-101
 *   H  STALE CURRENT    ar_year older than the newest ar_year seen for that
 *                       entity — the exact defect that shipped in S346
 *
 * USAGE
 *   node tools/hc_ar_consistency_gate.js newsroom/index.html [--entity "MPACT"] [-v]
 *
 * EXIT  0 = clean   1 = one or more errors   2 = could not run
 *
 * NOTE ON SCOPE: this gate proves INTERNAL consistency only. It cannot know
 * whether a name matches the annual report. Name correctness still requires
 * reconciliation against the AR remuneration table by a human or by the
 * per-entity reconciler used in S346.
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

const argv = process.argv.slice(2);
const FILE = argv.find(a => !a.startsWith('-') && !/^(MPACT|.*Trust|.*Limited)$/.test(a));
const VERBOSE = argv.includes('-v');
const eIdx = argv.indexOf('--entity');
const ONLY = eIdx !== -1 ? argv[eIdx + 1] : null;

if (!FILE) { console.error('usage: node hc_ar_consistency_gate.js <newsroom/index.html> [--entity NAME] [-v]'); process.exit(2); }

let src;
try { src = fs.readFileSync(FILE, 'utf8'); } catch (e) { console.error('cannot read ' + FILE); process.exit(2); }

/* --- L-PARSE-8: slice from the declaration's '[', grow to each ']', accept
       the first slice V8 will parse. Never hand-roll a bracket matcher. --- */
function v8Slice(declRe, label) {
  const m = declRe.exec(src);
  if (!m) { console.error(label + ' declaration not found'); process.exit(2); }
  const lb = src.indexOf('[', m.index);
  let rb = src.indexOf(']', lb), tries = 0;
  while (rb !== -1) {
    tries++;
    try { return { val: vm.runInNewContext('(' + src.slice(lb, rb + 1) + ')'), tries }; }
    catch (e) { rb = src.indexOf(']', rb + 1); }
    if (tries > 400000) break;
  }
  console.error(label + ': no parseable slice'); process.exit(2);
}

const parsed = v8Slice(/(?:var|const|let)\s+TALENT_DATA\s*=/g, 'TALENT_DATA');
const T = parsed.val;

const DEPARTED = /\b(until|retired|resigned|stepped down|ceased)\b/i;
// Normalise FY labels to a comparable key. Issuers mix conventions: FPL writes
// "FY25", Mapletree writes "FY25/26" and "FY2025/26". Digits-only is not enough —
// FY25 and FY2025 are the same year but differ digit-for-digit. Reduce every
// component to its last two digits and join.
const yearKey = y => (String(y || '').match(/\d{2,4}/g) || [])
  .map(n => n.slice(-2)).join('-');
const errs = [], warns = [];
const E = (e, c, m) => errs.push('[' + c + '] ' + e + ': ' + m);
const W = (e, c, m) => warns.push('[' + c + '] ' + e + ': ' + m);

console.log('=== HC AR consistency gate: ' + FILE + ' ===');
console.log('TALENT_DATA ' + T.length + ' records · parsed in ' + parsed.tries + ' slice attempts');

/* D — duplicate ids, file-wide */
const idSeen = new Map();
for (const r of T) {
  if (idSeen.has(r.id)) E('(file)', 'DUP ID', r.id + ' appears more than once');
  idSeen.set(r.id, true);
}

const entities = [...new Set(T.map(r => r.entity))].filter(e => !ONLY || e === ONLY);

for (const ent of entities) {
  const rows = T.filter(r => r.entity === ent);
  const current = rows.filter(r => !DEPARTED.test(r.role || ''));
  // A record with no remuneration figure carries no AR vintage — it is an
  // appointment record, not an AR extract — so it cannot be "behind" a year.
  // Including them produced a false MIXED AR YEAR on Frasers in S346.
  const dated = current.filter(r => r.rem_exact != null || (r.rem_history || []).filter(Boolean).length > 0);

  /* B — entity_short */
  const shorts = [...new Set(rows.map(r => r.entity_short))];
  if (shorts.length > 1) E(ent, 'ENTITY_SHORT', 'multiple values: ' + shorts.join(', '));

  /* A + H — ar_year coherence among current people */
  const years = [...new Set(dated.map(r => r.ar_year))];
  if (years.length > 1) {
    const newest = years.slice().sort((a, b) => yearKey(b).localeCompare(yearKey(a)))[0];
    const stale = dated.filter(r => r.ar_year !== newest);
    E(ent, 'MIXED AR YEAR', years.length + ' years among current people (' + years.join(' / ') +
      '). Newest is ' + newest + '; ' + stale.length + ' record(s) behind: ' +
      stale.map(r => r.name + ' [' + r.ar_year + ']').join(', '));
  }

  /* C — duplicate names within entity */
  const nameSeen = new Map();
  for (const r of rows) {
    if (nameSeen.has(r.name)) E(ent, 'DUP NAME', r.name + ' appears twice (' + nameSeen.get(r.name) + ', ' + r.id + ')');
    nameSeen.set(r.name, r.id);
  }

  for (const r of rows) {
    /* E — history newer than ar_year */
    for (const h of (r.rem_history || []).filter(Boolean)) {
      if (yearKey(h.year) > yearKey(r.ar_year)) E(ent, 'ORPHAN HISTORY', r.name + ': history year ' + h.year + ' is newer than ar_year ' + r.ar_year);
    }
    /* F — components vs total */
    const parts = [r.rem_fixed, r.rem_bonus, r.rem_other];
    if (r.rem_exact != null && parts.every(p => typeof p === 'number')) {
      const sum = parts.reduce((a, b) => a + b, 0);
      if (Math.abs(sum - r.rem_exact) > 1) E(ent, 'SUM MISMATCH', r.name + ': ' + parts.join(' + ') + ' = ' + sum + ' vs rem_exact ' + r.rem_exact);
    }
    /* G — percentages */
    // rem_pct_ltp is a FOURTH component present on some records (long-term
    // incentives). Omitting it produced 11 false positives in S346 — the data
    // was correct and the gate was wrong. Always include it when present.
    const pcts = [r.rem_pct_fixed, r.rem_pct_bonus, r.rem_pct_other];
    if (pcts.every(p => typeof p === 'number')) {
      const ps = pcts.reduce((a, b) => a + b, 0) + (typeof r.rem_pct_ltp === 'number' ? r.rem_pct_ltp : 0);
      if (ps < 99 || ps > 101) W(ent, 'PCT', r.name + ': percentages sum to ' + ps);
    }
  }

  if (VERBOSE) console.log('  ' + ent + ': ' + rows.length + ' records, ' + current.length + ' current, years=' + years.join('/') + ', short=' + shorts.join('/'));
}

/* I — hardcoded entity <select> year labels vs TALENT_DATA */
const optRe = /<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g;
const allOpts = [...src.matchAll(optRe)].filter(o => o[1] && T.some(r => r.entity === o[1]));
if (allOpts.length === 0) {
  W('(file)', 'OPTION DRIFT', 'no entity <option> list found — check the selector still exists');
} else {
  let checked = 0;
  for (const [, val, label] of allOpts) {
    if (ONLY && val !== ONLY) continue;
    const rs = T.filter(r => r.entity === val);
    const cur = rs.filter(r => !DEPARTED.test(r.role || '') && (r.rem_exact != null || (r.rem_history || []).filter(Boolean).length > 0));
    if (!cur.length) continue;
    const newest = [...new Set(cur.map(r => r.ar_year))].sort((a, b) => yearKey(b).localeCompare(yearKey(a)))[0];
    const lm = /\(([^)]*)\)/.exec(label);
    const shown = lm ? lm[1] : null;
    checked++;
    if (shown === null) { W(val, 'OPTION DRIFT', 'option label "' + label.trim() + '" carries no year; data newest is ' + newest); continue; }
    if (yearKey(shown) !== yearKey(newest)) {
      E(val, 'OPTION DRIFT', 'dropdown shows "' + label.trim() + '" but TALENT_DATA newest is ' + newest);
    }
    const shortName = [...new Set(rs.map(r => r.entity_short))][0];
    const labelName = label.replace(/\s*\([^)]*\)\s*$/, '').trim();
    if (shortName && labelName !== shortName) W(val, 'OPTION NAME', 'label "' + labelName + '" vs entity_short "' + shortName + '" (cosmetic unless wrong)');
  }
  if (VERBOSE) console.log('  entity <option> labels checked: ' + checked);
}

console.log();
if (warns.length) { console.log('WARNINGS (' + warns.length + '):'); warns.forEach(w => console.log('  ' + w)); console.log(); }
if (errs.length) {
  console.log('ERRORS (' + errs.length + '):');
  errs.forEach(e => console.log('  ' + e));
  console.log('\nFAIL');
  process.exit(1);
}
console.log('CLEAN: no HC consistency defects across ' + entities.length + ' entities.');
process.exit(0);
