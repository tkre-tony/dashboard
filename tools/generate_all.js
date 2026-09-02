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
// ─── PROMO-1 (S208): article-page promo slots ──────────────────────────────
// Spec: ATLAS_PROMO-1_article_promo_slots_spec_v1.md
// Values only — never markup or CSS in this object. `treatment` is an enum
// resolved to a CSS class, not a style string. One place to edit copy/links.
const PROMO_SLOTS = {
  leaderboard: {
    id: 'leaderboard-map',
    active: true,
    label: 'From PropertyAtlas',
    kicker: 'PropertyAtlas Map',
    headline: 'New caveats every Tuesday and Friday, the week they are released.',
    subline: 'Singapore commercial, industrial and landed transactions \u2014 mapped, filterable, free to search.',
    cta: 'Open the map',
    href: '/',
    creative: 'cadence_tue_fri',
  },
  rail: [
    { id: 'rail-map', kind: 'mpu', tier: 1, active: true,
      eyebrow: 'Transaction Map',
      headline: 'Every caveat, on one map.',
      body: 'Commercial, industrial and landed transactions across Singapore \u2014 with profit-and-loss pairing on resales.',
      stats: [{ n: '82K+', l: 'C&amp;I caveats' }, { n: '80K+', l: 'Landed' }],
      cta: 'Explore the map', href: '/', creative: 'rail_map_default' },
    { id: 'rail-pulse', kind: 'compact', tier: 2, active: true,
      icon: 'pulse',
      headline: 'Market Pulse',
      body: 'What moved this week \u2014 latest caveats, prices and volumes as they land.',
      cta: 'Open Market Pulse', href: '/?lens=pulse', creative: 'rail_pulse_default' },
    { id: 'rail-analysis', kind: 'compact', tier: 3, active: true,
      icon: 'bars',
      headline: 'Market Analysis',
      body: 'Price and PSF trends by segment, district and property type, over time.',
      cta: 'Open Market Analysis', href: '/?lens=analysis', creative: 'rail_analysis_default' },
    { id: 'rail-directory', kind: 'native', tier: 4, active: true,
      eyebrow: 'Asset Directory',
      headline: 'S-REIT and developer portfolios, asset by asset.',
      body: '1,700+ assets across 60+ listed entities \u2014 occupancy, lease expiry and valuation in one place.',
      cta: 'Open directory', href: '/newsroom/#asset-directory', creative: 'rail_directory_default' },
    { id: 'rail-sponsor', kind: 'tkre', tier: 5, active: true,
      label: 'From TK Real Estate',
      eyebrow: 'TK Real Estate',
      photo: '/images/tony_koe_headshot.jpg',
      name: 'Tony Koe',
      role: 'Founder \u00b7 Key Executive Officer',
      // headline renders RAW (not esc'd) so the <em> highlight survives.
      headline: 'Buying, selling or leasing <em>commercial &amp; industrial</em> space?',
      body: 'Bespoke advisory from 25 years in Singapore real estate \u2014 built on the same transaction data you are reading.',
      bullets: ['Acquisition &amp; disposal mandates', 'Landlord &amp; tenant representation'],
      wa: 'https://wa.me/6597971118?text=Hi%20Tony%2C%20I%20read%20PropertyAtlas%20and%20would%20like%20to%20discuss%20a%20commercial%20or%20industrial%20requirement.',
      email: 'mailto:tony@tkre.sg?subject=Commercial%20%2F%20industrial%20enquiry%20via%20PropertyAtlas',
      li: 'https://www.linkedin.com/in/tonykoe/',
      footLine1: 'TK Real Estate Pte Ltd',
      footLine2: 'Estate Agent Licence L3011027G \u00b7 CEA Reg R003757I',
      creative: 'tkre_bespoke_v1' },
  ],
};

const PROMO_ICONS = {
  pulse: '<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="2 13 7 13 10 5 14 19 17 13 22 13"/></svg>',
  bars:  '<svg viewBox="0 0 24 24" aria-hidden="true"><line x1="4" y1="20" x2="4" y2="12"/><line x1="10" y1="20" x2="10" y2="4"/><line x1="16" y1="20" x2="16" y2="9"/><line x1="22" y1="20" x2="22" y2="15"/></svg>',
  tick:  '<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>',
  whatsapp: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.25-.46-2.38-1.47-.88-.78-1.47-1.75-1.65-2.05-.17-.3-.02-.46.13-.6.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.6-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.47s1.06 2.86 1.21 3.06c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.72 2-1.41.25-.69.25-1.28.17-1.41-.07-.12-.27-.2-.57-.35zM12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.87 9.87 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2z"/></svg>',
  mail:  '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="rgba(255,255,255,.86)" stroke-width="2"><rect x="2.5" y="4.5" width="19" height="15" rx="2"/><polyline points="3 6.5 12 13 21 6.5"/></svg>',
  linkedin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1-.02 5 2.5 2.5 0 0 1 .02-5zM3 9h4v12H3V9zm7 0h3.8v1.7h.05c.53-.95 1.83-1.95 3.77-1.95 4.03 0 4.78 2.5 4.78 5.76V21h-4v-5.6c0-1.34-.03-3.06-1.9-3.06-1.9 0-2.2 1.46-2.2 2.96V21h-4V9z"/></svg>',
};

const PROMO_CSS = [
// leaderboard band + unit (IAB 728x90 class; fluid to 1080, 90 tall)
'.pa-adzone{background:var(--ed-cream-lt,#F7F3E9);padding:20px 28px;border-bottom:1px solid var(--ed-hairline,#E4DCC8)}',
'.pa-adzone-in{max-width:1080px;margin:0 auto}',
'.pa-ad-label{font-family:"DM Sans",Arial,sans-serif;font-size:8.5px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--ed-muted,#6B6157);opacity:.55;margin:0 0 6px 2px}',
'.pa-ad-unit{position:relative;display:flex;align-items:center;gap:20px;min-height:90px;padding:14px 20px 14px 22px;border-radius:4px;font-family:"DM Sans",Arial,sans-serif;border:1px solid #0F3775;background:linear-gradient(100deg,#0F3775 0%,#1A4F9C 62%,#2C6BC4 100%);box-shadow:0 1px 3px rgba(11,43,92,.07),0 6px 18px rgba(11,43,92,.06);transition:.15s;overflow:hidden}',
'.pa-ad-unit:hover{box-shadow:0 2px 6px rgba(11,43,92,.10),0 10px 26px rgba(11,43,92,.10);transform:translateY(-1px)}',
'.pa-ad-kick{flex:0 0 auto;font-size:9.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;padding:4px 9px;border-radius:2px;white-space:nowrap;color:var(--ed-bronze-lt,#C9A264);border:1px solid rgba(201,162,100,.5);background:rgba(0,0,0,.14)}',
'.pa-ad-copy{flex:1 1 auto;min-width:0;font-size:16px;line-height:1.28;color:#fff;position:relative;z-index:2;pointer-events:none}',
'.pa-ad-copy b{font-weight:700;display:block}',
'.pa-ad-copy .pa-ad-sub{display:block;font-size:12.5px;margin-top:4px;font-weight:400;color:rgba(255,255,255,.72)}',
'.pa-ad-cta{position:relative;z-index:2;flex:0 0 auto;text-decoration:none;font-size:12.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;padding:12px 22px;border-radius:3px;white-space:nowrap;background:var(--ed-bronze,#A67C3A);color:#fff;box-shadow:0 1px 0 rgba(0,0,0,.2)}',
'.pa-ad-unit:hover .pa-ad-cta{background:var(--ed-bronze-lt,#C9A264)}',
'.pa-ad-stretch::after{content:"";position:absolute;inset:0;z-index:1}',
'.pa-ad-x{position:absolute;top:6px;right:8px;z-index:3;background:none;border:0;cursor:pointer;font-size:15px;line-height:1;padding:2px 4px;color:rgba(255,255,255,.45)}',
'.pa-ad-x:hover{color:#fff}',
'@media (max-width:860px){.pa-adzone{padding:14px}.pa-ad-unit{flex-wrap:wrap;gap:10px;padding:14px 16px;min-height:0}.pa-ad-kick{display:none}.pa-ad-copy{flex:1 1 100%;font-size:14.5px}.pa-ad-copy .pa-ad-sub{font-size:11.5px}.pa-ad-cta{flex:1 1 100%;text-align:center;padding:11px 14px;font-size:11.5px}}',
// sticky nav + banner (D8/D9/D10)
'.pa-tb{position:sticky;top:0;z-index:200;transition:box-shadow .18s ease}',
'body.pa-scrolled .pa-tb{box-shadow:0 2px 10px rgba(11,43,92,.20),0 1px 0 rgba(0,0,0,.10)}',
'.pa-adzone{position:sticky;top:44px;z-index:190}',
'body.pa-scrolled .pa-adzone{box-shadow:0 2px 10px rgba(11,43,92,.14)}',
'body.pa-scrolled .pa-adzone{padding-top:8px;padding-bottom:8px}',
'body.pa-scrolled .pa-ad-label{height:0;margin:0;opacity:0;overflow:hidden}',
'body.pa-scrolled .pa-ad-unit{min-height:0;padding-top:9px;padding-bottom:9px;box-shadow:0 1px 3px rgba(11,43,92,.10)}',
'body.pa-scrolled .pa-ad-copy{font-size:13.5px}',
'body.pa-scrolled .pa-ad-copy .pa-ad-sub{height:0;margin:0;opacity:0;overflow:hidden}',
'body.pa-scrolled .pa-ad-cta{padding:8px 16px;font-size:11.5px}',
'.pa-adzone,.pa-ad-unit,.pa-ad-label,.pa-ad-copy,.pa-ad-copy .pa-ad-sub,.pa-ad-cta{transition:padding .18s ease,height .18s ease,opacity .16s ease,margin .18s ease,font-size .18s ease}',
'@media (prefers-reduced-motion:reduce){.pa-adzone,.pa-ad-unit,.pa-ad-label,.pa-ad-copy,.pa-ad-copy .pa-ad-sub,.pa-ad-cta,.pa-tb{transition:none}}',
'@media (max-width:760px){.pa-adzone{position:static}}',
// two-column shell + rail
'.pa-shell{max-width:1104px;margin:0 auto;display:grid;grid-template-columns:minmax(0,720px) 300px;gap:36px;align-items:start;justify-content:center}',
'.pa-shell > .ed-art-content{max-width:720px;margin:0;padding-left:0;padding-right:0}',
'.pa-rail{padding-top:56px;font-family:"DM Sans",Arial,sans-serif;display:flex;flex-direction:column;gap:20px}',
'.pa-rail-label{font-size:9px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--ed-muted,#6B6157);opacity:.7;margin-bottom:7px}',
'.pa-slot{border:1px solid rgba(26,79,156,.20);border-radius:6px;overflow:hidden;position:relative;text-decoration:none;color:inherit;display:block;transition:.15s;background:var(--ed-cream,#FCF9F0)}',
'.pa-slot:hover{box-shadow:0 2px 6px rgba(11,43,92,.10),0 10px 26px rgba(11,43,92,.08)}',
'.pa-slot::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px}',
// graded shades (D6) — tier 4 darkened to #EAF1FB per O4 resolution
'.pa-slot-t1{background:linear-gradient(160deg,#0B2B5C 0%,#14418A 100%);border-color:#0B2B5C}',
'.pa-slot-t1::before{background:var(--ed-bronze,#A67C3A)}',
'.pa-slot-t2{background:#E4EDF9}.pa-slot-t2::before{background:#1A4F9C}',
'.pa-slot-t3{background:#EDF3FB}.pa-slot-t3::before{background:#3B82D4}',
'.pa-slot-t4{background:#EAF1FB}.pa-slot-t4::before{background:#6C9BD6}',
'.pa-slot-t1 .pa-slot-eyebrow{color:var(--ed-bronze-lt,#C9A264)}',
'.pa-slot-t1 .pa-slot-h{color:#fff}',
'.pa-slot-t1 .pa-slot-p{color:rgba(255,255,255,.78)}',
'.pa-slot-t1 .pa-slot-stats{border-top-color:rgba(255,255,255,.24)}',
'.pa-slot-t1 .pa-slot-stat b{color:#fff}',
'.pa-slot-t1 .pa-slot-stat span{color:rgba(255,255,255,.78)}',
// slot internals
'.pa-slot-mpu{min-height:250px;padding:22px 20px 20px;display:flex;flex-direction:column}',
// rail-sponsor 300x600 : TK Real Estate commercial promo (added S352)
'.pa-slot-tk{position:relative;width:300px;min-height:600px;box-sizing:border-box;border:1px solid #0A0A0C;border-radius:6px;overflow:hidden;background:linear-gradient(168deg,#14161C 0%,#0C0E13 58%,#080A0E 100%);display:flex;flex-direction:column;padding:24px 20px 18px;font-family:"DM Sans",Arial,sans-serif}',
'.pa-slot-tk::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--ed-bronze,#A67C3A)}',
'.pa-slot-tk::after{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(120% 62% at 50% -6%,rgba(201,162,100,.16) 0%,rgba(201,162,100,0) 62%)}',
'.pa-slot-tk > *{position:relative;z-index:1}',
'.tk-eyebrow{font-size:9.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--ed-bronze-lt,#C9A264);text-align:center}',
'.tk-rule{width:34px;height:2px;background:var(--ed-bronze,#A67C3A);margin:11px auto 0;border-radius:2px}',
'.tk-photo{width:104px;height:104px;border-radius:50%;margin:20px auto 0;overflow:hidden;border:2px solid rgba(201,162,100,.55);box-shadow:0 0 0 5px rgba(201,162,100,.09),0 8px 22px rgba(0,0,0,.45);background:#fff}',
'.tk-photo img{width:100%;height:100%;object-fit:cover;object-position:50% 18%;display:block}',
'.tk-name{margin:14px 0 0;text-align:center;font-size:17px;font-weight:700;color:#fff;letter-spacing:-.01em}',
'.tk-role{margin:3px 0 0;text-align:center;font-size:10.5px;font-weight:500;letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.52)}',
'.tk-h{margin:20px 0 0;font-size:18px;line-height:1.32;font-weight:700;color:#fff;text-align:center;letter-spacing:-.015em}',
'.tk-h em{font-style:normal;color:var(--ed-bronze-lt,#C9A264)}',
'.tk-p{margin:11px 0 0;font-size:12.5px;line-height:1.55;color:rgba(255,255,255,.66);text-align:center}',
'.tk-list{margin:17px 0 0;padding:13px 0;list-style:none;border-top:1px solid rgba(255,255,255,.11);border-bottom:1px solid rgba(255,255,255,.11)}',
'.tk-list li{display:flex;gap:9px;align-items:flex-start;font-size:11.5px;line-height:1.45;color:rgba(255,255,255,.76);padding:3.5px 0}',
'.tk-list svg{flex:0 0 auto;width:12px;height:12px;margin-top:2px;stroke:var(--ed-bronze-lt,#C9A264);fill:none;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}',
'.tk-cta{margin-top:auto;padding-top:16px;display:flex;flex-direction:column;gap:8px}',
'.tk-cta-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}',
'.tk-cta-row .tk-btn{font-size:11px;letter-spacing:.04em;padding:10px 6px;gap:6px}',
'.tk-cta-row .tk-btn svg{width:13px;height:13px}',
'.tk-btn{display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;font-size:12px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:11px 12px;border-radius:4px;transition:.15s}',
'.tk-btn svg{width:14px;height:14px;flex:0 0 auto}',
'.tk-wa{background:var(--ed-bronze,#A67C3A);color:#fff;border:1px solid var(--ed-bronze,#A67C3A)}',
'.tk-wa:hover{background:#B98C46;border-color:#B98C46}',
'.tk-wa svg{fill:#fff}',
'.tk-em{background:transparent;color:rgba(255,255,255,.86);border:1px solid rgba(255,255,255,.26)}',
'.tk-em:hover{background:rgba(255,255,255,.07);border-color:rgba(255,255,255,.42)}',
'.tk-li svg{fill:rgba(255,255,255,.86);stroke:none}',
'.tk-foot{margin-top:13px;text-align:center;font-size:8.5px;line-height:1.6;letter-spacing:.04em;color:rgba(255,255,255,.36)}',
'.pa-slot-eyebrow{font-size:9.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--ed-navy,#0B2B5C);margin-bottom:10px}',
'.pa-slot-h{font-family:Georgia,"Times New Roman",serif;font-size:19px;line-height:1.22;font-weight:700;color:var(--ed-navy-ink,#12233f);margin:0 0 10px}',
'.pa-slot-p{font-size:12.5px;line-height:1.5;color:var(--ed-muted,#6B6157);margin:0 0 14px}',
'.pa-slot-stats{display:flex;gap:14px;margin:0 0 16px;padding-top:12px;border-top:1px solid rgba(26,79,156,.18)}',
'.pa-slot-stat b{display:block;font-family:Georgia,"Times New Roman",serif;font-size:17px;color:var(--ed-navy,#0B2B5C);line-height:1}',
'.pa-slot-stat span{display:block;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--ed-muted,#6B6157);margin-top:4px}',
'.pa-slot-btn{margin-top:auto;display:block;text-align:center;background:var(--ed-bronze,#A67C3A);color:#fff;font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:10px 14px;border-radius:3px}',
'.pa-slot-compact{padding:16px 18px 16px 20px;display:flex;gap:13px;align-items:flex-start}',
'.pa-slot-ico{flex:0 0 auto;width:34px;height:34px;border-radius:5px;background:var(--ed-navy,#0B2B5C);display:flex;align-items:center;justify-content:center;margin-top:2px}',
'.pa-slot-ico svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}',
'.pa-slot-compact .pa-slot-h{font-size:15px;margin:0 0 5px}',
'.pa-slot-compact .pa-slot-p{font-size:12px;margin:0 0 8px;line-height:1.45}',
'.pa-slot-native{padding:18px 20px}',
'.pa-slot-native .pa-slot-h{font-size:15px;margin-bottom:8px}',
'.pa-slot-native .pa-slot-p{margin-bottom:10px;font-size:12px}',
'.pa-slot-link{font-size:11.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--ed-navy,#0B2B5C)}',
'.pa-slot-hp{min-height:600px;display:flex;align-items:center;justify-content:center;background:repeating-linear-gradient(135deg,#FCF9F0 0 12px,#F7F3E9 12px 24px);border-style:dashed}',
'.pa-slot-hp::before{background:rgba(26,79,156,.25)}',
'.pa-slot-hp-in{text-align:center;padding:24px}',
'.pa-slot-hp-in b{display:block;font-family:Georgia,"Times New Roman",serif;font-size:15px;color:var(--ed-navy-ink,#12233f);margin-bottom:6px}',
'.pa-slot-hp-in span{font-size:11px;color:var(--ed-muted,#6B6157);line-height:1.5}',
// rail collapses; mobile/tablet layout unchanged from pre-PROMO-1
'@media (max-width:1103px){.pa-shell{display:block;max-width:none}.pa-shell > .ed-art-content{max-width:720px;margin:0 auto;padding-left:28px;padding-right:28px}.pa-rail{display:none}}',
].join('\n');

// GA4 — L-PROMO-1: static article pages carried NO analytics before S208.
const GA4_ID = 'G-Z2Z6HM2P8M';
const GA4_SNIPPET =
  '<script async src="https://www.googletagmanager.com/gtag/js?id=' + GA4_ID + '"></script>' +
  '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}' +
  'gtag("js",new Date());gtag("config","' + GA4_ID + '");</script>';

function promoLeaderboardHtml() {
  const p = PROMO_SLOTS.leaderboard;
  if (!p || !p.active) return '';
  return '<div class="pa-adzone" id="pa-adzone"><div class="pa-adzone-in">' +
    (p.label ? '<div class="pa-ad-label">' + esc(p.label) + '</div>' : '') +
    '<div class="pa-ad-unit" data-promo="' + esc(p.id) + '" data-creative="' + esc(p.creative || '') + '">' +
    (p.kicker ? '<span class="pa-ad-kick">' + esc(p.kicker) + '</span>' : '') +
    '<span class="pa-ad-copy"><b>' + esc(p.headline) + '</b>' +
    (p.subline ? '<span class="pa-ad-sub">' + esc(p.subline) + '</span>' : '') + '</span>' +
    '<a class="pa-ad-cta pa-ad-stretch" href="' + esc(p.href) + '" target="_blank" rel="noopener">' + esc(p.cta) + '</a>' +
    '<button class="pa-ad-x" type="button" aria-label="Dismiss this message" ' +
    'onclick="document.getElementById(\'pa-adzone\').style.display=\'none\'">&times;</button>' +
    '</div></div></div>';
}

function promoRailHtml() {
  const units = (PROMO_SLOTS.rail || []).filter(u => u.active);
  if (!units.length) return '';
  const out = ['<aside class="pa-rail">'];
  units.forEach((u, i) => {
    const tier = ' pa-slot-t' + (u.tier || 1);
    const attrs = ' data-promo="' + esc(u.id) + '" data-creative="' + esc(u.creative || '') + '"';
    if (i === 0) out.push('<div class="pa-rail-label">From PropertyAtlas</div>');
    if (i === 1) out.push('<div class="pa-rail-label">Also on PropertyAtlas</div>');
    if (u.kind === 'mpu') {
      out.push('<a class="pa-slot pa-slot-mpu' + tier + '" href="' + esc(u.href) + '" target="_blank" rel="noopener"' + attrs + '>' +
        '<div class="pa-slot-eyebrow">' + esc(u.eyebrow) + '</div>' +
        '<h3 class="pa-slot-h">' + esc(u.headline) + '</h3>' +
        '<p class="pa-slot-p">' + u.body + '</p>' +
        '<div class="pa-slot-stats">' + (u.stats || []).map(st =>
          '<div class="pa-slot-stat"><b>' + st.n + '</b><span>' + st.l + '</span></div>').join('') + '</div>' +
        '<span class="pa-slot-btn">' + esc(u.cta) + '</span></a>');
    } else if (u.kind === 'compact') {
      out.push('<a class="pa-slot pa-slot-compact' + tier + '" href="' + esc(u.href) + '" target="_blank" rel="noopener"' + attrs + '>' +
        '<span class="pa-slot-ico">' + (PROMO_ICONS[u.icon] || '') + '</span><span>' +
        '<h3 class="pa-slot-h">' + esc(u.headline) + '</h3>' +
        '<p class="pa-slot-p">' + u.body + '</p>' +
        '<span class="pa-slot-link">' + esc(u.cta) + ' &rarr;</span></span></a>');
    } else if (u.kind === 'native') {
      out.push('<a class="pa-slot pa-slot-native' + tier + '" href="' + esc(u.href) + '" target="_blank" rel="noopener"' + attrs + '>' +
        '<div class="pa-slot-eyebrow">' + esc(u.eyebrow) + '</div>' +
        '<h3 class="pa-slot-h">' + esc(u.headline) + '</h3>' +
        '<p class="pa-slot-p">' + u.body + '</p>' +
        '<span class="pa-slot-link">' + esc(u.cta) + ' &rarr;</span></a>');
    } else if (u.kind === 'reserved') {
      out.push('<div><div class="pa-rail-label">' + esc(u.label) + '</div>' +
        '<div class="pa-slot pa-slot-hp"><div class="pa-slot-hp-in"><b>300 &times; 600</b>' +
        '<span>Half-page slot.</span></div></div></div>');
    } else if (u.kind === 'tkre') {
      // rail-sponsor 300x600. Commercial promo for TK Real Estate Pte Ltd.
      // NOT an <a>: it carries three CTAs, each independently tracked. The
      // container keeps data-promo so view_promotion still fires once.
      out.push('<div><div class="pa-rail-label">' + esc(u.label) + '</div>' +
        '<div class="pa-slot-tk"' + attrs + '>' +
        '<div class="tk-eyebrow">' + esc(u.eyebrow) + '</div>' +
        '<div class="tk-rule"></div>' +
        '<div class="tk-photo"><img src="' + esc(u.photo) + '" alt="' + esc(u.name) +
          ', Founder and Key Executive Officer, TK Real Estate Pte Ltd" ' +
          'width="104" height="104" loading="lazy" decoding="async"></div>' +
        '<h3 class="tk-name">' + esc(u.name) + '</h3>' +
        '<div class="tk-role">' + esc(u.role) + '</div>' +
        '<h4 class="tk-h">' + u.headline + '</h4>' +
        '<p class="tk-p">' + u.body + '</p>' +
        '<ul class="tk-list">' + (u.bullets || []).map(function (b) {
          return '<li>' + PROMO_ICONS.tick + '<span>' + b + '</span></li>'; }).join('') + '</ul>' +
        '<div class="tk-cta">' +
          '<a class="tk-btn tk-wa" href="' + esc(u.wa) + '" target="_blank" rel="noopener" ' +
            'data-promo="' + esc(u.id) + '-whatsapp" data-creative="' + esc(u.creative) + '">' +
            PROMO_ICONS.whatsapp + 'WhatsApp Tony</a>' +
          '<div class="tk-cta-row">' +
            '<a class="tk-btn tk-em" href="' + esc(u.email) + '" ' +
              'data-promo="' + esc(u.id) + '-email" data-creative="' + esc(u.creative) + '">' +
              PROMO_ICONS.mail + 'Email</a>' +
            '<a class="tk-btn tk-em tk-li" href="' + esc(u.li) + '" target="_blank" rel="noopener" ' +
              'data-promo="' + esc(u.id) + '-linkedin" data-creative="' + esc(u.creative) + '">' +
              PROMO_ICONS.linkedin + 'LinkedIn</a>' +
          '</div>' +
        '</div>' +
        '<div class="tk-foot">' + esc(u.footLine1) + '<br>' + esc(u.footLine2) + '</div>' +
        '</div></div>');
    }
  });
  out.push('</aside>');
  return out.join('');
}

// Promotion tracking (GA4 view_promotion / select_promotion). No UTMs on
// internal links (ATLAS_UTM_tagging_convention.md). Degrades silently.
const PROMO_JS =
'<script>(function(){' +
'var u=document.querySelectorAll("[data-promo]");if(!u.length)return;' +
'function t(e,el){if(typeof window.gtag!=="function")return;' +
'var s=el.getAttribute("data-promo");window.gtag("event",e,{promotion_id:s,' +
'promotion_name:"propertyatlas_house_promo",creative_name:el.getAttribute("data-creative")||s,' +
'creative_slot:s,location_id:"article_page"});}' +
'if("IntersectionObserver" in window){var seen={};var io=new IntersectionObserver(function(es){' +
'es.forEach(function(en){var s=en.target.getAttribute("data-promo");' +
'if(en.isIntersecting&&!seen[s]){seen[s]=1;t("view_promotion",en.target);}});},{threshold:.5});' +
'Array.prototype.forEach.call(u,function(x){io.observe(x);});}' +
'Array.prototype.forEach.call(u,function(x){x.addEventListener("click",function(){t("select_promotion",x);});});' +
'var k=false;window.addEventListener("scroll",function(){if(k)return;k=true;' +
'window.requestAnimationFrame(function(){document.body.classList.toggle("pa-scrolled",window.scrollY>8);k=false;});},' +
'{passive:true});})();</script>';

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
  // L-SEO: edRenderShareBlock() branches on window.location.hostname. The stub
  // previously had no hostname, so the apex test failed at build time and every
  // static page baked the pre-flip github.io origin into all seven share targets.
  // Static pages are only ever served from the apex — pin it.
  window: { location: { href: 'https://propertyatlas.sg/', search: '', hostname: 'propertyatlas.sg', origin: 'https://propertyatlas.sg', protocol: 'https:' }, scrollTo() {}, addEventListener() {}, innerWidth: 1200 },
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
const CARD_OVERRIDE = new Set([78, 79, 84, 86, 91, 92, 93, 98, 99, 101, 106, 137]);
function socialImage(a, img) {
  if (img && !CARD_OVERRIDE.has(a.id)) return img;
  const f = 'news_' + a.id + '_card.png';
  return fs.existsSync(path.join(IMAGES_DIR, f))
    ? SITE + '/images/' + f
    : SITE + '/images/og-default.png';
}

function buildHead(a, canonical) {
  const title = stripTags(a.display_headline || a.display_title || a.title);
  // v48.336 (S262): word-boundary-aware meta description.
  // Previously .slice(0, 200) cut mid-word with no ellipsis, which forced
  // standfirsts to be authored under 200 chars to avoid a broken SERP snippet.
  // Mirrors the proven deriveStandfirst() pattern (v48.75, S20). Feeds
  // meta description, og:description, twitter:description and JSON-LD.
  const rawDesc = stripTags(a.standfirst || a.summary);
  const desc  = rawDesc.length <= 200
    ? rawDesc
    : rawDesc.slice(0, 197).replace(/\s+\S*$/, '') + '\u2026';
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
    GA4_SNIPPET,
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
  fragment = fragment.replace(mastRe, NAVY_TOPBAR_HTML + promoLeaderboardHtml());
  // PROMO-1: wrap the article column + rail in the two-column shell.
  const artOpen = '<article class="ed-art-content">';
  const artHits = fragment.split(artOpen).length - 1;
  const closeHits = fragment.split('</article>').length - 1;
  if (artHits !== 1 || closeHits !== 1) throw new Error('PROMO-1: expected exactly 1 ed-art-content article, found ' + artHits + '/' + closeHits + ' (id:' + a.id + ')');
  fragment = fragment.replace(artOpen, '<div class="pa-shell">' + artOpen);
  fragment = fragment.replace('</article>', '</article>' + promoRailHtml() + '</div>');
  const usedClasses = new Set();
  (fragment.match(/class=["']([^"']*)["']/g) || []).forEach(m => {
    m.replace(/class=["']([^"']*)["']/, (x, cl) => cl.split(/\s+/).forEach(c => c && usedClasses.add(c)));
  });
  const css  = extractArticleCss(usedClasses);
  // SOP-required rule absent from the index's article CSS: grey, no-direction
  // deltas. The index ships only .up/.down; injecting .neutral keeps neutral
  // financial-headline deltas covered (L-SEO-8) and correctly coloured.
  const injected = '.ed-art-fh-delta.neutral{color:var(--ed-muted)}' + '\n' + NAVY_TOPBAR_CSS + '\n' + PROMO_CSS;
  const head = buildHead(a, canonical);
  return '<!DOCTYPE html>\n<html lang="en" data-ready>\n<head>\n' + head +
    '\n<style>\n' + css + '\n' + injected + '\n' + SUBSCRIBE_CSS + '\n</style>\n</head>\n<body>\n' + fragment + '\n' + SUBSCRIBE_BODY + '\n' + PROMO_JS + '\n</body>\n</html>\n';
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
