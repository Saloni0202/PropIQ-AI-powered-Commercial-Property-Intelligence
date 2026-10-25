"""Smoke + correctness tests.  Run:  pytest -q"""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import DB_PATH, METRICS_PATH
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


GET = ["/api/health", "/api/filters", "/api/overview", "/api/markets", "/api/trends", "/api/market-matrix", "/api/analysis/binned?x=age",
       "/api/properties", "/api/model/metrics", "/api/rag/eval", "/api/documents", "/api/pipeline", "/api/schema"]


@pytest.mark.parametrize("path", GET)
def test_get_ok(client, path):
    assert client.get(path).status_code == 200


def test_pages_served(client):
    for p in ["/", "/markets.html", "/properties.html", "/predict.html", "/model.html", "/assistant.html", "/data.html"]:
        r = client.get(p)
        assert r.status_code == 200 and "PropIQ" in r.text


def test_no_duplicates_in_clean_table():
    con = sqlite3.connect(DB_PATH)
    dup = con.execute("SELECT COUNT(*) FROM (SELECT lower(trim(name)), market, size_sf FROM properties GROUP BY 1,2,3 HAVING COUNT(*)>1)").fetchone()[0]
    bad = con.execute("SELECT COUNT(*) FROM properties WHERE rent_psf NOT BETWEEN 3 AND 250 OR occupancy_pct NOT BETWEEN 0 AND 100").fetchone()[0]
    assert dup == 0 and bad == 0


def test_model_beats_baseline():
    m = json.loads(METRICS_PATH.read_text())
    base = min(r["test_rmse"] for r in m["comparison"] if r["is_baseline"])
    assert m["test"]["rmse"] < base
    assert 0.80 <= m["interval"]["empirical_test_coverage"] <= 0.98


def test_predict_valid_and_monotone_in_class(client):
    body = dict(market="Chicago", property_type="Office", building_class="A", year_built=2015, size_sf=120000, occupancy_pct=88)
    d = client.post("/api/predict", json=body).json()
    assert d["low"] < d["predicted_rent_psf"] < d["high"]
    assert d["by_class"]["A"] > d["by_class"]["B"] > d["by_class"]["C"]


@pytest.mark.parametrize("patch", [dict(market="Mars"), dict(property_type="Castle"), dict(building_class="Z"), dict(occupancy_pct=188), dict(size_sf=5), dict(year_built=1200)])
def test_predict_rejects_bad_input(client, patch):
    body = dict(market="Chicago", property_type="Office", building_class="A", year_built=2015, size_sf=120000, occupancy_pct=88); body.update(patch)
    assert client.post("/api/predict", json=body).status_code in (422,)


def test_rag_answers_and_abstains(client):
    a = client.post("/api/ask", json={"question": "What is the vacancy rate in Chicago?", "use_llm": False}).json()
    assert not a["abstained"] and "[1]" in a["answer"] and a["sources"][0]["title"].endswith("Chicago")
    b = client.post("/api/ask", json={"question": "What is the capital of France?", "use_llm": False}).json()
    assert b["abstained"]


def test_properties_search_and_404(client):
    assert client.get("/api/properties?q=Apex&page_size=5").json()["total"] > 0
    assert client.get("/api/properties/NOPE").status_code == 404
    assert client.get("/api/documents/nope").status_code == 404
    assert client.get("/api/overview?market=Nowhere").status_code == 404
