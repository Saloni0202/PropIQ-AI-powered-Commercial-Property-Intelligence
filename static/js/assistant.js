(function () {
  const $ = (id) => document.getElementById(id);
  const EXAMPLES = [
    "What is the vacancy rate in Chicago?", "What is driving leasing demand in Austin?", "Which leases have a termination right?",
    "What renewal options are common in lease abstracts?", "How much space expires within 24 months at the largest property in Dallas?", "What is the capital of France?",
  ];
  let busy = false;

  function init() {
    $("examples").innerHTML = EXAMPLES.map((e) => `<span class="chip" data-q="${esc(e)}">${esc(e)}</span>`).join("");
    $("examples").onclick = (e) => { const c = e.target.closest(".chip"); if (c) { $("qa-q").value = c.dataset.q; ask(); } };
    $("qa-form").addEventListener("submit", (e) => { e.preventDefault(); ask(); });
    $("m-close").onclick = closeModal; $("ov").onclick = closeModal;
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
    $("dtype").addEventListener("change", loadDocs);
    let t; $("dq").addEventListener("input", () => { clearTimeout(t); t = setTimeout(loadDocs, 250); });
    loadEval(); loadDocs();
  }

  async function ask() {
    const q = $("qa-q").value.trim();
    if (busy) return;
    if (q.length < 3) return toast("Please type a question (at least 3 characters).");
    busy = true; $("qa-go").disabled = true; $("qa-go").textContent = "Searching…";
    $("qa-out").innerHTML = `<div class="skeleton" style="height:120px"></div>`;
    try {
      const d = await post("/api/ask", { question: q, k: 5, use_llm: true });
      renderAnswer(d); renderEvidence(d);
    } catch (e) { showError($("qa-out"), e.message); }
    busy = false; $("qa-go").disabled = false; $("qa-go").textContent = "Ask";
  }

  function renderAnswer(d) {
    const html = esc(d.answer).replace(/\[(\d+)\]/g, (m, n) => `<span class="cite" data-n="${n}">${n}</span>`);
    const modeBadge = d.mode === "llm" ? `<span class="badge violet">LLM answer, grounded in sources</span>` : d.mode === "extractive" ? `<span class="badge blue">extractive · quoted from sources</span>` : `<span class="badge amber">no evidence found</span>`;
    $("qa-out").innerHTML = `<div class="answer ${d.abstained ? "abstain" : ""}">${html}</div>
      <div class="toolbar" style="margin-top:10px">${modeBadge}<span class="muted small">top retrieval score ${fDec(d.confidence, 2)} (abstains below 0.12)</span></div>`;
    $("qa-out").querySelectorAll(".cite").forEach((c) => (c.onclick = () => {
      const el = document.getElementById("src-" + c.dataset.n); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
    }));
  }

  function renderEvidence(d) {
    $("ev-hint").textContent = `${d.sources.length} passages retrieved`;
    const mx = Math.max(...d.sources.map((s) => s.score), 0.001);
    $("evidence").innerHTML = d.sources.map((s) => `<div class="src" id="src-${s.n}"><div class="t"><span><span class="cite" style="cursor:default">${s.n}</span> ${esc(s.title)}</span><span class="badge">${esc(s.doc_type)}</span></div>
      <div class="muted small" style="margin-bottom:4px">${esc(s.section)}</div><div class="tx">${esc(s.text)}</div>
      <div class="score"><i style="width:${(s.score / mx * 100).toFixed(0)}%"></i></div>
      <div class="toolbar" style="justify-content:space-between;margin-top:6px"><span class="muted small">relevance ${fDec(s.score, 3)}</span><a href="#" data-doc="${esc(s.doc_id)}" class="small">Open full document →</a></div></div>`).join("");
    $("evidence").querySelectorAll("a[data-doc]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); openDoc(a.dataset.doc); }));
  }

  async function loadEval() {
    try {
      const e = await api("/api/rag/eval"), o = e.overall, a = e.abstention;
      const tile = (v, l) => `<div class="kpi" style="box-shadow:none"><div class="v">${v}</div><div class="l">${l}</div></div>`;
      $("rag-eval").innerHTML = `<div class="kpis k4" style="margin-bottom:12px">${tile(fPct(o["hit@1"] * 100, 0), "Hit@1")}${tile(fPct(o["hit@3"] * 100, 0), "Hit@3")}${tile(fDec(o.mrr, 2), "MRR")}${tile(`${a.out_of_scope_refused}/${a.out_of_scope_n}`, "Off-topic refused")}</div>
        <table><thead><tr><th>Question type</th><th class="num">n</th><th class="num">Hit@1</th><th class="num">Hit@3</th><th class="num">MRR</th></tr></thead><tbody>
        ${Object.entries(e.by_type).map(([k, v]) => `<tr><td><b>${esc(k)}</b></td><td class="num">${v.n}</td><td class="num">${fPct(v["hit@1"] * 100, 0)}</td><td class="num">${fPct(v["hit@3"] * 100, 0)}</td><td class="num">${fDec(v.mrr, 2)}</td></tr>`).join("")}</tbody></table>
        <div class="note" style="margin-top:12px"><b>Read with care.</b> ${esc(e.caveat)}</div>`;
    } catch (err) { showError($("rag-eval"), err.message); }
  }

  async function loadDocs() {
    const qs = new URLSearchParams(); if ($("dtype").value) qs.set("type", $("dtype").value); if ($("dq").value.trim()) qs.set("q", $("dq").value.trim());
    try {
      const d = await api("/api/documents?" + qs);
      $("docs").innerHTML = `<thead><tr><th>Title</th><th>Type</th></tr></thead><tbody>` + (d.documents.length ? d.documents.map((x) => `<tr class="click" data-id="${esc(x.doc_id)}"><td>${esc(x.title)}</td><td><span class="badge">${esc(x.doc_type)}</span></td></tr>`).join("") : `<tr><td colspan="2" class="empty">No documents match.</td></tr>`) + "</tbody>";
      $("docs").querySelectorAll("tr.click").forEach((tr) => (tr.onclick = () => openDoc(tr.dataset.id)));
    } catch (e) { showError($("docs"), e.message); }
  }

  async function openDoc(id) {
    try {
      const d = await api("/api/documents/" + encodeURIComponent(id));
      $("m-title").textContent = d.title; $("m-meta").textContent = d.meta;
      const lines = d.text.split("\n").slice(2);
      $("m-body").innerHTML = lines.map((l) => (l.startsWith("## ") ? `<h2>${esc(l.slice(3))}</h2>` : l.trim() ? `<p>${esc(l)}</p>` : "")).join("");
      $("modal").classList.add("open"); $("ov").classList.add("open");
    } catch (e) { toast(e.message); }
  }
  function closeModal() { $("modal").classList.remove("open"); $("ov").classList.remove("open"); }

  init();
})();
