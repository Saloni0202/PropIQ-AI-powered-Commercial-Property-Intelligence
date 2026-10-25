/* PropIQ shared shell: header, tabs, fetch helper, formatters, chart defaults */
(function () {
  const NAV = [
    { key: "overview", label: "Overview", href: "/" },
    { key: "markets", label: "Markets", href: "/markets.html" },
    { key: "properties", label: "Properties", href: "/properties.html" },
    { key: "predict", label: "Rent Predictor", href: "/predict.html" },
    { key: "model", label: "Model Evaluation", href: "/model.html" },
    { key: "assistant", label: "Document Q&A", href: "/assistant.html" },
    { key: "data", label: "Data & Pipeline", href: "/data.html" },
  ];

  const MARK = `<svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a90e2"/><stop offset="1" stop-color="#16314f"/></linearGradient></defs>
    <rect width="32" height="32" rx="8" fill="url(#lg)"/><rect x="7" y="13" width="5" height="12" rx="1" fill="#fff" opacity=".95"/><rect x="13.5" y="7" width="5" height="18" rx="1" fill="#fff"/><rect x="20" y="16" width="5" height="9" rx="1" fill="#fff" opacity=".8"/></svg>`;
  const SEARCH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>`;
  const BELL = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/></svg>`;

  window.PAL = { blue: "#4a90e2", lblue: "#b4d7fb", peach: "#fcc8a5", teal: "#86b4c7", pink: "#f9c4e6", lav: "#c7ccf3", navy: "#16314f", green: "#2e9e6e", red: "#d9534f", amber: "#d99a2b", grey: "#cfd8e1" };
  window.PALETTE = [PAL.blue, PAL.lblue, PAL.peach, PAL.teal, PAL.pink, PAL.lav, PAL.amber, PAL.green, "#9b8bd8", "#7fc6a4"];

  // ---------- formatting ----------
  const nf = new Intl.NumberFormat("en-US");
  window.esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  window.fInt = (n) => (n == null ? "–" : nf.format(Math.round(n)));
  window.fDec = (n, d = 2) => (n == null ? "–" : Number(n).toFixed(d));
  window.fRent = (n) => (n == null ? "–" : "$" + Number(n).toFixed(2));
  window.fPct = (n, d = 1) => (n == null ? "–" : Number(n).toFixed(d) + "%");
  window.fSigned = (n, d = 1) => (n == null ? "–" : (n > 0 ? "+" : "") + Number(n).toFixed(d) + "%");
  window.fCompact = (n, prefix = "") => {
    if (n == null) return "–";
    const a = Math.abs(n);
    if (a >= 1e9) return prefix + (n / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return prefix + (n / 1e6).toFixed(a >= 1e8 ? 0 : 1) + "M";
    if (a >= 1e3) return prefix + (n / 1e3).toFixed(a >= 1e5 ? 0 : 1) + "K";
    return prefix + Math.round(n);
  };

  // ---------- fetch ----------
  window.api = async function (path, opts) {
    let res;
    try { res = await fetch(path, opts); } catch (e) { throw new Error("Cannot reach the server. Is it running?"); }
    if (!res.ok) {
      let msg = res.statusText;
      try {
        const j = await res.json();
        msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join("; ") : msg;
      } catch (e) { /* ignore */ }
      throw new Error(msg);
    }
    return res.json();
  };
  window.post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  window.toast = function (msg) {
    const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
    setTimeout(() => t.remove(), 3600);
  };
  window.showError = (el, msg) => { el.innerHTML = `<div class="error">${esc(msg)}</div>`; };
  window.fillSelect = function (sel, items, placeholder) {
    sel.innerHTML = (placeholder != null ? `<option value="">${esc(placeholder)}</option>` : "") + items.map((i) => `<option value="${esc(i)}">${esc(i)}</option>`).join("");
  };

  // ---------- charts ----------
  if (window.Chart) {
    const C = Chart.defaults;
    C.font.family = getComputedStyle(document.body).fontFamily;
    C.font.size = 12;
    C.color = "#6a7b8c";
    C.borderColor = "#edf1f5";
    C.maintainAspectRatio = false;
    C.animation.duration = 500;
    C.plugins.legend.position = "bottom";
    C.plugins.legend.labels.usePointStyle = true;
    C.plugins.legend.labels.boxWidth = 8;
    C.plugins.legend.labels.boxHeight = 8;
    C.plugins.legend.labels.padding = 16;
    C.plugins.tooltip.backgroundColor = "#16314f";
    C.plugins.tooltip.padding = 10;
    C.plugins.tooltip.cornerRadius = 6;
    C.plugins.tooltip.titleFont = { weight: "600" };
    C.elements.bar.borderRadius = 3;
  }
  const charts = {};
  window.chart = function (id, config) {
    if (charts[id]) charts[id].destroy();
    const el = document.getElementById(id);
    if (!el) return null;
    charts[id] = new Chart(el, config);
    return charts[id];
  };
  // draws numeric labels at the end of horizontal bars
  window.endLabels = (fmt) => ({
    id: "endLabels",
    afterDatasetsDraw(c) {
      const { ctx } = c; ctx.save(); ctx.fillStyle = "#33475b"; ctx.font = "12px " + Chart.defaults.font.family; ctx.textBaseline = "middle";
      const meta = c.getDatasetMeta(0);
      meta.data.forEach((bar, i) => {
        const v = c.data.datasets[0].data[i];
        if (c.options.indexAxis === "y") ctx.fillText(fmt(v), bar.x + 6, bar.y);
        else { ctx.textAlign = "center"; ctx.fillText(fmt(v), bar.x, bar.y - 8); }
      });
      ctx.restore();
    },
  });

  // ---------- shell ----------
  function buildShell() {
    const key = document.body.dataset.page, title = document.body.dataset.title || "", sub = document.body.dataset.sub || "";
    const top = document.createElement("header");
    top.className = "topbar";
    top.innerHTML = `<a class="brand" href="/">${MARK}<b>PropIQ</b><span>Asset Intelligence</span></a><div class="spacer"></div>
      <form class="gsearch" id="gsearch" autocomplete="off">${SEARCH}<input id="gsearch-input" type="search" placeholder="Search property, market or tenant…" aria-label="Search"></form>
      <button class="iconbtn" title="Notifications" aria-label="Notifications">${BELL}</button><div class="avatar" title="Demo user">PQ</div>`;
    document.body.prepend(top);
    const page = document.getElementById("page");
    const head = document.createElement("div");
    const crumb = key === "overview" ? `<span>Overview</span><span class="sep">›</span><span>US Commercial Portfolio</span>`
      : `<a href="/">Overview</a><span class="sep">›</span><span>${esc(title)}</span>`;
    head.innerHTML = `<div class="crumbs">${crumb}</div>
      <div class="titlebar"><div><h1>${esc(title)}</h1>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div><div class="toolbar" id="title-actions"></div></div>
      <nav class="tabs">${NAV.map((n) => `<a href="${n.href}" class="${n.key === key ? "active" : ""}">${n.label}</a>`).join("")}</nav>`;
    page.prepend(head);
    const foot = document.createElement("footer"); foot.className = "foot";
    foot.innerHTML = "PropIQ · portfolio project · all data is synthetic and for demonstration only";
    page.appendChild(foot);
    document.getElementById("gsearch").addEventListener("submit", (e) => {
      e.preventDefault();
      const v = document.getElementById("gsearch-input").value.trim();
      if (v) location.href = "/properties.html?q=" + encodeURIComponent(v);
    });
  }
  buildShell();

  // shared tooltip for d3
  window.tip = (function () {
    const el = document.createElement("div"); el.className = "tip"; document.body.appendChild(el);
    return {
      show(html, ev) { el.innerHTML = html; el.style.display = "block"; this.move(ev); },
      move(ev) { el.style.left = Math.min(ev.clientX + 14, window.innerWidth - 230) + "px"; el.style.top = ev.clientY + 14 + "px"; },
      hide() { el.style.display = "none"; },
    };
  })();
})();
