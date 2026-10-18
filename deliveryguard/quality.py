import csv
import io
import math
import re
from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from deliveryguard.config import settings

FIELDS = [
    "order_id",
    "ordered_at",
    "promised_delivery_at",
    "delivered_at",
    "status",
    "carrier",
    "destination_zone",
    "product_category",
    "weight_kg",
    "order_amount",
]
REQUIRED = {"order_id", "ordered_at", "promised_delivery_at", "status"}
ACTIONS = {
    "missing_id": "Renseigner un identifiant stable.",
    "duplicate_id": "Conserver une seule ligne par identifiant dans le fichier.",
    "invalid_row": "Vérifier les formats ISO 8601, les nombres et le statut.",
    "conflict": "Vérifier la commande existante puis autoriser explicitement la mise à jour.",
    "immutable_order_date": "La date de commande existante ne peut pas changer.",
    "terminal_status": "Une commande terminée ne peut pas redevenir ouverte ou changer d'issue.",
}


class DomainError(Exception):
    def __init__(self, code, message, status=422, details=None):
        self.code, self.message, self.status, self.details = code, message, status, details


def parse_date(value):
    if isinstance(value, datetime):
        dt = value
    else:
        value = str(value).strip()
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})?)?", value
        ):
            raise ValueError("Date ISO 8601 attendue; dates ambiguës refusées")
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Dates without an offset explicitly mean UTC, never workstation local time.
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


class NewOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    order_id: str = Field(min_length=1, max_length=128)
    ordered_at: datetime
    promised_delivery_at: datetime
    carrier: str | None = Field(default=None, max_length=128)
    destination_zone: str | None = Field(default=None, max_length=128)
    product_category: str | None = Field(default=None, max_length=128)
    weight_kg: float | None = Field(default=None, ge=0)
    order_amount: float | None = Field(default=None, ge=0)

    @field_validator("ordered_at", "promised_delivery_at", mode="before")
    @classmethod
    def dates(cls, value):
        return parse_date(value)

    @model_validator(mode="after")
    def chronology(self):
        if self.promised_delivery_at < self.ordered_at:
            raise ValueError("La promesse précède la commande")
        if self.ordered_at > datetime.now(UTC):
            raise ValueError("La date de commande est dans le futur")
        return self


class HistoryOrder(NewOrder):
    status: str
    delivered_at: datetime | None = None

    @field_validator("delivered_at", mode="before")
    @classmethod
    def delivery_date(cls, value):
        return None if value is None else parse_date(value)

    @model_validator(mode="after")
    def outcome(self):
        if self.status not in {"open", "delivered", "cancelled"}:
            raise ValueError("Statut attendu : open, delivered ou cancelled")
        if (self.status == "delivered") != (self.delivered_at is not None):
            raise ValueError("Seul le statut delivered exige une date de livraison")
        if self.delivered_at is not None:
            if self.delivered_at < self.ordered_at:
                raise ValueError("La livraison précède la commande")
            if self.delivered_at > datetime.now(UTC):
                raise ValueError("Une livraison observée ne peut pas être dans le futur")
        return self


def read_csv(raw, mapping=None):
    if len(raw) > settings().max_upload_bytes:
        raise DomainError("file_too_large", "CSV limité à 5 Mio", 413)
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader)
        if not header or len(set(header)) != len(header) or any(not c.strip() for c in header):
            raise ValueError("En-tête vide ou dupliqué")
        mapping = mapping or {h: h for h in header}
        if set(mapping) != set(header) or len(set(mapping.values())) != len(mapping):
            raise ValueError(
                "Mapper chaque colonne une seule fois; supprimer les colonnes hors schéma"
            )
        if not set(mapping.values()) <= set(FIELDS):
            raise ValueError("Colonnes hors schéma refusées; retirer toute donnée personnelle")
        missing = REQUIRED - set(mapping.values())
        if missing:
            raise DomainError(
                "missing_columns", "Colonnes obligatoires absentes", details=sorted(missing)
            )
        rows = []
        limit = min(settings().max_rows, 5000) if settings().demo else settings().max_rows
        for number, values in enumerate(reader, 2):
            if len(values) != len(header):
                raise ValueError(f"Nombre de colonnes incorrect à la ligne {number}")
            rows.append({mapping[h]: v for h, v in zip(header, values, strict=True)})
            if len(rows) > limit:
                raise DomainError("too_many_rows", f"Limite : {limit} lignes", 413)
        if not rows:
            raise ValueError("CSV vide")
        return rows
    except (UnicodeError, csv.Error, ValueError, StopIteration) as exc:
        raise DomainError(
            "malformed_csv", "CSV UTF-8 à virgules invalide", details=str(exc)
        ) from exc


def audit(rows):
    counts = Counter(str(r.get("order_id", "")).strip() for r in rows)
    accepted, rejected = [], []
    for number, row in enumerate(rows, 2):
        row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        code, message = None, None
        oid = row.get("order_id", "")
        if not oid:
            code, message = "missing_id", "Identifiant manquant"
        elif counts[oid] > 1:
            code, message = (
                "duplicate_id",
                "Toutes les occurrences de cet identifiant sont rejetées",
            )
        else:
            try:
                clean = HistoryOrder.model_validate({k: v or None for k, v in row.items()})
                accepted.append((number, clean.model_dump()))
            except ValueError as exc:
                code, message = "invalid_row", str(exc)
        if code:
            rejected.append({"row": number, "code": code, "reason": message, "values": row})
    return accepted, rejected


def report(total, accepted, rejected, **counters):
    issues = Counter(r["code"] for r in rejected)
    delivered = [r for _, r in accepted if r["status"] == "delivered"]
    labels = [int(r["delivered_at"] > r["promised_delivery_at"]) for r in delivered]
    warnings = []
    if len(delivered) < 120:
        warnings.append(
            "Cet import contient moins de 120 livraisons observées : il ne suffit pas à lui seul pour entraîner."
        )
    if len(set(labels)) < 2:
        warnings.append(
            "Cet import ne contient pas les deux classes. Le ML vérifiera l'ensemble des commandes stockées."
        )
    warnings.append("Commandes ouvertes et annulées exclues du ML : biais de sélection possible.")
    return {
        "total": total,
        "valid": len(accepted),
        "rejected": len(rejected),
        **counters,
        "issues": [{"code": k, "count": v, "action": ACTIONS[k]} for k, v in issues.items()],
        "examples": [{k: v for k, v in r.items() if k != "values"} for r in rejected[:5]],
        "warnings": warnings,
        "observable": len(delivered),
        "late_rate": sum(labels) / len(labels) if labels else None,
    }


def safe_cell(value):
    if isinstance(value, datetime):
        value = value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    # Escape data AND source-column headers on human-facing spreadsheet exports.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_bytes(rows, fields=None):
    buf = io.StringIO(newline="")
    fields = fields or (list(rows[0]) if rows else FIELDS)
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writerow({field: safe_cell(field) for field in fields})
    for row in rows:
        writer.writerow({k: safe_cell(value) for k, value in row.items()})
    return buf.getvalue().encode("utf-8-sig")
