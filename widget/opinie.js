/*!
 * Google Reviews widget — self-hosted, no vendor branding.
 * Data: official Google Places API (New), fetched live through a small proxy
 * that holds the API key (charts/google-opinie). Nothing is cached or stored.
 *
 * If the data fails to load it leaves the fallback markup that lives inside the
 * HTML container — the page never breaks.
 *
 * On-page labels are Polish on purpose (the target site is Polish). Translate the
 * strings in TXT for another language — but keep the words "Google Maps" exactly
 * as they are: Google's attribution rules forbid changing or translating them.
 *
 * Usage on the site:
 *   <div id="google-opinie" data-src="https://YOUR-PROXY/v1/reviews"></div>
 *   <script src="/opinie.js" defer></script>
 */
(function () {
  "use strict";

  var TXT = {
    reviewsIn: function (n) { return n + " " + plural(n) + " w Google"; },
    from: "Opinia z Google",
    see: "Zobacz w Google Maps",
    report: "Zgłoś",
    seeAll: "Zobacz wszystkie opinie w Google Maps",
    rating: function (n) { return "Ocena " + n + " na 5"; },
    // Google requires a clear notice of how reviews are ordered and filtered.
    order: "Do 5 opinii wybranych przez Google jako najtrafniejsze",
    filter: function (n) { return ", pokazujemy tylko oceny " + n + "★ i wyższe"; }
  };

  function plural(n) {
    n = Math.abs(Number(n) || 0);
    if (n === 1) return "opinia";
    var d = n % 10, dd = n % 100;
    return d >= 2 && d <= 4 && (dd < 12 || dd > 14) ? "opinie" : "opinii";
  }

  function h(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text != null) el.textContent = text;
    return el;
  }

  function link(href, cls, text) {
    var a = h("a", cls, text);
    // Only http(s) links from the API; anything else is dropped.
    if (/^https:\/\//i.test(href || "")) {
      a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
    }
    return a;
  }

  function stars(n) {
    n = Math.max(0, Math.min(5, Math.round(Number(n) || 0)));
    var s = h("span", "gop-stars", "★".repeat(n));
    s.setAttribute("role", "img");
    s.setAttribute("aria-label", TXT.rating(n));
    s.appendChild(h("span", "gop-stars-dim", "☆".repeat(5 - n)));
    return s;
  }

  function initials(name) {
    var p = String(name || "?").trim().split(/\s+/);
    return ((p[0] || "?")[0] + (p[1] ? p[1][0] : "")).toUpperCase();
  }

  function avatar(r) {
    var box = h("span", "gop-av", initials(r.author));
    box.setAttribute("aria-hidden", "true");
    if (/^https:\/\//i.test(r.authorPhoto || "")) {
      var img = h("img");
      img.src = r.authorPhoto; img.alt = ""; img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.width = 42; img.height = 42;
      img.onload = function () { box.textContent = ""; box.appendChild(img); };
    }
    return box;
  }

  // One-time styles — they use the host site's theme variables (--accent etc.)
  // with sensible fallbacks, so the widget blends into any design.
  var CSS = [
    "#google-opinie{--gop-accent:var(--accent,#e8900a);",
    "--gop-text:var(--text,#1c1f26);--gop-muted:var(--muted,#5b616e);",
    "--gop-surface:var(--surface,#fff);--gop-line:var(--line,#e4e7ec);",
    "--gop-soft:var(--accent-soft,#fff4e2);}",
    "#google-opinie .gop-badge{display:inline-flex;align-items:center;gap:12px;",
    "text-decoration:none;color:var(--gop-text);margin:0 auto 12px;",
    "padding:12px 18px;border:1px solid var(--gop-line);border-radius:14px;",
    "background:var(--gop-surface)}",
    "#google-opinie .gop-badge .gop-score{font-size:2rem;font-weight:700;color:var(--gop-accent);line-height:1}",
    "#google-opinie .gop-badge small{color:var(--gop-muted);font-size:.84rem}",
    "#google-opinie .gop-note{color:var(--gop-muted);font-size:.8rem;margin:0 0 26px}",
    "#google-opinie .gop-stars{color:var(--gop-accent);letter-spacing:2px}",
    "#google-opinie .gop-stars-dim{opacity:.3}",
    "#google-opinie .gop-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));",
    "gap:20px;max-width:960px;margin:0 auto}",
    "#google-opinie .gop-card{background:var(--gop-surface);border:1px solid var(--gop-line);",
    "border-radius:16px;padding:24px;text-align:left;display:flex;flex-direction:column}",
    "#google-opinie .gop-card p{color:var(--gop-text);margin:12px 0 18px;line-height:1.55;font-size:1.02rem;flex:1}",
    "#google-opinie .gop-who{display:flex;align-items:center;gap:11px}",
    "#google-opinie .gop-av{width:42px;height:42px;border-radius:50%;background:var(--gop-soft);overflow:hidden;",
    "color:var(--gop-accent);display:grid;place-items:center;font-weight:700;flex:none}",
    "#google-opinie .gop-av img{width:100%;height:100%;object-fit:cover}",
    "#google-opinie .gop-who a.gop-name{display:block;font-weight:700;font-size:.95rem;color:var(--gop-text);text-decoration:none}",
    "#google-opinie .gop-meta,#google-opinie .gop-meta a{color:var(--gop-muted);font-size:.82rem}",
    "#google-opinie .gop-cta{text-align:center;margin-top:34px}",
    "#google-opinie .gop-head{text-align:center}",
    // "Google Maps" attribution: 12-16px, unmodified, readable contrast.
    "#google-opinie .gop-attr{text-align:center;margin-top:18px;font-size:13px;color:var(--gop-muted)}"
  ].join("");

  function injectCSS() {
    if (document.getElementById("gop-style")) return;
    var s = h("style"); s.id = "gop-style"; s.textContent = CSS;
    document.head.appendChild(s);
  }

  function render(box, data) {
    var minStars = parseInt(box.getAttribute("data-stars") || "1", 10);
    var max = parseInt(box.getAttribute("data-max") || "5", 10);
    var reviews = (data.reviews || [])
      .filter(function (r) { return r.text && (Number(r.rating) || 0) >= minStars; })
      .slice(0, max);

    if (!reviews.length) return false; // nothing to show -> keep fallback

    injectCSS();
    box.textContent = "";

    var head = h("div", "gop-head");
    var badge = link(data.url, "gop-badge");
    var score = data.rating != null ? Number(data.rating).toFixed(1).replace(".", ",") : "★";
    badge.appendChild(h("span", "gop-score", score));
    var right = h("span");
    right.appendChild(stars(data.rating));
    right.appendChild(h("br"));
    right.appendChild(h("small", null, TXT.reviewsIn(data.count || reviews.length)));
    badge.appendChild(right);
    head.appendChild(badge);
    head.appendChild(h("p", "gop-note",
      TXT.order + (minStars > 1 ? TXT.filter(minStars) : "") + "."));
    box.appendChild(head);

    var grid = h("div", "gop-grid");
    reviews.forEach(function (r) {
      var card = h("article", "gop-card");
      card.appendChild(stars(r.rating));
      card.appendChild(h("p", null, "„" + r.text + "”"));

      var who = h("div", "gop-who");
      who.appendChild(avatar(r));
      var info = h("div");
      info.appendChild(link(r.authorUri, "gop-name", r.author || "Google"));
      var meta = h("span", "gop-meta", TXT.from + (r.when ? " · " + r.when : "") + " · ");
      meta.appendChild(link(r.reviewUri || data.url, null, TXT.see));
      if (r.flagUri) {
        meta.appendChild(document.createTextNode(" · "));
        meta.appendChild(link(r.flagUri, null, TXT.report));
      }
      info.appendChild(meta);
      who.appendChild(info);
      card.appendChild(who);
      grid.appendChild(card);
    });
    box.appendChild(grid);

    if (data.url) {
      var cta = h("div", "gop-cta");
      cta.appendChild(link(data.url, box.getAttribute("data-btn-class") || "btn btn-primary", TXT.seeAll));
      box.appendChild(cta);
    }

    box.appendChild(h("div", "gop-attr", "Google Maps"));
    return true;
  }

  function load(box) {
    var src = box.getAttribute("data-src");
    if (!src) return;
    fetch(src, { cache: "no-store", credentials: "omit" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { render(box, data); })
      .catch(function (e) {
        // Silent failure: keep whatever is in the HTML (the fallback content).
        if (window.console) console.warn("[google-opinie] fallback:", e.message);
      });
  }

  function boot() {
    var box = document.getElementById("google-opinie");
    if (!box) return;
    // Every load is a billed API call, so fetch only when the section is
    // about to scroll into view — visitors who never get there cost nothing.
    if (!("IntersectionObserver" in window)) return load(box);
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) {
        io.disconnect();
        load(box);
      }
    }, { rootMargin: "400px 0px" });
    io.observe(box);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
