/* pins_parity_check.js — S393. Field-by-field parity between two Directory pin sources.
 *
 * Each source may be:
 *   - a .json file: raw rows [lat,lng,n_raw,t,d,p,v,rg,ar,tn,di,ls,st,tt,pc] as an array, or {pins:[...]}
 *     (get_directory_pins() output / assets/directory_pins_fallback.json)
 *   - a .csv Supabase export of: SELECT x::text FROM json_array_elements(public.get_directory_pins()) x
 *   - an .html file carrying a legacy inline `const PINS = [{...}]` bake (objects, already title-cased)
 * Raw rows are title-cased with the same Python-title port the page uses.
 * Pairs on type|name (+ street for shophouses). Coordinates match within --tol degrees (default 0.0000101).
 * Exit 1 if any business field differs or any pin is unpaired.
 *
 * Usage: node tools/pins_parity_check.js <candidate> <baseline> [--tol 0.0000101] [--show 20]
 */
const fs=require('fs');
const [A,B]=process.argv.slice(2); if(!A||!B){console.error('usage: node tools/pins_parity_check.js <candidate> <baseline> [--tol N] [--show N]');process.exit(2);}
const arg=(k,d)=>{const i=process.argv.indexOf(k);return i>0?process.argv[i+1]:d;};
const TOL=parseFloat(arg('--tol','0.0000101')), SHOW=parseInt(arg('--show','20'),10);
const K=['lat','lng','n','t','d','p','v','rg','ar','tn','di','ls','st','tt'];
const title=x=>String(x==null?'':x).toLowerCase().replace(/\p{L}+/gu,w=>w.charAt(0).toUpperCase()+w.slice(1));
const fromRow=r=>({lat:r[0],lng:r[1],n:title(r[2]),t:r[3],d:r[4]||0,p:r[5]||0,v:r[6]||0,rg:r[7]||'',ar:r[8]||'',tn:r[9]||'',di:r[10]||0,ls:r[11]||'',st:r[12]||'',tt:r[13]||0});
function load(f){
  const s=fs.readFileSync(f,'utf8');
  if(/\.html?$/i.test(f)){
    const m=/const\s+PINS\s*=\s*\[/.exec(s); if(!m) throw new Error(f+': no inline PINS');
    const lb=s.indexOf('[',m.index); let d=0,j=lb,str=false,q='',e=false;
    for(;j<s.length;j++){const c=s[j]; if(str){ if(e)e=false; else if(c==='\\')e=true; else if(c===q)str=false; continue;}
      if(c==='"'||c==="'"){str=true;q=c;continue;} if(c==='[')d++; else if(c===']'){d--; if(!d)break;}}
    return JSON.parse(s.slice(lb,j+1)).map(o=>({...o,d:o.d||0,p:o.p||0,v:o.v||0,di:o.di||0,tt:o.tt||0}));
  }
  if(/\.csv$/i.test(f)){
    const rows=[]; let i=s.indexOf('\n')+1;
    while(i<s.length){ if(s[i]==='\r'||s[i]==='\n'){i++;continue;}
      if(s[i]==='"'){let j=i+1,o='';for(;;j++){if(s[j]==='"'){if(s[j+1]==='"'){o+='"';j++;}else break;}else o+=s[j];} rows.push(o); i=j+1;}
      else {let j=s.indexOf('\n',i); if(j<0)j=s.length; rows.push(s.slice(i,j).replace(/\r$/,'')); i=j+1;} }
    return rows.map(r=>fromRow(JSON.parse(r)));
  }
  const j=JSON.parse(s); return (Array.isArray(j)?j:j.pins).map(fromRow);
}
const C=load(A), L=load(B);
const key=o=>o.t+'|'+o.n+'|'+(o.t==='Shophouse'?o.st:'');
const LM=new Map(); L.forEach(o=>{const k=key(o); if(!LM.has(k))LM.set(k,[]); LM.get(k).push(o);});
let exact=0,coordOnly=0,biz=0,unpairedC=0; const fd={}, ex=[];
C.forEach(o=>{
  const arr=LM.get(key(o)); if(!arr||!arr.length){unpairedC++; if(ex.length<SHOW)ex.push('ONLY IN CANDIDATE: '+key(o)); return;}
  // pick the closest by coordinates when keys repeat
  let bi=0,bd=1e9; arr.forEach((p,i)=>{const dd=Math.abs(p.lat-o.lat)+Math.abs(p.lng-o.lng); if(dd<bd){bd=dd;bi=i;}});
  const p=arr.splice(bi,1)[0];
  const diffs=K.filter(k=>k==='lat'||k==='lng'?Math.abs((p[k]||0)-(o[k]||0))>TOL:JSON.stringify(p[k])!==JSON.stringify(o[k]));
  const coordDiff=K.slice(0,2).some(k=>p[k]!==o[k]);
  if(!diffs.length){ if(coordDiff)coordOnly++; else exact++; return; }
  biz++; diffs.forEach(k=>fd[k]=(fd[k]||0)+1);
  if(ex.length<SHOW) ex.push(key(o)+' :: '+diffs.map(k=>k+' '+JSON.stringify(p[k])+' -> '+JSON.stringify(o[k])).join('; '));
});
let unpairedB=0; LM.forEach(a=>{unpairedB+=a.length; a.forEach(o=>{ if(ex.length<SHOW) ex.push('ONLY IN BASELINE: '+key(o)); });});
console.log(`candidate ${C.length} · baseline ${L.length}`);
console.log(`exact ${exact} · coordinates within ${TOL} deg only ${coordOnly} · field differences ${biz} · only in candidate ${unpairedC} · only in baseline ${unpairedB}`);
if(Object.keys(fd).length) console.log('fields:',JSON.stringify(fd));
ex.forEach(x=>console.log('  '+x));
const ok=!biz&&!unpairedC&&!unpairedB;
console.log(ok?'\nPARITY: PASS':'\nPARITY: FAIL'); process.exit(ok?0:1);
