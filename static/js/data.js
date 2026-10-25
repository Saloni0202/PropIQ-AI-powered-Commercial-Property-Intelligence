(function () {
  const $ = (id) => document.getElementById(id);
  async function init() {
    try {
      const [p, s] = await Promise.all([api("/api/pipeline"), api("/api/schema")]);
      render(p); renderSchema(s);
    } catch (e) { toast(e.message); }
  }
  function render(p) {
    const steps = [
      ["Raw export", p.raw_rows, "rows loaded"], ["Text fixed", p.text_values_standardised, "values standardised"], ["De-duplicated", p.after_dedupe_rows, `${p.duplicates_removed} duplicates removed`],
      ["Validated", p.final_rows, `${p.rows_dropped_validation} invalid dropped`], ["Leases linked", p.lease_rows, "lease records"], ["Trend rows", p.trend_rows, "market-month rows"],
    ];
    $("funnel").innerHTML = steps.map(([t, n, s], i) => `<div class="step"><div class="n">${i + 1}</div><b>${t}</b><div class="c">${fInt(n)}</div><small>${s}</small></div>`).join("");
    const q = p.quality_flags;
    const labels = ["Missing rent", "Rent out of range", "Impossible occupancy", "Unmapped category"], vals = [q.missing_rent, q.rent_out_of_range, q.bad_occupancy, q.unmapped_category];
    chart("c-dq", { type: "bar", data: { labels: ["Duplicate rows", ...labels], datasets: [{ data: [p.duplicates_removed, ...vals], backgroundColor: [PAL.amber, PAL.red, PAL.red, PAL.red, PAL.red] }] },
      options: { indexAxis: "y", layout: { padding: { right: 30 } }, plugins: { legend: { display: false } }, scales: { x: { display: false, beginAtZero: true }, y: { grid: { display: false } } } }, plugins: [endLabels((v) => String(v))] });
    $("dq-note").textContent = "Rent outside $3–$250/SF (typos such as ×10) and occupancy above 100% are removed rather than silently 'fixed', because guessing the right value would bias the model.";
    const mv = p.missing_values_in_features;
    chart("c-miss", { type: "bar", data: { labels: Object.keys(mv).map((k) => k.replace(/_/g, " ")), datasets: [{ data: Object.values(mv), backgroundColor: PAL.teal }] },
      options: { layout: { padding: { top: 18 } }, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: "#f0f3f6" } }, x: { grid: { display: false }, ticks: { font: { size: 11 } } } } }, plugins: [endLabels((v) => String(v))] });
    $("miss-note").textContent = p.missing_value_policy;
    $("sql1").textContent = p.sql.dedupe; $("sql2").textContent = p.sql.validation_filter;
  }
  function renderSchema(s) {
    $("schema").innerHTML = s.tables.map((t) => `<div class="card" style="box-shadow:none"><div class="card-h"><h3 class="mono" style="font-size:14px">${esc(t.table)}</h3><span class="badge blue">${fInt(t.rows)} rows</span></div>
      <div class="card-b flush tbl-wrap" style="max-height:230px"><table><tbody>${t.columns.map((c) => `<tr><td class="mono small">${esc(c.name)}</td><td class="muted small">${esc(c.type || "")}</td></tr>`).join("")}</tbody></table></div></div>`).join("");
  }
  init();
})();
