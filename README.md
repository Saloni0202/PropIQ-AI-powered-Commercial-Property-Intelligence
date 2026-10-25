# PropIQ — AI-powered Commercial Property Intelligence

End-to-end portfolio project: data cleaning (Pandas + SQL) → rent regression with honest evaluation → RAG over lease/market/property documents → FastAPI + a 7-page dashboard.

> All data is **synthetic** (seeded, reproducible). The goal is a sound evaluation process and clearly stated limitations, not scale.

## Run locally (5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/build_all.py        # generate data -> clean -> docs -> train -> evaluate (~30 s)
uvicorn app.main:app --port 8000   # open http://localhost:8000
pytest -q                          # optional: 25 tests (pip install pytest)
```
If you skip `build_all.py`, the app builds everything automatically on first start.

## Pages
| Page | What it shows |
|---|---|
| Overview | KPIs, lease-expiry profile, industry mix, actual vs model rent, US map, largest gaps vs model |
| Markets | 36-month rent/vacancy/absorption trends, scorecard, heatmap, rent drivers |
| Properties | Search/sort/filter 1,766 assets; drawer with tenants, comps, model interval |
| Rent Predictor | Live estimate with 90% range, class what-if, sensitivity chart, comps |
| Model Evaluation | Baselines vs models, CV vs test, residuals, importance, error by market, limitations |
| Document Q&A | RAG answers with numbered citations, evidence cards, retrieval metrics, abstention |
| Data & Pipeline | Cleaning funnel, SQL used, quality issues, schema |

## How the pieces work
1. `scripts/generate_data.py` – 1,800 properties, 8k leases, 36 months × 20 markets; then injects realistic mess (duplicates, case/whitespace, missing values, ×10 rent typos, occupancy > 100).
2. `scripts/pipeline.py` – Pandas standardises text; SQL `ROW_NUMBER()` window de-duplicates; CASE checks count issues; a validation filter builds the clean table (SQLite).
3. `scripts/build_docs.py` – 125 documents (80 lease abstracts, 20 market reports, 25 property reports) generated from the clean DB so every number is checkable.
4. `scripts/train.py` – 80/20 stratified split; 5-fold CV on train picks the model; test set used once. Baselines: global median and market×type×class median. Models: Ridge, Random Forest, Gradient Boosting (log target). Metrics: MAE, RMSE, R², MAPE. 90% interval from out-of-fold relative errors, coverage checked on test. Permutation importance, error by segment.
5. `app/rag.py` + `scripts/eval_rag.py` – TF-IDF retrieval over section chunks, extractive cited answers (optional LLM synthesis if `ANTHROPIC_API_KEY` is set), abstains below a score threshold. Evaluated with 75 questions of known source + 10 off-topic questions.
6. `app/main.py` – FastAPI (`/docs` shows interactive API docs) serving JSON + the static dashboard.

## Deploy
**Render (free, easiest):** push this folder to GitHub → Render → New → Blueprint → select repo (uses `render.yaml` + `Dockerfile`). Build takes ~3–5 min; model and data are built during the image build.

**Railway / Fly.io / any Docker host:** `docker build -t propiq . && docker run -p 8000:8000 propiq`.

**Optional LLM answers:** set env var `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`). Without it the app uses extractive answers — nothing breaks.

## Honest limitations (say these in interviews)
- Synthetic data: scores prove the pipeline, not real-world accuracy.
- Rent model is cross-sectional (today's rent), not a forecast; no time/spatial split.
- 90% interval uses one average relative error; volatile segments are under-covered.
- RAG eval uses templated questions that name entities, so near-100% retrieval is an upper bound.
- TF-IDF has no semantic understanding; production would use embeddings + re-ranking + LLM with citation checks.

## Swap in real data
Replace `raw_properties.csv` / `leases.csv` / `market_trends.csv` with your own (same columns), rerun `python scripts/build_all.py`. Good public sources: NYC PLUTO / Rolling Sales, Zillow Research, HUD, Kaggle commercial-property listings, SEC EDGAR REIT 10-K filings (for RAG documents).
