"""PropIQ API + static dashboard.   Run:  uvicorn app.main:app --port 8000"""
import json
import sqlite3
import sys
from contextlib import asynccontextmanager
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import (AS_OF_DATE, BUILDING_CLASSES, DB_PATH, DOCS_MANIFEST_PATH, MARKETS, METRICS_PATH, MODEL_PATH,
                     PIPELINE_REPORT_PATH, PROPERTY_TYPES, RAG_EVAL_PATH, ROOT, STATIC_DIR)
from .features import make_features
from .rag import RagIndex

STATE = {}


def ensure_artifacts():
    needed = [DB_PATH, MODEL_PATH, METRICS_PATH, RAG_EVAL_PATH, DOCS_MANIFEST_PATH, PIPELINE_REPORT_PATH]
    if all(p.exists() for p in needed):
        return
    print("[startup] artifacts missing -> running full build (about 30-60 seconds)...")
    sys.path.insert(0, str(ROOT))
    from scripts import build_all
    build_all.main()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_artifacts()
    STATE["bundle"] = joblib.load(MODEL_PATH)
    STATE["rag"] = RagIndex()
    con = sqlite3.connect(DB_PATH)
    STATE["props"] = pd.read_sql_query("SELECT * FROM properties", con)
    con.close()
    p = STATE["props"]
    STATE["defaults"] = {c: float(p[c].median()) for c in ["floors", "parking_ratio", "transit_score", "walk_score", "amenities_score"]}
    yield


app = FastAPI(title="PropIQ - AI-powered Commercial Property Intelligence", version="1.0", lifespan=lifespan)


# ------------------------------------------------------------------ helpers
def db():
    con = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def q(sql: str, params=()):
    con = db()
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def one(sql: str, params=()):
    rows = q(sql, params)
    return rows[0] if rows else {}


def flt(market, property_type, building_class, alias="p"):
    parts, params = [], []
    for col, val in (("market", market), ("property_type", property_type), ("building_class", building_class)):
        if val:
            parts.append(f"{alias}.{col} = ?")
            params.append(val)
    return (" WHERE " + " AND ".join(parts)) if parts else "", params


def f(x, nd=2):
    return None if x is None else round(float(x), nd)


# ------------------------------------------------------------------ meta
@app.get("/api/health")
def health():
    return {"status": "ok", "properties": int(len(STATE["props"])), "model": STATE["bundle"]["name"], "as_of": AS_OF_DATE}


@app.get("/api/filters")
def filters():
    return {"markets": sorted(MARKETS), "property_types": PROPERTY_TYPES, "building_classes": BUILDING_CLASSES, "as_of": AS_OF_DATE}


# ------------------------------------------------------------------ overview
@app.get("/api/overview")
def overview(market: Optional[str] = None, property_type: Optional[str] = None, building_class: Optional[str] = None):
    where, params = flt(market, property_type, building_class)
    k = one(f"SELECT COUNT(*) n, SUM(p.size_sf) gla, SUM(p.rent_psf*p.size_sf)/SUM(p.size_sf) war, "
            f"SUM(p.occupied_sf)*100.0/SUM(p.size_sf) occ FROM properties p{where}", params)
    if not k.get("n"):
        raise HTTPException(404, "No properties match these filters")
    lj = f"FROM leases l JOIN properties p ON p.property_id = l.property_id{where}"
    lk = one(f"SELECT COUNT(*) n, SUM(l.area_sf*l.rent_psf) roll, SUM(l.area_sf) leased {lj}", params)

    exp_rows = q(f"SELECT CASE WHEN CAST(strftime('%Y', l.expiry_date) AS INTEGER) >= 2032 THEN '2032+' ELSE strftime('%Y', l.expiry_date) END AS bucket, "
                 f"SUM(l.area_sf) area, SUM(l.area_sf*l.rent_psf) rent, COUNT(*) n {lj} GROUP BY bucket ORDER BY bucket", params)
    by = {r["bucket"]: r for r in exp_rows}
    total_area = sum(r["area"] for r in exp_rows) or 1
    expiry, cum = [], 0.0
    for b in ["2026", "2027", "2028", "2029", "2030", "2031", "2032+"]:
        r = by.get(b, {"area": 0, "rent": 0, "n": 0})
        cum += r["area"]
        expiry.append({"bucket": b, "area_sf": r["area"], "rent_usd": r["rent"], "leases": r["n"], "cum_pct": round(cum / total_area * 100, 1)})

    ind = q(f"SELECT l.industry, SUM(l.area_sf) area, SUM(l.area_sf*l.rent_psf) rent {lj} GROUP BY l.industry ORDER BY area DESC", params)
    ta, tr = sum(r["area"] for r in ind) or 1, sum(r["rent"] for r in ind) or 1
    industry = [{"industry": r["industry"], "area_sf": r["area"], "rent_usd": r["rent"],
                 "pct_area": round(r["area"] / ta * 100, 1), "pct_rent": round(r["rent"] / tr * 100, 1)} for r in ind]

    markets = q(f"SELECT p.market, m.state, m.lat, m.lon, COUNT(*) properties, SUM(p.size_sf) gla, SUM(p.rent_psf*p.size_sf)/SUM(p.size_sf) avg_rent, "
                f"SUM(p.occupied_sf)*100.0/SUM(p.size_sf) occupancy FROM properties p JOIN markets m ON m.market = p.market{where} GROUP BY p.market ORDER BY gla DESC", params)
    avm = q(f"SELECT p.market, AVG(p.rent_psf) actual, AVG(pr.pred_rent_psf) model, COUNT(*) n FROM properties p "
            f"JOIN property_predictions pr ON pr.property_id = p.property_id{where} GROUP BY p.market ORDER BY n DESC", params)
    by_type = q(f"SELECT p.property_type, COUNT(*) n, SUM(p.size_sf) gla, AVG(p.rent_psf) avg_rent, SUM(p.occupied_sf)*100.0/SUM(p.size_sf) occupancy "
                f"FROM properties p{where} GROUP BY p.property_type ORDER BY gla DESC", params)

    occ = [r["occupancy_pct"] for r in q(f"SELECT p.occupancy_pct FROM properties p{where}", params)]
    counts, edges = np.histogram(occ, bins=np.arange(45, 105, 5))
    gap_sql = (f"SELECT p.property_id, p.name, p.market, p.property_type, p.building_class, p.size_sf, p.rent_psf, pr.pred_rent_psf, "
               f"(p.rent_psf - pr.pred_rent_psf)*100.0/pr.pred_rent_psf AS gap_pct FROM properties p "
               f"JOIN property_predictions pr ON pr.property_id = p.property_id{where} ORDER BY gap_pct {{o}} LIMIT 6")
    return {
        "kpis": {"gla_sf": k["gla"], "properties": k["n"], "tenants": lk["n"], "wa_rent_psf": f(k["war"]), "occupancy_pct": f(k["occ"], 1),
                 "rent_roll_usd": lk["roll"], "leased_sf": lk["leased"]},
        "expiry": expiry, "industry": industry, "markets": markets, "actual_vs_model": avm, "by_type": by_type,
        "occupancy_hist": {"edges": edges.tolist(), "counts": counts.tolist()},
        "below_model": q(gap_sql.format(o="ASC"), params), "above_model": q(gap_sql.format(o="DESC"), params),
    }


# ------------------------------------------------------------------ markets
def market_table():
    t = pd.DataFrame(q("SELECT * FROM market_trends ORDER BY market, month"))
    props = STATE["props"]
    rows = []
    for m, g in t.groupby("market"):
        g = g.sort_values("month")
        last, prev = g.iloc[-1], g.iloc[-13]
        sub = props[props.market == m]
        rows.append({
            "market": m, "state": MARKETS[m][0], "properties": int(len(sub)), "gla_sf": float(sub.size_sf.sum()),
            "avg_rent_psf": f(last.avg_rent_psf), "yoy_rent_growth_pct": f((last.avg_rent_psf / prev.avg_rent_psf - 1) * 100, 2),
            "vacancy_pct": f(last.vacancy_pct, 1), "vacancy_chg_pp": f(last.vacancy_pct - prev.vacancy_pct, 1),
            "absorption_ttm_ksf": f(g.tail(12).net_absorption_ksf.sum(), 0),
            "occupancy_pct": f(float(sub.occupied_sf.sum() / sub.size_sf.sum() * 100), 1),
        })
    return sorted(rows, key=lambda r: -r["gla_sf"])


@app.get("/api/markets")
def markets():
    return {"markets": market_table()}


@app.get("/api/trends")
def trends(markets: Optional[str] = None):
    table = market_table()
    names = [m.strip() for m in markets.split(",")] if markets else [r["market"] for r in table[:5]]
    names = [m for m in names if m in MARKETS][:8]
    if not names:
        raise HTTPException(422, "No valid markets supplied")
    ph = ",".join("?" * len(names))
    rows = q(f"SELECT * FROM market_trends WHERE market IN ({ph}) ORDER BY month", names)
    months = sorted({r["month"] for r in rows})
    series = {m: {"rent": [], "vacancy": [], "absorption": []} for m in names}
    for m in names:
        d = {r["month"]: r for r in rows if r["market"] == m}
        for mo in months:
            series[m]["rent"].append(d[mo]["avg_rent_psf"]); series[m]["vacancy"].append(d[mo]["vacancy_pct"])
            series[m]["absorption"].append(d[mo]["net_absorption_ksf"])
    return {"months": months, "series": series}


@app.get("/api/market-matrix")
def market_matrix():
    return {"rows": q("SELECT market, property_type, AVG(rent_psf) avg_rent, COUNT(*) n FROM properties GROUP BY market, property_type")}


BIN_VARS = {"age": "Building age (years)", "transit_score": "Transit score", "amenities_score": "Amenities score",
            "occupancy_pct": "Occupancy (%)", "size_sf": "Building size (SF)"}


@app.get("/api/analysis/binned")
def binned(x: str = "age", property_type: str = "Office"):
    if x not in BIN_VARS:
        raise HTTPException(422, f"x must be one of {list(BIN_VARS)}")
    df = STATE["props"]
    df = df[df.property_type == property_type].dropna(subset=[x])
    if len(df) < 30:
        raise HTTPException(404, "Not enough rows for this property type")
    cut = pd.qcut(df[x], 6, duplicates="drop")
    codes = cut.cat.codes.to_numpy()
    cats = list(cut.cat.categories)

    def fmt(v):
        return f"{v / 1000:.0f}K" if x == "size_sf" else f"{v:.0f}"
    labels = [f"{fmt(iv.left)}-{fmt(iv.right)}" for iv in cats]
    out = {}
    for cl in BUILDING_CLASSES:
        vals = []
        for i in range(len(cats)):
            sel = df[(codes == i) & (df.building_class.to_numpy() == cl)]
            vals.append(f(sel.rent_psf.mean()) if len(sel) >= 5 else None)
        out[cl] = vals
    return {"x": x, "x_label": BIN_VARS[x], "property_type": property_type, "bins": labels, "series": out}


# ------------------------------------------------------------------ properties
SORTS = {"name": "p.name", "market": "p.market", "property_type": "p.property_type", "building_class": "p.building_class",
         "size_sf": "p.size_sf", "year_built": "p.year_built", "occupancy_pct": "p.occupancy_pct",
         "rent_psf": "p.rent_psf", "pred_rent_psf": "pr.pred_rent_psf", "gap_pct": "gap_pct"}


@app.get("/api/properties")
def properties(q_text: Optional[str] = Query(None, alias="q"), market: Optional[str] = None, property_type: Optional[str] = None,
               building_class: Optional[str] = None, sort: str = "size_sf", order: str = "desc",
               page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100)):
    where, params = flt(market, property_type, building_class)
    if q_text:
        like = f"%{q_text.strip()}%"
        cond = ("(p.name LIKE ? OR p.market LIKE ? OR p.property_id LIKE ? OR "
                "p.property_id IN (SELECT property_id FROM leases WHERE tenant LIKE ?))")
        where = (where + " AND " if where else " WHERE ") + cond
        params += [like, like, like, like]
    col = SORTS.get(sort, "p.size_sf")
    direction = "ASC" if order.lower() == "asc" else "DESC"
    base = "FROM properties p LEFT JOIN property_predictions pr ON pr.property_id = p.property_id"
    total = one(f"SELECT COUNT(*) n {base}{where}", params)["n"]
    rows = q(f"SELECT p.property_id, p.name, p.market, p.state, p.property_type, p.building_class, p.size_sf, p.year_built, p.occupancy_pct, "
             f"p.rent_psf, pr.pred_rent_psf, (p.rent_psf - pr.pred_rent_psf)*100.0/pr.pred_rent_psf AS gap_pct {base}{where} "
             f"ORDER BY {col} {direction}, p.property_id LIMIT ? OFFSET ?", params + [page_size, (page - 1) * page_size])
    return {"total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size)), "rows": rows}


@app.get("/api/properties/{property_id}")
def property_detail(property_id: str):
    p = one("SELECT p.*, pr.pred_rent_psf, pr.pred_low, pr.pred_high FROM properties p "
            "LEFT JOIN property_predictions pr ON pr.property_id = p.property_id WHERE p.property_id = ?", (property_id,))
    if not p:
        raise HTTPException(404, "Property not found")
    leases = q("SELECT lease_id, tenant, industry, area_sf, rent_psf, expiry_date, lease_type, escalation_pct, renewal_option "
               "FROM leases WHERE property_id = ? ORDER BY area_sf DESC", (property_id,))
    comps = q("SELECT property_id, name, building_class, size_sf, occupancy_pct, rent_psf FROM properties WHERE market = ? AND property_type = ? "
              "AND property_id != ? ORDER BY (building_class != ?), ABS(size_sf - ?) LIMIT 5",
              (p["market"], p["property_type"], property_id, p["building_class"], p["size_sf"]))
    exp = {}
    for l in leases:
        y = min(int(l["expiry_date"][:4]), 2032)
        exp[y] = exp.get(y, 0) + l["area_sf"]
    expiry = [{"bucket": (str(y) if y < 2032 else "2032+"), "area_sf": exp.get(y, 0)} for y in range(2026, 2033)]
    return {"property": p, "leases": leases, "comps": comps, "expiry": expiry}


# ------------------------------------------------------------------ prediction
class PredictIn(BaseModel):
    market: str
    property_type: str
    building_class: str
    year_built: int = Field(ge=1850, le=2027)
    size_sf: float = Field(ge=1000, le=5_000_000)
    occupancy_pct: float = Field(ge=0, le=100)
    floors: Optional[float] = Field(None, ge=1, le=120)
    parking_ratio: Optional[float] = Field(None, ge=0, le=15)
    transit_score: Optional[float] = Field(None, ge=0, le=100)
    walk_score: Optional[float] = Field(None, ge=0, le=100)
    amenities_score: Optional[float] = Field(None, ge=0, le=100)


def model_predict(rows):
    return STATE["bundle"]["model"].predict(make_features(pd.DataFrame(rows)))


@app.post("/api/predict")
def predict(body: PredictIn):
    if body.market not in MARKETS:
        raise HTTPException(422, f"Unknown market '{body.market}'")
    if body.property_type not in PROPERTY_TYPES:
        raise HTTPException(422, f"Unknown property_type '{body.property_type}'")
    if body.building_class not in BUILDING_CLASSES:
        raise HTTPException(422, f"Unknown building_class '{body.building_class}'")
    row, assumed = body.model_dump(), {}
    for k, v in STATE["defaults"].items():
        if row.get(k) is None:
            row[k] = v
            assumed[k] = round(v, 1)
    base = float(model_predict([row])[0])
    rel = STATE["bundle"]["interval_rel_90"]

    def variant(**kw):
        r = dict(row); r.update(kw); return r
    age_yb = row["year_built"]
    specs = [
        ("Amenities score", variant(amenities_score=max(0, row["amenities_score"] - 15)), variant(amenities_score=min(100, row["amenities_score"] + 15)), "-15 pts", "+15 pts"),
        ("Transit score", variant(transit_score=max(0, row["transit_score"] - 15)), variant(transit_score=min(100, row["transit_score"] + 15)), "-15 pts", "+15 pts"),
        ("Occupancy", variant(occupancy_pct=max(0, row["occupancy_pct"] - 10)), variant(occupancy_pct=min(100, row["occupancy_pct"] + 10)), "-10 pts", "+10 pts"),
        ("Building age", variant(year_built=max(1850, age_yb - 15)), variant(year_built=min(2027, age_yb + 15)), "15 yrs older", "15 yrs newer"),
        ("Building size", variant(size_sf=row["size_sf"] * 2), variant(size_sf=max(1000, row["size_sf"] / 2)), "2x larger", "half the size"),
    ]
    rows = [r for s in specs for r in (s[1], s[2])]
    preds = model_predict(rows)
    tornado = [{"driver": s[0], "low_label": s[3], "high_label": s[4], "low_delta": float(preds[2 * i] - base), "high_delta": float(preds[2 * i + 1] - base)}
               for i, s in enumerate(specs)]
    cls_preds = model_predict([variant(building_class=c) for c in BUILDING_CLASSES])
    props = STATE["props"]
    seg = props[(props.market == body.market) & (props.property_type == body.property_type)]
    med = float(seg.rent_psf.median()) if len(seg) else None
    comps = q("SELECT property_id, name, building_class, size_sf, occupancy_pct, year_built, rent_psf FROM properties WHERE market = ? AND property_type = ? "
              "ORDER BY (building_class != ?), ABS(size_sf - ?) LIMIT 6", (body.market, body.property_type, body.building_class, body.size_sf))
    return {
        "predicted_rent_psf": round(base, 2), "low": round(base * (1 - rel), 2), "high": round(base * (1 + rel), 2), "interval_level": 0.90,
        "annual_rent_usd": round(base * body.size_sf), "segment_median_psf": f(med), "segment_n": int(len(seg)),
        "vs_segment_pct": f((base / med - 1) * 100, 1) if med else None,
        "by_class": {c: round(float(v), 2) for c, v in zip(BUILDING_CLASSES, cls_preds)}, "tornado": tornado,
        "assumed_inputs": assumed, "comps": comps, "model": STATE["bundle"]["name"],
    }


# ------------------------------------------------------------------ model / rag / data pages
@app.get("/api/model/metrics")
def model_metrics():
    return json.loads(METRICS_PATH.read_text())


@app.get("/api/rag/eval")
def rag_eval():
    return json.loads(RAG_EVAL_PATH.read_text())


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    k: int = Field(5, ge=1, le=8)
    use_llm: bool = True


@app.post("/api/ask")
def ask(body: AskIn):
    return STATE["rag"].ask(body.question.strip(), k=body.k, use_llm=body.use_llm)


@app.get("/api/documents")
def documents(type: Optional[str] = None, q: Optional[str] = None):
    docs = STATE["rag"].manifest
    if type:
        docs = [d for d in docs if d["doc_type"] == type]
    if q:
        ql = q.lower()
        docs = [d for d in docs if ql in d["title"].lower() or ql in d["meta"].lower()]
    return {"total": len(docs), "documents": [{k: d[k] for k in ("doc_id", "title", "doc_type", "meta")} for d in docs]}


@app.get("/api/documents/{doc_id}")
def document(doc_id: str):
    d = STATE["rag"].document(doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    return d


@app.get("/api/pipeline")
def pipeline_report():
    return json.loads(PIPELINE_REPORT_PATH.read_text())


@app.get("/api/schema")
def schema():
    out = []
    con = db()
    try:
        for t in ["properties", "leases", "market_trends", "markets", "property_predictions"]:
            cols = [{"name": r["name"], "type": r["type"]} for r in con.execute(f"PRAGMA table_info({t})").fetchall()]
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            out.append({"table": t, "rows": n, "columns": cols})
    finally:
        con.close()
    return {"tables": out}


# Static dashboard (must be mounted LAST so /api routes win)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
