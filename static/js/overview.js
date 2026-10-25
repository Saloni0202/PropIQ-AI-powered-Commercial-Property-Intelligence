(function () {
  const F = { market: "", property_type: "", building_class: "" };
  let DATA = null, usTopo = null;

  async function init() {
    const box = document.getElementById("title-actions");
    box.innerHTML = `<select id="f-market"></select><select id="f-type"></select><select id="f-class"></select>`;
    try {
      const f = await api("/api/filters");
      fillSelect(document.getElementById("f-market"), f.markets, "All markets");
      fillSelect(document.getElementById("f-type"), f.property_types, "All property types");
      fillSelect(document.getElementById("f-class"), f.building_classes.map((c) => c), "All classes");
      document.getElementById("asof").textContent = new Date(f.as_of + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch (e) { toast(e.message); }
    [["f-market", "market"], ["f-type", "property_type"], ["f-class", "building_class"]].forEach(([id, k]) =>
      document.getElementById(id).addEventListener("change", (e) => { F[k] = e.target.value; load(); }));
    document.getElementById("ind-metric").addEventListener("change", () => DATA && renderIndustry(DATA));
    document.getElementById("gap-seg").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      document.querySelectorAll("#gap-seg button").forEach((x) => x.classList.toggle("on", x === b));
      renderGaps(DATA, b.dataset.k);
    });
    loadHero();
    load();
  }

  async function loadHero() {
    try {
      const m = await api("/api/model/metrics");
      const h = await api("/api/health");
      document.getElementById("hero-dl").innerHTML = `
        <dt>Properties</dt><dd>${fInt(h.properties)}</dd><dt>Markets</dt><dd>20 US metros</dd>
        <dt>Rent model</dt><dd>${esc(m.selected_model.replace(" (log target)", ""))}</dd>
        <dt>Test MAE</dt><dd>$${fDec(m.test.mae)} / SF</dd><dt>Test RMSE</dt><dd>$${fDec(m.test.rmse)} / SF</dd><dt>Test R²</dt><dd>${fDec(m.test.r2, 3)}</dd>`;
    } catch (e) { /* hero is decorative */ }
  }

  async function load() {
    const qs = new URLSearchParams(Object.entries(F).filter(([, v]) => v)).toString();
    try {
      DATA = await api("/api/overview" + (qs ? "?" + qs : ""));
    } catch (e) { toast(e.message); return; }
    renderKpis(DATA); renderExpiry(DATA); renderIndustry(DATA); renderAVM(DATA); renderMap(DATA); renderType(DATA); renderOcc(DATA);
    const on = document.querySelector("#gap-seg button.on");
    renderGaps(DATA, on ? on.dataset.k : "below_model");
  }

  function renderKpis(d) {
    const k = d.kpis;
    const items = [
      [k.gla_sf >= 1e7 ? fCompact(k.gla_sf) + " SF" : fInt(k.gla_sf) + " SF", "GLA"],
      [fInt(k.properties), "Properties"], [fInt(k.tenants), "Tenants (leases)"],
      [fRent(k.wa_rent_psf), "W/A Rent SF"], [fPct(k.occupancy_pct), "Occupancy"], [fCompact(k.rent_roll_usd, "$"), "Annual rent roll"],
    ];
    document.getElementById("kpis").innerHTML = items.map(([v, l]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
  }

  function renderExpiry(d) {
    const e = d.expiry;
    chart("c-expiry", {
      type: "bar",
      data: {
        labels: e.map((x) => x.bucket),
        datasets: [
          { type: "bar", label: "Area expiring (M SF)", data: e.map((x) => +(x.area_sf / 1e6).toFixed(3)), backgroundColor: PAL.blue, yAxisID: "y" },
          { type: "bar", label: "Rent expiring ($M)", data: e.map((x) => +(x.rent_usd / 1e6).toFixed(2)), backgroundColor: PAL.lblue, yAxisID: "y1" },
          { type: "line", label: "Cumulative % of area", data: e.map((x) => x.cum_pct), borderColor: PAL.peach, backgroundColor: PAL.peach, borderWidth: 2.5, tension: 0.3, pointRadius: 3, yAxisID: "y2" },
        ],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: "M SF" }, grid: { color: "#f0f3f6" } },
          y1: { beginAtZero: true, position: "right", grid: { display: false }, title: { display: true, text: "$M" } },
          y2: { display: false, min: 0, max: 100 },
          x: { grid: { display: false } },
        },
      },
    });
  }

  function renderIndustry(d) {
    const key = document.getElementById("ind-metric").value;
    const rows = d.industry.filter((r) => r.industry !== "Other").sort((a, b) => b[key] - a[key]);
    const top = rows.slice(0, 7), rest = rows.slice(7).concat(d.industry.filter((r) => r.industry === "Other"));
    if (rest.length) top.push({ industry: "All other industries", [key]: rest.reduce((s, r) => s + r[key], 0) });
    chart("c-industry", {
      type: "bar",
      data: { labels: top.map((r) => r.industry), datasets: [{ data: top.map((r) => +r[key].toFixed(1)), backgroundColor: top.map((_, i) => PALETTE[i % PALETTE.length]), borderRadius: 3, barPercentage: 0.78 }] },
      options: {
        indexAxis: "y", layout: { padding: { right: 46 } },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.parsed.x}% of ${key === "pct_area" ? "leased area" : "rent roll"}` } } },
        scales: { x: { display: false, beginAtZero: true }, y: { grid: { display: false } } },
      },
      plugins: [endLabels((v) => v.toFixed(1) + "%")],
    });
  }

  function renderAVM(d) {
    const rows = d.actual_vs_model.slice(0, 12);
    chart("c-avm", {
      type: "bar",
      data: {
        labels: rows.map((r) => r.market),
        datasets: [
          { label: "Actual", data: rows.map((r) => +r.actual.toFixed(2)), backgroundColor: PAL.blue },
          { label: "Model estimate", data: rows.map((r) => +r.model.toFixed(2)), backgroundColor: PAL.lblue },
        ],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: { y: { beginAtZero: true, title: { display: true, text: "$ / SF / yr" }, grid: { color: "#f0f3f6" } }, x: { grid: { display: false }, ticks: { maxRotation: 55, minRotation: 40, autoSkip: false, font: { size: 11 } } } },
      },
    });
  }

  async function renderMap(d) {
    const el = document.getElementById("map");
    try {
      if (!usTopo) usTopo = await (await fetch("/vendor/states-10m.json")).json();
      const W = 640, H = 350;
      el.innerHTML = "";
      const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "Map of portfolio by market");
      const nation = topojson.feature(usTopo, usTopo.objects.nation);
      const proj = d3.geoAlbersUsa().fitExtent([[6, 6], [W - 6, H - 6]], nation);
      const path = d3.geoPath(proj);
      svg.append("path").datum(nation).attr("d", path).attr("fill", "#e9eff5");
      svg.append("path").datum(topojson.mesh(usTopo, usTopo.objects.states, (a, b) => a !== b)).attr("d", path).attr("fill", "none").attr("stroke", "#fff").attr("stroke-width", 1);
      const pts = d.markets.map((m) => ({ m, xy: proj([m.lon, m.lat]) })).filter((p) => p.xy);
      const glaMax = d3.max(pts, (p) => p.m.gla) || 1;
      const rent = d3.extent(pts, (p) => p.m.avg_rent);
      const r = d3.scaleSqrt().domain([0, glaMax]).range([4, 24]);
      const col = d3.scaleLinear().domain(rent[0] === rent[1] ? [rent[0] - 1, rent[1]] : rent).range(["#a9cdf3", "#16498f"]);
      const g = svg.append("g");
      g.selectAll("circle").data(pts.sort((a, b) => b.m.gla - a.m.gla)).enter().append("circle")
        .attr("cx", (p) => p.xy[0]).attr("cy", (p) => p.xy[1]).attr("r", (p) => r(p.m.gla)).attr("fill", (p) => col(p.m.avg_rent))
        .attr("fill-opacity", 0.88).attr("stroke", "#fff").attr("stroke-width", 1.5).style("cursor", "pointer")
        .on("mousemove", (ev, p) => tip.show(`<b>${esc(p.m.market)}, ${esc(p.m.state)}</b><br>${fInt(p.m.properties)} properties · ${fCompact(p.m.gla)} SF<br>Avg rent ${fRent(p.m.avg_rent)} · Occ ${fPct(p.m.occupancy)}`, ev))
        .on("mouseleave", () => tip.hide())
        .on("click", (ev, p) => { location.href = "/properties.html?market=" + encodeURIComponent(p.m.market); });
      g.selectAll("text").data(pts.slice(0, 8)).enter().append("text").attr("x", (p) => p.xy[0]).attr("y", (p) => p.xy[1] + r(p.m.gla) + 11)
        .attr("text-anchor", "middle").attr("font-size", 10).attr("fill", "#33475b").attr("pointer-events", "none").text((p) => p.m.market);
    } catch (e) { showError(el, "Map failed to load: " + e.message); }
  }

  function renderType(d) {
    const rows = d.by_type;
    chart("c-type", {
      type: "bar",
      data: { labels: rows.map((r) => r.property_type), datasets: [{ data: rows.map((r) => +r.avg_rent.toFixed(2)), backgroundColor: [PAL.blue, PAL.peach, PAL.teal, PAL.lav, PAL.pink] }] },
      options: { layout: { padding: { top: 20 } }, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: "#f0f3f6" } }, x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: false, font: { size: 11 } } } } },
      plugins: [endLabels((v) => "$" + v.toFixed(1))],
    });
  }

  function renderOcc(d) {
    const h = d.occupancy_hist;
    chart("c-occ", {
      type: "bar",
      data: { labels: h.counts.map((_, i) => `${h.edges[i]}–${h.edges[i + 1]}`), datasets: [{ data: h.counts, backgroundColor: PAL.teal, categoryPercentage: 0.95, barPercentage: 0.95 }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: { title: (i) => `Occupancy ${i[0].label}%` } } }, scales: { y: { beginAtZero: true, grid: { color: "#f0f3f6" } }, x: { grid: { display: false }, ticks: { font: { size: 10 } } } } },
    });
  }

  function renderGaps(d, key) {
    const rows = (d && d[key]) || [];
    document.getElementById("gap-table").innerHTML = `<thead><tr><th>Property</th><th class="num">Actual</th><th class="num">Model</th><th class="num">Gap</th></tr></thead><tbody>` +
      rows.map((r) => `<tr class="click" onclick="location.href='/properties.html?open=${esc(r.property_id)}'"><td><b>${esc(r.name)}</b><div class="muted small">${esc(r.market)} · ${esc(r.property_type)} ${esc(r.building_class)}</div></td>
        <td class="num">${fRent(r.rent_psf)}</td><td class="num">${fRent(r.pred_rent_psf)}</td><td class="num ${r.gap_pct < 0 ? "neg" : "pos"}">${fSigned(r.gap_pct)}</td></tr>`).join("") + `</tbody>`;
  }

  init();
})();
