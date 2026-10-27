<div align="center">

# 🏙️ PropIQ
### AI-Powered Commercial Property Intelligence

**From raw property data to rent insights and evidence-backed answers.**

Python · Pandas · SQL · Scikit-learn · TF-IDF · FastAPI · Docker

</div>

---

## 📊 Project at a Glance

PropIQ is an end-to-end commercial real-estate intelligence platform that combines data engineering, machine learning, document retrieval, and interactive analytics. Explore portfolio performance, estimate property rents, compare markets, and ask questions across lease and market documents—all through one dashboard.

<div align="center">

| **1,766** | **$2.65** | **0.967** | **98%** |
|:---:|:---:|:---:|:---:|
| Clean property records | Rent MAE | Test-set R² | RAG Hit@1 |

</div>

*Results are measured on the project's generated dataset and labelled evaluation questions.*

## ✨ What You Can Do

- **Explore portfolio performance** — review property KPIs, occupancy, lease expiries, tenant industries, and rent distribution.
- **Understand market trends** — compare rent, vacancy, and absorption across markets.
- **Search properties** — filter and inspect assets, leases, and comparable properties.
- **Predict rent** — estimate rent per square foot with a prediction range, building-class comparisons, and sensitivity analysis.
- **Ask documents questions** — retrieve evidence from lease abstracts, market reports, and property reports with numbered citations.
- **Inspect model performance** — compare regression models and baselines, examine residuals, and review feature importance.
- **Trace the data pipeline** — explore cleaning stages, validation checks, SQL transformations, and database schema.

## 🧠 How It Works

```text
Raw property, lease & market data
               │
               ▼
   Pandas cleaning + SQL validation
               │
               ▼
          SQLite database
               │
       ┌───────┴────────┐
       ▼                ▼
 Rent regression    Document generation
       │                │
       ▼                ▼
 Predictions       TF-IDF retrieval + citations
       └────────┬───────┘
                ▼
         FastAPI backend
                │
                ▼
      Interactive web dashboard
```

## 🚀 Key Engineering Highlights

### Data engineering
- Standardised inconsistent text fields with Pandas.
- Used SQL window functions to identify duplicate records.
- Applied validation checks for missing and invalid rent and occupancy values.
- Processed **1,910 raw records into 1,766 clean property records**.

### Rent prediction
- Trained and compared **Ridge Regression, Random Forest, and Gradient Boosting**.
- Used cross-validation for model selection and a held-out test set for final evaluation.
- Evaluated models using MAE, RMSE, R², and MAPE.
- Achieved **$2.65 MAE, $3.96 RMSE, and 0.967 R²**, with a **38% RMSE reduction against the selected baseline** on the project dataset.

### Document intelligence (RAG)
- Built a TF-IDF retrieval pipeline over **125 lease, market, and property documents**.
- Evaluated retrieval using **75 labelled questions**, achieving **98% Hit@1**.
- Returned answers with numbered source citations and supporting evidence.
- Included a configurable abstention path for questions with low retrieval confidence.

## 🛠️ Tech Stack

| Area | Technologies |
|---|---|
| Data processing | Python, Pandas, NumPy |
| Data storage & transformation | SQLite, SQL |
| Machine learning | Scikit-learn, Ridge, Random Forest, Gradient Boosting |
| Document retrieval | TF-IDF, retrieval-augmented generation (RAG) |
| API | FastAPI, Pydantic, Uvicorn |
| Deployment & testing | Docker, pytest |

## ⚡ Run Locally

**1. Clone the repository**
```bash
git clone <your-repository-url>
cd <your-project-folder>
```

**2. Create an environment and install dependencies**

Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS / Linux:
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**3. Build the data, model, and document artifacts**
```bash
python scripts/build_all.py
```

**4. Start PropIQ**
```bash
uvicorn app.main:app --reload --port 8000
```

| Resource | URL |
|---|---|
| Dashboard | [http://localhost:8000](http://localhost:8000) |
| Interactive API documentation | [http://localhost:8000/docs](http://localhost:8000/docs) |

**5. Run tests**
```bash
pytest -q
```

## 🐳 Docker

```bash
docker build -t propiq .
docker run --rm -p 8000:8000 propiq
```

Then open [http://localhost:8000](http://localhost:8000).

## 📁 Project Structure

```text
PropIQ/
├── app/
│   ├── main.py          # FastAPI routes and application lifecycle
│   ├── features.py      # Shared model feature preparation
│   └── rag.py           # Document retrieval and answer generation
├── scripts/
│   ├── generate_data.py # Reproducible data generation
│   ├── pipeline.py      # Cleaning, SQL transformations, validation
│   ├── build_docs.py    # Lease, market and property documents
│   ├── train.py         # Model training and evaluation
│   ├── eval_rag.py      # RAG evaluation
│   └── build_all.py     # End-to-end build orchestrator
├── static/              # Dashboard assets
├── tests/               # Automated tests
├── Dockerfile
├── render.yaml
└── requirements.txt
```

## 🎯 Project Goal

PropIQ demonstrates how a complete analytics product can connect **data quality, predictive modelling, document retrieval, and API-driven visualisation** in a single workflow.

<div align="center">

**PropIQ** · Data → Intelligence → Decisions

</div>
