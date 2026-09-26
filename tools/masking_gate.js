#!/usr/bin/env node
// masking_gate.js — S384. Fails on unmasked unit numbers in anything published.
//
// Usage:
//   node tools/masking_gate.js <file|dir> [...]  [--allow tools/masking_allowlist.json]
//
//   *.html under news/            article page, scanned whole
//   newsroom/index.html           only the NEWS array is scanned (the data layers in the
//                                 monolith are raw by design and masked at render time)
//   *.json                        card spec: every string value scanned for units AND for
//                                 a bare street number ("25 TAI SENG AVENUE", S383)
//   a directory                   every news/*/index.html beneath it
//
// Unit rule (house style): '#01-33' -> '#01-XX'. Basement and letter floors count:
// '#B1-33' must read '#B1-XX'. A unit is unmasked if the part after the dash contains
// a digit. Slash/comma-joined units ('#07-14,15', '#04-51/52') are caught on the first.
//
// Street rule (spec JSON only): a whole asset has no street number on a card. A number
// is allowed only when a masked unit follows it (strata keeps the block number:
// '60 PAYA LEBAR ROAD #05-XX').
//
// Allowlist: JSON array of {file, match, reason}. 'file' is a path suffix, 'match' an
// exact substring of the hit's context. Every entry must be used, or the gate fails:
// a stale allowance is drift too.

const fs = require('fs');
const path = require('path');

const UNIT = /#\s?[A-Za-z]?\d{1,3}-[A-Za-z]{0,2}\d[A-Za-z0-9]*/g;
const SUFFIX = '(?:ROAD|RD|AVENUE|AVE|STREET|ST|DRIVE|CRESCENT|LANE|LINK|CLOSE|WAY|PLACE|' +
  'BOULEVARD|TERRACE|WALK|VIEW|RISE|HILL|PARK|LOOP|QUAY|SQUARE|CIRCLE|GROVE|ESTATE|' +
  'CENTRAL|NORTH|SOUTH|EAST|WEST|SECTOR|INDUSTRIAL)';
const STREET = new RegExp('(^|[\\s·|,(])(\\d{1,4}[A-Za-z]?)\\s+((?:[A-Za-z@&\'.]+\\s+){0,4}' +
  SUFFIX + '\\b(?:\\s+\\d{1,2}\\b)?)(\\s*#\\s?[A-Za-z]?\\d{1,3}-[Xx*]+)?', 'gi');

const args = process.argv.slice(2);
let allowPath = null;
const targets = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--allow') allowPath = args[++i];
  else targets.push(args[i]);
}
if (!targets.length) {
  console.error('usage: node tools/masking_gate.js <file|dir> [...] [--allow list.json]');
  process.exit(2);
}
const allow = allowPath ? JSON.parse(fs.readFileSync(allowPath, 'utf8')) : [];
const used = new Set();

function expand(t) {
  const st = fs.statSync(t);
  if (st.isFile()) return [t];
  const out = [];
  const news = path.join(t, 'news');
  const base = fs.existsSync(news) ? news : t;
  for (const d of fs.readdirSync(base).sort()) {
    const p = path.join(base, d, 'index.html');
    if (fs.existsSync(p)) out.push(p);
  }
  return out;
}

function newsRegion(s) {
  const m = s.match(/\bvar\s+NEWS\s*=\s*\[/) || s.match(/\bNEWS\s*=\s*\[/);
  if (!m) return null;
  let i = m.index + m[0].length, d = 1, q = null, esc = false;
  for (; i < s.length && d > 0; i++) {
    const c = s[i];
    if (q) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === '`') q = c;
    else if (c === '[' || c === '{') d++;
    else if (c === ']' || c === '}') d--;
  }
  return { text: s.slice(m.index, i), offset: m.index };
}

function ctx(s, i, len) {
  return s.slice(Math.max(0, i - 50), i + len + 30).replace(/<[^>]+>/g, ' ')
    .replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim();
}
function allowed(file, context) {
  for (let k = 0; k < allow.length; k++) {
    const a = allow[k];
    if (file.endsWith(a.file) && context.includes(a.match)) { used.add(k); return a.reason; }
  }
  return null;
}

let files = [];
for (const t of targets) files = files.concat(expand(t));

let fails = 0, allowedHits = 0, scanned = 0;
const failingFiles = new Set();
for (const f of files) {
  const raw = fs.readFileSync(f, 'utf8');
  scanned++;
  const hits = [];
  if (f.endsWith('.json')) {
    const strings = [];
    (function walk(v, k) {
      if (typeof v === 'string') strings.push([k, v]);
      else if (Array.isArray(v)) v.forEach((x, j) => walk(x, `${k}[${j}]`));
      else if (v && typeof v === 'object') for (const kk of Object.keys(v)) walk(v[kk], k ? `${k}.${kk}` : kk);
    })(JSON.parse(raw), '');
    for (const [k, v] of strings) {
      for (const m of v.matchAll(UNIT)) hits.push({ kind: 'UNIT', text: m[0], context: `${k}: ${v}` });
      for (const m of v.matchAll(STREET)) {
        if (m[4]) continue;                       // block number + masked unit: strata, allowed
        hits.push({ kind: 'STREET', text: `${m[2]} ${m[3]}`, context: `${k}: ${v}` });
      }
    }
  } else {
    let s = raw, label = '';
    if (/newsroom[\/\\]index\.html$/.test(f)) {
      const r = newsRegion(raw);
      if (!r) { console.log(`FAIL  ${f}: NEWS array not found`); fails++; continue; }
      s = r.text; label = ' (NEWS)';
    }
    for (const m of s.matchAll(UNIT)) {
      const line = raw.slice(0, (label ? newsRegion(raw).offset : 0) + m.index).split('\n').length;
      hits.push({ kind: 'UNIT', text: m[0], context: ctx(s, m.index, m[0].length), line });
    }
  }
  for (const h of hits) {
    const why = allowed(f, h.context);
    if (why) { allowedHits++; continue; }
    fails++; failingFiles.add(f);
    console.log(`FAIL  ${h.kind}  ${f}${h.line ? ':' + h.line : ''}  ${h.text}\n      ${h.context}`);
  }
}

const stale = allow.map((a, k) => used.has(k) ? null : a).filter(Boolean);
for (const a of stale) {
  fails++;
  console.log(`FAIL  STALE ALLOWANCE  ${a.file}  "${a.match}"  (${a.reason})`);
}

console.log(`\n=== masking gate: ${scanned} file(s) scanned · ${allowedHits} allowed · ` +
  `${fails} failure(s) in ${failingFiles.size} file(s)${stale.length ? ` · ${stale.length} stale allowance(s)` : ''}`);
console.log(fails ? 'FAIL' : 'CLEAN: no unmasked unit numbers.');
process.exit(fails ? 1 : 0);
