# Changelog

## Unreleased

- Immutable order-time snapshots, initial-promise labels and explicit correction
  codes. Legacy rows without proven snapshots are excluded; migration deactivates
  legacy models and requires a fresh evaluation.
- Independently selected Dummy threshold and constant on-time/late baselines.
- Bounded model cache with version/file-change invalidation; safe technical
  diagnostics correlated with request/run IDs.
- Server-enforced demo imports restricted to the bundled synthetic fixture.
- Short bilingual entry pages; full illustrated reports moved to docs/walkthrough.

## 0.1.0 — 2026-10-18

- Initial local pilot: CSV mapping, preview, strict quality audit, rejected export,
  idempotent receipts and explicit updates with PostgreSQL/Alembic persistence.
- FastAPI API key protection, structured request logs and health endpoints.
- Chronological ML evaluation with purging, baseline, logistic regression, random
  forest, persistent worker states, reviewed activation and versioned risk ranking.
- French Streamlit/Plotly interface and CSV exports for BI integration.
- Synthetic generator/examples, Docker Compose, tests, browser check and bilingual
  documentation. Actual local execution evidence is recorded in docs/verification.md.
