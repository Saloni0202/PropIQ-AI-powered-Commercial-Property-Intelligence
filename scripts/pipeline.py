"""Step 2 - clean, de-duplicate and load the data with Pandas + SQL (SQLite).

Pandas: standardise text, map categories to canonical values.
SQL   : de-duplicate with a window function, validate with CASE counts, build the analysis tables.
Output: data/propiq.db  and  data/pipeline_report.json (shown on the 'Data & Pipeline' page).
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import AS_OF_YEAR, DB_PATH, MARKETS, PIPELINE_REPORT_PATH, RAW_DIR  # noqa: E402

DEDUPE_SQL = """
CREATE TABLE properties_dedup AS
SELECT * FROM (
    SELECT s.*,
           ROW_NUMBER() OVER (
               PARTITION BY lower(trim(name)), market, size_sf     -- same building = same name + market + size
               ORDER BY updated_at DESC, property_id ASC           -- keep the freshest record
           ) AS rn
    FROM stg_properties s
)
WHERE rn = 1;
""".strip()

QUALITY_SQL = """
SELECT
  SUM(CASE WHEN rent_psf IS NULL THEN 1 ELSE 0 END)                                         AS missing_rent,
  SUM(CASE WHEN rent_psf IS NOT NULL AND (rent_psf < 3 OR rent_psf > 250) THEN 1 ELSE 0 END) AS rent_out_of_range,
  SUM(CASE WHEN occupancy_pct < 0 OR occupancy_pct > 100 THEN 1 ELSE 0 END)                  AS bad_occupancy,
  SUM(CASE WHEN market IS NULL OR property_type IS NULL OR building_class IS NULL THEN 1 ELSE 0 END) AS unmapped_category
FROM properties_dedup;
""".strip()

VALID_SQL = """
CREATE TABLE properties_valid AS
SELECT property_id, name, market, state, lat, lon, property_type, building_class,
       year_built, size_sf, floors, occupancy_pct, parking_ratio, transit_score,
       walk_score, amenities_score, rent_psf, updated_at
FROM properties_dedup
WHERE rent_psf IS NOT NULL
  AND rent_psf BETWEEN 3 AND 250
  AND occupancy_pct BETWEEN 0 AND 100
  AND size_sf > 0
  AND market IS NOT NULL AND property_type IS NOT NULL AND building_class IS NOT NULL;
""".strip()

INDEX_SQL = """
CREATE INDEX idx_prop_market ON properties(market);
CREATE INDEX idx_prop_type   ON properties(property_type);
CREATE INDEX idx_lease_prop  ON leases(property_id);
CREATE INDEX idx_lease_exp   ON leases(expiry_date);
""".strip()


def _key(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    raw = pd.read_csv(RAW_DIR / "raw_properties.csv")
    leases = pd.read_csv(RAW_DIR / "leases.csv")
    trends = pd.read_csv(RAW_DIR / "market_trends.csv")
    report = {"raw_rows": int(len(raw))}

    # ---------- 1. pandas: standardise text ----------
    df = raw.copy()
    df["name"] = df["name"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    canon_m = {_key(m): m for m in MARKETS}
    canon_t = {_key(t): t for t in ["Office", "Retail", "Industrial", "Medical Office", "Flex"]}
    n_text_fixed = int(((df["market"] != df["market"].map(lambda x: canon_m.get(_key(x))))
                        | (df["property_type"] != df["property_type"].map(lambda x: canon_t.get(_key(x))))
                        | (df["building_class"].astype(str).str.strip().str.upper().str[-1] != df["building_class"].astype(str))).sum())
    df["market"] = df["market"].map(lambda x: canon_m.get(_key(x)))
    df["property_type"] = df["property_type"].map(lambda x: canon_t.get(_key(x)))
    df["building_class"] = df["building_class"].astype(str).str.strip().str.upper().str[-1]
    df.loc[~df["building_class"].isin(list("ABC")), "building_class"] = None
    report["text_values_standardised"] = n_text_fixed

    con = sqlite3.connect(DB_PATH)
    try:
        # ---------- 2. SQL: de-duplicate with a window function ----------
        df.to_sql("stg_properties", con, index=False)
        con.executescript("DROP TABLE IF EXISTS properties_dedup;")
        con.executescript(DEDUPE_SQL)
        report["after_dedupe_rows"] = int(con.execute("SELECT COUNT(*) FROM properties_dedup").fetchone()[0])
        report["duplicates_removed"] = report["raw_rows"] - report["after_dedupe_rows"]

        # ---------- 3. SQL: data-quality counts, then validation filter ----------
        q = con.execute(QUALITY_SQL).fetchone()
        report["quality_flags"] = {"missing_rent": int(q[0] or 0), "rent_out_of_range": int(q[1] or 0),
                                   "bad_occupancy": int(q[2] or 0), "unmapped_category": int(q[3] or 0)}
        con.executescript(VALID_SQL)

        # ---------- 4. pandas: derived columns + final tables ----------
        props = pd.read_sql_query("SELECT * FROM properties_valid", con)
        props["age"] = AS_OF_YEAR - props["year_built"]
        props["occupied_sf"] = (props["size_sf"] * props["occupancy_pct"] / 100).round(0)
        props["vacant_sf"] = props["size_sf"] - props["occupied_sf"]
        report["final_rows"] = int(len(props))
        report["rows_dropped_validation"] = report["after_dedupe_rows"] - report["final_rows"]
        report["missing_values_in_features"] = {c: int(props[c].isna().sum()) for c in
                                                ["year_built", "floors", "parking_ratio", "transit_score", "walk_score", "amenities_score"]}
        report["missing_value_policy"] = ("Left as NaN in the table; imputed with the training-fold median INSIDE the model "
                                          "pipeline (so no information leaks from the test set).")

        con.executescript("DROP TABLE IF EXISTS properties; DROP TABLE IF EXISTS stg_properties; "
                          "DROP TABLE IF EXISTS properties_valid; DROP TABLE IF EXISTS properties_dedup;")
        props.to_sql("properties", con, index=False)

        leases = leases[leases["property_id"].isin(props["property_id"])].copy()
        leases.to_sql("leases", con, index=False)
        trends.to_sql("market_trends", con, index=False)
        mk = pd.DataFrame([dict(market=m, state=v[0], lat=v[1], lon=v[2]) for m, v in MARKETS.items()])
        mk.to_sql("markets", con, index=False)
        con.executescript(INDEX_SQL)
        con.commit()
    finally:
        con.close()

    report["lease_rows"] = int(len(leases))
    report["trend_rows"] = int(len(trends))
    report["sql"] = {"dedupe": DEDUPE_SQL, "quality_checks": QUALITY_SQL, "validation_filter": VALID_SQL}
    PIPELINE_REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"[pipeline] raw={report['raw_rows']:,} -> dedup={report['after_dedupe_rows']:,} -> final={report['final_rows']:,} "
          f"| leases={report['lease_rows']:,} | flags={report['quality_flags']}")


if __name__ == "__main__":
    main()
