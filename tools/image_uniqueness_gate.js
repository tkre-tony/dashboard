#!/usr/bin/env node
// image_uniqueness_gate.js — S384. No two articles may show the same image.
//
// Usage: node tools/image_uniqueness_gate.js newsroom/index.html [repoRoot]
//
// Hashes every image the NEWS array actually references (the `image` field) and fails
// when two different ids resolve to identical bytes, or when a referenced file is
// missing. Files on disk that nothing references are listed as INFO, not failures:
// several are superseded uploads, and deleting them is a separate decision.
//
// Accepted pairs (S379): the same photograph deliberately reused for the same asset.
//   112 / 147  SBF Center (two weekly REALIS pieces)
//   113 / 128  Elite UK REIT (Queensway House / Wales DWP)
// Accepted S384 (Tony): the same photograph reused for the same asset.
//   132 / 224  Bukit Sembawang — Pollen Collection II aerial (FY2026 results / AGM)
//   116 / 129  Weekly REALIS — Suntec City office towers (15 June / 29 June 2026)
// An accepted pair that no longer matches fails as STALE, so the list cannot rot.

const fs = require('fs'), path = require('path'), vm = require('vm'), crypto = require('crypto');
const ACCEPTED = [[112, 147], [113, 128], [132, 224], [116, 129]];

const [idx, rootArg] = process.argv.slice(2);
if (!idx) { console.error('usage: node tools/image_uniqueness_gate.js newsroom/index.html [repoRoot]'); process.exit(2); }
const root = rootArg || path.resolve(path.dirname(idx), '..');

function loadNews(file) {
  const s = fs.readFileSync(file, 'utf8');
  const m = s.match(/\bvar\s+NEWS\s*=\s*\[/) || s.match(/\bNEWS\s*=\s*\[/);
  if (!m) throw new Error('NEWS array not found');
  let i = m.index + m[0].length, d = 1, q = null, e = false;
  for (; i < s.length && d > 0; i++) {
    const c = s[i];
    if (q) { if (e) e = false; else if (c === '\\') e = true; else if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === '`') q = c; else if (c === '[' || c === '{') d++; else if (c === ']' || c === '}') d--;
  }
  return vm.runInNewContext('(' + s.slice(s.indexOf('[', m.index), i) + ')');
}

const NEWS = loadNews(idx);
const byHash = new Map(), used = new Set();
let fails = 0, refs = 0;
for (const n of NEWS) {
  if (!n.image || /^https?:/i.test(n.image)) continue;
  const f = path.join(root, n.image.replace(/^\//, ''));
  refs++; used.add(path.resolve(f));
  if (!fs.existsSync(f)) { fails++; console.log(`FAIL  MISSING  id:${n.id}  ${n.image}`); continue; }
  const h = crypto.createHash('md5').update(fs.readFileSync(f)).digest('hex');
  if (!byHash.has(h)) byHash.set(h, []);
  byHash.get(h).push({ id: n.id, image: n.image });
}

const key = a => a.slice().sort((x, y) => x - y).join('/');
const accepted = new Set(ACCEPTED.map(key)), seen = new Set();
for (const [h, list] of byHash) {
  const ids = [...new Set(list.map(x => x.id))];
  if (ids.length < 2) continue;
  const k = key(ids);
  if (accepted.has(k)) { seen.add(k); console.log(`OK    ACCEPTED  ids ${k}  (${h.slice(0, 8)})`); continue; }
  fails++;
  console.log(`FAIL  SHARED IMAGE  ids ${k}  md5 ${h.slice(0, 8)}\n      ` + list.map(x => `id:${x.id} ${x.image}`).join('\n      '));
}
for (const k of accepted) if (!seen.has(k)) { fails++; console.log(`FAIL  STALE ACCEPTANCE  ids ${k} no longer share an image`); }

const imgDir = path.join(root, 'images');
const orphans = fs.existsSync(imgDir)
  ? fs.readdirSync(imgDir).filter(f => /^news_/.test(f) && !used.has(path.resolve(imgDir, f))) : [];
if (orphans.length) console.log(`INFO  ${orphans.length} images/news_* file(s) not referenced by NEWS: ` + orphans.slice(0, 12).join(', ') + (orphans.length > 12 ? ', …' : ''));

console.log(`\n=== image uniqueness gate: ${NEWS.length} NEWS entries · ${refs} image refs · ${byHash.size} distinct images · ${fails} failure(s)`);
console.log(fails ? 'FAIL' : 'CLEAN: every article image is unique (accepted pairs excepted).');
process.exit(fails ? 1 : 0);
