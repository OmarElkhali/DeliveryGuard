# Contributing

Use Python 3.12 and PostgreSQL 16. Follow the README development setup, use a
disposable `deliveryguard_test*` database, run Ruff and pytest, then run the browser
check against synthetic demo data for UI changes. Never attach company CSVs,
database dumps, secrets or serialized models to an issue or PR. Prefer a small
synthetic reproducer. The generator is deterministic (`--seed 42`).

Keep domain rules in the shared Python modules, UI calls through the API, train-only
preprocessing inside the sklearn Pipeline, and test holdouts outside selection.
Add a minimal regression check for changed business logic and Alembic revision
for schema changes. Never replace a real feature with a placeholder control.

PRs should explain the behavior change and actual checks, with relevant screenshots
on synthetic data. Distinguish tests run locally from CI not yet executed. Avoid new
services/dependencies without an immediate need. Use [SECURITY.md](SECURITY.md) for
security disclosures. Contributions are under MIT; do not contribute datasets or
code you do not have the right to license.
