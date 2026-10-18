"""Public response contracts used by OpenAPI; business logic lives in services."""

from datetime import datetime

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Issue(BaseModel):
    code: str
    count: int
    action: str


class QualityReport(BaseModel):
    total: int
    valid: int
    rejected: int
    inserted: int
    updated: int
    unchanged: int
    preview: bool
    issues: list[Issue]
    examples: list[dict]
    warnings: list[str]
    observable: int
    late_rate: float | None


class ImportReceipt(QualityReport):
    id: str
    reused: bool = False


class QueuedRun(BaseModel):
    id: str
    status: str


class TrainingRun(QueuedRun):
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    report: dict


class ModelInfo(TrainingRun):
    active: bool


class PredictionItem(BaseModel):
    order_id: str
    risk_score: float
    risk_label: str


class PredictionResponse(BaseModel):
    model_id: str
    threshold: float
    score_note: str
    predictions: list[PredictionItem]


class Summary(BaseModel):
    counts: dict[str, int]
    total: int
    observed: int
    late: int
    late_rate: float | None
    overdue_count: int
    overdue: list[dict]
    late_by_carrier: list[dict]
    as_of: str
    warning: str
