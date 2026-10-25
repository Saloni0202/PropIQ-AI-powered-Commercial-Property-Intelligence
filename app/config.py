"""Central paths and constants shared by the pipeline, training scripts and the API."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DOCS_DIR = DATA_DIR / "docs"
MODELS_DIR = ROOT / "models"
STATIC_DIR = ROOT / "static"

DB_PATH = DATA_DIR / "propiq.db"
MODEL_PATH = MODELS_DIR / "rent_model.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"
RAG_EVAL_PATH = MODELS_DIR / "rag_eval.json"
PIPELINE_REPORT_PATH = DATA_DIR / "pipeline_report.json"
DOCS_MANIFEST_PATH = DOCS_DIR / "manifest.json"

SEED = 42
AS_OF_DATE = "2026-10-01"   # "today" inside the synthetic world
AS_OF_YEAR = 2026

# Markets: name -> (state, lat, lon, base office rent $/SF/yr, urban factor 0-1,
#                   annual rent drift, base vacancy, relative size weight)
MARKETS = {
    "New York":        ("NY", 40.71, -74.00, 68, 1.00,  0.030, 0.14, 1.9),
    "San Francisco":   ("CA", 37.77, -122.42, 62, 0.90, -0.010, 0.22, 1.1),
    "Boston":          ("MA", 42.36, -71.06, 52, 0.85,  0.025, 0.13, 1.1),
    "Washington DC":   ("DC", 38.90, -77.04, 50, 0.85,  0.010, 0.17, 1.2),
    "Los Angeles":     ("CA", 34.05, -118.24, 46, 0.65,  0.015, 0.17, 1.5),
    "Seattle":         ("WA", 47.61, -122.33, 44, 0.80,  0.005, 0.19, 1.0),
    "Miami":           ("FL", 25.76, -80.19, 48, 0.65,  0.045, 0.10, 1.0),
    "Chicago":         ("IL", 41.88, -87.63, 38, 0.80,  0.012, 0.18, 1.4),
    "San Diego":       ("CA", 32.72, -117.16, 42, 0.60,  0.020, 0.12, 0.8),
    "Austin":          ("TX", 30.27, -97.74, 40, 0.55,  0.035, 0.15, 0.9),
    "Denver":          ("CO", 39.74, -104.99, 36, 0.60,  0.018, 0.16, 0.9),
    "Atlanta":         ("GA", 33.75, -84.39, 34, 0.55,  0.028, 0.14, 1.1),
    "Dallas":          ("TX", 32.78, -96.80, 33, 0.50,  0.030, 0.15, 1.3),
    "Houston":         ("TX", 29.76, -95.37, 31, 0.45,  0.010, 0.17, 1.2),
    "Charlotte":       ("NC", 35.23, -80.84, 32, 0.50,  0.032, 0.11, 0.8),
    "Nashville":       ("TN", 36.16, -86.78, 33, 0.50,  0.040, 0.10, 0.7),
    "Philadelphia":    ("PA", 39.95, -75.17, 33, 0.75,  0.008, 0.15, 0.9),
    "Minneapolis":     ("MN", 44.98, -93.27, 29, 0.60,  0.006, 0.16, 0.7),
    "Phoenix":         ("AZ", 33.45, -112.07, 30, 0.40,  0.034, 0.12, 1.0),
    "Salt Lake City":  ("UT", 40.76, -111.89, 28, 0.40,  0.028, 0.11, 0.6),
}

PROPERTY_TYPES = ["Office", "Retail", "Industrial", "Medical Office", "Flex"]
BUILDING_CLASSES = ["A", "B", "C"]
