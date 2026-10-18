"""Compare live synthetic instances after restart or isolated restoration."""

import argparse
import hashlib
import json
from pathlib import Path

import requests

from deliveryguard.config import settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["record", "verify"])
    args = parser.parse_args()
    config = settings()
    client = requests.Session()
    client.headers["X-API-Key"] = config.api_key

    def call(method, path, **kwargs):
        response = client.request(method, config.api_url + path, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    assert call("GET", "/health/live")["demo"], "Synthetic demo only"
    summary = call("GET", "/analytics/summary")
    models = call("GET", "/models")
    active = next(m for m in models if m["active"])
    prediction = call(
        "POST",
        "/predict",
        json={
            "order_id": "PERSISTENCE-CHECK",
            "ordered_at": "2025-01-01",
            "promised_delivery_at": "2025-01-03",
        },
    )
    exported = client.get(config.api_url + "/exports/orders.csv", timeout=30)
    exported.raise_for_status()
    snapshot = {
        "counts": summary["counts"],
        "total": summary["total"],
        "model_id": active["id"],
        "prediction": prediction,
        "orders_export_sha256": hashlib.sha256(exported.content).hexdigest(),
        "imports": call("GET", "/imports"),
        "models": models,
    }
    path = Path("artifacts/persistence-before.json")
    path.parent.mkdir(exist_ok=True)
    if args.operation == "record":
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        print("Recorded synthetic orders export, receipts, model reports and prediction.")
    else:
        assert snapshot == json.loads(path.read_text(encoding="utf-8")), "Persistence changed"
        Path("artifacts/persistence-result.json").write_text(
            json.dumps({"status": "passed", **snapshot}, indent=2), encoding="utf-8"
        )
        print(
            "PASS: counts, order snapshots/export, receipts, model reports and exact prediction match"
        )


if __name__ == "__main__":
    main()
