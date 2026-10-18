import csv
import io
import random
from datetime import UTC, datetime, timedelta

from deliveryguard.quality import FIELDS


def generate(n=1500, seed=42):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        ordered = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(
            hours=i * min(6, 24 * 600 / max(n, 1))
        )
        carrier = rng.choice(["Atlas", "Express", "Régional"])
        zone = rng.choice(["Centre", "Périphérie", "Rural"])
        promise = ordered + timedelta(hours=rng.choice([24, 48, 72, 96]))
        risk = 0.08 + 0.4 * (carrier == "Régional") + 0.22 * (zone == "Rural")
        late = rng.random() < risk
        delivered = promise + timedelta(hours=rng.randint(2, 48) if late else -rng.randint(0, 18))
        status = rng.choices(["delivered", "open", "cancelled"], weights=[90, 7, 3])[0]
        rows.append(
            {
                "order_id": f"SYN-{seed}-{i:05}",
                "ordered_at": ordered.isoformat(),
                "promised_delivery_at": promise.isoformat(),
                "delivered_at": delivered.isoformat() if status == "delivered" else "",
                "status": status,
                "carrier": carrier,
                "destination_zone": zone,
                "product_category": rng.choice(["Maison", "Mode", "Électronique"]),
                "weight_kg": round(rng.uniform(0.1, 20), 2),
                "order_amount": round(rng.uniform(10, 900), 2),
            }
        )
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")
