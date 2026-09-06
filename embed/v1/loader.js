/* PropertyAtlas white-label embed loader — v1
 *
 * Usage on a partner page:
 *
 *   <div id="pa-asset-directory"></div>
 *   <script src="https://propertyatlas.sg/embed/v1/loader.js"
 *           data-pa-key="pk_your_key_here"
 *           data-pa-module="asset_directory"
 *           data-pa-target="#pa-asset-directory"></script>
 *
 * Design notes
 * ------------
 * The loader runs on the PARTNER's page, not inside an iframe. That is
 * deliberate: the browser sets the Origin header from the executing document,
 * so wl-config validates the real embedding origin. An iframe served from
 * propertyatlas.sg would send propertyatlas.sg as its origin and the origin
 * allowlist would check nothing useful.
 *
 * Rendering happens inside a shadow root, so partner CSS cannot reach in and
 * this stylesheet cannot leak out. Attribution lives inside that shadow root.
 *
 * Data is read directly from anon PostgREST — the same endpoint and the same
 * public key the propertyatlas.sg site uses. wl-config returns configuration
 * only and never proxies rows.
 */
(function () {
  "use strict";

  var SB_URL = "https://xywgocvjuygudzrduvwr.supabase.co";
  var SB_ANON =
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh5d2dvY3ZqdXlndWR6cmR1dndyIiwicm9sZSI6" +
    "ImFub24iLCJpYXQiOjE3NzI5MTE5OTgsImV4cCI6MjA4ODQ4Nzk5OH0." +
    "lGQ0utJV1E00ug-Sf0ZXh9lEYfhGHSONQpPkBblDLTM";

  var CONFIG_ENDPOINT = SB_URL + "/functions/v1/wl-config";
  var HOME = "https://propertyatlas.sg";
  var PAGE_SIZE = 24;
  var FETCH_CAP = 2000;

  /* reit_assets.val is stored in MILLIONS and the table has no currency
   * column. The public site resolves currency from the entity name; this map
   * is a copy of REIT_CCY in newsroom/index.html and must be kept in step
   * with it. Anything absent falls back to S$. */
  var REIT_CCY = {
    "Acrophyte Hospitality Trust": "US$",
    "Manulife US REIT": "US$",
    "Prime US REIT": "US$",
    "United Hampshire US REIT": "US$",
    "Digital Core REIT": "US$",
    "KORE US REIT": "US$",
    "Sasseur REIT": "RMB",
    "EC World REIT": "RMB",
    "Elite UK REIT": "\u00a3",
    "IREIT Global": "\u20ac",
    "Stoneweg Europe Stapled Trust": "\u20ac",
    "Daiwa House Logistics Trust": "\u00a5",
    "Landmark REIT": "Rp"
  };

  var FIELDS = [
    "name", "addr", "type", "entity", "entity_type", "entity_short",
    "tenure", "nla_sqm", "occ", "val", "ar_year", "region", "area",
    "country", "city", "district"
  ].join(",");

  /* ------------------------------------------------------------ utilities */

  function esc(v) {
    if (v === null || v === undefined) return "";
    return String(v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function num(v) {
    return (v === null || v === undefined || v === "") ? null : Number(v);
  }

  function fmtVal(row) {
    var v = num(row.val);
    if (v === null || isNaN(v)) return "\u2014";
    var ccy = REIT_CCY[row.entity] || "S$";
    return ccy + v.toLocaleString() + "M";
  }

  function fmtNla(row) {
    var v = num(row.nla_sqm);
    if (v === null || isNaN(v)) return "\u2014";
    return Math.round(v).toLocaleString() + " sqm";
  }

  function fmtOcc(row) {
    var v = num(row.occ);
    if (v === null || isNaN(v)) return "\u2014";
    return (Math.round(v * 10) / 10) + "%";
  }

  function isHex(s) {
    return typeof s === "string" && /^#[0-9a-fA-F]{6}$/.test(s);
  }

  /* Only accept an https logo URL. A partner-supplied string goes into an
   * <img src>, so anything else is dropped rather than sanitised. */
  function safeLogo(u) {
    if (typeof u !== "string" || !u) return null;
    try {
      var p = new URL(u, HOME);
      return p.protocol === "https:" ? p.href : null;
    } catch (e) { return null; }
  }

  function toArray(v) {
    if (v === null || v === undefined) return [];
    return Object.prototype.toString.call(v) === "[object Array]" ? v : [v];
  }

  /* ------------------------------------------------------------ bootstrap */

  var self = document.currentScript;
  if (!self) {
    var all = document.getElementsByTagName("script");
    for (var i = all.length - 1; i >= 0; i--) {
      if (all[i].getAttribute("data-pa-key")) { self = all[i]; break; }
    }
  }
  if (!self) return;

  var partnerKey = (self.getAttribute("data-pa-key") || "").trim();
  var moduleName = (self.getAttribute("data-pa-module") || "asset_directory").trim();
  var targetSel = (self.getAttribute("data-pa-target") || "").trim();

  var host = null;
  if (targetSel) {
    try { host = document.querySelector(targetSel); } catch (e) { host = null; }
  }
  if (!host) {
    host = document.createElement("div");
    self.parentNode.insertBefore(host, self.nextSibling);
  }

  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  /* --------------------------------------------------------------- notice */

  function notice(title, detail) {
    root.innerHTML =
      '<div style="font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;' +
      'padding:22px;border:1px solid #e4e0d6;border-radius:10px;' +
      'background:#faf8f3;color:#4a4a4a">' +
      '<div style="font-weight:700;margin-bottom:5px;color:#1a1a1a">' +
      esc(title) + "</div>" +
      '<div style="font-size:13px">' + esc(detail) + "</div></div>";
  }

  if (!partnerKey) {
    notice("PropertyAtlas embed not configured",
      "The script tag is missing its data-pa-key attribute.");
    return;
  }

  /* ---------------------------------------------------------------- state */

  var THEME = null;
  var MODCFG = {};
  var ROWS = [];
  var VIEW = [];
  var page = 0;
  var query = "";

  /* --------------------------------------------------------------- styles */

  function styleBlock(t) {
    var font = (typeof t.font_stack === "string" && t.font_stack.trim())
      ? t.font_stack
      : "'DM Sans',system-ui,-apple-system,'Segoe UI',sans-serif";
    return "" +
      ":host{all:initial;display:block}" +
      "*{box-sizing:border-box;margin:0;padding:0}" +
      ".pa{font-family:" + font + ";color:" + t.ink + ";background:" + t.surface +
      ";padding:20px;border-radius:12px;border:1px solid rgba(0,0,0,.08)}" +
      ".pa-top{display:flex;align-items:center;justify-content:space-between;" +
      "gap:14px;flex-wrap:wrap;margin-bottom:14px}" +
      ".pa-brand{display:flex;align-items:center;gap:10px;min-height:26px}" +
      ".pa-brand img{height:26px;width:auto;display:block}" +
      ".pa-title{font-size:15px;font-weight:700;letter-spacing:-.01em}" +
      ".pa-count{font-size:12px;color:" + t.primary + ";font-weight:600}" +
      ".pa-search{width:100%;max-width:340px;padding:9px 12px;font:inherit;" +
      "font-size:13px;border:1px solid rgba(0,0,0,.16);border-radius:8px;" +
      "background:#fff;color:inherit}" +
      ".pa-search:focus{outline:2px solid " + t.accent + ";outline-offset:1px}" +
      ".pa-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(248px,1fr))}" +
      ".pa-card{background:#fff;border:1px solid rgba(0,0,0,.09);border-radius:10px;" +
      "padding:14px;border-top:3px solid " + t.primary + "}" +
      ".pa-nm{font-size:14px;font-weight:700;line-height:1.3;margin-bottom:3px}" +
      ".pa-ad{font-size:12px;opacity:.72;line-height:1.4;margin-bottom:9px}" +
      ".pa-ent{display:inline-block;font-size:10.5px;font-weight:700;" +
      "letter-spacing:.04em;text-transform:uppercase;color:" + t.accent +
      ";margin-bottom:8px}" +
      ".pa-rows{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:12px}" +
      ".pa-k{opacity:.6}" +
      ".pa-v{text-align:right;font-weight:600;font-variant-numeric:tabular-nums}" +
      ".pa-pg{display:flex;align-items:center;justify-content:center;gap:8px;" +
      "margin-top:16px;font-size:12.5px}" +
      ".pa-pg button{font:inherit;font-size:12.5px;font-weight:600;padding:6px 13px;" +
      "border:1px solid rgba(0,0,0,.16);border-radius:7px;background:#fff;" +
      "color:inherit;cursor:pointer}" +
      ".pa-pg button:disabled{opacity:.4;cursor:default}" +
      ".pa-empty{padding:34px 12px;text-align:center;font-size:13px;opacity:.65}" +
      ".pa-att{margin-top:16px;padding-top:12px;border-top:1px solid rgba(0,0,0,.1);" +
      "font-size:11.5px;opacity:.75;text-align:right}" +
      ".pa-att a{color:" + t.primary + ";font-weight:600;text-decoration:none}" +
      ".pa-att a:hover{text-decoration:underline}";
  }

  /* ---------------------------------------------------------------- fetch */

  function getConfig() {
    return fetch(CONFIG_ENDPOINT + "?key=" + encodeURIComponent(partnerKey), {
      method: "GET",
      headers: { "Accept": "application/json" }
    }).then(function (r) {
      return r.json().then(function (j) { return { status: r.status, body: j }; });
    });
  }

  function buildFilter(cfg) {
    var qs = [];
    var ents = toArray(cfg.entities);
    var shorts = toArray(cfg.entity_short);
    if (ents.length) {
      qs.push("entity=in.(" + ents.map(function (e) {
        return '"' + String(e).replace(/"/g, '""') + '"';
      }).join(",") + ")");
    }
    if (shorts.length) {
      qs.push("entity_short=in.(" + shorts.map(function (e) {
        return '"' + String(e).replace(/"/g, '""') + '"';
      }).join(",") + ")");
    }
    if (typeof cfg.country === "string" && cfg.country) {
      qs.push("country=eq." + encodeURIComponent(cfg.country));
    }
    if (typeof cfg.entity_type === "string" && cfg.entity_type) {
      qs.push("entity_type=eq." + encodeURIComponent(cfg.entity_type));
    }
    if (typeof cfg.type === "string" && cfg.type) {
      qs.push("type=eq." + encodeURIComponent(cfg.type));
    }
    return qs;
  }

  function getRows(cfg) {
    var lim = Math.min(Number(cfg.limit) || FETCH_CAP, FETCH_CAP);
    var q = ["select=" + FIELDS, "order=id.asc", "limit=" + lim]
      .concat(buildFilter(cfg)).join("&");
    return fetch(SB_URL + "/rest/v1/reit_assets?" + q, {
      headers: { apikey: SB_ANON, Authorization: "Bearer " + SB_ANON }
    }).then(function (r) {
      if (!r.ok) throw new Error("reit_assets HTTP " + r.status);
      return r.json();
    });
  }

  /* --------------------------------------------------------------- render */

  function applyQuery() {
    var q = query.trim().toLowerCase();
    VIEW = !q ? ROWS.slice() : ROWS.filter(function (r) {
      return (
        (r.name && String(r.name).toLowerCase().indexOf(q) !== -1) ||
        (r.addr && String(r.addr).toLowerCase().indexOf(q) !== -1) ||
        (r.entity && String(r.entity).toLowerCase().indexOf(q) !== -1) ||
        (r.entity_short && String(r.entity_short).toLowerCase().indexOf(q) !== -1)
      );
    });
    page = 0;
  }

  function cardHtml(r) {
    var bits = [
      ["Type", esc(r.type || "\u2014")],
      ["NLA", esc(fmtNla(r))],
      ["Occupancy", esc(fmtOcc(r))],
      ["Valuation", esc(fmtVal(r))]
    ];
    if (r.tenure) bits.push(["Tenure", esc(r.tenure)]);
    if (r.ar_year) bits.push(["Reported", esc(r.ar_year)]);

    var rows = bits.map(function (b) {
      return '<div class="pa-k">' + b[0] + '</div><div class="pa-v">' + b[1] + "</div>";
    }).join("");

    var where = [r.district ? "D" + esc(r.district) : "", esc(r.city || r.country || "")]
      .filter(Boolean).join(" \u00b7 ");

    return '<div class="pa-card">' +
      (r.entity_short ? '<div class="pa-ent">' + esc(r.entity_short) + "</div>" : "") +
      '<div class="pa-nm">' + esc(r.name || "Unnamed asset") + "</div>" +
      '<div class="pa-ad">' + esc(r.addr || "") +
      (where ? '<br>' + where : "") + "</div>" +
      '<div class="pa-rows">' + rows + "</div></div>";
  }

  function paint() {
    var t = THEME;
    var total = VIEW.length;
    var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (page >= pages) page = pages - 1;
    var slice = VIEW.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

    var logo = safeLogo(t.logo_url);
    var heading = (typeof MODCFG.title === "string" && MODCFG.title)
      ? MODCFG.title : "Asset Directory";

    var grid = slice.length
      ? '<div class="pa-grid">' + slice.map(cardHtml).join("") + "</div>"
      : '<div class="pa-empty">No assets match that search.</div>';

    var pager = total > PAGE_SIZE
      ? '<div class="pa-pg"><button data-pa-prev' + (page === 0 ? " disabled" : "") +
        ">Previous</button><span>Page " + (page + 1) + " of " + pages +
        '</span><button data-pa-next' + (page >= pages - 1 ? " disabled" : "") +
        ">Next</button></div>"
      : "";

    /* attribution_mode is enforced here, not negotiated. Anything other than
     * an explicit "none" from wl-config renders the credit. */
    var att = (t.attribution_mode === "none") ? "" :
      '<div class="pa-att">Property data by ' +
      '<a href="' + HOME + '/?utm_source=embed&utm_medium=whitelabel" ' +
      'target="_blank" rel="noopener">PropertyAtlas</a></div>';

    root.innerHTML =
      "<style>" + styleBlock(t) + "</style>" +
      '<div class="pa"><div class="pa-top"><div class="pa-brand">' +
      (logo ? '<img src="' + esc(logo) + '" alt="">' : "") +
      '<span class="pa-title">' + esc(heading) + "</span></div>" +
      '<span class="pa-count">' + total.toLocaleString() +
      (total === 1 ? " asset" : " assets") + "</span></div>" +
      '<input class="pa-search" type="search" placeholder="Search asset, address or entity\u2026" ' +
      'value="' + esc(query) + '" data-pa-search>' +
      '<div style="height:14px"></div>' + grid + pager + att + "</div>";

    var box = root.querySelector("[data-pa-search]");
    if (box) {
      var timer = null;
      box.addEventListener("input", function (e) {
        var v = e.target.value;
        clearTimeout(timer);
        timer = setTimeout(function () {
          query = v; applyQuery(); paint();
          var b2 = root.querySelector("[data-pa-search]");
          if (b2) { b2.focus(); b2.setSelectionRange(v.length, v.length); }
        }, 220);
      });
    }
    var prev = root.querySelector("[data-pa-prev]");
    var next = root.querySelector("[data-pa-next]");
    if (prev) prev.addEventListener("click", function () { if (page > 0) { page--; paint(); } });
    if (next) next.addEventListener("click", function () { page++; paint(); });
  }

  /* ------------------------------------------------------------------ run */

  getConfig().then(function (res) {
    var body = res.body || {};

    if (res.status !== 200 || !body.ok) {
      var code = body.code || "unavailable";
      var msg = "This embed could not be loaded.";
      if (code === "origin_not_allowed") {
        msg = "This domain is not registered for the supplied PropertyAtlas key.";
      } else if (code === "key_revoked") {
        msg = "The PropertyAtlas key for this embed has been revoked.";
      } else if (code === "key_invalid" || code === "key_missing") {
        msg = "The PropertyAtlas key for this embed was not recognised.";
      } else if (code === "partner_inactive") {
        msg = "This PropertyAtlas partner account is not active.";
      }
      notice("PropertyAtlas embed unavailable", msg);
      return;
    }

    var wanted = null;
    for (var i = 0; i < (body.modules || []).length; i++) {
      if (body.modules[i].module === moduleName) { wanted = body.modules[i]; break; }
    }
    if (!wanted) {
      var why = "";
      for (var j = 0; j < (body.withheld || []).length; j++) {
        if (body.withheld[j].module === moduleName) { why = body.withheld[j].reason; break; }
      }
      notice("Module not available",
        why === "licence_required"
          ? "The \u201c" + moduleName + "\u201d module needs an external data licence " +
            "reference before it can be displayed."
          : "The \u201c" + moduleName + "\u201d module is not enabled for this partner.");
      return;
    }

    if (moduleName !== "asset_directory") {
      notice("Module not yet implemented",
        "This loader currently renders asset_directory only.");
      return;
    }

    var t = body.theme || {};
    THEME = {
      logo_url: t.logo_url || null,
      primary: isHex(t.primary) ? t.primary : "#1A4F9C",
      accent: isHex(t.accent) ? t.accent : "#A67C3A",
      surface: isHex(t.surface) ? t.surface : "#F7F3EB",
      ink: isHex(t.ink) ? t.ink : "#1A1A1A",
      font_stack: t.font_stack || null,
      attribution_mode: t.attribution_mode || "required"
    };
    MODCFG = wanted.config || {};

    notice("Loading asset directory\u2026", "Fetching properties from PropertyAtlas.");

    return getRows(MODCFG).then(function (rows) {
      ROWS = rows || [];
      applyQuery();
      paint();
    });
  }).catch(function (err) {
    try { console.error("PropertyAtlas embed:", err); } catch (e) {}
    notice("PropertyAtlas embed unavailable",
      "The directory could not be reached. Please try again shortly.");
  });
})();
