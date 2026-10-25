"""Step 4 - rent regression: baselines -> linear -> tree ensembles, with an honest evaluation.

Evaluation design
  * 80/20 stratified train/test split (test set touched ONCE, for reporting only)
  * 5-fold cross-validation on the training set is used to choose the model (not the test set)
  * metrics: MAE, RMSE (both in $/SF/yr), R2, MAPE
  * two baselines so we know whether ML actually adds value: global median and market x type x class median
  * prediction intervals: split-conformal style, from out-of-fold relative errors; coverage checked on test
  * permutation importance, error breakdown by market / type, residual diagnostics
  * final model refit on all data for serving; out-of-fold predictions stored for the dashboard
"""
import json
import sqlite3
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import DB_PATH, METRICS_PATH, MODEL_PATH, MODELS_DIR, SEED  # noqa: E402
from app.features import CAT_FEATURES, FEATURES, NUM_FEATURES, GroupMedianBaseline, make_features  # noqa: E402


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), NUM_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_FEATURES),
    ])


def log_target(reg):
    return TransformedTargetRegressor(regressor=reg, func=np.log, inverse_func=np.exp)


def build_models() -> dict:
    return {
        "Baseline: global median": DummyRegressor(strategy="median"),
        "Baseline: market x type x class median": GroupMedianBaseline(),
        "Ridge regression (log target)": log_target(Pipeline([("prep", preprocessor()), ("reg", Ridge(alpha=1.0))])),
        "Random forest (log target)": log_target(Pipeline([("prep", preprocessor()),
                                                           ("reg", RandomForestRegressor(n_estimators=300, min_samples_leaf=3, n_jobs=-1, random_state=SEED))])),
        "Gradient boosting (log target)": log_target(Pipeline([("prep", preprocessor()),
                                                               ("reg", HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=15,
                                                                                                     min_samples_leaf=20, l2_regularization=1.0, random_state=SEED))])),
    }


def metrics(y, p) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return {"mae": float(mean_absolute_error(y, p)), "rmse": float(np.sqrt(mean_squared_error(y, p))),
            "r2": float(r2_score(y, p)), "mape": float(np.mean(np.abs(y - p) / y) * 100)}


def main():
    MODELS_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    props = pd.read_sql_query("SELECT * FROM properties", con)
    con.close()
    X, y = make_features(props), props["rent_psf"].astype(float).values
    n = len(props)

    X_tr, X_te, y_tr, y_te, idx_tr, idx_te = train_test_split(
        X, y, np.arange(n), test_size=0.2, random_state=SEED, stratify=props["property_type"])
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    models = build_models()

    # ---------- compare models: CV on train (selection) + held-out test (reporting) ----------
    table, fitted = [], {}
    for name, est in models.items():
        oof = cross_val_predict(est, X_tr, y_tr, cv=kf)
        cv = metrics(y_tr, oof)
        est.fit(X_tr, y_tr)
        fitted[name] = est
        te = metrics(y_te, est.predict(X_te))
        table.append({"model": name, "is_baseline": name.startswith("Baseline"),
                      "cv_mae": cv["mae"], "cv_rmse": cv["rmse"], "cv_r2": cv["r2"],
                      "test_mae": te["mae"], "test_rmse": te["rmse"], "test_r2": te["r2"], "test_mape": te["mape"]})
        print(f"[train] {name:42s} CV RMSE={cv['rmse']:.3f} | TEST MAE={te['mae']:.3f} RMSE={te['rmse']:.3f} R2={te['r2']:.3f}")

    non_base = [r for r in table if not r["is_baseline"]]
    best = min(non_base, key=lambda r: r["cv_rmse"])["model"]       # chosen on CV only
    for r in table:
        r["selected"] = r["model"] == best
    best_est = fitted[best]
    print(f"[train] selected on CV RMSE: {best}")

    # ---------- test-set diagnostics for the selected model ----------
    pred_te = best_est.predict(X_te)
    test_m = metrics(y_te, pred_te)
    best_base = min([r for r in table if r["is_baseline"]], key=lambda r: r["test_rmse"])
    improvement = (1 - test_m["rmse"] / best_base["test_rmse"]) * 100

    # conformal-style relative interval from training OOF
    oof_tr = cross_val_predict(build_models()[best], X_tr, y_tr, cv=kf)
    rel_err_tr = np.abs(y_tr - oof_tr) / oof_tr
    q90_tr = float(np.quantile(rel_err_tr, 0.90))
    coverage = float(np.mean(np.abs(y_te - pred_te) / pred_te <= q90_tr))

    pe = (pred_te - y_te) / y_te * 100
    hist_counts, hist_edges = np.histogram(np.clip(pe, -40, 40), bins=np.arange(-40, 41, 5))
    rng = np.random.default_rng(SEED)
    samp = rng.choice(len(y_te), size=min(400, len(y_te)), replace=False)

    imp = permutation_importance(best_est, X_te, y_te, scoring="neg_mean_absolute_error", n_repeats=8, random_state=SEED)
    importance = sorted([{"feature": f, "importance": float(m), "std": float(s)} for f, m, s in
                         zip(FEATURES, imp.importances_mean, imp.importances_std)], key=lambda d: -d["importance"])

    # ---------- final model on ALL data + out-of-fold predictions for the dashboard ----------
    oof_all = cross_val_predict(build_models()[best], X, y, cv=kf)
    q90_all = float(np.quantile(np.abs(y - oof_all) / oof_all, 0.90))
    final = build_models()[best].fit(X, y)
    joblib.dump({"model": final, "name": best, "interval_rel_90": q90_all, "features": FEATURES}, MODEL_PATH)

    pred_df = pd.DataFrame({"property_id": props["property_id"], "pred_rent_psf": oof_all.round(2),
                            "pred_low": (oof_all * (1 - q90_all)).round(2), "pred_high": (oof_all * (1 + q90_all)).round(2)})
    con = sqlite3.connect(DB_PATH)
    pred_df.to_sql("property_predictions", con, index=False, if_exists="replace")
    con.execute("CREATE INDEX IF NOT EXISTS idx_pred_prop ON property_predictions(property_id)")
    con.commit(); con.close()

    # ---------- error breakdown (out-of-fold on all data -> larger n per group) ----------
    bd = props[["market", "property_type", "building_class"]].copy()
    bd["ae"] = np.abs(y - oof_all); bd["ape"] = bd["ae"] / y * 100
    def grp(col):
        g = bd.groupby(col).agg(n=("ae", "size"), mae=("ae", "mean"), mape=("ape", "mean")).reset_index()
        return g.sort_values("mape", ascending=False).round(3).to_dict("records")

    out = {
        "dataset": {"n_properties": n, "n_train": int(len(y_tr)), "n_test": int(len(y_te)),
                    "target": "rent_psf (USD per SF per year)", "target_mean": float(y.mean()), "target_median": float(np.median(y)),
                    "target_std": float(y.std())},
        "selected_model": best, "comparison": table, "test": test_m,
        "improvement_vs_best_baseline_rmse_pct": float(improvement), "best_baseline": best_base["model"],
        "interval": {"level": 0.90, "relative_half_width_train": q90_tr, "relative_half_width_final": q90_all, "empirical_test_coverage": coverage},
        "oof_all": metrics(y, oof_all),
        "residual_hist": {"edges": hist_edges.tolist(), "counts": hist_counts.tolist()},
        "scatter": [{"actual": float(y_te[i]), "pred": float(pred_te[i])} for i in samp],
        "importance": importance, "by_market": grp("market"), "by_type": grp("property_type"), "by_class": grp("building_class"),
        "meta": {"sklearn": sklearn.__version__, "seed": SEED, "cv_folds": 5, "split": "80/20 stratified by property_type"},
    }
    METRICS_PATH.write_text(json.dumps(out, indent=1))
    print(f"[train] FINAL TEST  MAE={test_m['mae']:.3f}  RMSE={test_m['rmse']:.3f}  R2={test_m['r2']:.3f}  MAPE={test_m['mape']:.1f}%  "
          f"| vs best baseline: {improvement:.0f}% lower RMSE | 90% interval coverage on test = {coverage:.2%}")


if __name__ == "__main__":
    main()
