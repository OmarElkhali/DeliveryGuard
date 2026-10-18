import hashlib
import importlib.metadata
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select, text

from deliveryguard.config import settings
from deliveryguard.db import ActiveModel, Import, Order, Run, session, uid
from deliveryguard.quality import DomainError, audit, csv_bytes, read_csv, report


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


def import_csv(raw, mapping=None, update=False, preview=False):
    rows = read_csv(raw, mapping)
    accepted, rejected = audit(rows)
    fingerprint = hashlib.sha256(
        raw + json.dumps([mapping, update], sort_keys=True).encode()
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
                    unchanged += 1
                elif not update:
                    code = "conflict"
                elif before["ordered_at"] != values["ordered_at"]:
                    code = "immutable_order_date"
                elif before["status"] != "open" and before["status"] != values["status"]:
                    code = "terminal_status"
                else:
                    updated += 1
                    if not preview:
                        for key, value in values.items():
                            setattr(existing, key, value)
            else:
                inserted += 1
                if not preview:
                    db.add(Order(**values))
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
    return {c.name: getattr(order, c.name) for c in Order.__table__.columns}


def orders_frame(db):
    return pd.DataFrame(
        [order_dict(o) for o in db.scalars(select(Order))],
        columns=[c.name for c in Order.__table__.columns],
    )


def summary():
    with session() as db:
        # SQL aggregates count only observed deliveries in the lateness denominator.
        counts = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
        late = db.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.status == "delivered", Order.delivered_at > Order.promised_delivery_at)
        )
        open_orders = list(db.scalars(select(Order).where(Order.status == "open")))
        overdue = [order_dict(o) for o in open_orders if o.promised_delivery_at < datetime.now(UTC)]
        grouped = db.execute(
            select(Order.carrier, func.count())
            .where(Order.status == "delivered", Order.delivered_at > Order.promised_delivery_at)
            .group_by(Order.carrier)
        ).all()
        return {
            "counts": counts,
            "total": sum(counts.values()),
            "observed": counts.get("delivered", 0),
            "late": late,
            "late_rate": late / counts["delivered"] if counts.get("delivered") else None,
            "overdue_count": len(overdue),
            "overdue": overdue,
            "late_by_carrier": [{"carrier": c or "Non renseigné", "late": n} for c, n in grouped],
            "as_of": datetime.now(UTC).isoformat(),
            "warning": "Alertes constatées ≠ scores ML. Issues ouvertes/annulées exclues du taux.",
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
        if run.status != "succeeded" or not run.report.get("activation_allowed"):
            raise DomainError(
                "activation_blocked", "Évaluation non valable ou entraînement inachevé", 409
            )
        model_bytes(run)
        db.merge(ActiveModel(id=1, run_id=run.id, confirmed=True))
    return {"id": run_id, "active": True}


def predict(orders):
    import joblib

    from deliveryguard.ml import features

    with session() as db:
        active = db.get(ActiveModel, 1)
        if not active:
            raise DomainError("no_active_model", "Entraîner, évaluer puis activer un modèle", 409)
        run = db.get(Run, active.run_id)
        # Trusted, locally generated artifacts only. There is no model-upload endpoint.
        model = joblib.load(io.BytesIO(model_bytes(run)))
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
