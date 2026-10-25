(function () {
  const S = { q: "", market: "", property_type: "", building_class: "", sort: "size_sf", order: "desc", page: 1, page_size: 15 };
  const url = new URLSearchParams(location.search);
  let timer = null;

  const COLS = [["name", "Property", 0], ["market", "Market", 0], ["property_type", "Type", 0], ["building_class", "Class", 0], ["size_sf", "Size (SF)", 1],
    ["year_built", "Built", 1], ["occupancy_pct", "Occupancy", 1], ["rent_psf", "Rent $/SF", 1], ["pred_rent_psf", "Model $/SF", 1], ["gap_pct", "Gap vs model", 1]];

  async function init() {
    ["q", "market", "property_type", "building_class"].forEach((k) => { if (url.get(k)) S[k] = url.get(k); });
    document.getElementById("q").value = S.q;
    try {
      const f = await api("/api/filters");
      fillSelect(document.getElementById("f-market"), f.markets, "All markets");
      fillSelect(document.getElementById("f-type"), f.property_types, "All types");
      fillSelect(document.getElementById("f-class"), f.building_classes, "All classes");
      document.getElementById("f-market").value = S.market;
      document.getElementById("f-type").value = S.property_type;
      document.getElementById("f-class").value = S.building_class;
    } catch (e) { toast(e.message); }
    document.getElementById("q").addEventListener("input", (e) => { clearTimeout(timer); timer = setTimeout(() => { S.q = e.target.value.trim(); S.page = 1; load(); }, 250); });
    [["f-market", "market"], ["f-type", "property_type"], ["f-class", "building_class"]].forEach(([id, k]) =>
      document.getElementById(id).addEventListener("change", (e) => { S[k] = e.target.value; S.page = 1; load(); }));
    document.getElementById("reset").onclick = () => {
      Object.assign(S, { q: "", market: "", property_type: "", building_class: "", sort: "size_sf", order: "desc", page: 1 });
      document.getElementById("q").value = ""; ["f-market", "f-type", "f-class"].forEach((i) => (document.getElementById(i).value = "")); load();
    };
    document.getElementById("prev").onclick = () => { if (S.page > 1) { S.page--; load(); } };
    document.getElementById("next").onclick = () => { S.page++; load(); };
    document.getElementById("d-close").onclick = closeDrawer;
    document.getElementById("ov").onclick = closeDrawer;
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
    await load();
    if (url.get("open")) openDrawer(url.get("open"));
  }

  async function load() {
    const qs = new URLSearchParams();
    Object.entries(S).forEach(([k, v]) => { if (v !== "" && v != null) qs.set(k === "q" ? "q" : k, v); });
    const tbl = document.getElementById("tbl");
    try {
      const d = await api("/api/properties?" + qs.toString());
      if (S.page > d.pages) { S.page = d.pages; return load(); }
      document.getElementById("count").textContent = `${fInt(d.total)} properties`;
      document.getElementById("range").textContent = d.total ? `Showing ${(d.page - 1) * d.page_size + 1}–${Math.min(d.total, d.page * d.page_size)} of ${fInt(d.total)}` : "No results";
      document.getElementById("pg").textContent = `Page ${d.page} / ${d.pages}`;
      document.getElementById("prev").disabled = d.page <= 1; document.getElementById("next").disabled = d.page >= d.pages;
      const head = `<thead><tr>${COLS.map(([k, l, n]) => `<th class="sortable ${n ? "num" : ""}" data-k="${k}">${l}${S.sort === k ? (S.order === "asc" ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>`;
      const body = d.rows.length ? d.rows.map((r) => `<tr class="click" data-id="${esc(r.property_id)}"><td><b>${esc(r.name)}</b><div class="muted small">${esc(r.property_id)}</div></td><td>${esc(r.market)}, ${esc(r.state)}</td>
        <td>${esc(r.property_type)}</td><td><span class="badge ${r.building_class === "A" ? "blue" : r.building_class === "B" ? "" : "amber"}">${esc(r.building_class)}</span></td>
        <td class="num">${fInt(r.size_sf)}</td><td class="num">${r.year_built == null ? "–" : r.year_built}</td><td class="num">${fPct(r.occupancy_pct)}</td>
        <td class="num"><b>${fRent(r.rent_psf)}</b></td><td class="num">${fRent(r.pred_rent_psf)}</td>
        <td class="num ${r.gap_pct == null ? "" : r.gap_pct < 0 ? "neg" : "pos"}">${fSigned(r.gap_pct)}</td></tr>`).join("") : `<tr><td colspan="${COLS.length}" class="empty">No properties match your filters.</td></tr>`;
      tbl.innerHTML = head + "<tbody>" + body + "</tbody>";
      tbl.querySelectorAll("th.sortable").forEach((th) => (th.onclick = () => {
        const k = th.dataset.k; if (S.sort === k) S.order = S.order === "asc" ? "desc" : "asc"; else { S.sort = k; S.order = ["name", "market", "property_type", "building_class"].includes(k) ? "asc" : "desc"; }
        S.page = 1; load();
      }));
      tbl.querySelectorAll("tbody tr.click").forEach((tr) => (tr.onclick = () => openDrawer(tr.dataset.id)));
    } catch (e) { showError(tbl, e.message); }
  }

  function closeDrawer() {
    document.getElementById("drawer").classList.remove("open"); document.getElementById("ov").classList.remove("open");
    document.getElementById("drawer").setAttribute("aria-hidden", "true");
  }

  async function openDrawer(id) {
    const dr = document.getElementById("drawer"), body = document.getElementById("d-body");
    dr.classList.add("open"); document.getElementById("ov").classList.add("open"); dr.setAttribute("aria-hidden", "false");
    body.innerHTML = `<div class="skeleton" style="height:120px"></div><div class="skeleton" style="height:240px"></div>`;
    try {
      const d = await api("/api/properties/" + encodeURIComponent(id));
      const p = d.property;
      document.getElementById("d-title").textContent = p.name;
      document.getElementById("d-sub").textContent = `${p.property_id} · ${p.market}, ${p.state} · ${p.property_type} · Class ${p.building_class}`;
      const gap = p.pred_rent_psf ? (p.rent_psf / p.pred_rent_psf - 1) * 100 : null;
      const lo = p.pred_low, hi = p.pred_high, mx = Math.max(p.rent_psf, hi || 0) * 1.1, mn = Math.min(p.rent_psf, lo || p.rent_psf) * 0.85;
      const pos = (v) => ((v - mn) / (mx - mn)) * 100;
      body.innerHTML = `
        <div class="kpis k4">
          <div class="kpi"><div class="v">${fRent(p.rent_psf)}</div><div class="l">Actual rent / SF</div></div>
          <div class="kpi"><div class="v">${fRent(p.pred_rent_psf)}</div><div class="l">Model estimate</div><div class="d ${gap == null ? "" : gap < 0 ? "down" : "up"}">${fSigned(gap)} vs model</div></div>
          <div class="kpi"><div class="v">${fInt(p.size_sf)}</div><div class="l">Size (SF)</div></div>
          <div class="kpi"><div class="v">${fPct(p.occupancy_pct)}</div><div class="l">Occupancy</div></div>
        </div>
        <section class="card"><div class="card-h"><h3>Rent vs. model 90% interval</h3><span class="hint">out-of-fold estimate</span></div><div class="card-b">
          <div class="range-bar"><div class="fill" style="left:${pos(lo)}%;width:${pos(hi) - pos(lo)}%"></div><div class="pt" style="left:${pos(p.rent_psf)}%" title="Actual"></div></div>
          <div class="small muted" style="display:flex;justify-content:space-between"><span>${fRent(lo)}</span><span><b style="color:var(--navy)">▮</b> actual ${fRent(p.rent_psf)}</span><span>${fRent(hi)}</span></div>
          <p class="small muted" style="margin:10px 0 0">${gap != null && (p.rent_psf < lo || p.rent_psf > hi) ? "⚠ Actual rent sits outside the model's typical range — worth a manual review (data error, special lease, or genuine mispricing)." : "Actual rent is inside the model's typical range."}</p></div></section>
        <div class="grid g2">
          <section class="card"><div class="card-h"><h3>Lease expiry</h3><span class="hint">SF by year</span></div><div class="card-b"><div class="chart-box short"><canvas id="d-exp"></canvas></div></div></section>
          <section class="card"><div class="card-h"><h3>Asset facts</h3></div><div class="card-b"><table><tbody>
            ${[["Year built", p.year_built == null ? "–" : p.year_built], ["Floors", p.floors == null ? "–" : p.floors], ["Parking / 1,000 SF", p.parking_ratio == null ? "–" : fDec(p.parking_ratio)],
               ["Transit score", p.transit_score == null ? "–" : p.transit_score], ["Walk score", p.walk_score == null ? "–" : p.walk_score], ["Amenities score", p.amenities_score == null ? "–" : p.amenities_score]]
              .map(([k, v]) => `<tr><td class="muted">${k}</td><td class="num"><b>${v}</b></td></tr>`).join("")}</tbody></table></div></section>
        </div>
        <section class="card"><div class="card-h"><h3>Tenants (${d.leases.length})</h3></div><div class="card-b flush tbl-wrap" style="max-height:280px"><table>
          <thead><tr><th>Tenant</th><th>Industry</th><th class="num">Area SF</th><th class="num">Rent</th><th>Expires</th></tr></thead><tbody>
          ${d.leases.map((l) => `<tr><td><b>${esc(l.tenant)}</b></td><td>${esc(l.industry)}</td><td class="num">${fInt(l.area_sf)}</td><td class="num">${fRent(l.rent_psf)}</td><td>${esc(l.expiry_date)}</td></tr>`).join("")}</tbody></table></div></section>
        <section class="card"><div class="card-h"><h3>Comparable properties</h3><span class="hint">same market &amp; type, nearest size</span></div><div class="card-b flush tbl-wrap"><table>
          <thead><tr><th>Property</th><th>Class</th><th class="num">Size SF</th><th class="num">Occ.</th><th class="num">Rent</th></tr></thead><tbody>
          ${d.comps.map((c) => `<tr class="click" data-id="${esc(c.property_id)}"><td><b>${esc(c.name)}</b></td><td>${esc(c.building_class)}</td><td class="num">${fInt(c.size_sf)}</td><td class="num">${fPct(c.occupancy_pct)}</td><td class="num">${fRent(c.rent_psf)}</td></tr>`).join("")}</tbody></table></div></section>`;
      body.querySelectorAll("tr.click").forEach((tr) => (tr.onclick = () => openDrawer(tr.dataset.id)));
      chart("d-exp", { type: "bar", data: { labels: d.expiry.map((e) => e.bucket), datasets: [{ data: d.expiry.map((e) => e.area_sf), backgroundColor: PAL.blue }] },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: "#f0f3f6" }, ticks: { callback: (v) => fCompact(v) } }, x: { grid: { display: false } } } } });
    } catch (e) { showError(body, e.message); }
  }

  init();
})();
