#!/usr/bin/env node
/**
 * generate_all.js — PropertyAtlas newsroom static-page generator
 * ---------------------------------------------------------------
 * Reconstructed S85 from the live index.html SPA renderer + the
 * Newsroom Article Publishing SOP (ATLAS_newsroom_article_publishing_SOP.md).
 *
 * Emits one gate-clean  news/<slug>/index.html  per public NEWS article,
 * by LIFTING the site's own render helpers out of index.html and running
 * them in a sandbox — so the static page can never drift from the SPA.
 *
 * Correct-by-construction vs the S72 defects:
 *   - ZERO HTML comments in output  -> the unclosed-comment blank-page trap
 *     is structurally impossible.
 *   - share block + related rail come from the lifted renderer itself.
 *   - full .ed-art-* CSS (incl. .neutral + .ptable) extracted by selector
 *     match -> every body class resolves to a rule (L-SEO-8 by construction).
 *   - ?article=N rewritten to /news/<slug>/  (zero ?article= in output).
 *   - image paths made root-absolute (/images/...).
 *   - self-canonical + favicon set + OG + Twitter + JSON-LD NewsArticle in <head>.
 *
 * Usage:
 *   node generate_all.js [indexPath] [outDir] [--only <id>] [--dry]
 *     indexPath  default ./index.html
 *     outDir     default ./           (pages -> <outDir>/news/<slug>/index.html)
 *     --only <id>  generate a single article (milestone / spot-check)
 *     --dry        render + gate but do NOT write files
 *
 * Exit: 0 = all generated pages passed every gate; 1 = a gate failed.
 *
 * NOTE: hero-image optimisation (Stage 2) and the pre-push coverage gate
 * (Stage 3) are wired in subsequent stages; this file is the render+gate core.
 */
'use strict';

const fs   = require('fs');
const path = require('path');
const vm   = require('vm');
const { execFileSync } = require('child_process');
const { JSDOM } = require('jsdom');
let sharp = null; try { sharp = require('sharp'); } catch (_) { /* optimiser degrades to skip */ }

// ─────────────────────────── config ───────────────────────────
const SITE  = 'https://propertyatlas.sg';
const HERO_BUDGET = 290 * 1024;   // ~290 KB target for hero images
const HERO_MAXW   = 1600;         // cap hero width; heroes display ≤ ~1200 CSS px
const argv  = process.argv.slice(2);
const flags = {};
const pos   = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--only')          flags.only = argv[++i];
  else if (argv[i] === '--dry')      flags.dry  = true;
  else if (argv[i] === '--no-images') flags.noImages = true;
  else if (argv[i] === '--check')    flags.check = true;   // pre-push gate (Stage 3)
  else pos.push(argv[i]);
}
const INDEX  = pos[0] || './index.html';
const OUTDIR = pos[1] || './';
const IMAGES_DIR = path.join(OUTDIR, 'images');
const SITEMAP    = path.join(OUTDIR, 'sitemap.xml');
// Resolve the L282 checker: next to this script (e.g. tools/), else repo root.
const L282 = [path.join(__dirname, 'html_balance_check.js'),
              path.join(OUTDIR, 'html_balance_check.js')]
  .find(p => { try { return fs.existsSync(p); } catch (_) { return false; } })
  || path.join(__dirname, 'html_balance_check.js');

// NAV-1/S164: normalise input EOLs — the newsroom monolith is CRLF but
// static article pages are LF-only (L-EOL-1). Lifted CSS/JS must not leak \r.
const html = fs.readFileSync(INDEX, 'utf8').replace(/\r\n/g, '\n');

// ─── v48.245 (S136): static-page newsletter subscribe ───────────────────────
// The article-end CTA button (onclick="nlSubOpen('article-end')") is rendered
// by the lifted SPA renderer, but nlSubOpen only exists in the SPA — on static
// pages it was a dead button. We inject a self-contained subscribe modal that
// defines window.nlSubOpen and POSTs straight to the newsletter-subscribe Edge
// Function (CORS already configured). The public anon JWT + project URL are
// pulled from the same index we're parsing, so there is one source of truth.
const SB_URL  = (html.match(/PROJ_SUPABASE_URL\s*=\s*["']([^"']+)["']/) || [])[1] || '';
const SB_ANON = (html.match(/PROJ_SUPABASE_KEY\s*=\s*["']([^"']+)["']/) || [])[1] || '';
if (!SB_URL || !SB_ANON) {
  console.error('FATAL: could not extract PROJ_SUPABASE_URL/KEY from index for the static subscribe handler.');
  process.exit(1);
}

// pa-sub-* CSS — appended into the page HEAD <style> so L-SEO-8 class coverage
// resolves every class (the gate reads only the first <style> block).
const SUBSCRIBE_CSS = [
  '.pa-sub-overlay{display:none;position:fixed;inset:0;background:rgba(13,31,60,.55);z-index:3000}',
  '.pa-sub-modal{display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:3001;width:min(440px,94vw);max-height:92vh;overflow-y:auto;background:#fff;border-radius:14px;box-shadow:0 12px 48px rgba(13,31,60,.32);font-family:inherit}',
  '.pa-sub-head{background:#0d1f3c;color:#fff;padding:22px 24px 18px;border-radius:14px 14px 0 0;position:relative}',
  '.pa-sub-close{position:absolute;top:12px;right:12px;width:28px;height:28px;border:none;border-radius:7px;background:rgba(255,255,255,.14);color:#fff;font-size:18px;line-height:1;cursor:pointer}',
  '.pa-sub-close:hover{background:rgba(255,255,255,.26)}',
  '.pa-sub-title{font-size:17px;font-weight:700;line-height:1.3}',
  '.pa-sub-sub{font-size:12px;color:rgba(255,255,255,.7);line-height:1.5;margin-top:6px}',
  '.pa-sub-body{padding:20px 24px 22px}',
  '.pa-sub-field{margin-bottom:14px}',
  '.pa-sub-field label{display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;color:#475569;margin-bottom:6px}',
  '.pa-sub-field label span{font-weight:500;text-transform:none;letter-spacing:0;color:#94a3b8}',
  '.pa-sub-field input{width:100%;height:40px;padding:0 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;font-family:inherit;color:#1e293b;box-sizing:border-box;outline:none}',
  '.pa-sub-field input:focus{border-color:#0d1f3c}',
  '.pa-sub-submit{width:100%;height:44px;background:#0d1f3c;color:#fff;border:none;border-radius:9px;font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;transition:opacity .15s}',
  '.pa-sub-submit:hover:not(:disabled){opacity:.9}',
  '.pa-sub-submit:disabled{opacity:.55;cursor:not-allowed}',
  '.pa-sub-error{display:none;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:10px 12px;font-size:12.5px;color:#b91c1c;line-height:1.5;margin-bottom:14px}',
  '.pa-sub-privacy{margin-top:12px;font-size:10.5px;color:#94a3b8;line-height:1.5;text-align:center}',
  '.pa-sub-success{padding:8px 24px 24px;text-align:center}',
  '.pa-sub-success-icon{width:48px;height:48px;margin:8px auto 14px;border-radius:50%;background:#dcfce7;color:#16a34a;font-size:24px;line-height:48px;font-weight:700}',
  '.pa-sub-success-title{font-size:16px;font-weight:700;color:#1e293b;margin-bottom:8px}',
  '.pa-sub-success-msg{font-size:13px;color:#64748b;line-height:1.6;margin-bottom:18px}'
].join('\n');

// pa-sub-* markup + self-contained script, injected before </body>.
// No regex/backslashes in the script (avoids generator-escaping traps); the
// Edge Function does authoritative validation server-side. No HTML comments.
const SUBSCRIBE_BODY =
'<div id="pa-sub-overlay" class="pa-sub-overlay"></div>\n' +
'<div id="pa-sub-modal" class="pa-sub-modal" role="dialog" aria-modal="true" aria-labelledby="pa-sub-title">\n' +
'<div class="pa-sub-head">\n' +
'<button type="button" class="pa-sub-close" aria-label="Close" onclick="paSubClose()">&times;</button>\n' +
'<div id="pa-sub-title" class="pa-sub-title">Get the brief in your inbox</div>\n' +
'<div class="pa-sub-sub">Weekly newsroom highlights, REIT earnings coverage, and Singapore commercial-property market signal.</div>\n' +
'</div>\n' +
'<div class="pa-sub-body" id="pa-sub-formwrap">\n' +
'<div id="pa-sub-error" class="pa-sub-error"></div>\n' +
'<div class="pa-sub-field"><label for="pa-sub-name">Name <span>(optional)</span></label><input id="pa-sub-name" type="text" autocomplete="name"></div>\n' +
'<div class="pa-sub-field"><label for="pa-sub-email">Email</label><input id="pa-sub-email" type="email" autocomplete="email"></div>\n' +
'<button type="button" id="pa-sub-submit" class="pa-sub-submit" onclick="paSubSubmit()">Subscribe</button>\n' +
'<div class="pa-sub-privacy">Double opt-in: we will email a confirmation link. Unsubscribe anytime.</div>\n' +
'</div>\n' +
'<div class="pa-sub-success" id="pa-sub-success" style="display:none">\n' +
'<div class="pa-sub-success-icon">&#10003;</div>\n' +
'<div class="pa-sub-success-title">Almost there</div>\n' +
'<div class="pa-sub-success-msg">Check your inbox to confirm your subscription.</div>\n' +
'<button type="button" class="pa-sub-submit" onclick="paSubClose()">Done</button>\n' +
'</div>\n' +
'</div>\n' +
'<script>\n' +
'(function(){\n' +
'var SB_URL=' + JSON.stringify(SB_URL) + ';\n' +
'var SB_ANON=' + JSON.stringify(SB_ANON) + ';\n' +
"var src='article-end';\n" +
'function g(id){return document.getElementById(id);}\n' +
"function looksEmail(s){if(!s||s.indexOf(' ')>=0)return false;var at=s.indexOf('@');if(at<1)return false;var dot=s.indexOf('.',at);return dot>at+1&&dot<s.length-1;}\n" +
'window.nlSubOpen=function(sourcePage){\n' +
"src=sourcePage||'article-end';\n" +
"g('pa-sub-error').style.display='none';\n" +
"g('pa-sub-formwrap').style.display='';\n" +
"g('pa-sub-success').style.display='none';\n" +
"var b=g('pa-sub-submit');b.disabled=false;b.textContent='Subscribe';\n" +
"g('pa-sub-overlay').style.display='block';\n" +
"g('pa-sub-modal').style.display='block';\n" +
"setTimeout(function(){try{g('pa-sub-email').focus();}catch(e){}},60);\n" +
'};\n' +
"window.paSubClose=function(){g('pa-sub-overlay').style.display='none';g('pa-sub-modal').style.display='none';};\n" +
'window.paSubSubmit=async function(){\n' +
"var name=g('pa-sub-name').value.trim();\n" +
"var email=g('pa-sub-email').value.trim();\n" +
"var err=g('pa-sub-error');\n" +
"if(!looksEmail(email)){err.textContent='Please enter a valid email address.';err.style.display='block';return;}\n" +
"err.style.display='none';\n" +
"var b=g('pa-sub-submit');b.disabled=true;b.textContent='Subscribing...';\n" +
'try{\n' +
"var res=await fetch(SB_URL+'/functions/v1/newsletter-subscribe',{\n" +
"method:'POST',\n" +
"headers:{'Content-Type':'application/json','Authorization':'Bearer '+SB_ANON},\n" +
"body:JSON.stringify({email:email,name:name||null,categories:['All'],cadence:'weekly',source_page:src})\n" +
'});\n' +
'var data=null;try{data=await res.json();}catch(e){}\n' +
"if(!res.ok||(data&&data.ok===false)){throw new Error((data&&data.error)||'Subscription failed. Please try again.');}\n" +
"g('pa-sub-formwrap').style.display='none';\n" +
"g('pa-sub-success').style.display='block';\n" +
'}catch(ex){\n' +
"err.textContent=(ex&&ex.message)?ex.message:'Something went wrong. Please try again.';\n" +
"err.style.display='block';\n" +
"b.disabled=false;b.textContent='Subscribe';\n" +
'}\n' +
'};\n' +
"document.addEventListener('keydown',function(e){if(e.key==='Escape'&&typeof window.paSubClose==='function')window.paSubClose();});\n" +
"document.addEventListener('click',function(e){if(e.target&&e.target.id==='pa-sub-overlay')window.paSubClose();});\n" +
'})();\n' +
'<\/script>';
// ─── end v48.245 static-page subscribe block ────────────────────────────────


// ─── NAV-1 Phase 1 (S164): navy global topbar on static article pages ───────
// Mirrors the map root's .topbar visually; self-contained pa-tb-* namespace
// (no collision with ed-art-* / monolith classes). Bucket hrefs use the map's
// canonical showBucket() destinations. Replaces the legacy ed-art-masthead in
// buildPage; the inline "← PropertyAtlas" back link in the body is retained.
// Colors hardcoded (article :root does not define the map's --navy/--gold).
const NAVY_TOPBAR_CSS = [
'.pa-tb{background:#15233f;display:flex;align-items:center;padding:0 20px;height:44px}',
'.pa-tb-home{display:flex;align-items:center;text-decoration:none}',
'.pa-tb-logo{width:26px;height:26px;border-radius:6px;background:rgba(200,145,42,.15);display:flex;align-items:center;justify-content:center;color:#C8912A;font-weight:800;font-family:Georgia,"Times New Roman",serif;font-size:13px}',
'.pa-tb-brand{font-family:Georgia,"Times New Roman",serif;font-size:17px;font-weight:700;color:#fff;margin-left:8px}',
'.pa-tb-brand i{color:#C8912A;font-style:normal}',
'.pa-tb-buckets{display:flex;gap:2px;margin-left:32px}',
'.pa-tb-bucket{color:rgba(255,255,255,.55);font-size:13px;font-weight:600;text-decoration:none;padding:6px 14px;border-radius:6px;transition:.15s;letter-spacing:.01em}',
'.pa-tb-bucket:hover{color:#fff;background:rgba(255,255,255,.08)}',
'.pa-tb-bucket.on{color:#fff;background:#1a4f9c}',
'.pa-tb-pagenav{margin-left:auto;display:flex;gap:6px}',
'.pa-tb-pagenav a{color:rgba(255,255,255,.65);font-size:12px;text-decoration:none;padding:5px 10px;border-radius:5px;transition:.12s}',
'.pa-tb-pagenav a:hover{color:#fff;background:rgba(255,255,255,.08)}',
'@media(max-width:760px){.pa-tb{padding:0 10px}.pa-tb-buckets{margin-left:14px;overflow-x:auto;-webkit-overflow-scrolling:touch}.pa-tb-pagenav a{font-size:11px;padding:4px 6px}.pa-tb-pagenav a.pa-tb-static{display:none}}'
].join('\n');

const NAVY_TOPBAR_HTML =
'<div class="pa-tb">' +
'<a class="pa-tb-home" href="/" aria-label="PropertyAtlas home"><span class="pa-tb-logo">P</span><span class="pa-tb-brand">Property<i>Atlas</i></span></a>' +
'<nav class="pa-tb-buckets" aria-label="Primary">' +
'<a href="/" class="pa-tb-bucket">Market</a>' +
'<a href="/newsroom/#asset-directory" class="pa-tb-bucket">Entities</a>' +
'<a href="/newsroom/" class="pa-tb-bucket on">Newsroom</a>' +
'<a href="/newsroom/#listings" class="pa-tb-bucket">Listings</a>' +
'</nav>' +
'<div class="pa-tb-pagenav">' +
'<a href="/terms.html" class="pa-tb-static">Terms</a>' +
'<a href="/privacy.html" class="pa-tb-static">Privacy</a>' +
'<a href="/about.html" class="pa-tb-static">About</a>' +
'<a href="/newsroom/">Sign in</a>' +
'</div>' +
'</div>';

// ───────────────── JS region lifters (brace/bracket aware) ─────────────────
// Walk from an anchor to the matching close delimiter, ignoring strings and
// comments, so we can extract balanced source no matter the line layout.
function liftFrom(src, startIdx, openCh, closeCh) {
  let i = src.indexOf(openCh, startIdx);
  if (i < 0) throw new Error('open delimiter not found after index ' + startIdx);
  const open = i;
  let depth = 0, inStr = false, q = '', esc = false, inLC = false, inBC = false;
  let inRe = false, reClass = false, prevSig = '';
  // chars after which a `/` begins a regex literal (not division)
  const RE_PREV = new Set(['(', ',', ';', ':', '=', '[', '!', '&', '|', '?', '{', '}', '<', '>', '+', '-', '*', '%', '^', '~', '']);
  for (; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (esc) { esc = false; continue; }
    if (inLC) { if (c === '\n') inLC = false; continue; }
    if (inBC) { if (c === '*' && n === '/') { inBC = false; i++; } continue; }
    if (inStr) {
      if (c === '\\') { esc = true; }
      else if (c === q) { inStr = false; }
      continue;
    }
    if (inRe) {                                   // inside a /regex/ literal
      if (c === '\\') { esc = true; }
      else if (reClass) { if (c === ']') reClass = false; }
      else if (c === '[') reClass = true;
      else if (c === '/') inRe = false;           // unescaped, outside class -> ends regex
      continue;
    }
    if (c === '/' && n === '/') { inLC = true; i++; continue; }
    if (c === '/' && n === '*') { inBC = true; i++; continue; }
    if (c === '/' && RE_PREV.has(prevSig)) { inRe = true; reClass = false; continue; }
    if (c === '"' || c === "'" || c === '`') { inStr = true; q = c; prevSig = c; continue; }
    if (c === openCh) depth++;
    else if (c === closeCh) { depth--; if (depth === 0) return { open, close: i }; }
    if (!/\s/.test(c)) prevSig = c;               // track last significant char
  }
  throw new Error('unbalanced region from index ' + startIdx);
}

function liftArray(src, anchor) {
  const a = src.indexOf(anchor);
  if (a < 0) throw new Error('array anchor not found: ' + anchor);
  const { open, close } = liftFrom(src, a, '[', ']');
  return src.slice(open, close + 1); // the [...] literal
}

function liftFn(src, name, occ = 0) {
  const re = new RegExp('function\\s+' + name + '\\s*\\(', 'g');
  let m, k = 0, hit = null;
  while ((m = re.exec(src)) !== null) { if (k === occ) { hit = m; break; } k++; }
  if (!hit) throw new Error('function not found: ' + name + ' (occ ' + occ + ')');
  const { close } = liftFrom(src, hit.index, '{', '}');
  return src.slice(hit.index, close + 1);
}

// ───────────────── lift helpers + NEWS, run in a sandbox ─────────────────
const HELPERS = [
  'edCatClass', 'edDeriveStandfirst', 'edDeriveDisplayHeadline', 'edDeriveCardHeadline',
  'edDeriveByline', 'edDeriveWordCount', 'edDeriveReadTime', 'edRenderFhRow',
  'edFormatDate', 'edBuildEyebrow',
  'edFindRelated', 'edRenderShareBlock', 'edShareLegacyCopy', 'edRenderArticlePage',
];
// non-ed render dependencies discovered via callee analysis:
//   formatNewsSummary -> builds .ed-art-body ; dayDistance -> edFindRelated ;
//   esc (2nd def, the HTML-escaper in the render closure) -> edRenderShareBlock
const DEP_FNS = [
  { name: 'formatNewsSummary', occ: 0 },
  { name: 'dayDistance',       occ: 0 },
  { name: 'esc',               occ: 1 },
];

const sandbox = {
  console,
  LANDING_URL: '/',                       // root-absolute for static pages
  getBackLabel: () => '\u2190 PropertyAtlas',
  atlasArticleBack: () => false,          // referenced only inside onclick text
  window: { location: { href: '', search: '' }, scrollTo() {}, addEventListener() {}, innerWidth: 1200 },
  document: { addEventListener() {}, getElementById() { return null; } },
};
vm.createContext(sandbox);

// NEWS first (helpers like edFindRelated read it), then deps, then helpers.
vm.runInContext('var NEWS = ' + liftArray(html, 'var NEWS=[') + ';', sandbox, { filename: 'NEWS' });
for (const d of DEP_FNS) {
  vm.runInContext(liftFn(html, d.name, d.occ), sandbox, { filename: d.name });
}
for (const name of HELPERS) {
  vm.runInContext(liftFn(html, name), sandbox, { filename: name });
}

const NEWS = sandbox.NEWS;
const byId = new Map(NEWS.map(a => [a.id, a]));

// ───────────────── CSS extraction (article-scoped, L-SEO-8 clean) ─────────────────
// Pull every <style> block, walk rules brace-aware, keep :root + base resets +
// any rule whose selector references a class actually used in the article body.
function allStyleCss(src) {
  // strip HTML comments first — several comments in index.html literally
  // discuss "<style>", and a naive scan would capture comment prose + scripts.
  const clean = src.replace(/<!--[\s\S]*?-->/g, '');
  const out = [];
  const re = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  let m;
  while ((m = re.exec(clean)) !== null) out.push(m[1]);
  return out.join('\n');
}

// Split CSS into top-level rules / at-rules, brace-aware.
function splitRules(css) {
  const rules = [];
  let i = 0, n = css.length;
  while (i < n) {
    // skip whitespace + css comments
    while (i < n && /\s/.test(css[i])) i++;
    if (i + 1 < n && css[i] === '/' && css[i + 1] === '*') {
      const end = css.indexOf('*/', i + 2);
      i = end < 0 ? n : end + 2;
      continue;
    }
    if (i >= n) break;
    const selStart = i;
    // read selector / at-rule prelude up to '{' or ';' (bare at-statements)
    while (i < n && css[i] !== '{' && css[i] !== ';') i++;
    if (i < n && css[i] === ';') { // bare at-rule like @import/@charset — keep as-is
      rules.push({ prelude: css.slice(selStart, i + 1).trim(), body: null, bare: true });
      i++; continue;
    }
    if (i >= n) break;
    const prelude = css.slice(selStart, i).trim();
    // brace-match the body
    let depth = 0, bodyStart = i;
    for (; i < n; i++) {
      if (css[i] === '{') depth++;
      else if (css[i] === '}') { depth--; if (depth === 0) { i++; break; } }
    }
    const body = css.slice(bodyStart, i); // includes { }
    rules.push({ prelude, body, bare: false });
  }
  return rules;
}

const BASE_SELECTORS = /^(:root|\*|html|body|h1|h2|h3|h4|p|a|em|strong|img|figure|figcaption|blockquote|ul|ol|li|table|thead|tbody|tr|th|td)\b/;

function selectorWantsClass(prelude, usedClasses) {
  // any .class token in the selector that the body uses?
  const classes = prelude.match(/\.[A-Za-z0-9_-]+/g) || [];
  if (classes.length === 0) return BASE_SELECTORS.test(prelude); // element-only base rule
  return classes.some(c => usedClasses.has(c.slice(1)));
}

function extractArticleCss(usedClasses) {
  const css = allStyleCss(html);
  const rules = splitRules(css);
  const kept = [];
  for (const r of rules) {
    if (r.bare) continue;
    const p = r.prelude;
    if (/^:root\b/.test(p)) { kept.push(p + r.body); continue; }            // always keep vars
    if (/^@media/i.test(p)) {                                                // recurse into media
      const inner = splitRules(r.body.replace(/^\{/, '').replace(/\}$/, ''));
      const innerKept = inner.filter(ir => !ir.bare &&
        (/^:root\b/.test(ir.prelude) || selectorWantsClass(ir.prelude, usedClasses)))
        .map(ir => ir.prelude + ir.body);
      if (innerKept.length) kept.push(p + '{' + innerKept.join('') + '}');
      continue;
    }
    if (/^@/.test(p)) {                                                      // other at-rules (keyframes/font) — skip unless referenced; keep keyframes used by kept rules later if needed
      continue;
    }
    // ordinary selector list — keep if any comma-part wants a used class / is base
    const parts = p.split(',').map(s => s.trim());
    if (parts.some(part => selectorWantsClass(part, usedClasses))) {
      const keptParts = parts.filter(part => selectorWantsClass(part, usedClasses));
      kept.push(keptParts.join(',') + r.body);
    }
  }
  return kept.join('\n');
}

// ───────────────── link / path rewrites for static context ─────────────────
function rewriteLinks(fragment) {
  let f = fragment;
  // ?article=N (optionally with &-suffixed SPA nav params, single or double quotes)
  // -> canonical /news/<slug>/
  f = f.replace(/href=(["'])\?article=(\d+)(?:&[^"']*)?\1/g, (full, qt, id) => {
    const a = byId.get(Number(id));
    return a && a.slug ? 'href=' + qt + '/news/' + a.slug + '/' + qt : full;
  });
  // image paths -> root-absolute
  f = f.replace(/(src=")\.\/images\//g, '$1/images/');
  f = f.replace(/(src=")images\//g, '$1/images/');
  // strip any stray HTML comments (defensive — renderer emits none)
  f = f.replace(/<!--[\s\S]*?-->/g, '');
  return f;
}

// ───────────────── head builder (SEO/social) ─────────────────
function stripTags(s) { return String(s || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim(); }
function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

function heroAbs(a) {
  if (!a.image) return '';
  return SITE + '/' + a.image.replace(/^\.\//, '').replace(/^\//, '');
}

// Gap 2/3 (S97): the SERP/social image (og:image, twitter:image, JSON-LD image)
// falls back to a branded title card when an article has no usable hero photo.
// CARD_OVERRIDE lists ids whose hero photo is under ~696px wide and therefore
// cannot render as a search thumbnail — these are superseded by a card for
// social meta only; the in-article hero photo is left untouched.
// To restore a photo: drop the id here AND set a >=1200px-wide image in NEWS.
const CARD_OVERRIDE = new Set([78, 79, 84, 86, 91, 92, 93, 98, 99, 101, 106]);
function socialImage(a, img) {
  if (img && !CARD_OVERRIDE.has(a.id)) return img;
  const f = 'news_' + a.id + '_card.png';
  return fs.existsSync(path.join(IMAGES_DIR, f))
    ? SITE + '/images/' + f
    : SITE + '/images/og-default.png';
}

function buildHead(a, canonical) {
  const title = stripTags(a.display_headline || a.display_title || a.title);
  const desc  = stripTags(a.standfirst || a.summary).slice(0, 200);
  const img    = heroAbs(a);
  const social = socialImage(a, img);
  const ld = {
    '@context': 'https://schema.org', '@type': 'NewsArticle',
    headline: title, datePublished: a.date, dateModified: a.date,
    image: [social],
    author: { '@type': 'Organization', name: 'PropertyAtlas' },
    publisher: { '@type': 'Organization', name: 'PropertyAtlas',
      logo: { '@type': 'ImageObject', url: SITE + '/images/logo.png' } },
    mainEntityOfPage: { '@type': 'WebPage', '@id': canonical },
    description: desc,
  };
  return [
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<link rel="icon" href="/favicon.ico" sizes="any">',
    '<link rel="icon" type="image/svg+xml" href="/favicon.svg">',
    '<link rel="icon" type="image/png" sizes="96x96" href="/images/favicon-96x96.png">',
    '<link rel="icon" type="image/png" sizes="192x192" href="/images/favicon-192x192.png">',
    '<link rel="apple-touch-icon" href="/images/apple-touch-icon.png">',
    '<title>' + esc(title) + ' | PropertyAtlas</title>',
    '<meta name="description" content="' + esc(desc) + '">',
    '<link rel="canonical" href="' + esc(canonical) + '">',
    '<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">',
    '<meta property="og:type" content="article">',
    '<meta property="og:site_name" content="PropertyAtlas">',
    '<meta property="og:title" content="' + esc(title) + '">',
    '<meta property="og:description" content="' + esc(desc) + '">',
    '<meta property="og:url" content="' + esc(canonical) + '">',
    '<meta property="og:image" content="' + esc(social) + '">',
    '<meta name="twitter:card" content="summary_large_image">',
    '<meta name="twitter:title" content="' + esc(title) + '">',
    '<meta name="twitter:description" content="' + esc(desc) + '">',
    '<meta name="twitter:image" content="' + esc(social) + '">',
    '<script type="application/ld+json">' + JSON.stringify(ld) + '</script>',
  ].filter(Boolean).join('\n');
}

// ───────────────── assemble one page ─────────────────
function buildPage(a) {
  const canonical = SITE + '/news/' + a.slug + '/';
  let fragment = sandbox.edRenderArticlePage(a);
  fragment = rewriteLinks(fragment);
  // NAV-1 Phase 1: replace legacy ed-art-masthead with the navy global topbar.
  const mastRe = /<header class="ed-art-masthead">[\s\S]*?<\/header>/;
  const mastHits = (fragment.match(new RegExp(mastRe.source, 'g')) || []).length;
  if (mastHits !== 1) throw new Error('NAV-1: expected exactly 1 ed-art-masthead, found ' + mastHits + ' (id:' + a.id + ')');
  fragment = fragment.replace(mastRe, NAVY_TOPBAR_HTML);
  const usedClasses = new Set();
  (fragment.match(/class=["']([^"']*)["']/g) || []).forEach(m => {
    m.replace(/class=["']([^"']*)["']/, (x, cl) => cl.split(/\s+/).forEach(c => c && usedClasses.add(c)));
  });
  const css  = extractArticleCss(usedClasses);
  // SOP-required rule absent from the index's article CSS: grey, no-direction
  // deltas. The index ships only .up/.down; injecting .neutral keeps neutral
  // financial-headline deltas covered (L-SEO-8) and correctly coloured.
  const injected = '.ed-art-fh-delta.neutral{color:var(--ed-muted)}' + '\n' + NAVY_TOPBAR_CSS;
  const head = buildHead(a, canonical);
  return '<!DOCTYPE html>\n<html lang="en" data-ready>\n<head>\n' + head +
    '\n<style>\n' + css + '\n' + injected + '\n' + SUBSCRIBE_CSS + '\n</style>\n</head>\n<body>\n' + fragment + '\n' + SUBSCRIBE_BODY + '\n</body>\n</html>\n';
}

// ───────────────── per-page gates ─────────────────
function gatePage(a, htmlOut, filePath) {
  const errs = [];
  // 1. DOM-parse (L-SEO-11): body/h1/article reachable + share + related present
  try {
    const dom = new JSDOM(htmlOut);
    const d = dom.window.document;
    if (!d.body) errs.push('DOM: no <body>');
    if (!d.querySelector('h1')) errs.push('DOM: no <h1>');
    if (!d.querySelector('article')) errs.push('DOM: no <article>');
    if (!d.querySelector('.ed-art-share-block, .ed-art-share, [class*="share"]')) errs.push('DOM: share block missing');
    if (!d.querySelector('.ed-art-related')) errs.push('DOM: related rail missing');
  } catch (e) { errs.push('DOM parse threw: ' + e.message); }

  // 2. L-SEO-8 class coverage: every class used in <body> resolves to a rule
  const styleCss = (htmlOut.match(/<style>([\s\S]*?)<\/style>/) || [, ''])[1];
  const cssClasses = new Set((styleCss.match(/\.[A-Za-z0-9_-]+/g) || []).map(c => c.slice(1)));
  const bodyHtml = (htmlOut.match(/<body>([\s\S]*?)<\/body>/) || [, ''])[1];
  const bodyClasses = new Set();
  (bodyHtml.match(/class="([^"]*)"/g) || []).forEach(m =>
    m.replace(/class="([^"]*)"/, (x, cl) => cl.split(/\s+/).forEach(c => c && bodyClasses.add(c))));
  const uncovered = [...bodyClasses].filter(c => !cssClasses.has(c));
  if (uncovered.length) errs.push('L-SEO-8: uncovered classes: ' + uncovered.join(', '));

  // 4. link resolution: zero ?article=, every /news/<slug>/ resolves to a real NEWS slug
  if (/\?article=/.test(htmlOut)) errs.push('LINK: stray ?article= in output');
  const slugSet = new Set(NEWS.filter(x => x.slug).map(x => x.slug));
  (htmlOut.match(/\/news\/([a-z0-9-]+)\//g) || []).forEach(u => {
    const s = u.replace(/^\/news\//, '').replace(/\/$/, '');
    if (s !== a.slug && !slugSet.has(s)) errs.push('LINK: unresolved /news/' + s + '/');
  });

  // 3. L282 balance (shell out to the canonical checker)
  if (filePath) {
    try { execFileSync('node', [L282, filePath], { stdio: 'pipe' }); }
    catch (e) { errs.push('L282: ' + ((e.stdout && e.stdout.toString().trim()) || e.message)); }
  }
  return errs;
}

// ───────────────── Stage 2: build-time hero optimiser ─────────────────
// Re-encode over-budget heroes to progressive JPEG, metadata stripped.
// WARN-AND-PROCEED: image weight never fails the build (gate fails are
// reserved for page validity/crawlability). Missing/incompressible heroes
// print a loud, file-named warning and the build continues.
function heroLocalPath(a) {
  if (!a.image) return null;
  const rel = a.image.replace(/^\.?\//, '').replace(/^images\//, '');
  return path.join(IMAGES_DIR, rel);
}

async function optimizeHero(a) {
  if (flags.noImages || !a.image) return;
  const file = heroLocalPath(a);
  if (!file || !fs.existsSync(file)) {
    console.log(`  ! WARN id:${a.id} MISSING HERO: ${a.image} (page references an image not on disk)`);
    return;
  }
  const before = fs.statSync(file).size;
  if (before <= HERO_BUDGET) return;                 // under budget -> leave as-is
  if (!sharp) { console.log(`  ! WARN id:${a.id} hero ${(before/1024|0)}KB over budget but sharp unavailable`); return; }
  if (flags.dry) { console.log(`  · id:${a.id} would optimise ${(before/1024|0)}KB hero`); return; }
  try {
    let out, usedQ, meta = await sharp(file).metadata();
    const resize = meta.width && meta.width > HERO_MAXW ? { width: HERO_MAXW } : null;
    for (let q = 82; q >= 58; q -= 6) {               // step quality down until under budget
      let pipe = sharp(file).rotate();                 // rotate() bakes EXIF orientation, then strips
      if (resize) pipe = pipe.resize(resize);
      out = await pipe.jpeg({ quality: q, progressive: true, mozjpeg: true }).toBuffer();
      usedQ = q;
      if (out.length <= HERO_BUDGET) break;
    }
    fs.writeFileSync(file, out);
    const tag = out.length <= HERO_BUDGET ? '' : '  ! WARN still over budget (hand-optimise if it matters)';
    console.log(`  · id:${a.id} hero ${(before/1024|0)}KB -> ${(out.length/1024|0)}KB (q${usedQ}, progressive)${tag}`);
  } catch (e) {
    console.log(`  ! WARN id:${a.id} hero optimise failed: ${e.message} (kept original)`);
  }
}

// ───────────────── Stage 4: sitemap emission ─────────────────
// Emit/refresh the article <url> entries. Preserves any non-article URLs
// (homepage, tabs) already present in sitemap.xml; rewrites only /news/ ones.
function writeSitemap(articles) {
  const today = new Date().toISOString().slice(0, 10);
  const artUrls = articles.map(a =>
    `  <url><loc>${SITE}/news/${a.slug}/</loc><lastmod>${a.date || today}</lastmod>` +
    `<changefreq>monthly</changefreq><priority>0.7</priority></url>`).join('\n');
  let preserved = [];
  if (fs.existsSync(SITEMAP)) {
    const cur = fs.readFileSync(SITEMAP, 'utf8');
    preserved = (cur.match(/<url>[\s\S]*?<\/url>/g) || [])
      .filter(u => !/\/news\//.test(u));               // keep non-article URLs as-is
  } else {
    preserved = [`  <url><loc>${SITE}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>`];
  }
  const body = '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    preserved.map(u => u.trim().startsWith('<url>') ? '  ' + u.trim() : u).join('\n') +
    (preserved.length ? '\n' : '') + artUrls + '\n</urlset>\n';
  if (!flags.dry) fs.writeFileSync(SITEMAP, body);
  return artUrls.split('\n').length;
}


// ───────────────── run ─────────────────
const publicArticles = NEWS.filter(a => a.slug);

// Stage 3: pre-push coverage gate. Verifies the ON-DISK repo state:
// every public NEWS id has a valid news/<slug>/index.html that passes every
// page gate, and its slug round-trips through sitemap.xml. Regenerates nothing.
function runCheck() {
  let fail = 0;
  const sitemap = fs.existsSync(SITEMAP) ? fs.readFileSync(SITEMAP, 'utf8') : '';
  for (const a of publicArticles) {
    const p = path.join(OUTDIR, 'news', a.slug, 'index.html');
    const probs = [];
    if (!fs.existsSync(p)) {
      probs.push('MISSING static page (public NEWS id has no news/<slug>/index.html)');
    } else {
      const pageHtml = fs.readFileSync(p, 'utf8');
      probs.push(...gatePage(a, pageHtml, p));
      if (sitemap && sitemap.indexOf('/news/' + a.slug + '/') === -1)
        probs.push('slug not present in sitemap.xml');
    }
    if (probs.length) { fail++; console.log(`[FAIL] id:${a.id}  news/${a.slug}/`); probs.forEach(e => console.log('        - ' + e)); }
  }
  console.log(`\nPRE-PUSH GATE: ${publicArticles.length} public article(s), ${fail} failed.`);
  process.exit(fail ? 1 : 0);
}

async function runGenerate() {
  const targets = flags.only
    ? NEWS.filter(a => String(a.id) === String(flags.only))
    : publicArticles;
  let failures = 0;
  for (const a of targets) {
    const outPath = path.join(OUTDIR, 'news', a.slug, 'index.html');
    const page = buildPage(a);
    let writePath;
    if (!flags.dry) {
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      fs.writeFileSync(outPath, page);
      writePath = outPath;
    } else {
      writePath = path.join('/tmp', 'gen_' + a.id + '.html');   // L282 needs a file
      fs.writeFileSync(writePath, page);
    }
    const errs = gatePage(a, page, writePath);
    const tag = errs.length ? 'FAIL' : 'OK  ';
    console.log(`[${tag}] id:${a.id}  ${(page.length / 1024).toFixed(1)}KB  news/${a.slug}/`);
    if (errs.length) { failures++; errs.forEach(e => console.log('        - ' + e)); }
    await optimizeHero(a);                                       // Stage 2 (warn-and-proceed)
  }
  // Sitemap is a whole-site artifact: always written over the FULL public set,
  // never just `targets` — otherwise a single-article (--only) regen would
  // clobber every other article URL. (Caught by the Stage 3 gate in testing.)
  const n = writeSitemap(publicArticles);                       // Stage 4
  console.log(`\n${targets.length} page(s), ${failures} failed. Sitemap: ${n} article URL(s)${flags.dry ? ' (dry, not written)' : ''}.`);
  process.exit(failures ? 1 : 0);
}

(flags.check ? Promise.resolve(runCheck()) : runGenerate()).catch(e => {
  console.error('FATAL:', e.message); process.exit(2);
});
