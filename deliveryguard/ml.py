import hashlib
import importlib.metadata
import io
import platform
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import select, text

from deliveryguard.db import Run, engine, now, session
from deliveryguard.diagnostics import log_failure
from deliveryguard.quality import DomainError
from deliveryguard.service import lock, orders_frame, private_file

NUMERIC = [
    "promise_hours",
    "order_hour",
    "order_weekday",
    "order_month",
    "weight_kg",
    "order_amount",
]
CATEGORICAL = ["carrier", "destination_zone", "product_category"]
FEATURES = NUMERIC + CATEGORICAL


def features(frame):
    ordered = pd.to_datetime(frame["ordered_at"], utc=True)
    promised = pd.to_datetime(frame["promised_delivery_at"], utc=True)
    out = pd.DataFrame(index=frame.index)
    out["promise_hours"] = (promised - ordered).dt.total_seconds() / 3600
    out["order_hour"] = ordered.dt.hour
    out["order_weekday"] = ordered.dt.dayofweek
    out["order_month"] = ordered.dt.month
    for column in ["weight_kg", "order_amount"]:
        out[column] = pd.to_numeric(
            frame.get(column, pd.Series(index=frame.index, dtype=float)), errors="coerce"
        )
    for column in CATEGORICAL:
        out[column] = frame.get(column, pd.Series(index=frame.index, dtype=object)).fillna(
            "missing"
        )
    return out[FEATURES]


def pipeline(classifier):
    prep = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("missing", SimpleImputer(strategy="median", keep_empty_features=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUMERIC,
            ),
            ("category", OneHotEncoder(handle_unknown="ignore", max_categories=50), CATEGORICAL),
        ]
    )
    return Pipeline([("preprocess", prep), ("classifier", classifier)])


def metrics(y, scores, threshold):
    predicted = scores >= threshold
    return {
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "average_precision": float(average_precision_score(y, scores)),
        "roc_auc": float(roc_auc_score(y, scores)) if len(set(y)) == 2 else None,
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
    }


def select_threshold(y, scores):
    return float(
        max(np.linspace(0.05, 0.95, 37), key=lambda t: f1_score(y, scores >= t, zero_division=0))
    )


def split(frame):
    data = frame[frame.status == "delivered"].copy()
    for c in ["ordered_at", "delivered_at", "promised_delivery_at"]:
        data[c] = pd.to_datetime(data[c], utc=True)
    data = data[data.delivered_at <= pd.Timestamp.now(tz="UTC")].sort_values(
        ["ordered_at", "order_id"]
    )
    times = data.ordered_at.drop_duplicates().sort_values().tolist()
    if len(data) < 120 or len(times) < 10:
        raise DomainError(
            "insufficient_data",
            f"{len(data)} livraisons observées et {len(times)} instants distincts; minimum 120 et 10",
        )
    val_start, test_start = times[int(len(times) * 0.6)], times[int(len(times) * 0.8)]
    train = data[(data.ordered_at < val_start) & (data.delivered_at < val_start)]
    val = data[
        (data.ordered_at >= val_start)
        & (data.ordered_at < test_start)
        & (data.delivered_at < test_start)
    ]
    test = data[data.ordered_at >= test_start]
    parts, summaries = [], {}
    for name, part, minimum in zip(
        ["train", "validation", "test"], [train, val, test], [60, 20, 20], strict=True
    ):
        y = (part.delivered_at > part.promised_delivery_at).astype(int)
        counts = y.value_counts()
        if len(part) < minimum or len(counts) != 2 or counts.min() < 5:
            raise DomainError(
                "invalid_split",
                f"Split {name} : {len(part)} lignes, {int((y == 0).sum())} à l'heure et {int(y.sum())} en retard; minimum {minimum} lignes et 5 par classe après purge temporelle",
            )
        parts.append((features(part), y))
        summaries[name] = {
            "n": len(part),
            "late": int(y.sum()),
            "late_rate": float(y.mean()),
            "ordered_from": part.ordered_at.min().isoformat(),
            "ordered_until": part.ordered_at.max().isoformat(),
            "latest_outcome": part.delivered_at.max().isoformat(),
        }
    summaries["purged_unavailable_outcomes"] = len(data) - sum(len(p[1]) for p in parts)
    summaries["excluded_missing_or_corrected_snapshot"] = frame.attrs.get(
        "excluded_missing_or_corrected_snapshot", 0
    )
    return parts, summaries


def train(frame, run_id):
    parts, summaries = split(frame)
    (xtr, ytr), (xv, yv), (xt, yt) = parts
    candidates = [
        ("dummy", DummyClassifier(strategy="prior")),
        ("logistic_C0.1", LogisticRegression(C=0.1, max_iter=1000, random_state=42)),
        ("logistic_C1", LogisticRegression(C=1, max_iter=1000, random_state=42)),
        (
            "forest_depth5",
            RandomForestClassifier(
                n_estimators=100, max_depth=5, min_samples_leaf=5, random_state=42, n_jobs=1
            ),
        ),
        (
            "forest_depth10",
            RandomForestClassifier(
                n_estimators=100, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=1
            ),
        ),
    ]
    results, fitted = [], []
    for name, classifier in candidates:
        model = pipeline(classifier).fit(xtr, ytr)
        score = model.predict_proba(xv)[:, 1]
        ap = float(average_precision_score(yv, score))
        results.append(
            {
                "name": name,
                "validation_average_precision": ap,
                "parameters": classifier.get_params(),
            }
        )
        fitted.append(model)
    # Test is untouched until model AND threshold have been selected on validation.
    best = max(range(1, len(results)), key=lambda i: results[i]["validation_average_precision"])
    model = fitted[best]
    val_scores = model.predict_proba(xv)[:, 1]
    threshold = select_threshold(yv, val_scores)
    val_metrics = metrics(yv, val_scores, threshold)
    test_metrics = metrics(yt, model.predict_proba(xt)[:, 1], threshold)
    baseline = {
        "threshold": select_threshold(yv, fitted[0].predict_proba(xv)[:, 1]),
    }
    baseline.update(
        validation=metrics(yv, fitted[0].predict_proba(xv)[:, 1], baseline["threshold"]),
        test=metrics(yt, fitted[0].predict_proba(xt)[:, 1], baseline["threshold"]),
    )
    constant_baselines = {
        name: {
            period: metrics(y, np.full(len(y), value), 0.5)
            for period, y in [("validation", yv), ("test", yt)]
        }
        for name, value in [("all_on_time", 0), ("all_late", 1)]
    }
    importance = permutation_importance(
        model, xv, yv, n_repeats=3, scoring="average_precision", random_state=42, n_jobs=1
    )
    allowed = val_metrics["average_precision"] > baseline["validation"]["average_precision"]
    artifact = io.BytesIO()
    joblib.dump(model, artifact)
    private_file(f"models/{run_id}.joblib", artifact.getvalue())
    snapshot = frame.to_csv(index=False).encode()
    private_file(f"models/{run_id}.csv", snapshot)
    return {
        "snapshot_policy": "initial_v1",
        "activation_allowed": allowed,
        "activation_reason": "Évaluation valable; revue humaine requise"
        if allowed
        else "Le modèle ne dépasse pas la baseline sur validation",
        "selected": results[best]["name"],
        "threshold": threshold,
        "selection": "Maximum average precision sur validation; seuil F1 sur validation; sans refit",
        "features": FEATURES,
        "candidates": results,
        "splits": summaries,
        "validation": val_metrics,
        "test": test_metrics,
        "baseline": baseline,
        "constant_baselines": constant_baselines,
        "associations": [
            {"feature": f, "mean": float(m), "std": float(s)}
            for f, m, s in zip(
                FEATURES, importance.importances_mean, importance.importances_std, strict=True
            )
        ],
        "dataset_sha256": hashlib.sha256(snapshot).hexdigest(),
        "artifact_sha256": hashlib.sha256(artifact.getvalue()).hexdigest(),
        "dependencies": {
            p: importlib.metadata.version(p) for p in ["scikit-learn", "pandas", "numpy", "joblib"]
        },
        "python": platform.python_version(),
        "seed": 42,
        "limitations": [
            "Score non calibré",
            "Associations, jamais causalité",
            "Biais des commandes non terminées et annulées",
            "Aucun engagement de performance sur données réelles",
            "Carrier/zone/catégorie doivent être connus au moment de la commande",
        ],
    }


def work_once():
    # Session advisory lock survives transactions, but releases automatically on worker crash.
    with engine().connect() as connection:
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(614033)"))
        connection.commit()
        if not acquired:
            return False
        try:
            with session() as db, db.begin():
                lock(db)
                # A previous crashed worker can no longer own this lock; never silently retry it.
                for interrupted in db.scalars(select(Run).where(Run.status == "running")):
                    interrupted.status = "failed"
                    interrupted.finished_at = now()
                    interrupted.report = {
                        "code": "worker_interrupted",
                        "message": "Worker interrompu; créer un nouvel entraînement",
                    }
                run = db.scalar(select(Run).where(Run.status == "queued").order_by(Run.created_at))
                if not run:
                    return False
                run_id = run.id
                run.status, run.started_at = "running", now()
                frame = orders_frame(db, training=True)
            try:
                result = train(frame, run_id)
                state = "succeeded"
            except DomainError as exc:
                result, state = (
                    {"code": exc.code, "message": exc.message, "activation_allowed": False},
                    "failed",
                )
            except Exception as exc:
                log_failure(exc, run_id=run_id, operation="training")
                # Do not expose training data, SQL parameters, or exception payloads in logs/API.
                result, state = (
                    {
                        "code": "training_error",
                        "message": "Erreur interne; vérifier versions et ressources locales",
                        "activation_allowed": False,
                    },
                    "failed",
                )
            with session() as db, db.begin():
                run = db.get(Run, run_id)
                run.report, run.status, run.finished_at = result, state, now()
            return True
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(614033)"))
            connection.commit()


def worker():
    while True:
        try:
            work_once()
        except Exception as exc:
            log_failure(exc, operation="worker_poll")
        time.sleep(2)
