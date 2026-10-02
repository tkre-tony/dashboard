/* pins_freshness_gate.js — S391. Fails when the baked Directory PINS fall behind the caveat feed.
 *
 * Why: PINS (root index.html) is a static bake of project_directory_mv. It went 3 months stale
 * (July bake, view itself stale since 4 Jun) while weekly ingests kept running, because nothing
 * checked it. Same failure class as L-SEED-1.
 *
 * Rule: lag = (latest sale_date among non-shophouse SEED_CAVEATS) - (latest ls among non-shophouse
 * PINS). FAIL if lag > MAX_LAG_DAYS (default 35, override with --max N). Shophouse pins are reported
 * separately as INFO (carried from the July bake until a shophouse rule is adopted).
 * Also asserts every pin has lat/lng/n/t and no duplicate (n,t).
 *
 * Usage: node tools/pins_freshness_gate.js index.html [--max 35]
 */
const fs=require('fs');
const f=process.argv[2]; if(!f){console.error('usage: node tools/pins_freshness_gate.js index.html [--max N]');process.exit(2);}
const mi=process.argv.indexOf('--max'); const MAX=mi>0?parseInt(process.argv[mi+1],10):35;
const s=fs.readFileSync(f,'utf8');
function arr(name){
  const m=new RegExp('(?:const |var |let )?'+name+'\\s*=\\s*\\[').exec(s); if(!m) throw new Error(name+' not found');
  const lb=s.indexOf('[',m.index); let d=0,j=lb,str=false,q='',e=false;
  for(;j<s.length;j++){const c=s[j]; if(str){ if(e)e=false; else if(c==='\\')e=true; else if(c===q)str=false; continue;}
    if(c==='"'||c==="'"){str=true;q=c;continue;} if(c==='[')d++; else if(c===']'){d--; if(!d)break;}}
  return JSON.parse(s.slice(lb,j+1));
}
const PINS=arr('PINS'), SEED=arr('SEED_CAVEATS');
let fail=0; const out=[];
const day=x=>new Date(x+'T00:00:00Z');
const ns=PINS.filter(p=>p.t!=='Shophouse'), sh=PINS.filter(p=>p.t==='Shophouse');
const pinMax=ns.reduce((a,p)=>p.ls>a?p.ls:a,'');
const seedMax=SEED.filter(c=>c.property_type!=='Shop House').reduce((a,c)=>c.sale_date>a?c.sale_date:a,'');
const lag=Math.round((day(seedMax)-day(pinMax))/864e5);
out.push(`PINS ${PINS.length} (non-shophouse ${ns.length}, shophouse ${sh.length}) · latest non-shophouse ls ${pinMax} · latest seed sale ${seedMax} · lag ${lag}d (max ${MAX})`);
if(lag>MAX){fail++; out.push(`FAIL: PINS are ${lag} days behind the caveat feed — refresh project_directory_mv and re-bake PINS.`);}
const bad=PINS.filter(p=>typeof p.lat!=='number'||typeof p.lng!=='number'||!p.n||!p.t);
if(bad.length){fail++; out.push(`FAIL: ${bad.length} pin(s) missing lat/lng/n/t`);}
const seen=new Map(); let dup=0; ns.forEach(p=>{const k=p.n+'|'+p.t; if(seen.has(k))dup++; seen.set(k,1);});
if(dup){fail++; out.push(`FAIL: ${dup} duplicate (name,type) among non-shophouse pins`);}
const shMax=sh.reduce((a,p)=>p.ls>a?p.ls:a,'');
out.push(`INFO: shophouse pins latest ls ${shMax||'—'} (carried; not gated until a shophouse rule is adopted)`);
console.log(out.join('\n'));
console.log(fail?`\n${fail} failure(s).`:'\nCLEAN: Directory PINS are current with the caveat feed.');
process.exit(fail?1:0);
