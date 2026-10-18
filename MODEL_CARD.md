# DeliveryGuard model card · v0.1

## Intended use

Rank new orders by relative risk of late delivery **at order placement** for one
company. Human operational prioritization; no guarantee of a delivery outcome.
Never use the score as a customer eligibility or punitive decision. Demo data are
synthetic and deliberately include a learnable carrier/zone association; success
on them is a software check, not evidence of real-world utility.

## Target and admissible inputs

Target: delivered_at > **initial** promised_delivery_at, among observable delivered orders only.
Open and cancelled orders are excluded. Open overdue alerts are separate rules.
Admissible features: promised lead time in hours, order hour/weekday/month (UTC),
weight, amount, carrier, destination zone and product category. The last five must
already be known at placement; exclude/leave null if they are assigned later.
Order IDs, status, delivery timestamp and derivatives of outcomes are never features.

Carrier/category codes must not encode customer identity or future outcome.
Schema validation alone cannot determine when a company's fields became available.
No aggregate target encoding or features based on future delivery performance.

At the first accepted import, all NewOrder fields are stored in an immutable
`initial_snapshot`. PostgreSQL rejects changes to it. Later operational changes
affect current columns only; training uses snapshot features with current observed
outcomes. The first import must contain the actual original inputs: capturing a
previously revised historical CSV cannot recover its past. Explicit corrections
that contradict these inputs exclude the order, irreversibly, from future training
and the original-promise delay rate. They never rewrite the original evidence.
Legacy rows with no snapshot are excluded. Migration deactivates legacy models;
their old metrics remain historical records, not eligible activation reports.

## Evaluation procedure

Sort delivered orders by order time, keep equal timestamps in one split, choose
60/20/20 cutoffs over distinct timestamps. Purge train outcomes not known before
validation begins and validation outcomes not known before test begins. Minimum
120 delivered records, 10 distinct order times; after purge train >=60, validation
and test >=20, and at least 5 of each class in every split. Failure is persisted
with an explanation and blocks activation. This is a minimal validity gate, not
statistical evidence of adequate sample size for a company's risk tolerance.

Train-only `ColumnTransformer` + imputers/scaler/OneHotEncoder in sklearn Pipeline.
DummyClassifier(prior), LogisticRegression C in {0.1,1}, RandomForest 100 trees,
depth in {5,10}, min_samples_leaf=5; seed=42. Unknown categories ignored, cardinality
bounded with max_categories=50. Choose the non-dummy model by validation average
precision. Choose its threshold by highest validation F1 over 0.05..0.95 in steps
of 0.025 (tie: first/lower threshold). No refit on validation. Test used once after
both decisions; never use test metrics for the activation gate. The gate also
requires validation AP strictly above Dummy AP. Human review is always required.

Reports show precision, recall, F1, average precision, confusion matrix
[[TN,FP],[FN,TP]] and ROC-AUC if calculable; split counts, prevalence and periods;
baseline validation/test metrics, all candidate hyperparameters and versions.
Dummy selects its own threshold on the same validation grid, independently of the
selected model. Constant all-on-time and all-late rules also have full metrics.
The activation gate remains validation average precision, unaffected by thresholds.
Raw `predict_proba` output is described only as an **uncalibrated risk score**.
Permutation importance on validation (3 repeats) is association, never causality.

## Traceability

Every run has ID, created/started/finished dates and persisted state. Successful
reports include parameters, feature allowlist, dependency/Python versions, seed,
threshold, periods, metrics and SHA-256 of snapshot/artifact. Its immutable
private snapshot represents the database at **worker start**, not enqueue time.
Activation only changes one database pointer. Historical versions remain available;
an earlier eligible version can be reactivated manually.

## Known limitations

Unfinished orders may be the slowest deliveries: excluding them can underestimate
risk (right censoring/selection bias). Cancelled orders have a different unobserved
outcome. Purging reduces but does not remove this bias. No survival model in v0.1.
No calibration validation, uncertainty intervals, fairness assessment, drift alerting,
cross-company transfer validation or business cost threshold optimization is provided.
Repeated model experiments can indirectly overfit a reused holdout; create a truly
later holdout for serious pilot validation. Small-sample test metrics are unstable.
No automated training, external model uploads or causal claims.
