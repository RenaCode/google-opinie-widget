/*!
 * Google Reviews widget — self-hosted, no API key, no vendor branding, free.
 * Reads a small reviews.json (served from your own site) and renders a
 * reviews section. If the data fails to load it leaves the fallback markup that
 * lives inside the HTML container (or hides an empty one) — the page never breaks.
 *
 * On-page labels are Polish on purpose (the target site is Polish). Translate the
 * strings below for another language.
 *
 * Usage on the site:
 *   <div id="google-opinie" data-stars="5" data-max="6" data-src="/reviews.json"></div>
 *   <script src="/opinie.js" defer></script>
 */
(function () {
  "use strict";

  // Where to read the data from. Default is same-origin "reviews.json" (served
  // from your own site). Override with the data-src attribute on the container.
  var DEFAULT_SRC = "reviews.json";

  function h(tag, cls, html) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (html != null) el.innerHTML = html;
    return el;
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function stars(n) {
    n = Math.max(0, Math.min(5, Math.round(Number(n) || 0)));
    var full = "★".repeat(n), empty = "☆".repeat(5 - n);
    return '<span class="gop-stars" role="img" aria-label="Ocena ' + n +
      ' na 5">' + full + '<span class="gop-stars-dim">' + empty + "</span></span>";
  }

  function initials(name) {
    var p = String(name || "?").trim().split(/\s+/);
    return ((p[0] || "?")[0] + (p[1] ? p[1][0] : "")).toUpperCase();
  }

  // One-time styles — they use the host site's theme variables (--accent etc.)
  // with sensible fallbacks, so the widget blends into any design.
  var CSS = [
    "#google-opinie{--gop-accent:var(--accent,#e8900a);",
    "--gop-text:var(--text,#1c1f26);--gop-muted:var(--muted,#5b616e);",
    "--gop-surface:var(--surface,#fff);--gop-line:var(--line,#e4e7ec);",
    "--gop-soft:var(--accent-soft,#fff4e2);}",
    "#google-opinie .gop-badge{display:inline-flex;align-items:center;gap:12px;",
    "text-decoration:none;color:var(--gop-text);margin:0 auto 34px;",
    "padding:12px 18px;border:1px solid var(--gop-line);border-radius:14px;",
    "background:var(--gop-surface)}",
    "#google-opinie .gop-badge .gop-score{font-size:2rem;font-weight:700;color:var(--gop-accent);line-height:1}",
    "#google-opinie .gop-badge small{color:var(--gop-muted);font-size:.84rem}",
    "#google-opinie .gop-stars{color:var(--gop-accent);letter-spacing:2px}",
    "#google-opinie .gop-stars-dim{opacity:.3}",
    "#google-opinie .gop-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));",
    "gap:20px;max-width:960px;margin:0 auto}",
    "#google-opinie .gop-card{background:var(--gop-surface);border:1px solid var(--gop-line);",
    "border-radius:16px;padding:24px;text-align:left}",
    "#google-opinie .gop-card p{color:var(--gop-text);margin:12px 0 18px;line-height:1.55;font-size:1.02rem}",
    "#google-opinie .gop-who{display:flex;align-items:center;gap:11px}",
    "#google-opinie .gop-av{width:42px;height:42px;border-radius:50%;background:var(--gop-soft);",
    "color:var(--gop-accent);display:grid;place-items:center;font-weight:700;flex:none}",
    "#google-opinie .gop-who b{display:block;font-size:.95rem;color:var(--gop-text)}",
    "#google-opinie .gop-who span{color:var(--gop-muted);font-size:.82rem}",
    "#google-opinie .gop-cta{text-align:center;margin-top:34px}",
    "#google-opinie .gop-head{text-align:center;margin-bottom:8px}"
  ].join("");

  function injectCSS() {
    if (document.getElementById("gop-style")) return;
    var s = h("style"); s.id = "gop-style"; s.textContent = CSS;
    document.head.appendChild(s);
  }

  function render(box, data) {
    var minStars = parseInt(box.getAttribute("data-stars") || "5", 10);
    var max = parseInt(box.getAttribute("data-max") || "6", 10);
    var reviews = (data.reviews || [])
      .filter(function (r) { return (Number(r.rating) || 0) >= minStars; })
      .slice(0, max);

    if (!reviews.length) return false; // nothing to show -> keep fallback

    injectCSS();
    box.textContent = "";

    var head = h("div", "gop-head");
    var badge = h("a", "gop-badge");
    badge.href = data.url || ("https://www.google.com/maps?cid=" + (data.cid || ""));
    badge.target = "_blank"; badge.rel = "noopener";
    var score = (data.rating || "").toString().replace(".", ",");
    badge.innerHTML =
      '<span class="gop-score">' + esc(score || "★") + "</span>" +
      "<span>" + stars(data.rating) + "<br><small>" +
      esc(data.count || reviews.length) + " opinii w Google</small></span>";
    head.appendChild(badge);
    box.appendChild(head);

    var grid = h("div", "gop-grid");
    reviews.forEach(function (r) {
      var card = h("article", "gop-card");
      card.innerHTML =
        stars(r.rating) +
        "<p>„" + esc(r.text) + "”</p>" +
        '<div class="gop-who"><span class="gop-av" aria-hidden="true">' +
        esc(initials(r.author)) + "</span><div><b>" + esc(r.author) +
        "</b><span>Opinia z Google" +
        (r.when ? " · " + esc(r.when) : "") + "</span></div></div>";
      grid.appendChild(card);
    });
    box.appendChild(grid);

    var cta = h("div", "gop-cta");
    var btn = h("a", box.getAttribute("data-btn-class") || "btn btn-primary");
    btn.href = badge.href; btn.target = "_blank"; btn.rel = "noopener";
    btn.textContent = "Zobacz wszystkie opinie w Google";
    cta.appendChild(btn);
    box.appendChild(cta);
    return true;
  }

  function boot() {
    var box = document.getElementById("google-opinie");
    if (!box) return;
    var src = box.getAttribute("data-src") || DEFAULT_SRC;
    fetch(src, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { render(box, data); })
      .catch(function (e) {
        // Silent failure: keep whatever is in the HTML (the fallback content).
        if (window.console) console.warn("[google-opinie] fallback:", e.message);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
