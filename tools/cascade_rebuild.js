/* cascade_rebuild.js — regenerate the landing hero + 3 cards + 7 feed rows + NR_STATIC_IDS
 * from the NEWS array (single source of truth). CRLF output, literal Unicode for text,
 * &middot;/&#8594; kept for decorative chars (matches existing). alt DERIVED from
 * landing_credit so alt/credit can never drift. Replaces three regions only; leaves the
 * cards head comment + feed tail breadcrumb intact. Bumps version.
 *
 * Fields consumed per id: slug, image, landing_headline, display_teaser, landing_credit,
 * category, tag (hero only), date, word_count (hero only), read_time_min.
 */
const fs=require("fs");
const FILE=process.argv[2]||"work_index.html";
const VER_OLD="48.242", VER_NEW="48.243";
const CR="\r\n";
let s=fs.readFileSync(FILE,"utf8");

// ---- parse NEWS ----
const head=s.indexOf("var NEWS="); const lb=s.indexOf("[",head);
let d=0,j=lb,st=false,q="",e=false;
for(;j<s.length;j++){const c=s[j];
  if(st){ if(e){e=false;} else if(c==="\\"){e=true;} else if(c===q){st=false;} continue; }
  if(c==='"'||c==="'"){st=true;q=c;continue;}
  if(c==="[")d++; else if(c==="]"){d--; if(d===0)break;}
}
const NEWS=eval(s.slice(lb,j+1));
const byId=Object.fromEntries(NEWS.map(x=>[x.id,x]));

// ---- helpers ----
const escText=t=>String(t).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const escAttr=t=>escText(t).replace(/"/g,"&quot;");
const altFrom=c=>String(c).split(". Credit:")[0].trim();
const MON=["January","February","March","April","May","June","July","August","September","October","November","December"];
const MONA=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const dFull=iso=>{const[y,m,dd]=iso.split("-").map(Number);return dd+" "+MON[m-1]+" "+y;};
const dAbbr=iso=>{const[y,m,dd]=iso.split("-").map(Number);return dd+" "+MONA[m-1]+" "+y;};

function need(x){for(const f of["slug","image","landing_headline","display_teaser","landing_credit","category","tag","date","read_time_min","word_count"]){if(!(f in x)||x[f]===""||x[f]==null)throw new Error("id "+x.id+" missing "+f);}}

// ---- order: top 11 by id desc ----
const ids=NEWS.map(x=>x.id).sort((a,b)=>b-a).slice(0,11);
// assert contiguity (cascade gate expects [N..N-10])
for(let k=1;k<ids.length;k++) if(ids[k]!==ids[0]-k) throw new Error("ids not contiguous: "+ids.join(","));
ids.forEach(id=>need(byId[id]));
console.log("Landing order:", ids.join(","));

// ---- block builders ----
function hero(x){
  const alt=altFrom(x.landing_credit);
  return [
`<section class="hero" aria-labelledby="hero-h">`,
`  <div class="wrap hero-grid">`,
``,
`    <!-- Image \u2014 id:${x.id} ${x.category} hero. v${VER_NEW} cascade. -->`,
`    <div class="hero-image-col">`,
`      <a class="hero-image" href="/news/${x.slug}/" data-article-id="${x.id}" aria-label="Read full story: ${escAttr(alt)}">`,
`        <img src="${escAttr(x.image)}" alt="${escAttr(alt)}" class="hero-image-photo" loading="eager" fetchpriority="high" />`,
`      </a>`,
`      <p class="hero-credit">${escText(x.landing_credit)}</p>`,
`    </div>`,
`    <div class="hero-text">`,
`      <div class="hero-eyebrow">`,
`        <span class="pill">Latest</span>`,
`        <span class="cat-tag">${escText(x.category)}</span>`,
`        <span class="cat-tag">${escText(x.tag)}</span>`,
`      </div>`,
`      <h1 id="hero-h" class="hero-headline">`,
`        <a href="/news/${x.slug}/" data-article-id="${x.id}">${escText(x.landing_headline)}</a>`,
`      </h1>`,
`    </div>`,
`    <div class="hero-body">`,
`      <p class="hero-teaser">${escText(x.display_teaser)}</p>`,
`      <div class="hero-meta">`,
`        <span>${dFull(x.date)}</span>`,
`        <span class="sep">&middot;</span>`,
`        <span>${x.word_count} words</span>`,
`        <span class="sep">&middot;</span>`,
`        <span>${x.read_time_min} min read</span>`,
`      </div>`,
`      <a class="btn-primary" href="/news/${x.slug}/" data-article-id="${x.id}">`,
`        Read full story`,
`        <span class="arrow" aria-hidden="true">&#8594;</span>`,
`      </a>`,
`    </div>`,
`  </div>`,
`</section>`
  ].join(CR);
}
function card(x){
  const alt=altFrom(x.landing_credit);
  return [
`<a class="card" href="/news/${x.slug}/" data-article-id="${x.id}">`,
`        <div class="card-image">`,
`          <img src="${escAttr(x.image)}"`,
`               alt="${escAttr(alt)}"`,
`               class="card-image-photo"`,
`               loading="lazy" />`,
`        </div>`,
`        <p class="card-credit">${escText(x.landing_credit)}</p>`,
`        <p class="card-cat">${escText(x.category)}</p>`,
`        <h3 class="card-headline">${escText(x.landing_headline)}</h3>`,
`        <p class="card-teaser">${escText(x.display_teaser)}</p>`,
`        <p class="card-meta">`,
`          <span>${dAbbr(x.date)}</span>`,
`          <span class="sep">&middot;</span>`,
`          <span>${x.read_time_min} min read</span>`,
`        </p>`,
`      </a>`
  ].join(CR);
}
function feedRow(x){
  const alt=altFrom(x.landing_credit);
  return [
`<a class="feed-row" href="/news/${x.slug}/" data-article-id="${x.id}">`,
`        <div class="feed-row-image-col">`,
`          <div class="feed-row-image">`,
`            <img src="${escAttr(x.image)}" alt="${escAttr(alt)}" class="feed-row-image-photo" loading="lazy" />`,
`          </div>`,
`          <p class="feed-row-credit">${escText(x.landing_credit)}</p>`,
`        </div>`,
`        <div class="feed-row-text">`,
`          <p class="feed-row-cat">${escText(x.category)}</p>`,
`          <h3 class="feed-row-headline">${escText(x.landing_headline)}</h3>`,
`          <p class="feed-row-teaser">${escText(x.display_teaser)}</p>`,
`          <p class="feed-row-meta"><span>${dAbbr(x.date)}</span><span class="sep">&middot;</span><span>${x.read_time_min} min read</span></p>`,
`        </div>`,
`      </a>`
  ].join(CR);
}

// ---- region replacement helpers ----
function matchDivClose(str, openIdx){
  let depth=0; const re=/<\/?div\b/g; re.lastIndex=openIdx; let m;
  while((m=re.exec(str))){ if(m[0]==="<div")depth++; else {depth--; if(depth===0) return str.indexOf("</div>",m.index)+6;} }
  throw new Error("unbalanced div from "+openIdx);
}
function replaceSpan(str,a,b,txt){ return str.slice(0,a)+txt+str.slice(b); }

// 1) HERO
{
  const a=s.indexOf('<section class="hero" aria-labelledby="hero-h">');
  if(a<0) throw new Error("hero anchor not found");
  const b=s.indexOf('</section>',a)+'</section>'.length;
  s=replaceSpan(s,a,b,hero(byId[ids[0]]));
}
// 2) CARDS anchor-run (leave head comment + closing div intact)
{
  const cs=s.indexOf('<div class="cards">');
  const ce=matchDivClose(s,cs);
  const region=s.slice(cs,ce);
  const firstA=cs+region.indexOf('<a class="card"');
  const lastClose=cs+region.lastIndexOf('</a>')+4;
  const cardsTxt=[card(byId[ids[1]]),card(byId[ids[2]]),card(byId[ids[3]])].join(CR+"      ");
  s=replaceSpan(s,firstA,lastClose,cardsTxt);
}
// 3) FEED anchor-run (leave feed-month head + tail breadcrumb intact)
{
  const fsx=s.indexOf('<div class="feed-list">');
  const fe=matchDivClose(s,fsx);
  const region=s.slice(fsx,fe);
  const firstA=fsx+region.indexOf('<a class="feed-row"');
  const lastClose=fsx+region.lastIndexOf('</a>')+4;
  const feedTxt=ids.slice(4,11).map(id=>feedRow(byId[id])).join(CR+"      ");
  s=replaceSpan(s,firstA,lastClose,feedTxt);
}
// 4) NR_STATIC_IDS = ids[1..10]
{
  const re=/var NR_STATIC_IDS = \[[0-9, ]*\];/;
  if(!re.test(s)) throw new Error("NR_STATIC_IDS not found");
  s=s.replace(re, "var NR_STATIC_IDS = ["+ids.slice(1,11).join(", ")+"];");
}
// 5) version bump (line-2 canonical header)
{
  const re=new RegExp("<!-- v"+VER_OLD.replace(".","\\.")+" \\([^>]*?-->");
  if(re.test(s)){
    s=s.replace(re, `<!-- v${VER_NEW} (26 Jun 2026, S134): landing cascade regenerated from NEWS (hero+cards+feed teaser/alt/tag/meta drift fixed); display_teaser+landing_credit+landing_headline backfilled. -->`);
  } else { throw new Error("version header v"+VER_OLD+" not found"); }
}

fs.writeFileSync(FILE,s);
console.log("Cascade regenerated; version -> v"+VER_NEW);
