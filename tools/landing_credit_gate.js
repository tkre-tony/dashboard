#!/usr/bin/env node
// landing_credit_gate.js — S384. landing_credit on the landing page must be <= 130 chars.
//
// Usage: node tools/landing_credit_gate.js newsroom/index.html [--max 130]
//
// The landing set is the NEWS head (hero) plus NR_STATIC_IDS (cards and feed) — the
// eleven articles the landing page renders. v48.464 trimmed these to the 130-char
// standard. Older entries carry longer credits written before the standard; they have
// rolled off the landing page and never re-enter it, so they are counted, not failed.
// An id in the landing set with an image but no landing_credit is also a failure.

const fs = require('fs'), vm = require('vm');
const args = process.argv.slice(2);
const idx = args.find(a => !a.startsWith('--') && !/^\d+$/.test(a));
const mi = args.indexOf('--max'); const MAX = mi >= 0 ? +args[mi + 1] : 130;
if (!idx) { console.error('usage: node tools/landing_credit_gate.js newsroom/index.html [--max 130]'); process.exit(2); }
const s = fs.readFileSync(idx, 'utf8');

const m = s.match(/\bvar\s+NEWS\s*=\s*\[/) || s.match(/\bNEWS\s*=\s*\[/);
let i = m.index + m[0].length, d = 1, q = null, e = false;
for (; i < s.length && d > 0; i++) {
  const c = s[i];
  if (q) { if (e) e = false; else if (c === '\\') e = true; else if (c === q) q = null; continue; }
  if (c === '"' || c === "'" || c === '`') q = c; else if (c === '[' || c === '{') d++; else if (c === ']' || c === '}') d--;
}
const NEWS = vm.runInNewContext('(' + s.slice(s.indexOf('[', m.index), i) + ')');

const st = s.match(/NR_STATIC_IDS\s*=\s*\[\s*(\d+(?:\s*,\s*\d+)+)\s*\]/);
if (!st) { console.log('FAIL  NR_STATIC_IDS assignment not found'); process.exit(1); }
const statics = st[1].split(',').map(x => +x.trim());
const head = Math.max(...NEWS.map(n => +n.id));
const landing = [head, ...statics];

let fails = 0;
for (const id of landing) {
  const n = NEWS.find(x => +x.id === id);
  if (!n) { fails++; console.log(`FAIL  id:${id} in landing set but not in NEWS`); continue; }
  const c = n.landing_credit;
  if (!c) { if (n.image) { fails++; console.log(`FAIL  id:${id} has an image but no landing_credit`); } continue; }
  const len = [...c].length;
  const flag = len > MAX ? 'FAIL' : 'ok  ';
  if (len > MAX) fails++;
  console.log(`${flag}  id:${id}  ${String(len).padStart(3)} chars${id === head ? '  (hero)' : ''}${len > MAX ? '\n      ' + c : ''}`);
}
const older = NEWS.filter(n => n.landing_credit && !landing.includes(+n.id) && [...n.landing_credit].length > MAX).length;
console.log(`\n=== landing_credit gate: landing set ${landing.length} ids (hero ${head}) · max ${MAX} · ${fails} failure(s) · ${older} off-landing entr${older === 1 ? 'y' : 'ies'} over ${MAX} (pre-standard, not gated)`);
console.log(fails ? 'FAIL' : `CLEAN: every landing credit is within ${MAX} characters.`);
process.exit(fails ? 1 : 0);
