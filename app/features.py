"""Feature engineering + the baseline estimator. Used identically at training time and serving time."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

from .config import AS_OF_YEAR

CAT_FEATURES = ["market", "property_type", "building_class"]
NUM_FEATURES = [
    "age", "log_size_sf", "floors", "occupancy_pct",
    "parking_ratio", "transit_score", "walk_score", "amenities_score",
]
FEATURES = CAT_FEATURES + NUM_FEATURES

# Columns a caller must supply (raw, human-friendly) -> make_features() derives the rest
RAW_INPUT_COLUMNS = [
    "market", "property_type", "building_class", "year_built", "size_sf", "floors",
    "occupancy_pct", "parking_ratio", "transit_score", "walk_score", "amenities_score",
]


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c in CAT_FEATURES:
        out[c] = df[c].astype(object)
    out["age"] = AS_OF_YEAR - pd.to_numeric(df["year_built"], errors="coerce")
    out["log_size_sf"] = np.log(pd.to_numeric(df["size_sf"], errors="coerce").astype(float))
    for c in ["floors", "occupancy_pct", "parking_ratio", "transit_score", "walk_score", "amenities_score"]:
        out[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return out[FEATURES]


class GroupMedianBaseline(BaseEstimator, RegressorMixin):
    """'What would a broker's rule of thumb say?' - median rent of the same market x type x class."""

    def fit(self, X, y):
        d = pd.DataFrame({
            "market": np.asarray(X["market"]),
            "property_type": np.asarray(X["property_type"]),
            "building_class": np.asarray(X["building_class"]),
            "_y": np.asarray(y, dtype=float),
        })
        self.global_ = float(np.median(d["_y"]))
        self.full_ = {k: float(v) for k, v in d.groupby(["market", "property_type", "building_class"])["_y"].median().items()}
        self.mt_ = {k: float(v) for k, v in d.groupby(["market", "property_type"])["_y"].median().items()}
        return self

    def predict(self, X):
        out = []
        for m, t, c in zip(X["market"], X["property_type"], X["building_class"]):
            v = self.full_.get((m, t, c))
            if v is None:
                v = self.mt_.get((m, t), self.global_)
            out.append(v)
        return np.asarray(out, dtype=float)
