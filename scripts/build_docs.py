"""Step 3 - create the sample document corpus for the RAG pipeline.

Documents are generated from the cleaned database so every number in them can be verified against the
structured data (that is what makes evidence-backed answers testable):
  * 80 lease abstracts   * 20 market reports (one per market)   * 25 property reports
"""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import AS_OF_DATE, DB_PATH, DOCS_DIR, DOCS_MANIFEST_PATH, SEED  # noqa: E402

DRIVERS = {
    "New York": "financial services, media and law firms, with a flight-to-quality bias towards amenitised Class A towers",
    "San Francisco": "AI and software start-ups slowly re-leasing space, while legacy tech footprints keep shrinking",
    "Boston": "life sciences, higher education and healthcare employers",
    "Washington DC": "federal agencies, defence contractors and associations, with hybrid work limiting demand",
    "Los Angeles": "entertainment, logistics linked to the ports and creative-office users",
    "Seattle": "large technology employers and cloud-infrastructure growth",
    "Miami": "financial-services relocations from the north-east and strong in-migration",
    "Chicago": "professional services, trading firms and a deep industrial base around the airports",
    "San Diego": "biotech, defence and military-related contractors",
    "Austin": "technology and semiconductor employers, with new supply moderating rent growth",
    "Denver": "energy transition, aerospace and outdoor-industry firms",
    "Atlanta": "logistics, film production and corporate headquarters relocations",
    "Dallas": "corporate relocations, financial services and a booming distribution corridor",
    "Houston": "energy, healthcare and port-related logistics",
    "Charlotte": "banking and fintech with steady in-migration",
    "Nashville": "healthcare management, music and entertainment and new corporate offices",
    "Philadelphia": "life sciences, universities and healthcare systems",
    "Minneapolis": "corporate headquarters, medical devices and retail head offices",
    "Phoenix": "semiconductor manufacturing, logistics and population growth",
    "Salt Lake City": "technology, financial back-offices and outdoor recreation brands",
}


def _write(doc_id, title, doc_type, meta, sections, manifest, extra=None):
    lines = [f"# {title}", meta, ""]
    for head, body in sections:
        lines += [f"## {head}", body, ""]
    path = DOCS_DIR / f"{doc_id}.md"
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    entry = {"doc_id": doc_id, "title": title, "doc_type": doc_type, "file": path.name, "meta": meta}
    entry.update(extra or {})
    manifest.append(entry)


def main():
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True)
    rng = np.random.default_rng(SEED)
    con = sqlite3.connect(DB_PATH)
    props = pd.read_sql_query("SELECT * FROM properties", con)
    leases = pd.read_sql_query("SELECT * FROM leases", con)
    trends = pd.read_sql_query("SELECT * FROM market_trends", con)
    con.close()
    manifest = []
    pmap = props.set_index("property_id")

    # ---------- lease abstracts ----------
    sample = leases.sample(n=80, random_state=SEED)
    for r in sample.itertuples():
        p = pmap.loc[r.property_id]
        ptxt = f"{p['name']} in {p['market']}, {p['state']}"
        meta = (f"Property: {p['name']} | Market: {p['market']} | Tenant: {r.tenant} | "
                f"Type: {p['property_type']} Class {p['building_class']}")
        secs = [
            ("Premises and Term",
             f"{r.tenant} ({r.industry}) leases {r.area_sf:,} SF at {ptxt}. The lease commenced on {r.start_date} and expires on "
             f"{r.expiry_date}, a term of {r.term_years} years. The lease structure is {r.lease_type}."),
            ("Rent and Escalations",
             f"Current base rent is ${r.rent_psf:.2f} per SF per year. Rent escalates {r.escalation_pct:.1f}% annually. "
             f"The tenant received {r.free_rent_months} months of free rent and a tenant improvement allowance of ${r.ti_allowance_psf:.0f} per SF. "
             f"The security deposit equals {r.security_deposit_months} months of rent."),
            ("Options and Termination Rights",
             f"Renewal option: {r.renewal_option}. Termination right: {r.termination_right}. "
             f"Assignment and subletting require landlord consent, not to be unreasonably withheld."),
        ]
        _write(f"lease-{r.lease_id}", f"Lease Abstract {r.lease_id} - {r.tenant} at {p['name']}", "Lease abstract", meta, secs, manifest,
               dict(property=p["name"], market=p["market"], tenant=r.tenant, lease_id=r.lease_id, property_id=r.property_id))

    # ---------- market reports ----------
    for m, g in trends.groupby("market"):
        g = g.sort_values("month")
        last, prev = g.iloc[-1], g.iloc[-13]
        yoy = (last.avg_rent_psf / prev.avg_rent_psf - 1) * 100
        v_chg = last.vacancy_pct - prev.vacancy_pct
        sub = props[props.market == m]
        by_type = sub.groupby("property_type").agg(rent=("rent_psf", "mean"), n=("rent_psf", "size"))
        top_type = by_type["rent"].idxmax()
        class_a = sub[(sub.property_type == "Office") & (sub.building_class == "A")]["rent_psf"].mean()
        class_c = sub[(sub.property_type == "Office") & (sub.building_class == "C")]["rent_psf"].mean()
        absorp = g.tail(12)["net_absorption_ksf"].sum()
        outlook = "modest rent growth" if yoy > 1 else "flat to softening rents"
        secs = [
            ("Market Overview",
             f"The {m} market closed September 2026 with an average asking rent of ${last.avg_rent_psf:.2f} per SF per year, "
             f"{'up' if yoy >= 0 else 'down'} {abs(yoy):.1f}% year over year. The vacancy rate was {last.vacancy_pct:.1f}%, "
             f"{'up' if v_chg >= 0 else 'down'} {abs(v_chg):.1f} percentage points from a year earlier."),
            ("Demand Drivers", f"Leasing demand in {m} is led by {DRIVERS[m]}. Trailing twelve-month net absorption was {absorp:,.0f} thousand SF."),
            ("Rents by Segment",
             f"Among property types, {top_type} commands the highest average rent in {m} at ${by_type.loc[top_type, 'rent']:.2f} per SF. "
             + (f"Class A office averages ${class_a:.2f} per SF versus ${class_c:.2f} per SF for Class C office, "
                f"a premium of {(class_a / class_c - 1) * 100:.0f}%." if not (np.isnan(class_a) or np.isnan(class_c)) else "Office class spreads are not reported for this market this quarter.")),
            ("Outlook and Risks",
             f"We expect {outlook} in {m} over the next twelve months. Key risks are hybrid-work driven space reductions, "
             f"new supply deliveries and tenant credit quality. Landlords are offering concessions such as free rent and tenant improvement allowances to secure renewals."),
        ]
        _write(f"market-{m.lower().replace(' ', '-')}", f"Market Report Q3 2026 - {m}", "Market report",
               f"Market: {m} | Period: Q3 2026 | Source: PropIQ research (synthetic)", secs, manifest, dict(market=m))

    # ---------- property reports (largest 25 properties) ----------
    horizon = (pd.Timestamp(AS_OF_DATE) + pd.DateOffset(months=24)).date().isoformat()
    for p in props.sort_values("size_sf", ascending=False).head(25).itertuples():
        pl = leases[leases.property_id == p.property_id]
        exp24 = pl[pl.expiry_date <= horizon]
        top = pl.sort_values("area_sf", ascending=False).head(3)
        mk_rent = props[(props.market == p.market) & (props.property_type == p.property_type)]["rent_psf"].median()
        diff = (p.rent_psf / mk_rent - 1) * 100
        secs = [
            ("Asset Summary",
             f"{p.name} is a {p.size_sf:,} SF Class {p.building_class} {p.property_type.lower()} property in {p.market}, {p.state}, built in "
             f"{int(p.year_built) if pd.notna(p.year_built) else 'an unrecorded year'}. It is currently {p.occupancy_pct:.1f}% occupied, "
             f"leaving {p.vacant_sf:,.0f} SF vacant."),
            ("Rent Position",
             f"The in-place average rent is ${p.rent_psf:.2f} per SF per year, which is {abs(diff):.0f}% {'above' if diff >= 0 else 'below'} the "
             f"{p.market} median of ${mk_rent:.2f} per SF for {p.property_type.lower()} assets."),
            ("Lease Expiry and Rollover",
             f"{exp24.area_sf.sum():,.0f} SF across {len(exp24)} lease{'s' if len(exp24) != 1 else ''} will expire within the next 24 months (before {horizon}), representing "
             f"{exp24.area_sf.sum() / max(pl.area_sf.sum(), 1) * 100:.0f}% of leased area. The property has {len(pl)} tenants in total."),
            ("Major Tenants",
             "The largest tenants are " + "; ".join(f"{t.tenant} ({t.area_sf:,} SF, expiring {t.expiry_date})" for t in top.itertuples()) + "."),
        ]
        _write(f"property-{p.property_id}", f"Property Report - {p.name} ({p.market})", "Property report",
               f"Property: {p.name} | Market: {p.market} | Type: {p.property_type} Class {p.building_class}", secs, manifest,
               dict(property=p.name, market=p.market, property_id=p.property_id))

    DOCS_MANIFEST_PATH.write_text(json.dumps(manifest, indent=1))
    counts = pd.Series([m["doc_type"] for m in manifest]).value_counts().to_dict()
    print(f"[docs] wrote {len(manifest)} documents: {counts}")


if __name__ == "__main__":
    main()
