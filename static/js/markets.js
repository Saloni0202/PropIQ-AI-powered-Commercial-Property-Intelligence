(function () {
  const COLORS = ["#3b82d6", "#f08a4b", "#2e9e6e", "#9b6fd0", "#d9534f", "#2fa4b8", "#d99a2b", "#6b7a8c"];
  let TABLE = [], selected = [], sortKey = "gla_sf", sortDir = -1, colorOf = {};

  async function init() {
    try {
      const m = await api("/api/markets");
      TABLE = m.markets;
      selected = TABLE.slice(0, 5).map((r) => r.market);
      renderChips(); renderTable(); renderYoY(); renderKpis();
      loadTrends();
      loadHeat();
    } catch (e) { toast(e.message); }
    const bx = document.getElementById("bx"), bt = document.getElementById("bt");
    bx.innerHTML = [["age", "Building age"], ["transit_score", "Transit score"], ["amenities_score", "Amenities score"], ["occupancy_pct", "Occupancy"], ["size_sf", "Building size"]]
      .map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    api("/api/filters").then((f) => { fillSelect(bt, f.property_types); bt.value = "Office"; loadBinned(); }).catch((e) => toast(e.message));
    bx.addEventListener("change", loadBinned); bt.addEventListener("change", loadBinned);
  }

  function renderKpis() {
    const t = TABLE;
    const best = t.slice().sort((a, b) => b.yoy_rent_growth_pct - a.yoy_rent_growth_pct)[0];
    const worst = t.slice().sort((a, b) => a.yoy_rent_growth_pct - b.yoy_rent_growth_pct)[0];
    const tightest = t.slice().sort((a, b) => a.vacancy_pct - b.vacancy_pct)[0];
    const gla = t.reduce((s, r) => s + r.gla_sf, 0);
    const avgVac = t.reduce((s, r) => s + r.vacancy_pct * r.gla_sf, 0) / gla;
    document.getElementById("mk-kpis").innerHTML = `
      <div class="kpi"><div class="v">${fPct(avgVac)}</div><div class="l">Portfolio-weighted vacancy</div></div>
      <div class="kpi"><div class="v pos">${esc(best.market)}</div><div class="l">Fastest rent growth</div><div class="d up">${fSigned(best.yoy_rent_growth_pct)} YoY</div></div>
      <div class="kpi"><div class="v neg">${esc(worst.market)}</div><div class="l">Weakest rent growth</div><div class="d down">${fSigned(worst.yoy_rent_growth_pct)} YoY</div></div>
      <div class="kpi"><div class="v">${esc(tightest.market)}</div><div class="l">Tightest market</div><div class="d">${fPct(tightest.vacancy_pct)} vacancy</div></div>`;
  }

  function renderChips() {
    TABLE.forEach((r) => { if (!colorOf[r.market]) colorOf[r.market] = null; });
    const el = document.getElementById("chips");
    el.innerHTML = TABLE.map((r) => `<span class="chip ${selected.includes(r.market) ? "on" : ""}" data-m="${esc(r.market)}">${esc(r.market)}</span>`).join("");
    el.onclick = (e) => {
      const c = e.target.closest(".chip"); if (!c) return;
      const m = c.dataset.m, i = selected.indexOf(m);
      if (i >= 0) { if (selected.length === 1) return toast("Keep at least one market selected"); selected.splice(i, 1); }
      else { if (selected.length >= 8) return toast("You can compare up to 8 markets"); selected.push(m); }
      renderChips(); loadTrends();
    };
  }

  async function loadTrends() {
    try {
      const d = await api("/api/trends?markets=" + encodeURIComponent(selected.join(",")));
      const names = Object.keys(d.series);
      const ds = (key) => names.map((m, i) => ({ label: m, data: d.series[m][key], borderColor: COLORS[i % 8], backgroundColor: COLORS[i % 8], borderWidth: 2.2, pointRadius: 0, pointHoverRadius: 4, tension: 0.25 }));
      const opts = (title) => ({ interaction: { mode: "index", intersect: false }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { title: { display: true, text: title }, grid: { color: "#f0f3f6" } } } });
      chart("c-rent", { type: "line", data: { labels: d.months, datasets: ds("rent") }, options: opts("$ / SF / yr") });
      chart("c-vac", { type: "line", data: { labels: d.months, datasets: ds("vacancy") }, options: opts("Vacancy %") });
      const ttm = names.map((m) => d.series[m].absorption.slice(-12).reduce((a, b) => a + b, 0));
      chart("c-abs", {
        type: "bar",
        data: { labels: names, datasets: [{ data: ttm.map((v) => Math.round(v)), backgroundColor: ttm.map((v) => (v >= 0 ? PAL.blue : PAL.red)) }] },
        options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: "#f0f3f6" }, title: { display: true, text: "K SF" } }, x: { grid: { display: false } } } },
      });
    } catch (e) { toast(e.message); }
  }

  function renderYoY() {
    const rows = TABLE.slice().sort((a, b) => b.yoy_rent_growth_pct - a.yoy_rent_growth_pct);
    chart("c-yoy", {
      type: "bar",
      data: { labels: rows.map((r) => r.market), datasets: [{ data: rows.map((r) => r.yoy_rent_growth_pct), backgroundColor: rows.map((r) => (r.yoy_rent_growth_pct >= 0 ? PAL.blue : PAL.red)), barPercentage: 0.8 }] },
      options: { indexAxis: "y", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${fSigned(c.parsed.x, 2)} YoY` } } },
        scales: { x: { grid: { color: "#f0f3f6" }, ticks: { callback: (v) => v + "%" } }, y: { grid: { display: false }, ticks: { font: { size: 11 }, autoSkip: false } } } },
    });
  }

  const COLS = [["market", "Market", 0], ["properties", "Properties", 1], ["gla_sf", "GLA (SF)", 1], ["avg_rent_psf", "Avg rent", 1], ["yoy_rent_growth_pct", "Rent YoY", 1],
    ["vacancy_pct", "Vacancy", 1], ["vacancy_chg_pp", "Δ Vacancy (pp)", 1], ["absorption_ttm_ksf", "Absorption TTM (K SF)", 1], ["occupancy_pct", "Portfolio occ.", 1]];
  function renderTable() {
    const rows = TABLE.slice().sort((a, b) => (typeof a[sortKey] === "string" ? a[sortKey].localeCompare(b[sortKey]) : a[sortKey] - b[sortKey]) * sortDir);
    const maxGla = Math.max(...TABLE.map((r) => r.gla_sf));
    document.getElementById("mk-table").innerHTML = `<thead><tr>${COLS.map(([k, l, n]) => `<th class="sortable ${n ? "num" : ""}" data-k="${k}">${l}${sortKey === k ? (sortDir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead><tbody>` +
      rows.map((r) => `<tr><td><a href="/properties.html?market=${encodeURIComponent(r.market)}"><b>${esc(r.market)}</b></a> <span class="muted small">${esc(r.state)}</span></td>
        <td class="num">${fInt(r.properties)}</td><td class="num">${fInt(r.gla_sf)}<span class="bar-inline" style="width:${Math.round(r.gla_sf / maxGla * 60)}px"></span></td>
        <td class="num">${fRent(r.avg_rent_psf)}</td><td class="num ${r.yoy_rent_growth_pct >= 0 ? "pos" : "neg"}">${fSigned(r.yoy_rent_growth_pct, 2)}</td>
        <td class="num">${fPct(r.vacancy_pct)}</td><td class="num ${r.vacancy_chg_pp <= 0 ? "pos" : "neg"}">${r.vacancy_chg_pp > 0 ? "+" : ""}${fDec(r.vacancy_chg_pp, 1)}</td>
        <td class="num">${fInt(r.absorption_ttm_ksf)}</td><td class="num">${fPct(r.occupancy_pct)}</td></tr>`).join("") + "</tbody>";
    document.querySelectorAll("#mk-table th.sortable").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.k; if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = k === "market" ? 1 : -1; }
      renderTable();
    }));
  }

  async function loadHeat() {
    try {
      const d = await api("/api/market-matrix");
      const types = ["Office", "Retail", "Industrial", "Medical Office", "Flex"];
      const markets = TABLE.map((r) => r.market);
      const map = {}; d.rows.forEach((r) => { map[r.market + "|" + r.property_type] = r; });
      const rng = {};
      types.forEach((t) => { const v = d.rows.filter((r) => r.property_type === t).map((r) => r.avg_rent); rng[t] = [Math.min(...v), Math.max(...v)]; });
      document.getElementById("heat").innerHTML = `<thead><tr><th>Market</th>${types.map((t) => `<th class="num">${t}</th>`).join("")}</tr></thead><tbody>` +
        markets.map((m) => `<tr><td><b>${esc(m)}</b></td>${types.map((t) => {
          const c = map[m + "|" + t];
          if (!c) return `<td class="cell muted">–</td>`;
          const [lo, hi] = rng[t], a = hi === lo ? 0.2 : 0.08 + 0.7 * ((c.avg_rent - lo) / (hi - lo));
          return `<td class="cell" title="${c.n} properties" style="background:rgba(59,130,214,${a.toFixed(2)});color:${a > 0.5 ? "#fff" : "#1b2733"}">${fRent(c.avg_rent)}</td>`;
        }).join("")}</tr>`).join("") + "</tbody>";
    } catch (e) { toast(e.message); }
  }

  async function loadBinned() {
    const x = document.getElementById("bx").value, t = document.getElementById("bt").value;
    if (!t) return;
    try {
      const d = await api(`/api/analysis/binned?x=${x}&property_type=${encodeURIComponent(t)}`);
      const col = { A: PAL.blue, B: PAL.amber, C: PAL.red };
      chart("c-bin", {
        type: "line",
        data: { labels: d.bins, datasets: Object.keys(d.series).map((c) => ({ label: "Class " + c, data: d.series[c], borderColor: col[c], backgroundColor: col[c], borderWidth: 2.4, tension: 0.25, pointRadius: 4, spanGaps: true })) },
        options: { interaction: { mode: "index", intersect: false }, scales: { y: { title: { display: true, text: "avg $ / SF / yr" }, grid: { color: "#f0f3f6" } }, x: { title: { display: true, text: d.x_label }, grid: { display: false } } } },
      });
    } catch (e) { toast(e.message); }
  }

  init();
})();
