#!/usr/bin/env node
/**
 * js_syntax_gate.js — parse every executable inline <script> block.
 *
 * WHY THIS EXISTS
 * ---------------
 * S287, 12 Aug 2026. A one-character quoting error in an inline renderer
 * expression left an unterminated string literal. The whole inline script
 * block failed to parse, no event handlers bound, and every tab on the live
 * site went dead.
 *
 * html_balance_check.js, landing_label_gate.js and news_integrity_gate.js
 * ALL returned exit 0 on that file. None of them parses JavaScript — they
 * check HTML tag balance, date labels and NEWS field structure. The monolith
 * is ~4.3MB of mostly inline JS and had no syntax gate at all.
 *
 * WHAT IT DOES
 * ------------
 * Extracts each <script> block that the browser will actually execute
 * (skipping src= imports and ld+json / application/json data blocks) and
 * compiles it with vm.Script, which is the same parser V8 uses. Reports the
 * offending line and a caret for any block that fails.
 *
 * USAGE
 * -----
 *   node tools/js_syntax_gate.js newsroom/index.html
 *   node tools/js_syntax_gate.js index.html
 *
 * Exit 0 = every block parses. Exit 1 = at least one block is broken.
 * MANDATORY before any monolith deploy.
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
if (!file) {
  console.error('usage: node tools/js_syntax_gate.js <html-file>');
  process.exit(2);
}

const src = fs.readFileSync(file, 'utf8');
console.log('=== JS syntax gate: ' + file + ' ===');
console.log('Size: ' + fs.statSync(file).size.toLocaleString() + ' bytes');

// Match <script ...>...</script>. Non-greedy body; `s`-less for older node.
const re = /<script([^>]*)>([\s\S]*?)<\/script>/gi;

let m, total = 0, checked = 0, skipped = 0, failures = [];
while ((m = re.exec(src)) !== null) {
  total++;
  const attrs = m[1] || '';
  const body  = m[2] || '';

  // Skip external imports and non-executable data blocks.
  if (/\bsrc\s*=/i.test(attrs)) { skipped++; continue; }
  if (/type\s*=\s*["'][^"']*(json|ld\+json|template|text\/plain)/i.test(attrs)) { skipped++; continue; }
  if (!body.trim()) { skipped++; continue; }

  checked++;

  // Line number of this block's opening tag, so errors map to the real file.
  const lineOffset = src.slice(0, m.index).split('\n').length;

  try {
    // Parse only. vm.Script compiles without executing.
    new vm.Script(body, { filename: file, displayErrors: true });
  } catch (err) {
    const rel = (err.stack || '').match(/^.*?:(\d+)\n/);
    const relLine = rel ? parseInt(rel[1], 10) : null;
    failures.push({
      blockIndex: total,
      offset: m.index,
      fileLine: relLine ? lineOffset + relLine - 1 : null,
      message: err.message,
      snippet: relLine ? (body.split('\n')[relLine - 1] || '').slice(0, 220) : null
    });
  }
}

console.log('Script blocks found: ' + total +
            '  ·  executable: ' + checked +
            '  ·  skipped (src / json / empty): ' + skipped);
console.log('');

if (!failures.length) {
  console.log('CLEAN: all ' + checked + ' executable script blocks parse.');
  process.exit(0);
}

console.log('SYNTAX FAILURES (' + failures.length + '):');
failures.forEach(f => {
  console.log('');
  console.log('  block #' + f.blockIndex + ' at byte offset ' + f.offset.toLocaleString() +
              (f.fileLine ? '  ·  approx. file line ' + f.fileLine : ''));
  console.log('  ' + f.message);
  if (f.snippet) console.log('  > ' + f.snippet);
});
console.log('');
console.log('FAILED: do not deploy. The browser will fail to bind event handlers');
console.log('for the whole block, which typically presents as dead navigation.');
process.exit(1);
