"""Step 1 - generate a realistic, *messy* synthetic commercial-property dataset (fully seeded).

Why synthetic?  Public datasets with commercial rent + occupancy + lease data do not exist in one
clean place, and a hidden known data-generating process lets us judge whether the evaluation is sound.
The raw file intentionally contains duplicates, inconsistent casing, missing values and typos so that the
cleaning step has real work to do.

Outputs (data/raw/):  raw_properties.csv, leases.csv, market_trends.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import AS_OF_DATE, AS_OF_YEAR, MARKETS, RAW_DIR, SEED  # noqa: E402

N_PROPERTIES = 1800

TYPE_MULT = {"Office": 1.00, "Retail": 0.95, "Industrial": 0.22, "Medical Office": 1.15, "Flex": 0.55}
TYPE_WEIGHTS = {"Office": 0.38, "Retail": 0.22, "Industrial": 0.20, "Medical Office": 0.08, "Flex": 0.12}
CLASS_MULT = {"A": 1.30, "B": 1.00, "C": 0.78}
CLASS_PROBS = {"A": 0.28, "B": 0.47, "C": 0.25}

NAME_A = ["Harbor", "Maple", "Summit", "Cedar", "Riverside", "Lakeview", "Union", "Liberty", "Heritage", "Pinnacle",
          "Gateway", "Crescent", "Oakmont", "Sterling", "Beacon", "Granite", "Willow", "Eastgate", "Westfield",
          "Northpoint", "Southpark", "Capitol", "Meridian", "Horizon", "Apex", "Ironwood", "Silverline", "Redwood"]
NAME_B = {"Office": ["Tower", "Plaza", "Center", "Centre", "Place", "Building", "Square"],
          "Retail": ["Marketplace", "Commons", "Shops", "Crossing", "Village", "Promenade"],
          "Industrial": ["Logistics Park", "Distribution Center", "Industrial Park", "Commerce Park", "Warehouse"],
          "Medical Office": ["Medical Plaza", "Health Pavilion", "Clinic Center", "Medical Arts"],
          "Flex": ["Flex Center", "Tech Park", "Business Park", "Innovation Hub"]}

INDUSTRIES = ["Technology", "Professional Services", "Financial Services", "Health Care", "Insurance",
              "Retail & Consumer", "Logistics & Distribution", "Manufacturing", "Media & Publishing",
              "Government & Education", "Real Estate", "Other"]
INDUSTRY_W = {
    "Office":         [.17, .22, .17, .06, .08, .02, .01, .02, .07, .08, .08, .02],
    "Retail":         [.02, .05, .04, .05, .03, .62, .01, .01, .03, .02, .02, .10],
    "Industrial":     [.03, .01, .01, .01, .00, .14, .45, .27, .01, .00, .01, .06],
    "Medical Office": [.01, .04, .01, .78, .05, .00, .00, .00, .00, .03, .02, .06],
    "Flex":           [.28, .07, .02, .06, .01, .07, .12, .20, .05, .02, .02, .08],
}
TENANT_PREFIX = ["Apex", "Summit", "Blue Harbor", "Northwind", "Cedar", "Ironwood", "Lumen", "Vertex", "Pioneer",
                 "Atlas", "Orchid", "Granite", "Keystone", "Meridian", "Silverline", "Redwood", "Beacon", "Falcon",
                 "Harbor", "Juniper", "Evergreen", "Crestline", "Bluebird", "Trident", "Quantum", "Sagebrush"]
TENANT_SUFFIX = {
    "Technology": ["Labs", "Systems", "Software", "Data"],
    "Professional Services": ["Advisors", "Consulting", "Law Group", "Partners"],
    "Financial Services": ["Capital", "Asset Management", "Securities", "Bank"],
    "Health Care": ["Health", "Medical Group", "Clinic", "Care"],
    "Insurance": ["Insurance", "Assurance", "Mutual", "Risk Group"],
    "Retail & Consumer": ["Foods", "Apparel", "Home Goods", "Fitness", "Cafe"],
    "Logistics & Distribution": ["Freight", "Logistics", "Supply", "Distribution"],
    "Manufacturing": ["Manufacturing", "Industries", "Components", "Works"],
    "Media & Publishing": ["Media", "Publishing", "Studios", "Press"],
    "Government & Education": ["Institute", "University Extension", "Agency", "Academy"],
    "Real Estate": ["Realty", "Properties", "Development", "Brokerage"],
    "Other": ["Holdings", "Group", "Enterprises", "Ventures"],
}


def make_properties(rng: np.random.Generator) -> pd.DataFrame:
    names = list(MARKETS.keys())
    w = np.array([MARKETS[m][7] for m in names]); w = w / w.sum()
    mk = rng.choice(names, size=N_PROPERTIES, p=w)
    types = rng.choice(list(TYPE_WEIGHTS), size=N_PROPERTIES, p=list(TYPE_WEIGHTS.values()))
    classes = rng.choice(list(CLASS_PROBS), size=N_PROPERTIES, p=list(CLASS_PROBS.values()))

    rows = []
    for i in range(N_PROPERTIES):
        m, t, c = mk[i], types[i], classes[i]
        state, lat, lon, base, urban, _, vac, _ = MARKETS[m]

        size = float(np.clip(rng.lognormal(np.log(70000 * (2.2 if t == "Industrial" else 1.0)), 0.75), 8000, 1_500_000))
        age = float(np.clip(rng.gamma(2.2, 14), 1, 75)) * {"A": 0.6, "B": 1.0, "C": 1.3}[c]
        age = float(np.clip(age, 1, 80))
        year_built = int(AS_OF_YEAR - round(age))
        plate = {"Office": rng.uniform(15000, 35000), "Retail": rng.uniform(40000, 150000),
                 "Industrial": rng.uniform(100000, 600000), "Medical Office": rng.uniform(12000, 30000),
                 "Flex": rng.uniform(50000, 200000)}[t]
        floors = int(np.clip(round(size / plate), 1, 70))
        occ = float(np.clip(rng.normal(100 * (1 - vac) + {"A": 3, "B": 0, "C": -4}[c] + (6 if t == "Industrial" else 0), 8), 45, 100))
        transit = float(np.clip(urban * 85 + rng.normal(0, 12), 5, 100))
        walk = float(np.clip(urban * 80 + (8 if t == "Retail" else 0) + rng.normal(0, 12), 5, 100))
        amen = float(np.clip({"A": 65, "B": 50, "C": 35}[c] + rng.normal(0, 15), 0, 100))
        pbase = {"Office": 3.0, "Retail": 5.0, "Industrial": 1.0, "Medical Office": 4.0, "Flex": 2.5}[t]
        parking = float(np.clip(pbase * (1.3 - 0.6 * urban) + rng.normal(0, 0.4), 0.3, 8))

        log_rent = (np.log(base) + np.log(TYPE_MULT[t]) + np.log(CLASS_MULT[c])
                    - 0.006 * age + 0.35 * (occ / 100 - 0.85)
                    + 0.0035 * (transit - 50) + 0.0030 * (amen - 50)
                    - 0.05 * (np.log(size) - np.log(70000)) - 0.015 * (parking - 3)
                    + rng.normal(0, 0.10))
        rent = float(np.clip(np.exp(log_rent), 3.5, 160))

        rows.append(dict(
            property_id=f"P{i + 1:05d}",
            name=f"{rng.choice(NAME_A)} {rng.choice(NAME_B[t])}",
            market=m, state=state,
            lat=round(lat + rng.normal(0, 0.05), 5), lon=round(lon + rng.normal(0, 0.05), 5),
            property_type=t, building_class=c, year_built=year_built, size_sf=int(round(size, -2)),
            floors=floors, occupancy_pct=round(occ, 1), parking_ratio=round(parking, 2),
            transit_score=round(transit, 0), walk_score=round(walk, 0), amenities_score=round(amen, 0),
            rent_psf=round(rent, 2),
            updated_at=str(pd.Timestamp("2026-09-30") - pd.Timedelta(days=int(rng.integers(0, 120)))).split(" ")[0],
        ))
    return pd.DataFrame(rows)


def make_leases(props: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    as_of = pd.Timestamp(AS_OF_DATE)
    rows, n = [], 0
    for p in props.itertuples():
        occupied = p.size_sf * p.occupancy_pct / 100
        t = p.property_type
        per = {"Office": rng.uniform(8000, 25000), "Retail": rng.uniform(5000, 20000),
               "Industrial": rng.uniform(60000, 300000), "Medical Office": rng.uniform(3000, 9000),
               "Flex": rng.uniform(10000, 50000)}[t]
        k = int(np.clip(round(occupied / per), 1, 12))
        shares = rng.dirichlet(np.ones(k) * 2.0)
        for s in shares:
            area = max(500, int(round(occupied * s, -1)))
            ind = rng.choice(INDUSTRIES, p=np.array(INDUSTRY_W[t]) / sum(INDUSTRY_W[t]))
            tenant = f"{rng.choice(TENANT_PREFIX)} {rng.choice(TENANT_SUFFIX[ind])}"
            term = int(rng.choice([5, 10] if t == "Retail" else ([5, 7, 10] if t == "Industrial" else [3, 5, 7, 10])))
            remaining = float(rng.uniform(0.1, term))
            expiry = as_of + pd.Timedelta(days=int(remaining * 365))
            start = expiry - pd.Timedelta(days=int(term * 365))
            n += 1
            rows.append(dict(
                lease_id=f"L-{n:05d}", property_id=p.property_id, tenant=tenant, industry=ind, area_sf=area,
                start_date=start.date().isoformat(), expiry_date=expiry.date().isoformat(), term_years=term,
                rent_psf=round(float(p.rent_psf * np.exp(rng.normal(-0.03, 0.08))), 2),
                escalation_pct=float(rng.choice([2.0, 2.5, 3.0, 3.5])),
                lease_type="NNN" if t in ("Retail", "Industrial", "Flex") else str(rng.choice(["Full Service Gross", "Modified Gross"])),
                renewal_option=str(rng.choice(["None", "1 x 5 years", "2 x 5 years", "1 x 3 years"], p=[.25, .35, .25, .15])),
                termination_right=str(rng.choice(["None", "Tenant may terminate after year 5 with 9 months notice",
                                                  "Mutual termination after year 7 with 12 months notice"], p=[.6, .25, .15])),
                free_rent_months=int(rng.choice([0, 2, 4, 6])), ti_allowance_psf=float(rng.choice([0, 20, 40, 60, 80])),
                security_deposit_months=int(rng.choice([1, 2, 3])),
            ))
    return pd.DataFrame(rows)


def make_trends(props: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    months = pd.period_range("2023-10", "2026-09", freq="M")
    rows = []
    for m, (_, _, _, _, _, drift, vac, _) in MARKETS.items():
        sub = props[props.market == m]
        end_rent = float(np.average(sub.rent_psf, weights=sub.size_sf))
        end_vac = float(100 - np.average(sub.occupancy_pct, weights=sub.size_sf))
        steps = drift / 12 + rng.normal(0, 0.004, len(months)) + 0.002 * np.sin(np.arange(len(months)) * 2 * np.pi / 12)
        idx = np.exp(np.cumsum(steps)); idx = idx / idx[-1]
        vacancy = end_vac - np.cumsum(rng.normal(0, 0.25, len(months)))[::-1] + 0.6 * (idx[::-1] - 1) * 10
        vacancy = vacancy - (vacancy[-1] - end_vac)
        for j, per in enumerate(months):
            rows.append(dict(month=str(per), market=m, avg_rent_psf=round(end_rent * idx[j], 2),
                             vacancy_pct=round(float(np.clip(vacancy[j], 2, 40)), 2),
                             net_absorption_ksf=round(float(rng.normal(60 * MARKETS[m][7], 120)), 1)))
    return pd.DataFrame(rows)


def inject_mess(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Make the raw file look like a real CRM export."""
    df = df.copy()
    n = len(df)
    # 1) inconsistent text (case / whitespace / separators)
    for col in ["market", "property_type"]:
        idx = rng.choice(n, size=int(n * 0.08), replace=False)
        df[col] = df[col].astype(object)
        for i in idx:
            v = df.at[df.index[i], col]
            df.at[df.index[i], col] = [v.lower(), v.upper(), f" {v} ", v + " "][int(rng.integers(0, 4))]
    idx = rng.choice(n, size=int(n * 0.05), replace=False)
    df["building_class"] = df["building_class"].astype(object)
    for i in idx:
        v = df.at[df.index[i], "building_class"]
        df.at[df.index[i], "building_class"] = [f"Class {v}", v.lower(), f"{v} "][int(rng.integers(0, 3))]
    # 2) missing values in feature columns (~4%) and a few missing targets (~1%)
    for col in ["year_built", "floors", "parking_ratio", "transit_score", "walk_score", "amenities_score"]:
        df[col] = df[col].astype(float)
        df.loc[rng.choice(n, size=int(n * 0.04), replace=False), col] = np.nan
    df.loc[rng.choice(n, size=int(n * 0.01), replace=False), "rent_psf"] = np.nan
    # 3) typos / outliers: rent x10, negative rent, occupancy > 100
    office_retail = df.index[(df.property_type.isin(["Office", "Retail"])) & (df.rent_psf > 30)]
    df.loc[rng.choice(office_retail, size=8, replace=False), "rent_psf"] *= 10
    df.loc[rng.choice(n, size=3, replace=False), "rent_psf"] = -df["rent_psf"].abs()
    df.loc[rng.choice(n, size=5, replace=False), "occupancy_pct"] = 105.0
    # 4) duplicates: exact copies + near-duplicates (different id, name case/whitespace) with OLDER updated_at
    dup_exact = df.sample(n=60, random_state=SEED).copy()
    dup_near = df.sample(n=50, random_state=SEED + 1).copy()
    dup_near["property_id"] = [f"X{j + 1:05d}" for j in range(len(dup_near))]
    dup_near["name"] = [str(x).upper() + " " for x in dup_near["name"]]
    dup_near["updated_at"] = "2025-01-15"
    df = pd.concat([df, dup_exact, dup_near], ignore_index=True)
    return df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)


def main():
    rng = np.random.default_rng(SEED)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    clean = make_properties(rng)
    leases = make_leases(clean, rng)
    trends = make_trends(clean, rng)
    raw = inject_mess(clean, rng)
    raw.to_csv(RAW_DIR / "raw_properties.csv", index=False)
    leases.to_csv(RAW_DIR / "leases.csv", index=False)
    trends.to_csv(RAW_DIR / "market_trends.csv", index=False)
    print(f"[generate] raw_properties={len(raw):,} (clean originals={len(clean):,}) leases={len(leases):,} trends={len(trends):,}")


if __name__ == "__main__":
    main()
