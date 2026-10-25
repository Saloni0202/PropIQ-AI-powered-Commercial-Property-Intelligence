(function () {
  const $ = (id) => document.getElementById(id);
  const OPT_SLIDERS = ["transit_score", "walk_score", "amenities_score"];
  const PRESETS = [
    { market: "New York", property_type: "Office", building_class: "A", year_built: 2016, size_sf: 450000, floors: 28, occupancy_pct: 91, transit: 92, walk: 95, amen: 85, parking_ratio: 0.8 },
    { market: "Dallas", property_type: "Retail", building_class: "B", year_built: 1998, size_sf: 85000, floors: 1, occupancy_pct: 86, transit: 28, walk: 40, amen: 45, parking_ratio: 5.2 },
    { market: "Atlanta", property_type: "Industrial", building_class: "B", year_built: 2008, size_sf: 380000, floors: 1, occupancy_pct: 96, transit: 20, walk: 15, amen: 35, parking_ratio: 0.9 },
  ];
  let timer = null, seq = 0;

  async function init() {
    try {
      const f = await api("/api/filters");
      fillSelect($("market"), f.markets); fillSelect($("property_type"), f.property_types); fillSelect($("building_class"), f.building_classes);
      $("market").value = "Chicago"; $("property_type").value = "Office"; $("building_class").value = "A";
    } catch (e) { return showError($("form-err"), e.message); }
    $("occupancy_pct").addEventListener("input", () => { $("occ-v").textContent = $("occupancy_pct").value + "%"; schedule(); });
    OPT_SLIDERS.forEach((id) => {
      $(id + "-auto").addEventListener("change", () => { $(id).disabled = $(id + "-auto").checked; $(id + "-v").textContent = $(id + "-auto").checked ? "auto" : $(id).value; schedule(); });
      $(id).addEventListener("input", () => { $(id + "-v").textContent = $(id).value; schedule(); });
    });
    ["market", "property_type", "building_class", "year_built", "size_sf", "floors", "parking_ratio"].forEach((id) => $(id).addEventListener("input", schedule));
    $("form").addEventListener("submit", (e) => { e.preventDefault(); run(); });
    $("presets").addEventListener("click", (e) => { const c = e.target.closest(".chip"); if (c) applyPreset(PRESETS[+c.dataset.p]); });
    run();
  }

  function applyPreset(p) {
    ["market", "property_type", "building_class", "year_built", "size_sf", "floors", "parking_ratio"].forEach((k) => ($(k).value = p[k]));
    $("occupancy_pct").value = p.occupancy_pct; $("occ-v").textContent = p.occupancy_pct + "%";
    [["transit_score", p.transit], ["walk_score", p.walk], ["amenities_score", p.amen]].forEach(([id, v]) => {
      $(id).value = v; $(id + "-auto").checked = false; $(id).disabled = false; $(id + "-v").textContent = v;
    });
    run();
  }

  function schedule() { clearTimeout(timer); timer = setTimeout(run, 450); }
  const num = (id) => { const v = $(id).value.trim(); return v === "" ? null : Number(v); };

  function payload() {
    const o = {
      market: $("market").value, property_type: $("property_type").value, building_class: $("building_class").value,
      year_built: num("year_built"), size_sf: num("size_sf"), occupancy_pct: Number($("occupancy_pct").value),
      floors: num("floors"), parking_ratio: num("parking_ratio"),
    };
    OPT_SLIDERS.forEach((id) => (o[id] = $(id + "-auto").checked ? null : Number($(id).value)));
    return o;
  }

  async function run() {
    const my = ++seq; $("form-err").innerHTML = "";
    const body = payload();
    if (body.year_built == null || body.size_sf == null) { return showError($("form-err"), "Please enter year built and size."); }
    try {
      const d = await post("/api/predict", body);
      if (my !== seq) return;
      render(d, body);
    } catch (e) { showError($("form-err"), e.message); }
  }

  function render(d, body) {
    const lo = d.low, hi = d.high, med = d.segment_median_psf;
    const mn = Math.min(lo, med || lo) * 0.9, mx = Math.max(hi, med || hi) * 1.08, pos = (v) => ((v - mn) / (mx - mn)) * 100;
    $("hero-result").innerHTML = `
      <div style="display:flex;gap:30px;flex-wrap:wrap;align-items:flex-end;justify-content:space-between">
        <div><div class="muted small" style="text-transform:uppercase;letter-spacing:.7px">Estimated market rent</div>
          <div class="big">$${d.predicted_rent_psf.toFixed(2)}<span style="font-size:18px;color:var(--muted);letter-spacing:0"> / SF / yr</span></div>
          <div class="muted" style="margin-top:6px">90% range <b style="color:var(--text)">${fRent(lo)} – ${fRent(hi)}</b></div></div>
        <div style="display:grid;grid-template-columns:repeat(3,auto);gap:10px 28px">
          <div><div class="muted small">Est. annual rent</div><div style="font-size:20px">${fCompact(d.annual_rent_usd, "$")}</div></div>
          <div><div class="muted small">Segment median (${d.segment_n})</div><div style="font-size:20px">${fRent(med)}</div></div>
          <div><div class="muted small">vs segment median</div><div style="font-size:20px" class="${d.vs_segment_pct == null ? "" : d.vs_segment_pct < 0 ? "neg" : "pos"}">${fSigned(d.vs_segment_pct)}</div></div></div>
      </div>
      <div class="range-bar"><div class="fill" style="left:${pos(lo)}%;width:${pos(hi) - pos(lo)}%"></div>
        <div class="pt" style="left:${pos(d.predicted_rent_psf)}%" title="Estimate"></div>${med ? `<div class="mk" style="left:${pos(med)}%" title="Segment median"></div>` : ""}</div>
      <div class="small muted"><b style="color:var(--navy)">▮</b> point estimate &nbsp; <b style="color:var(--amber)">▮</b> median of ${esc(body.property_type)} in ${esc(body.market)} &nbsp; · model: ${esc(d.model)}</div>`;

    chart("c-class", {
      type: "bar",
      data: { labels: Object.keys(d.by_class).map((c) => "Class " + c), datasets: [{ data: Object.values(d.by_class), backgroundColor: Object.keys(d.by_class).map((c) => (c === body.building_class ? PAL.blue : PAL.lblue)) }] },
      options: { layout: { padding: { top: 20 } }, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: "#f0f3f6" } }, x: { grid: { display: false } } } },
      plugins: [endLabels((v) => "$" + v.toFixed(1))],
    });

    const T = d.tornado.slice().sort((a, b) => Math.max(Math.abs(b.low_delta), Math.abs(b.high_delta)) - Math.max(Math.abs(a.low_delta), Math.abs(a.high_delta)));
    chart("c-torn", {
      type: "bar",
      data: { labels: T.map((t) => t.driver), datasets: [
        { label: "Downside case", data: T.map((t) => Math.min(t.low_delta, t.high_delta)), backgroundColor: PAL.red + "cc", cases: T.map((t) => (t.low_delta <= t.high_delta ? t.low_label : t.high_label)) },
        { label: "Upside case", data: T.map((t) => Math.max(t.low_delta, t.high_delta)), backgroundColor: PAL.blue, cases: T.map((t) => (t.low_delta <= t.high_delta ? t.high_label : t.low_label)) }] },
      options: { indexAxis: "y", plugins: { tooltip: { callbacks: { label: (c) => ` ${c.dataset.cases[c.dataIndex]}: ${c.parsed.x > 0 ? "+" : ""}$${c.parsed.x.toFixed(2)} / SF` } } },
        scales: { x: { stacked: true, grid: { color: "#f0f3f6" }, ticks: { callback: (v) => (v > 0 ? "+" : "") + v } }, y: { stacked: true, grid: { display: false } } } },
    });

    $("comps").innerHTML = `<thead><tr><th>Property</th><th>Class</th><th class="num">Size SF</th><th class="num">Built</th><th class="num">Occupancy</th><th class="num">Rent $/SF</th></tr></thead><tbody>` +
      d.comps.map((c) => `<tr class="click" onclick="location.href='/properties.html?open=${esc(c.property_id)}'"><td><b>${esc(c.name)}</b></td><td>${esc(c.building_class)}</td><td class="num">${fInt(c.size_sf)}</td><td class="num">${c.year_built == null ? "–" : c.year_built}</td><td class="num">${fPct(c.occupancy_pct)}</td><td class="num"><b>${fRent(c.rent_psf)}</b></td></tr>`).join("") + "</tbody>";

    const a = Object.entries(d.assumed_inputs);
    $("assumed").innerHTML = a.length ? `<b>Assumed inputs.</b> Blank fields were filled with portfolio medians: ${a.map(([k, v]) => `${k.replace(/_/g, " ")} = ${v}`).join(", ")}. Provide real values to tighten the estimate.`
      : `<b>All inputs supplied.</b> The 90% range comes from out-of-fold relative errors; it is a typical-error band, not a guarantee.`;
  }

  init();
})();
