import csv
import io
import json

import pandas as pd
import pytest

from deliveryguard.config import settings
from deliveryguard.db import engine
from deliveryguard.ml import FEATURES, features, split, work_once
from deliveryguard.quality import DomainError, csv_bytes, parse_date
from deliveryguard.synthetic import generate


def upload(client, raw, **data):
    return client.post("/imports", files={"file": ("history.csv", raw, "text/csv")}, data=data)


def rows_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


def base_row(**changes):
    return {
        "order_id": "A1",
        "ordered_at": "2025-01-01T00:00:00Z",
        "promised_delivery_at": "2025-01-03T00:00:00Z",
        "status": "open",
        **changes,
    }


def test_auth_health_structured_errors(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    client.headers.clear()
    for path in ["/models", "/analytics/summary", "/exports/orders.csv", "/imports"]:
        r = client.get(path)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
        assert r.headers["X-Request-ID"]
    assert client.get("/models", headers={b"X-API-Key": b"\xff"}).status_code == 401


@pytest.mark.parametrize(
    "raw", [b"", b"a,b\n1,2,3", b'order_id,ordered_at\n"unterminated', b"a,a\n1,2", b"\xff\xfe"]
)
def test_malformed(client, raw):
    assert upload(client, raw).status_code == 422


def test_mapping_preview_missing_fields_and_private_columns(client):
    assert upload(client, b"order_id\n1\n").json()["error"]["code"] == "missing_columns"
    raw = b"id,date,promise,state\nA1,2025-01-01,2025-01-02,open\n"
    mapping = json.dumps(
        dict(
            zip(
                ["id", "date", "promise", "state"],
                ["order_id", "ordered_at", "promised_delivery_at", "status"],
                strict=True,
            )
        )
    )
    r = client.post(
        "/imports/preview", files={"file": ("x.csv", raw, "text/csv")}, data={"mapping": mapping}
    )
    assert r.json()["valid"] == 1
    assert client.get("/analytics/summary").json()["total"] == 0
    assert upload(client, raw, mapping=mapping).json()["inserted"] == 1
    assert upload(client, rows_csv([base_row(email="private@example.com")])).status_code == 422
    assert upload(client, raw, mapping="[]").status_code == 422


def test_idempotence_updates_and_duplicates(client):
    raw = rows_csv([base_row()])
    first = upload(client, raw).json()
    assert (settings().data_dir / "imports" / first["id"] / "source.csv").read_bytes() == raw
    second = upload(client, raw).json()
    assert second["reused"] and first["id"] == second["id"]
    assert upload(client, b"\xef\xbb\xbf" + raw).json()["unchanged"] == 1
    assert upload(client, raw + b"\n").status_code == 422
    duplicate = upload(client, rows_csv([base_row(order_id="B"), base_row(order_id="B")])).json()
    assert duplicate["rejected"] == 2
    terminal = rows_csv([base_row(status="delivered", delivered_at="2025-01-04T00:00:00Z")])
    assert upload(client, terminal).json()["rejected"] == 1
    assert upload(client, terminal, update="true").json()["updated"] == 1
    assert upload(client, raw, update="true").json()["rejected"] == 1
    changed_date = rows_csv([base_row(ordered_at="2024-12-31T00:00:00Z")])
    assert upload(client, changed_date, update="true").json()["rejected"] == 1
    engine().dispose()
    assert client.get("/analytics/summary").json()["total"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"order_id": ""},
        {"ordered_at": "01/02/2025"},
        {"promised_delivery_at": "2024-12-01"},
        {"status": "delivered"},
        {"status": "cancelled", "delivered_at": "2025-01-04"},
        {"status": "delivered", "delivered_at": "2024-12-31"},
        {"weight_kg": "-1"},
        {"order_amount": "nan"},
        {"status": "unknown"},
        {"ordered_at": "2099-01-01"},
    ],
)
def test_incoherent_dates_status_numbers(client, changes):
    result = upload(client, rows_csv([base_row(**changes)])).json()
    assert result["rejected"] == 1 and result["valid"] == 0
    rejected = client.get(f"/imports/{result['id']}/rejected")
    assert "rejection_code" in rejected.text
    assert client.get("/analytics/summary").json()["total"] == 0


def test_open_cancelled_and_delivered_denominator(client):
    result = upload(
        client,
        rows_csv(
            [
                base_row(order_id="open"),
                base_row(order_id="cancelled", status="cancelled"),
                base_row(order_id="late", status="delivered", delivered_at="2025-01-04"),
                base_row(order_id="ontime", status="delivered", delivered_at="2025-01-03"),
            ]
        ),
    ).json()
    assert result["valid"] == 4
    result = client.get("/analytics/summary").json()
    assert result["late_rate"] == 0.5 and result["overdue_count"] == 1
    assert result["observed"] == 2


def test_limits_missing_artifacts_unknown_ids_and_formula_export(client, monkeypatch):
    monkeypatch.setattr(settings(), "max_upload_bytes", 10)
    assert upload(client, b"x" * 11).status_code == 413
    monkeypatch.setattr(settings(), "max_upload_bytes", 5 * 1024 * 1024)
    r = client.post("/imports", files={"file": ("model.pkl", b"x", "application/octet-stream")})
    assert r.status_code == 415
    assert client.get("/training-runs/00000000-0000-0000-0000-000000000000").status_code == 404
    assert (
        client.post(
            "/predict",
            json={
                "order_id": "x",
                "ordered_at": "2025-01-01",
                "promised_delivery_at": "2025-01-02",
            },
        ).status_code
        == 409
    )
    assert "'=HYPERLINK" in csv_bytes([{"id": "=HYPERLINK(1)"}]).decode("utf-8-sig")
    assert csv_bytes([{"=FORMULA": "text"}]).decode("utf-8-sig").startswith("'=FORMULA")
    assert parse_date("2025-01-01T02:00:00+02:00") == parse_date("2025-01-01")


def test_insufficient_training_and_activation_refusal(client):
    upload(client, rows_csv([base_row()]))
    queued = client.post("/training-runs").json()
    assert client.post("/training-runs").status_code == 409
    assert work_once()
    result = client.get(f"/training-runs/{queued['id']}").json()
    assert result["status"] == "failed" and result["report"]["code"] == "insufficient_data"
    assert (
        client.post(f"/models/{queued['id']}/activate", json={"reviewed_limits": True}).status_code
        == 409
    )


def test_no_leakage_temporal_split_and_single_class():
    frame = pd.read_csv(io.BytesIO(generate()))
    changed = frame.assign(status="cancelled", delivered_at="2099-01-01", order_id="anything")
    pd.testing.assert_frame_equal(features(frame), features(changed))
    assert not set(FEATURES) & {"delivered_at", "status", "order_id", "observed_late"}
    parts, stats = split(frame)
    assert stats["train"]["latest_outcome"] < stats["validation"]["ordered_from"]
    assert stats["validation"]["latest_outcome"] < stats["test"]["ordered_from"]
    assert all(len(y.unique()) == 2 for _, y in parts)
    oneclass = frame.assign(status="delivered", delivered_at=frame.promised_delivery_at)
    with pytest.raises(DomainError, match="Split"):
        split(oneclass)


def test_full_training_activation_prediction_persistence(client):
    result = upload(client, generate()).json()
    assert result["valid"] == 1500 and result["rejected"] == 0
    queued = client.post("/training-runs").json()
    assert work_once()
    run = client.get(f"/training-runs/{queued['id']}").json()
    assert run["status"] == "succeeded", run
    assert run["report"]["activation_allowed"]
    assert len(run["report"]["candidates"]) == 5
    assert (
        client.post(f"/models/{run['id']}/activate", json={"reviewed_limits": False}).status_code
        == 422
    )
    assert (
        client.post(f"/models/{run['id']}/activate", json={"reviewed_limits": True}).status_code
        == 200
    )
    order = {"order_id": "N1", "ordered_at": "2025-01-01", "promised_delivery_at": "2025-01-03"}
    first = client.post("/predict", json=order).json()
    assert 0 <= first["predictions"][0]["risk_score"] <= 1
    orders = [order, {**order, "order_id": "N2", "carrier": "never-seen"}]
    assert client.post("/predict/batch", json={"orders": orders}).status_code == 200
    assert client.post("/predict/batch", json={"orders": [order, order]}).status_code == 422
    assert client.post("/predict", json={**order, "delivered_at": "2025-01-04"}).status_code == 422
    engine().dispose()
    assert client.post("/predict", json=order).json() == first
    assert client.get("/exports/orders.csv").status_code == 200
    artifact = settings().data_dir / "models" / f"{run['id']}.joblib"
    artifact.write_bytes(b"corrupted")
    assert client.post("/predict", json=order).json()["error"]["code"] == "artifact_corrupted"
    assert (
        client.post(f"/models/{run['id']}/activate", json={"reviewed_limits": True}).status_code
        == 503
    )


def test_worker_crash_recovery_and_singleton(client):
    from sqlalchemy import text

    from deliveryguard.db import Run, session

    run_id = client.post("/training-runs").json()["id"]
    with engine().connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(614033)"))
        connection.commit()
        assert not work_once()
        connection.execute(text("SELECT pg_advisory_unlock(614033)"))
        connection.commit()
    with session() as db, db.begin():
        db.get(Run, run_id).status = "running"
    assert not work_once()
    run = client.get(f"/training-runs/{run_id}").json()
    assert run["status"] == "failed"
    assert run["report"]["code"] == "worker_interrupted"


def test_response_contracts_and_http_errors(client):
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/predict"]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("PredictionResponse")
    assert client.get("/missing").json()["error"]["code"] == "http_error"


def test_synthetic_generator_reproducible():
    assert generate() == generate()
    assert generate(seed=41) != generate()


def test_demo_limits_and_explicit_security(client, monkeypatch, tmp_path):
    from deliveryguard.config import Settings

    with pytest.raises(RuntimeError, match="DG_API_KEY"):
        Settings(_env_file=None, demo=False, api_key="", data_dir=tmp_path).validate_security()
    monkeypatch.setattr(settings(), "demo", True)
    client.headers.clear()
    assert client.get("/models").status_code == 200
    assert upload(client, generate(5001)).status_code == 413


def test_optional_columns_do_not_block_base_workflow(client):
    frame = pd.read_csv(io.BytesIO(generate()))
    minimal = frame[["order_id", "ordered_at", "promised_delivery_at", "delivered_at", "status"]]
    receipt = upload(client, minimal.to_csv(index=False).encode()).json()
    assert receipt["valid"] == 1500
    queued = client.post("/training-runs").json()
    assert work_once()
    result = client.get(f"/training-runs/{queued['id']}").json()
    assert result["status"] == "succeeded", result


def test_migration_matches_current_schema():
    from alembic import command
    from alembic.config import Config

    command.check(Config("alembic.ini"))
