# Integration guide

All business endpoints require `X-API-Key` unless the instance is explicitly in
local synthetic demo mode. Liveness and readiness are public and expose no rows.
OpenAPI lives at `/openapi.json`, interactive reference at `/docs`. IDs are UUIDs.
Errors use `{ "error": { "code", "message", "details", "request_id" } }` and
`X-Request-ID`. Validation errors omit raw input. Standard codes: 401 unauthorized,
404 missing resource, 409 state conflict, 413 limit, 415 file type, 422 validation,
503 readiness/artifact unavailable. Unknown routes use the same structured shape.

| Method | Route | Contract |
|---|---|---|
| GET | /health/live | process alive/version/demo flag |
| GET | /health/ready | DB and migration available; model not required |
| POST | /imports/preview | multipart CSV + mapping JSON string + update bool; no persistence |
| POST | /imports | same multipart; 201 receipt, counters, examples, warnings |
| GET | /imports | most recent 100 receipts |
| GET | /imports/{id}/quality | persisted audit |
| GET | /imports/{id}/rejected | rejected rows CSV |
| POST | /training-runs | no body; 202 persistent queued run, worker required |
| GET | /training-runs/{id} | persistent state and report |
| GET | /models | runs and active flag |
| POST | /models/{id}/activate | JSON `{"reviewed_limits":true}` |
| POST | /predict | one NewOrder, no outcome fields |
| POST | /predict/batch | `{"orders":[NewOrder,...]}`, 1..1000 unique IDs |
| GET | /analytics/summary | SQL counts, observed rate, operational overdue alerts |
| GET | /exports/orders.csv | UTF-8 BOM, observed_late nullable for non-delivered |

Predictions return `model_id`, `threshold`, `score_note`, and `predictions` sorted
by decreasing risk score. Labels are “À examiner” / “Priorité moindre”. A low score
does not guarantee on-time delivery. Input does not have to already exist in DB;
prediction requests themselves are not persisted. To monitor open orders over time,
import them with `status=open`, and later reimport with `update=true` when delivered
or cancelled. Monitoring alerts are derived from stored open orders.

## curl (POSIX shell; Windows use curl.exe and adapt quoting)

```sh
export DG_KEY='your-local-instance-key'
curl -fsS http://localhost:8000/health/ready
curl -fsS -H "X-API-Key: $DG_KEY" \
  -F 'file=@examples/mapped_history.csv;type=text/csv' \
  -F "mapping=$(cat examples/mapping.json)" http://localhost:8000/imports/preview
curl -fsS -H "X-API-Key: $DG_KEY" \
  -F 'file=@examples/mapped_history.csv;type=text/csv' \
  -F "mapping=$(cat examples/mapping.json)" http://localhost:8000/imports
curl -fsS -H "X-API-Key: $DG_KEY" -X POST http://localhost:8000/training-runs
curl -fsS -H "X-API-Key: $DG_KEY" http://localhost:8000/training-runs/RUN_UUID
curl -fsS -H "X-API-Key: $DG_KEY" -H 'Content-Type: application/json' \
  -d '{"reviewed_limits":true}' http://localhost:8000/models/RUN_UUID/activate
curl -fsS -H "X-API-Key: $DG_KEY" -H 'Content-Type: application/json' \
  -d '{"order_id":"ERP-1","ordered_at":"2026-01-01T10:00:00Z","promised_delivery_at":"2026-01-03T10:00:00Z"}' \
  http://localhost:8000/predict
```

The three-row mapping example is too small for ML by design; train on a sufficiently
large historical dataset, or use the 1,500-row synthetic demonstration. Poll the run
until `succeeded` or `failed`; do not assume HTTP 202 means the model is ready. If
`activation_allowed=false`, read the reason. Never retry activation to bypass it.

## Python

```python
import json
import os
import time
from pathlib import Path
import requests

api = requests.Session()
api.headers["X-API-Key"] = os.environ["DG_API_KEY"]
base = "http://localhost:8000"


def call(method, path, **kwargs):
    response = api.request(method, base + path, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


raw = Path("examples/synthetic.csv").read_bytes()  # synthetic only
receipt = call("POST", "/imports", files={"file": ("history.csv", raw, "text/csv")})
quality = call("GET", f"/imports/{receipt['id']}/quality")
print(quality["valid"], quality["rejected"], quality["warnings"])
run = call("POST", "/training-runs")
for _ in range(120):
    result = call("GET", f"/training-runs/{run['id']}")
    if result["status"] not in ("queued", "running"):
        break
    time.sleep(1)
print(json.dumps(result, indent=2, ensure_ascii=False))
# Human reviews this report before deliberately issuing the activation call:
# call('POST', f"/models/{run['id']}/activate", json={'reviewed_limits': True})
# Then: call('POST', '/predict/batch', json={'orders': [...]})
```

For an unattended reproducible **synthetic** check, use `deliveryguard smoke`
instead. Neither this example nor the API silently starts a worker. Operator CLI:
`deliveryguard worker` or `deliveryguard worker --once`. The latter processes at
most one pending run and then exits; idle is a successful no-op.
