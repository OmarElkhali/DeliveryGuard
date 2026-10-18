import json
import time

import requests

from deliveryguard.config import settings
from deliveryguard.synthetic import generate


def smoke():
    config = settings()
    client = requests.Session()
    client.headers["X-API-Key"] = config.api_key

    def call(method, path, **kwargs):
        response = client.request(method, config.api_url + path, timeout=60, **kwargs)
        if not response.ok:
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code} {response.text}")
        return response.json()

    call("GET", "/health/ready")
    imported = call("POST", "/imports", files={"file": ("synthetic.csv", generate(), "text/csv")})
    quality = call("GET", f"/imports/{imported['id']}/quality")
    assert quality["rejected"] == 0
    run = call("POST", "/training-runs")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = call("GET", f"/training-runs/{run['id']}")
        if result["status"] not in {"queued", "running"}:
            break
        time.sleep(1)
    assert result["status"] == "succeeded", result
    assert result["report"]["activation_allowed"], result["report"]
    call("POST", f"/models/{run['id']}/activate", json={"reviewed_limits": True})
    predicted = call(
        "POST",
        "/predict/batch",
        json={
            "orders": [
                {
                    "order_id": "SMOKE-1",
                    "ordered_at": "2026-01-01T10:00:00Z",
                    "promised_delivery_at": "2026-01-03T10:00:00Z",
                    "carrier": "Régional",
                    "destination_zone": "Rural",
                },
                {
                    "order_id": "SMOKE-2",
                    "ordered_at": "2026-01-01T10:00:00Z",
                    "promised_delivery_at": "2026-01-04T10:00:00Z",
                    "carrier": "Atlas",
                    "destination_zone": "Centre",
                },
            ]
        },
    )
    assert len(predicted["predictions"]) == 2
    print(
        json.dumps(
            {
                "import_id": imported["id"],
                "rows": quality["valid"],
                "run_id": run["id"],
                "selected": result["report"]["selected"],
                "splits": result["report"]["splits"],
                "test": result["report"]["test"],
                "predictions": predicted,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
