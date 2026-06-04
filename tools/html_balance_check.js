#!/usr/bin/env node
/**
 * html_balance_check.js — pre-deploy HTML tag balance validator
 *
 * Catches malformed HTML that browsers silently error-recover. Specifically:
 *   1. Tags that open with `<tag` and never reach `>` before next `</`
 *   2. Duplicate ids (warning only — some are acceptable patterns)
 *
 * Aware of <!-- comment -->, <script>...</script>, <style>...</style>
 * regions so it doesn't false-positive on code samples or literal-text content.
 *
 * Usage:  node html_balance_check.js /path/to/index.html
 * Exit:   0 = clean, 1 = defects found, 2 = file error
 */
const fs = require('fs');

const FILE = process.argv[2] || '/home/claude/work/index.html';
let html;
try { html = fs.readFileSync(FILE, 'utf-8'); }
catch (e) { console.error('ERROR: ' + e.message); process.exit(2); }

// ─── Build a fast "is offset N inside an ignore-block?" oracle ───
// Ignore blocks: HTML comments, <script>...</script>, <style>...</style>
const blockRanges = [];

function buildRanges(openRe, closeStr) {
  let m;
  while ((m = openRe.exec(html)) !== null) {
    const openEnd = m.index + m[0].length;
    const closeStart = html.indexOf(closeStr, openEnd);
    blockRanges.push([m.index, closeStart === -1 ? html.length : closeStart + closeStr.length]);
  }
}

// HTML comments: <!--...-->
buildRanges(/<!--/g, '-->');
// Real <script> tag opener (not script="..." attribute)
buildRanges(/<script(?=[\s>])/g, '</script>');
// Real <style> tag opener (not style="..." attribute)
buildRanges(/<style(?=[\s>])/g, '</style>');

// Sort ranges so we can binary-search later (optional optimization)
blockRanges.sort((a, b) => a[0] - b[0]);

function inBlock(pos) {
  // Linear is fine for ~thousands of ranges in a 4MB file
  for (const [s, e] of blockRanges) {
    if (pos < s) return false; // ranges sorted, can early-exit
    if (pos < e) return true;
  }
  return false;
}

const defects = [];
const warnings = [];

// ─── Check 1: Malformed openers — `<tag...</` with no `>` between ───
const tagOpenPattern = /<([a-zA-Z][a-zA-Z0-9]*)([^>]{0,800})<\//g;
let m;
while ((m = tagOpenPattern.exec(html)) !== null) {
  if (inBlock(m.index)) continue;
  if (m[2].includes('>')) continue; // defensive

  const before = html.substring(0, m.index);
  const lineNumber = before.split('\n').length;
  const lineStart = before.lastIndexOf('\n') + 1;
  const col = m.index - lineStart + 1;
  const lineEnd = html.indexOf('\n', m.index);
  const snippet = html.substring(lineStart, lineEnd > 0 ? lineEnd : m.index + 80)
                       .replace(/\r/g, '').substring(0, 160);

  defects.push({
    type: 'malformed-tag',
    line: lineNumber,
    col: col,
    bytePos: m.index,
    tagName: m[1],
    snippet: snippet,
  });
}

// ─── Check 2: Duplicate ids (outside ignore blocks) ───
const idPattern = /\sid=["']([^"']+)["']/g;
const idCounts = {};
while ((m = idPattern.exec(html)) !== null) {
  if (inBlock(m.index)) continue;
  const id = m[1];
  if (!idCounts[id]) idCounts[id] = [];
  idCounts[id].push(m.index);
}
for (const id in idCounts) {
  if (idCounts[id].length > 1) {
    warnings.push({ type: 'duplicate-id', id, count: idCounts[id].length, positions: idCounts[id] });
  }
}

// ─── Report ───
const sizeBytes = Buffer.byteLength(html, 'utf-8');
console.log('=== HTML balance check: ' + FILE + ' ===');
console.log('Size: ' + sizeBytes.toLocaleString() + ' bytes (UTF-8)');
console.log('Ignore-block ranges scanned: ' + blockRanges.length);
console.log();

if (defects.length === 0 && warnings.length === 0) {
  console.log('CLEAN: no malformed tags or duplicate ids.');
  process.exit(0);
}

if (defects.length > 0) {
  console.log('DEFECTS (' + defects.length + '):');
  defects.forEach(d => {
    console.log('  [' + d.type + '] line ' + d.line + ' col ' + d.col + ' byte ' + d.bytePos);
    console.log('    Opener `<' + d.tagName + '` reaches `</` before `>` — browser will error-recover');
    console.log('    > ' + d.snippet);
    console.log();
  });
}

if (warnings.length > 0) {
  console.log('WARNINGS (' + warnings.length + ', non-blocking):');
  warnings.forEach(w => {
    console.log('  [' + w.type + '] id="' + w.id + '" x' + w.count
      + ' at: ' + w.positions.slice(0, 5).join(', ')
      + (w.positions.length > 5 ? '...' : ''));
  });
}

process.exit(defects.length > 0 ? 1 : 0);
