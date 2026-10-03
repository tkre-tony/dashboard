/* pins_freshness_gate.js — S391; shophouse gating S392; REWRITTEN S393 for runtime PINS.
 *
 * Since v9.9.17 the map Directory reads public.get_directory_pins() at runtime (stored cache
 * public.directory_pins_mv), so there is no inline PINS bake to go stale. This gate now guards
 * the new arrangement:
 *   FAIL  an inline baked PINS array reappears in root index.html (the retired bug class)
 *   FAIL  the runtime loader is missing (get_directory_pins RPC, fallback URL, loadPins() call)
 *   FAIL  the fallback file is missing or malformed: every row 15 fields, numeric lat/lng inside
 *         Singapore, non-empty name and type, known type, no duplicate (type,name) among
 *         non-shophouse pins and no duplicate (name,street) among shophouse pins
 *   WARN  the fallback's newest non-shophouse sale is more than --max days (default 35) behind the
 *         newest non-shophouse sale in SEED_CAVEATS. The fallback is only served if the live read
 *         fails, so staleness is a warning: refresh it at the monthly rhythm.
 *
 * Usage: node tools/pins_freshness_gate.js index.html [--max 35] [--fallback assets/directory_pins_fallback.json]
 */
const fs=require('fs'), path=require('path');
const f=process.argv[2]; if(!f){console.error('usage: node tools/pins_freshness_gate.js index.html [--max N] [--fallback path]');process.exit(2);}
const arg=(k,d)=>{const i=process.argv.indexOf(k);return i>0?process.argv[i+1]:d;};
const MAX=parseInt(arg('--max','35'),10);
const FB=arg('--fallback',path.join(path.dirname(f),'assets','directory_pins_fallback.json'));
const s=fs.readFileSync(f,'utf8');
let fail=0; const out=[];
const FAIL=m=>{fail++;out.push('FAIL: '+m);};

if(/const\s+PINS\s*=\s*\[\s*\{/.test(s)) FAIL('inline baked PINS array found in '+f+' — Directory must read get_directory_pins() at runtime (v9.9.17).');
['/rpc/get_directory_pins','PINS_FALLBACK_URL','\nloadPins();','function pinsTitle('].forEach(m=>{ if(!s.includes(m)) FAIL('runtime loader marker missing: '+JSON.stringify(m.trim())); });

function arr(name){
  const m=new RegExp('(?:const |var |let )'+name+'\\s*=\\s*\\[').exec(s); if(!m) return null;
  const lb=s.indexOf('[',m.index); let d=0,j=lb,str=false,q='',e=false;
  for(;j<s.length;j++){const c=s[j]; if(str){ if(e)e=false; else if(c==='\\')e=true; else if(c===q)str=false; continue;}
    if(c==='"'||c==="'"){str=true;q=c;continue;} if(c==='[')d++; else if(c===']'){d--; if(!d)break;}}
  return JSON.parse(s.slice(lb,j+1));
}
const title=x=>String(x==null?'':x).toLowerCase().replace(/\p{L}+/gu,w=>w.charAt(0).toUpperCase()+w.slice(1));
const TYPES=new Set(['Office','Retail','Shophouse','Multi-User Factory','Single-User Factory','Business Park','Warehouse']);

let rows=null;
if(!fs.existsSync(FB)) FAIL('fallback file not found: '+FB);
else { try{ const j=JSON.parse(fs.readFileSync(FB,'utf8')); rows=Array.isArray(j)?j:j.pins; if(!Array.isArray(rows)||!rows.length) throw new Error('no pins array'); }
       catch(e){ FAIL('fallback file unreadable: '+e.message); rows=null; } }
if(rows){
  let bad=0,badType=0; const seenN=new Map(), seenS=new Map(); let dupN=0,dupS=0;
  rows.forEach(r=>{
    if(!Array.isArray(r)||r.length!==15||typeof r[0]!=='number'||typeof r[1]!=='number'||r[0]<1.1||r[0]>1.5||r[1]<103.5||r[1]>104.1||!r[2]||!r[3]){bad++;return;}
    if(!TYPES.has(r[3])) badType++;
    if(r[3]==='Shophouse'){const k=title(r[2])+'|'+r[12]; if(seenS.has(k))dupS++; seenS.set(k,1);}
    else {const k=r[3]+'|'+title(r[2]); if(seenN.has(k))dupN++; seenN.set(k,1);}
  });
  const ns=rows.filter(r=>r[3]!=='Shophouse'), sh=rows.filter(r=>r[3]==='Shophouse');
  const fbMax=ns.reduce((a,r)=>r[11]>a?r[11]:a,''), shMax=sh.reduce((a,r)=>r[11]>a?r[11]:a,'');
  out.push(`FALLBACK ${rows.length} pins (non-shophouse ${ns.length}, shophouse ${sh.length}) · newest sale non-shophouse ${fbMax} · shophouse ${shMax} · ${path.relative(process.cwd(),FB)||FB}`);
  if(bad) FAIL(bad+' fallback row(s) malformed (15 fields, numeric lat/lng inside Singapore, name, type)');
  if(badType) FAIL(badType+' fallback row(s) with an unknown type');
  if(dupN) FAIL(dupN+' duplicate (type,name) among non-shophouse fallback pins');
  if(dupS) FAIL(dupS+' duplicate (name,street) among shophouse fallback pins');
  const SEED=arr('SEED_CAVEATS');
  if(SEED){
    const seedMax=SEED.filter(c=>c.property_type!=='Shop House').reduce((a,c)=>c.sale_date>a?c.sale_date:a,'');
    const lag=Math.round((new Date(seedMax+'T00:00:00Z')-new Date(fbMax+'T00:00:00Z'))/864e5);
    out.push(`Seed newest non-shophouse sale ${seedMax} · fallback lag ${lag}d (warn above ${MAX})`);
    if(lag>MAX) out.push(`WARN: fallback is ${lag} days behind the caveat feed — re-export get_directory_pins() into ${path.basename(FB)} (live map unaffected).`);
  }
}
console.log(out.join('\n'));
console.log(fail?`\n${fail} FAIL(s).`:'\nCLEAN: Directory reads PINS at runtime; fallback present and well-formed.');
process.exit(fail?1:0);
