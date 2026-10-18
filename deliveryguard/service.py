import hashlib
import importlib.metadata
import io
import json
import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import DateTime, func, select, text

from deliveryguard.config import settings
from deliveryguard.db import ActiveModel, Import, Order, Run, session, uid
from deliveryguard.quality import FIELDS, DomainError, NewOrder, audit, csv_bytes, read_csv, report


def lock(db):
    # ponytail: one transactional writer lock; move to per-order locking for larger imports.
    db.execute(text("SELECT pg_advisory_xact_lock(614032)"))


def private_file(relative, content):
    path = settings().data_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(content)
    temp.replace(path)
    return path


def import_csv(raw, mapping=None, update=False, preview=False, correction_code=""):
    rows = read_csv(raw, mapping)
    if correction_code and (
        not update or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", correction_code)
    ):
        raise DomainError(
            "invalid_correction",
            "Correction : activer update et fournir un code A-Z/0-9/_ (3 à 64 caractères)",
        )
    if settings().demo:
        from deliveryguard.synthetic import generate

        fixture = generate().replace(b"\r\n", b"\n")
        if (
            raw.removeprefix(b"\xef\xbb\xbf").replace(b"\r\n", b"\n") != fixture
            or (mapping and any(source != target for source, target in mapping.items()))
            or update
            or correction_code
        ):
            raise DomainError(
                "demo_import_restricted",
                "La démo accepte uniquement le CSV synthétique fourni, sans mise à jour",
                403,
            )
    accepted, rejected = audit(rows)
    fingerprint = hashlib.sha256(
        raw
        + json.dumps(
            [mapping, update, correction_code, "initial_snapshot_v1"], sort_keys=True
        ).encode()
    ).hexdigest()
    with session() as db, db.begin():
        lock(db)
        previous = db.scalar(select(Import).where(Import.fingerprint == fingerprint))
        if previous and not preview:
            return {"id": previous.id, **previous.report, "reused": True}
        inserted = updated = unchanged = 0
        valid = []
        for line, values in accepted:
            existing = db.get(Order, values["order_id"])
            code = None
            if existing:
                before = order_dict(existing)
                if before == values:
                    if (
                        correction_code
                        and not existing.snapshot_excluded
                        and existing.initial_snapshot != initial_values(values)
                    ):
                        updated += 1
                    else:
                        unchanged += 1
                elif not update:
                    code = "conflict"
                elif before["ordered_at"] != values["ordered_at"]:
                    code = "immutable_order_date"
                elif (
                    not correction_code
                    and before["status"] != "open"
                    and (
                        before["status"] != values["status"]
                        or before["delivered_at"] != values["delivered_at"]
                    )
                ):
                    code = "terminal_status"
                else:
                    updated += 1
                    if not preview:
                        for key, value in values.items():
                            setattr(existing, key, value)
                # Corrections never rewrite the original evidence, including an unchanged
                # current row that explicitly disclaims its original feature values.
                if (
                    not code
                    and not preview
                    and correction_code
                    and existing.initial_snapshot != initial_values(values)
                ):
                    existing.snapshot_excluded = True
            else:
                inserted += 1
                if not preview:
                    db.add(Order(**values, initial_snapshot=initial_values(values)))
            if code:
                rejected.append(
                    {"row": line, "code": code, "reason": code, "values": rows[line - 2]}
                )
            else:
                valid.append((line, values))
        quality = report(
            len(rows),
            valid,
            rejected,
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
            preview=preview,
        )
        quality.update(
            update_kind="correction" if correction_code else "operational",
            correction_code=correction_code,
        )
        quality["warnings"].append(
            "Les champs initiaux doivent provenir de la commande, pas d'un historique révisé. Les mises à jour ne remplacent jamais cet instantané."
        )
        if preview:
            return quality
        import_id = uid()
        # Only schema-approved source columns are accepted; originals remain private and immutable.
        private_file(f"imports/{import_id}/source.csv", raw)
        rejects = [
            {
                **r["values"],
                "source_row": r["row"],
                "rejection_code": r["code"],
                "rejection_reason": r["reason"],
            }
            for r in rejected
        ]
        fields = list(rows[0]) + ["source_row", "rejection_code", "rejection_reason"]
        private_file(f"imports/{import_id}/rejected.csv", csv_bytes(rejects, fields))
        db.add(Import(id=import_id, fingerprint=fingerprint, report=quality))
        return {"id": import_id, **quality, "reused": False}


def order_dict(order):
    return {name: getattr(order, name) for name in FIELDS}


def initial_values(values):
    return NewOrder.model_validate(
        {k: v for k, v in values.items() if k in NewOrder.model_fields}
    ).model_dump(mode="json")


def orders_frame(db, training=False):
    orders = list(db.scalars(select(Order).order_by(Order.ordered_at, Order.order_id)))
    rows = []
    for order in orders:
        row = order_dict(order)
        if training:
            if not order.initial_snapshot or order.snapshot_excluded:
                continue
            row.update(order.initial_snapshot)
        rows.append(row)
    frame = pd.DataFrame(rows, columns=FIELDS)
    frame.attrs["excluded_missing_or_corrected_snapshot"] = len(orders) - len(rows)
    return frame


def initial_snapshot(order_id):
    with session() as db:
        order = db.get(Order, order_id)
        if not order:
            raise DomainError("not_found", "Commande introuvable", 404)
        return {
            "values": order.initial_snapshot,
            "eligible": bool(order.initial_snapshot and not order.snapshot_excluded),
        }


def summary():
    with session() as db:
        initial_promise = (
            Order.initial_snapshot["promised_delivery_at"].as_string().cast(DateTime(timezone=True))
        )
        eligible = Order.initial_snapshot.is_not(None) & ~Order.snapshot_excluded
        initial_carrier = Order.initial_snapshot["carrier"].as_string()
        # SQL aggregates count only observed deliveries in the lateness denominator.
        counts = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
        late = db.scalar(
            select(func.count())
            .select_from(Order)
            .where(eligible, Order.status == "delivered", Order.delivered_at > initial_promise)
        )
        observed = db.scalar(
            select(func.count()).select_from(Order).where(eligible, Order.status == "delivered")
        )
        open_orders = list(db.scalars(select(Order).where(Order.status == "open")))
        overdue = [order_dict(o) for o in open_orders if o.promised_delivery_at < datetime.now(UTC)]
        grouped = db.execute(
            select(initial_carrier, func.count())
            .where(eligible, Order.status == "delivered", Order.delivered_at > initial_promise)
            .group_by(initial_carrier)
        ).all()
        return {
            "counts": counts,
            "total": sum(counts.values()),
            "observed": observed,
            "excluded_outcomes": counts.get("delivered", 0) - observed,
            "late": late,
            "late_rate": late / observed if observed else None,
            "overdue_count": len(overdue),
            "overdue": overdue,
            "late_by_carrier": [{"carrier": c or "Non renseigné", "late": n} for c, n in grouped],
            "as_of": datetime.now(UTC).isoformat(),
            "warning": "Retards mesurés contre la promesse initiale; instantanés absents/corrigés exclus du taux et du ML. Alertes ouvertes contre la promesse opérationnelle actuelle.",
        }


def enqueue():
    with session() as db, db.begin():
        lock(db)
        pending = db.scalar(select(Run).where(Run.status.in_(["queued", "running"])))
        if pending:
            raise DomainError(
                "training_pending", "Un entraînement est déjà en attente ou en cours", 409
            )
        run = Run(id=uid(), report={})
        db.add(run)
        db.flush()
        return {"id": run.id, "status": run.status}


def run_dict(run):
    return {
        "id": run.id,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "status": run.status,
        "report": run.report,
    }


def get_run(run_id):
    with session() as db:
        run = db.get(Run, run_id)
        if not run:
            raise DomainError("not_found", "Entraînement introuvable", 404)
        return run_dict(run)


def model_list():
    with session() as db:
        active = db.get(ActiveModel, 1)
        return [
            {**run_dict(r), "active": bool(active and active.run_id == r.id)}
            for r in db.scalars(select(Run).order_by(Run.created_at.desc()))
        ]


def model_bytes(run):
    model_path = settings().data_dir / "models" / f"{run.id}.joblib"
    if not model_path.is_file():
        raise DomainError("artifact_missing", "Modèle local absent", 503)
    artifact = model_path.read_bytes()
    if hashlib.sha256(artifact).hexdigest() != run.report["artifact_sha256"]:
        raise DomainError(
            "artifact_corrupted", "Empreinte du modèle invalide; restaurer le volume", 503
        )
    if any(importlib.metadata.version(p) != v for p, v in run.report["dependencies"].items()):
        raise DomainError(
            "incompatible_versions", "Restaurer les dépendances du modèle ou réentraîner", 503
        )
    return artifact


def activate(run_id, confirmed):
    if not confirmed:
        raise DomainError("confirmation_required", "Confirmer la revue des limites et métriques")
    with session() as db, db.begin():
        lock(db)
        run = db.get(Run, run_id)
        if not run:
            raise DomainError("not_found", "Modèle introuvable", 404)
        if (
            run.status != "succeeded"
            or not run.report.get("activation_allowed")
            or run.report.get("snapshot_policy") != "initial_v1"
        ):
            raise DomainError(
                "activation_blocked", "Évaluation non valable ou entraînement inachevé", 409
            )
        model_bytes(run)
        db.merge(ActiveModel(id=1, run_id=run.id, confirmed=True))
    loaded_model.cache_clear()
    return {"id": run_id, "active": True}


@lru_cache(maxsize=2)
def loaded_model(path, modified_ns, size, run_id, digest, dependencies):
    import joblib

    # The cache key includes the active version, file stat and evaluation fingerprint.
    run = Run(id=run_id, report={"artifact_sha256": digest, "dependencies": dict(dependencies)})
    return joblib.load(io.BytesIO(model_bytes(run)))


def predict(orders):
    from deliveryguard.ml import features

    with session() as db:
        active = db.get(ActiveModel, 1)
        if not active:
            raise DomainError("no_active_model", "Entraîner, évaluer puis activer un modèle", 409)
        run = db.get(Run, active.run_id)
        # Trusted, locally generated artifacts only. There is no model-upload endpoint.
        if run.report.get("snapshot_policy") != "initial_v1":
            raise DomainError("legacy_model", "Réentraîner avec les instantanés initiaux", 409)
        path = settings().data_dir / "models" / f"{run.id}.joblib"
        try:
            stat = path.stat()
        except FileNotFoundError:
            raise DomainError("artifact_missing", "Modèle local absent", 503) from None
        model = loaded_model(
            str(path.resolve()),
            stat.st_mtime_ns,
            stat.st_size,
            run.id,
            run.report["artifact_sha256"],
            tuple(sorted(run.report["dependencies"].items())),
        )
        scores = model.predict_proba(features(pd.DataFrame(orders)))[:, 1]
        threshold = run.report["threshold"]
        return {
            "model_id": run.id,
            "threshold": threshold,
            "score_note": "Score non calibré; ce n'est pas une probabilité garantie.",
            "predictions": sorted(
                [
                    {
                        "order_id": o["order_id"],
                        "risk_score": float(score),
                        "risk_label": "À examiner" if score >= threshold else "Priorité moindre",
                    }
                    for o, score in zip(orders, scores, strict=True)
                ],
                key=lambda p: p["risk_score"],
                reverse=True,
            ),
        }


def import_path(import_id, filename):
    with session() as db:
        if not db.get(Import, import_id):
            raise DomainError("not_found", "Import introuvable", 404)
    path = settings().data_dir / "imports" / import_id / filename
    if not path.is_file():
        raise DomainError("artifact_missing", "Fichier absent; restaurer le volume de données", 404)
    return Path(path)
