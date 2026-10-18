# DeliveryGuard ? v0.1.0

[![Checks](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/OmarElkhali/DeliveryGuard/actions/workflows/ci.yml)

**Audit delivery histories and prioritize new orders by delay risk, on your own infrastructure.**

A self-hosted, single-company pilot with a French interface. Inspect CSV quality,
analyze observed delays, evaluate a model and activate it after human review.
Python ? pandas ? PostgreSQL ? FastAPI ? scikit-learn ? Streamlit ? Plotly.
No external account, paid service or external API key is needed.

**Pilot software. All examples are synthetic; no real-world predictive value or
customer adoption is claimed.** [Lire en fran?ais](README.fr.md).

[![Open the recorded browser demonstration](docs/screenshots/07-risk-ranking.png)](https://raw.githubusercontent.com/OmarElkhali/DeliveryGuard/main/docs/demo.gif)

*Click the image for the real browser GIF: upload ? audit ? evaluate ? activate ? rank.*
[Full illustrated walkthrough and measured results](docs/walkthrough.md).

## Run the synthetic demonstration

Requires Docker Engine with Compose v2 and approximately 3 GB free disk space.

```sh
git clone https://github.com/OmarElkhali/DeliveryGuard.git
cd DeliveryGuard
docker compose --env-file .env.demo up --build -d --wait
```

Open **http://localhost:8501** and click **Charger la d?monstration**. Examine
**Qualit?** and **Analyse des livraisons**, then create a run in **Mod?les et
?valuation**. Refresh until finished, review its evaluation and limits, and activate
it yourself. In **Commandes ? surveiller**, upload
[examples/new_orders.csv](examples/new_orders.csv) and calculate risks.

API/OpenAPI: **http://localhost:8000/docs**. Readiness: `/health/ready`.
The separate worker persists queued/running/succeeded/failed states.

```sh
# Complete API workflow, including explicit model activation:
docker compose --env-file .env.demo exec api deliveryguard smoke
# Stop while keeping data:
docker compose --env-file .env.demo down
```

Demo credentials are intentionally public and ports bind to loopback. The server
accepts **only the bundled 1,500-row, seed-42 history** in demo mode; arbitrary
imports and updates are refused. This shared demo is not a public hosting setup.

## An example result

On the recorded synthetic holdout, the model found **78 of 83 late deliveries**,
missed **5**, and raised **79 false alarms**. Final-test F1: **0.6500**; average
precision: **0.6522**. This illustrates the pipeline and its intervention burden;
it does not validate a company's decision policy. Scores are not calibrated probabilities.

| Synthetic order | Risk score | Label at threshold 0.20 |
|---|---:|---|
| `NEW-001` | 0.5662 | ? examiner |
| `NEW-002` | 0.0749 | Priorit? moindre |

[Evaluation snapshot](docs/results/synthetic-evaluation.json) ?
[Splits, baselines, metrics and figures](docs/walkthrough.md#measured-results-on-the-synthetic-demo).

## Use company data

Use **separate empty volumes**, `DG_DEMO=false`, and independent random database
and API secrets. Follow the [company setup](docs/walkthrough.md#use-company-csvs).
Remove personal columns and supply the **original order-time inputs**, including
the initial promise. Operational updates never replace this immutable snapshot.
Explicit corrections are recorded; contested snapshots are excluded from ML.

**Existing installations:** back up before migrating. Migration `0002` preserves
legacy rows but excludes their unverified inputs and deactivates legacy models.
Read the [upgrade procedure](docs/operations.md#upgrading-from-schema-0001).

One shared key currently gives all business permissions. This remains a controlled
local pilot: distinct identities/roles, authorized real-data evaluation and managed
HTTPS are needed before broader company use.

## Documentation

| Need | Guide |
|---|---|
| Screenshots, GIF and complete measured report | [Walkthrough](docs/walkthrough.md) |
| CSV schema, immutable snapshots and corrections | [Data contract](docs/data-contract.md) |
| Native Python setup and checks | [Development and verification](docs/walkthrough.md#native-python-development) |
| Actual checks and remaining verification limits | [Verification report](docs/verification.md) |
| API examples and BI exports | [Integration](docs/integration.md) ? [Power BI](docs/power-bi.md) |
| Model assumptions and limits | [Model card](MODEL_CARD.md) ? [Pilot limits](docs/limits.md) |
| Deployment, backups and diagnosis | [Operations](docs/operations.md) ? [Architecture](docs/architecture.md) |

Author: **Omar Elkhali**, Master 2 BDIO ? ENSAM Casablanca.
[GitHub](https://github.com/OmarElkhali/) ? [LinkedIn](https://www.linkedin.com/in/omar-elkhali-2bb683270/).
[MIT](LICENSE) for project code and generated examples; no rights to third-party datasets.
[Contributing](CONTRIBUTING.md) ? [Security](SECURITY.md).
