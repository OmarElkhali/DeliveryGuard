# DeliveryGuard · v0.1.0

[![Checks](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml)

**Audit delivery histories and prioritize new orders by delay risk, on your own infrastructure.**

DeliveryGuard is a single-company, self-hosted pilot built with Python, pandas, SQL,
FastAPI, scikit-learn, PostgreSQL, Streamlit and Plotly. It works without an external
account, API key or paid service. The interface is in French. [Lire en français](README.fr.md).

This is **pilot software**, not a claim of production readiness. All included data
are synthetic. No customer adoption or real-world model performance is claimed.

**[Français](README.fr.md) · [Walkthrough](#a-delivery-history-to-risk-ranking-walkthrough) ·
[Measured results](#measured-results-on-the-synthetic-demo) · [Quickstart](#quickstart-synthetic-demonstration) ·
[Model card](MODEL_CARD.md) · [Verification evidence](docs/verification.md)**

## The problem and the workflow

A delivery history can mix completed, still-open and cancelled orders, inconsistent
dates and duplicate identifiers. Training directly on that file can produce an
apparently convincing model with an incorrect target or information from the future.

DeliveryGuard makes those steps visible: **inspect the source → map columns → audit
the rows → analyze observed deliveries → evaluate a model → activate it deliberately
→ rank new orders**. It also displays already-overdue open orders as operational
alerts, independently of the machine-learning model.

![DeliveryGuard welcome screen, showing the synthetic-data notice and demonstration workflow](docs/screenshots/01-demo.png)

### Recorded demonstration

The recording below comes from the real local application, including upload,
evaluation, activation and predictions. All records shown are synthetic.

![Recorded DeliveryGuard browser walkthrough on synthetic data](docs/demo.gif)

## A delivery-history-to-risk-ranking walkthrough

### 1. Upload a CSV and map its columns

Upload UTF-8 CSV, associate each source column with a DeliveryGuard field, and
preview the audit **before** confirming persistence. Existing column names can be
mapped directly; renamed source fields are supported through the same interface.
Unknown columns are rejected, so personal information is not silently archived.

![CSV upload and configurable column mapping in the real interface](docs/screenshots/02-import.png)

The minimum historical fields are `order_id`, `ordered_at`,
`promised_delivery_at` and `status`; `delivered_at` is required for delivered
orders. Carrier, zone, category, weight and amount are optional. See the
[mapping example](examples/mapping.json) and [data contract](docs/data-contract.md).

### 2. Read the quality report and inspect rejected rows

The report counts accepted/rejected rows, explains detected issues and offers a
download containing rejected source rows and their reasons. Duplicate IDs,
invalid dates, impossible chronology, incompatible statuses and negative numbers
are checked. The example below passes because it contains valid generated records;
an all-valid demo is not evidence that every company CSV will pass.

![Quality report for 1500 synthetic orders, with zero rejected rows and a selection-bias notice](docs/screenshots/03-quality.png)

The original source remains private. Reimporting identical content returns the
same receipt; conflicting updates require an explicit option. A cancelled or open
order is never silently labelled as an on-time delivery.

### 3. Analyze observed delays and operational alerts

In the recorded demonstration: **1,500 orders**, **1,376 completed deliveries**,
**84 open orders**, **40 cancellations** and **397 observed delays**. The delay rate
is **397 / 1,376 = 28.85%**, excluding open and cancelled orders from its denominator.

![Delivery analysis with actual counts and the observed-delay denominator](docs/screenshots/04-analytics.png)

An open order whose promised date has passed is an **observed operational alert**.
It does not need a trained model. A model score, in contrast, estimates relative
risk using only information available when an order is placed.

![Open-order operational alerts displayed separately from model-based ranking](docs/screenshots/06-predictions.png)

### 4. Train, inspect the evaluation and activate a version

Training is queued in PostgreSQL and processed by a separate local worker. The UI
shows a persistent state instead of keeping the HTTP request busy. Each successful
run includes its periods, sample counts, candidate parameters, metrics, feature
allowlist, dependency versions and dataset/artifact fingerprints.

![Model evaluation in the application, including validation/test metrics and a confusion matrix](docs/screenshots/05-model.png)

Activation requires a valid evaluation, a model that beats the Dummy baseline on
validation, and explicit human review. Limits remain visible next to the action;
neither retraining nor activation happens automatically.

![Feature associations, model limitations and explicit activation control](docs/screenshots/08-model-limits.png)

### 5. Rank new orders and export the result

Upload order-time information or call `/predict` / `/predict/batch`. The response
is sorted by risk and includes the model version, selected threshold and a warning
that the score is **not a calibrated probability**. Ranking exports include the
version and threshold for BI traceability.

![Two new synthetic orders ranked by risk, with the model version and CSV export](docs/screenshots/07-risk-ranking.png)

| Example order | Risk score | Label at threshold 0.20 |
|---|---:|---|
| `NEW-001` | 0.5662 | Review / À examiner |
| `NEW-002` | 0.0749 | Lower priority / Priorité moindre |

These are recorded synthetic examples, not delivery guarantees. The input CSV is
[available here](examples/new_orders.csv).

## Measured results on the synthetic demo

The figures below are generated from the
[saved evaluation snapshot](docs/results/synthetic-evaluation.json) of run
`7af27c9c-8a80-458b-a74f-1bd88bf97cab`. Before capturing it, the report script compared
all stored order fields against the deterministic **1,500-row, seed-42 generator**.
No company data or invented measurements are used.

### Chronological split and leakage controls

Only delivered orders with an observable outcome enter classification. Equal order
timestamps stay in the same split. Outcomes that would not have been known at the
start of the next period are purged; **21 deliveries** are removed this way.
Preprocessing is fitted on train only. Model choice and threshold choice use
validation; the final test is kept out of those decisions.

| Split after purging | Orders | Late | Order period, UTC |
|---|---:|---:|---|
| Train | 815 | 221 | 2024-01-01 → 2024-08-08 |
| Validation | 264 | 83 | 2024-08-09 → 2024-10-26 |
| Final test | 276 | 83 | 2024-10-27 → 2025-01-09 |

![Delivered-order counts by chronological split and observed outcome](docs/results/01-chronological-split.png)

### Candidate comparison on validation

All five candidates use the same train-only preprocessing. The small fixed search
compares two logistic regressions and two random forests against a Dummy baseline.
The selection criterion is validation **average precision**, not final-test F1.

| Candidate | Validation average precision |
|---|---:|
| Dummy baseline | 0.3144 |
| Logistic regression, C=0.1 | 0.7378 |
| Logistic regression, C=1 | 0.7376 |
| **Random Forest, depth 5 — selected** | **0.7383** |
| Random Forest, depth 10 | 0.7201 |

![Validation-only comparison of the five model candidates](docs/results/02-model-comparison.png)

The tiny margin between the best candidates does not establish statistical
superiority. This demonstration validates the selection workflow, not a universal
recommendation to prefer Random Forest for real delivery data.

### Final-test metrics and practical interpretation

The selected model is `forest_depth5`; its threshold **0.20** maximizes F1 over the
documented validation grid. The model is not refitted on validation before testing.

| Metric | Validation | Final test |
|---|---:|---:|
| Precision | 0.5500 | 0.4968 |
| Recall | 0.9277 | 0.9398 |
| F1 | 0.6906 | 0.6500 |
| Average precision | 0.7383 | 0.6522 |
| ROC-AUC | 0.8589 | 0.8292 |

![Validation and final-test metrics at the fixed selected threshold](docs/results/04-evaluation-metrics.png)

On the 276 final-test deliveries, the model identifies **78 of 83 delays**, misses
**5**, and raises **79 false alarms** among on-time deliveries. High recall therefore
comes with a substantial intervention burden: approximately half the flagged
orders are false positives in this synthetic holdout. A company must define the
cost of intervention and missed delays before adopting a threshold.

![Final-test confusion matrix with 114 true negatives, 79 false positives, 5 false negatives and 78 true positives](docs/results/03-confusion-matrix.png)

### Feature associations, not causal explanations

Permutation importance is measured on validation over three repeats. The generator
deliberately creates a carrier/zone association, which the model can recover.
These associations do not establish causality or transferability to another company;
small or negative importance values can reflect noise and finite-sample variation.

![Validation permutation importance with variability across three repeats](docs/results/05-feature-associations.png)

### What has actually been verified

| Check | Recorded local result |
|---|---|
| PostgreSQL-backed pytest suite | **29 passed**, one disclosed deprecation warning |
| Ruff lint and formatting | Passed |
| Docker Compose build, migration and startup | Passed |
| Real browser workflow and downloads | Passed, **0 console/page errors** |
| Container recreation with persistent volumes | Same orders, active version and exact prediction |
| Native and Docker backup/isolated restore | Same counts, active version and exact prediction |

See [verification details](docs/verification.md) for commands, environments and
remaining limits. The badge at the top links to the current hosted CI status.
No company-data validation, load benchmark, Power BI Desktop integration or
independent security audit is claimed.

To rebuild the five figures from the committed snapshot after installing the
development dependencies and a Playwright browser:

```sh
python scripts/build_report.py --snapshot
```

## Quickstart: synthetic demonstration

Prerequisites: Docker Engine with Compose v2; approximately 3 GB free disk space.
From a terminal; if already cloned, run only the Compose command:

```sh
git clone https://github.com/OmarElkhali/DeliveryGuard.git
cd DeliveryGuard
docker compose --env-file .env.demo up --build -d --wait
```

Open **http://localhost:8501**. Click **Charger la démonstration**, examine **Qualité**
and **Analyse des livraisons**, then open **Modèles et évaluation**, create an
execution and refresh until finished. Review the evaluation and limitations, check
the review confirmation and activate the version yourself. Open **Commandes à
surveiller**, upload [examples/new_orders.csv](examples/new_orders.csv), and calculate risks.

API/OpenAPI: http://localhost:8000/docs. Readiness: http://localhost:8000/health/ready.
The worker persists queued/running/succeeded/failed states in PostgreSQL. Models are
never trained or activated automatically. `.env.demo` is deliberately public and
restricted to synthetic, local use; business endpoints have no key check in this mode.
Ports are bound to loopback. **Do not put real company data in the demo.**

Reproduce the complete API workflow (imports synthetic data and explicitly activates a model):

```sh
docker compose --env-file .env.demo exec api deliveryguard smoke
```

Stop without deleting data:

```sh
docker compose --env-file .env.demo down
```

## Use company CSVs

Use a **separate Compose project and empty volumes** from the demo:

1. Copy `.env.example` to `.env`. Set `DG_DEMO=false`.
2. Supply independent random `DG_DB_PASSWORD` and `DG_API_KEY` (at least 32 characters).
   Use URL-safe alphanumeric database passwords in the database URL. No production
   secret is included or generated by default. `python -c "import secrets; print(secrets.token_hex(32))"`
   can generate each secret locally.
3. Run `docker compose -p deliveryguard-company up --build -d --wait`.
   Stop the demo first if it uses the same ports. Enter your API key in the UI sidebar.
4. Remove personal columns from the CSV. Upload, map **every column**, preview the
   audit, then confirm the import. Mapping is `source_column: canonical_field`.
5. Review rejected rows and the ML eligibility report before training.

No names, phone numbers, emails or street addresses are part of the schema. All
unknown/unmapped columns are refused, rather than archived silently. Free text
fields must contain codes/categories, never personal information.

See [data contract](docs/data-contract.md), [integration examples](docs/integration.md),
[operations and backups](docs/operations.md), [architecture](docs/architecture.md),
[model card](MODEL_CARD.md) and [Power BI](docs/power-bi.md).

## What the product does

- Strict UTF-8 CSV parsing, configurable column mapping and non-mutating preview.
- Row-level audit, counters, examples, suggested actions and rejected CSV download.
- Content-idempotent imports, explicit updates and immutable original source files.
- SQL/pandas analysis; open overdue orders are operational alerts, separate from ML.
- Chronological train/validation/test with unavailable outcomes purged, train-only
  preprocessing, Dummy baseline, two logistic regressions and two random forests.
- Validation-only model/threshold selection, untouched final test, persistent reports,
  explicit activation and single/batch ranking with model version and score limits.
- Spreadsheet-safe UTF-8 CSV exports, genuine screenshots and reproducible browser check.

## Native Python development

Python **3.12** is the supported/tested runtime. PostgreSQL 16 is required; SQLite
is not substituted for PostgreSQL in tests. Install PostgreSQL yourself and create
the `deliveryguard` database with a local user.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install --no-deps -e .
# Set DG_DATABASE_URL, DG_API_KEY, DG_DEMO and optionally DG_DATA_DIR in .env.
deliveryguard migrate
uvicorn deliveryguard.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

In two additional terminals with the same environment:

```sh
deliveryguard worker
streamlit run ui/app.py --server.address=127.0.0.1
```

Generate the included dataset deterministically:

```sh
deliveryguard generate --rows 1500 --seed 42 --output examples/synthetic.csv
```

## Verification

Tests deliberately truncate only a **disposable database named `deliveryguard_test*`**.
Create it first; never point test configuration at company data.

```sh
# Linux/macOS:
export DG_TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/deliveryguard_test
# PowerShell equivalent:
# $env:DG_TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/deliveryguard_test'
ruff check .
ruff format --check .
pytest -q
# Running Docker synthetic demo required:
python -m playwright install chromium
python scripts/browser_check.py
```

Browser evidence goes to `artifacts/` (including a WebM recording); screenshots go
to `docs/screenshots/`. The browser script verifies a real upload → preview → import
→ audit → training → activation → batch ranking, downloads and console errors.
It refuses to run against a non-demo instance. See [the verification report](docs/verification.md)
for the recorded local executions; the Actions badge links to the current hosted runs.

If Chromium download is unavailable but Chrome is installed, set `PW_CHANNEL=chrome`.
If FFmpeg is unavailable, set `PW_NO_VIDEO=1`: the check records actual Chrome screen
frames as `artifacts/demo.gif` instead of WebM, without weakening the UI checks.

## Limits before a company pilot

One instance = one company; one shared API key; no multi-tenancy, user roles or audit
trail of individual actors. Imports are bounded (5 MiB, 20,000 rows; 5,000 in demo),
prediction batches at 1,000 orders, one training at a time. No distributed queue,
automatic retraining, automatic activation, model uploads or calibrated probability claim.
An HTTP timeout after import does not imply rollback: retry the same content to get
the same receipt. Native CLI can run the same import logic locally.

Priorities: (1) validate chronological evaluation on a company's representative
data and define operational cost/threshold policy; (2) add actor-specific access and
audit records behind HTTPS; (3) measure pilot volumes, drift and recovery objectives
before adding scheduling or scaling. See [limits](docs/limits.md).

## Project and license

Author: **Omar Elkhali**, Master 2 BDIO — ENSAM Casablanca.
[GitHub](https://github.com/OmarElkhali/) ·
[LinkedIn](https://www.linkedin.com/in/omar-elkhali-2bb683270/).
MIT for this project's code and generated synthetic examples; it does not grant
rights to third-party datasets. [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md).
