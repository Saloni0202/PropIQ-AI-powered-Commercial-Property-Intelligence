(function () {
  const NICE = { market: "Market", property_type: "Property type", building_class: "Building class", age: "Building age", log_size_sf: "Size (log SF)", floors: "Floors",
    occupancy_pct: "Occupancy", parking_ratio: "Parking ratio", transit_score: "Transit score", walk_score: "Walk score", amenities_score: "Amenities score" };

  async function init() {
    try {
      const m = await api("/api/model/metrics");
      render(m);
    } catch (e) { toast(e.message); }
  }

  function render(m) {
    const t = m.test, ds = m.dataset;
    document.getElementById("m-kpis").innerHTML = `
      <div class="kpi"><div class="v">$${fDec(t.mae)}</div><div class="l">Test MAE ($/SF)</div><div class="d">typical miss</div></div>
      <div class="kpi"><div class="v">$${fDec(t.rmse)}</div><div class="l">Test RMSE ($/SF)</div><div class="d">penalises big misses</div></div>
      <div class="kpi"><div class="v">${fDec(t.r2, 3)}</div><div class="l">Test R²</div><div class="d">share of variance explained</div></div>
      <div class="kpi"><div class="v">${fPct(t.mape)}</div><div class="l">Test MAPE</div><div class="d">average % error</div></div>
      <div class="kpi"><div class="v pos">−${fDec(m.improvement_vs_best_baseline_rmse_pct, 0)}%</div><div class="l">RMSE vs best baseline</div><div class="d">${esc(m.best_baseline.replace("Baseline: ", ""))}</div></div>`;

    document.getElementById("cmp").innerHTML = `<thead><tr><th>Model</th><th class="num">CV MAE</th><th class="num">CV RMSE</th><th class="num">CV R²</th><th class="num">Test MAE</th><th class="num">Test RMSE</th><th class="num">Test R²</th><th></th></tr></thead><tbody>` +
      m.comparison.map((r) => `<tr style="${r.selected ? "background:#f1f7fe" : ""}"><td><b>${esc(r.model)}</b> ${r.is_baseline ? '<span class="badge">baseline</span>' : ""}</td>
        <td class="num">${fDec(r.cv_mae)}</td><td class="num">${fDec(r.cv_rmse)}</td><td class="num">${fDec(r.cv_r2, 3)}</td>
        <td class="num">${fDec(r.test_mae)}</td><td class="num">${fDec(r.test_rmse)}</td><td class="num">${fDec(r.test_r2, 3)}</td>
        <td>${r.selected ? '<span class="badge green">selected on CV</span>' : ""}</td></tr>`).join("") + "</tbody>";

    chart("c-cmp", {
      type: "bar",
      data: { labels: m.comparison.map((r) => r.model.replace(" (log target)", "").replace("Baseline: ", "Base: ")), datasets: [{ data: m.comparison.map((r) => r.test_rmse), backgroundColor: m.comparison.map((r) => (r.selected ? PAL.blue : r.is_baseline ? PAL.grey : PAL.lblue)) }] },
      options: { indexAxis: "y", layout: { padding: { right: 46 } }, plugins: { legend: { display: false } }, scales: { x: { display: false, beginAtZero: true }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } } },
      plugins: [endLabels((v) => "$" + v.toFixed(2))],
    });

    const mx = Math.max(...m.scatter.map((p) => Math.max(p.actual, p.pred)));
    chart("c-sc", {
      type: "scatter",
      data: { datasets: [
        { label: "Test properties", data: m.scatter.map((p) => ({ x: p.actual, y: p.pred })), backgroundColor: PAL.blue + "88", pointRadius: 3.2 },
        { label: "Perfect prediction", type: "line", data: [{ x: 0, y: 0 }, { x: mx, y: mx }], borderColor: PAL.navy, borderDash: [5, 5], borderWidth: 1.5, pointRadius: 0 }] },
      options: { scales: { x: { title: { display: true, text: "Actual $/SF" }, grid: { color: "#f0f3f6" } }, y: { title: { display: true, text: "Predicted $/SF" }, grid: { color: "#f0f3f6" } } },
        plugins: { tooltip: { callbacks: { label: (c) => ` actual $${c.parsed.x.toFixed(1)} → predicted $${c.parsed.y.toFixed(1)}` } } } },
    });

    const h = m.residual_hist;
    chart("c-res", {
      type: "bar",
      data: { labels: h.counts.map((_, i) => `${h.edges[i]} to ${h.edges[i + 1]}%`), datasets: [{ data: h.counts, backgroundColor: h.counts.map((_, i) => (h.edges[i] < 0 && h.edges[i + 1] <= 0 ? PAL.peach : h.edges[i] >= 0 ? PAL.lblue : PAL.blue)), categoryPercentage: 0.96, barPercentage: 0.96 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: "#f0f3f6" }, title: { display: true, text: "properties" } }, x: { grid: { display: false }, ticks: { maxRotation: 60, font: { size: 10 } } } } },
    });

    const imp = m.importance.slice(0, 10);
    chart("c-imp", {
      type: "bar",
      data: { labels: imp.map((i) => NICE[i.feature] || i.feature), datasets: [{ data: imp.map((i) => +i.importance.toFixed(3)), backgroundColor: PAL.blue }] },
      options: { indexAxis: "y", layout: { padding: { right: 44 } }, plugins: { legend: { display: false } }, scales: { x: { display: false, beginAtZero: true }, y: { grid: { display: false }, ticks: { autoSkip: false } } } },
      plugins: [endLabels((v) => "+" + v.toFixed(2))],
    });

    const bm = m.by_market.slice();
    chart("c-mk", {
      type: "bar",
      data: { labels: bm.map((r) => r.market), datasets: [{ data: bm.map((r) => +r.mape.toFixed(2)), backgroundColor: bm.map((r, i) => (i < 3 ? PAL.peach : PAL.lblue)) }] },
      options: { indexAxis: "y", layout: { padding: { right: 40 } }, plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: (c) => `n = ${bm[c.dataIndex].n} · MAE $${bm[c.dataIndex].mae.toFixed(2)}` } } },
        scales: { x: { display: false, beginAtZero: true }, y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: 11 } } } } },
      plugins: [endLabels((v) => v.toFixed(1) + "%")],
    });

    document.getElementById("t-type").innerHTML = `<thead><tr><th>Type</th><th class="num">n</th><th class="num">MAE $/SF</th><th class="num">MAPE</th></tr></thead><tbody>` +
      m.by_type.map((r) => `<tr><td><b>${esc(r.property_type)}</b></td><td class="num">${r.n}</td><td class="num">${fDec(r.mae)}</td><td class="num">${fPct(r.mape)}</td></tr>`).join("") + "</tbody>";

    const iv = m.interval;
    document.getElementById("interval").innerHTML = `<div style="display:flex;gap:30px;flex-wrap:wrap"><div><div class="big" style="font-size:34px">${fPct(iv.empirical_test_coverage * 100, 1)}</div><div class="muted small">of test properties fell inside the band</div></div>
      <div><div class="big" style="font-size:34px">±${fPct(iv.relative_half_width_final * 100, 1)}</div><div class="muted small">relative half-width of the 90% band</div></div></div>
      <p class="muted small" style="margin:10px 0 0">The band was calibrated on training-set out-of-fold errors, then checked on the untouched test set. Coverage close to the 90% target means the band is honest on average.</p>`;

    document.getElementById("method").innerHTML = [
      `<b>Data:</b> ${fInt(ds.n_properties)} cleaned properties; target = rent in $/SF/yr (mean $${fDec(ds.target_mean)}, std $${fDec(ds.target_std)}).`,
      `<b>Split:</b> ${m.meta.split} → ${fInt(ds.n_train)} train / ${fInt(ds.n_test)} test. The test set was scored once, after choosing the model.`,
      `<b>Selection:</b> ${m.meta.cv_folds}-fold cross-validation on the training set; selected <b>${esc(m.selected_model)}</b> (lowest CV RMSE).`,
      `<b>Baselines:</b> global median and market × type × class median — the "broker rule of thumb" the ML model must beat.`,
      `<b>Preprocessing:</b> median imputation + scaling + one-hot encoding fitted inside each CV fold (no leakage); log-transformed target.`,
      `<b>Features:</b> market, type, class, age, log size, floors, occupancy, parking, transit / walk / amenities scores.`,
      `<b>Serving:</b> final model refit on all rows; dashboard estimates for existing properties are out-of-fold so they are never in-sample.`,
    ].map((x) => `<li>${x}</li>`).join("");
  }

  init();
})();
