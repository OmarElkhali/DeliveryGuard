import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from deliveryguard import __version__, service
from deliveryguard.config import settings
from deliveryguard.contracts import (
    ErrorResponse,
    ImportReceipt,
    ModelInfo,
    PredictionResponse,
    QualityReport,
    QueuedRun,
    Summary,
    TrainingRun,
)
from deliveryguard.db import Import, engine, session
from deliveryguard.quality import DomainError, NewOrder, csv_bytes

logger = logging.getLogger("deliveryguard")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app):
    settings().validate_security()
    yield


app = FastAPI(
    title="DeliveryGuard",
    version=__version__,
    lifespan=lifespan,
    description="Single-company pilot. Explicit model activation. Uncalibrated risk scores.",
    responses={
        code: {"model": ErrorResponse} for code in [400, 401, 404, 409, 413, 415, 422, 500, 503]
    },
)
key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def authorize(key: Annotated[str | None, Depends(key_header)]):
    config = settings()
    if config.demo:
        return
    if (
        not config.api_key
        or not key
        or not secrets.compare_digest(key.encode(), config.api_key.encode())
    ):
        raise DomainError("unauthorized", "Clé API requise", 401)


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    started = time.monotonic()
    # Bound streamed bodies too, not only clients that supply Content-Length.
    size = 0
    original_receive = request._receive

    async def limited_receive():
        nonlocal size
        message = await original_receive()
        size += len(message.get("body", b""))
        if size > settings().max_upload_bytes + 65536:
            raise DomainError("body_too_large", "Requête trop volumineuse", 413)
        return message

    request._receive = limited_receive
    try:
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > settings().max_upload_bytes + 65536):
            raise DomainError("body_too_large", "Requête trop volumineuse", 413)
        response = await call_next(request)
    except DomainError as exc:
        response = await domain_error(request, exc)
    except Exception:
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Erreur interne",
                    "request_id": request_id,
                }
            },
        )
    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


@app.exception_handler(DomainError)
async def domain_error(request, exc):
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Requête invalide",
                "details": [{"field": list(e["loc"]), "message": e["msg"]} for e in exc.errors()],
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return await domain_error(
        request,
        DomainError(
            "http_error",
            "Ressource introuvable" if exc.status_code == 404 else "Requête HTTP invalide",
            exc.status_code,
        ),
    )


@app.get("/health/live")
def live():
    return {"status": "alive", "version": __version__, "demo": settings().demo}


@app.get("/health/ready")
def ready():
    try:
        with engine().connect() as db:
            revision = db.scalar(text("SELECT version_num FROM alembic_version"))
            db.execute(text("SELECT 1 FROM orders LIMIT 1"))
        if revision != "0001":
            raise RuntimeError("Migration required")
        settings().validate_security()
        return {"status": "ready"}
    except Exception:
        raise DomainError("not_ready", "Base ou migrations indisponibles", 503) from None


async def upload(file, mapping):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise DomainError("invalid_type", "Seuls les fichiers .csv sont acceptés", 415)
    if file.content_type not in {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }:
        raise DomainError("invalid_type", "Type CSV requis", 415)
    try:
        parsed = json.loads(mapping) if mapping else None
        if parsed is not None and (
            not isinstance(parsed, dict) or any(not isinstance(v, str) for v in parsed.values())
        ):
            raise ValueError()
    except (ValueError, TypeError):
        raise DomainError(
            "invalid_mapping", "Mapping attendu : objet JSON source → champ DeliveryGuard"
        ) from None
    raw = await file.read(settings().max_upload_bytes + 1)
    return raw, parsed


@app.post("/imports/preview", response_model=QualityReport, dependencies=[Depends(authorize)])
async def preview(
    file: Annotated[UploadFile, File()],
    mapping: Annotated[str, Form()] = "",
    update: Annotated[bool, Form()] = False,
):
    from starlette.concurrency import run_in_threadpool

    raw, parsed = await upload(file, mapping)
    return await run_in_threadpool(service.import_csv, raw, parsed, update, True)


@app.post(
    "/imports", status_code=201, response_model=ImportReceipt, dependencies=[Depends(authorize)]
)
async def import_file(
    file: Annotated[UploadFile, File()],
    mapping: Annotated[str, Form()] = "",
    update: Annotated[bool, Form()] = False,
):
    from starlette.concurrency import run_in_threadpool

    raw, parsed = await upload(file, mapping)
    return await run_in_threadpool(service.import_csv, raw, parsed, update)


@app.get("/imports", dependencies=[Depends(authorize)])
def imports():
    from sqlalchemy import select

    with session() as db:
        return [
            {"id": i.id, "created_at": i.created_at, **i.report}
            for i in db.scalars(select(Import).order_by(Import.created_at.desc()).limit(100))
        ]


@app.get(
    "/imports/{import_id}/quality", response_model=ImportReceipt, dependencies=[Depends(authorize)]
)
def quality(import_id: UUID):
    with session() as db:
        item = db.get(Import, str(import_id))
        if not item:
            raise DomainError("not_found", "Import introuvable", 404)
        return {"id": item.id, **item.report}


@app.get("/imports/{import_id}/rejected", dependencies=[Depends(authorize)])
def rejected(import_id: UUID):
    return FileResponse(
        service.import_path(str(import_id), "rejected.csv"),
        media_type="text/csv",
        filename="rejected.csv",
    )


@app.post(
    "/training-runs", status_code=202, response_model=QueuedRun, dependencies=[Depends(authorize)]
)
def training():
    return service.enqueue()


@app.get("/training-runs/{run_id}", response_model=TrainingRun, dependencies=[Depends(authorize)])
def training_run(run_id: UUID):
    return service.get_run(str(run_id))


@app.get("/models", response_model=list[ModelInfo], dependencies=[Depends(authorize)])
def models():
    return service.model_list()


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewed_limits: bool


@app.post("/models/{model_id}/activate", dependencies=[Depends(authorize)])
def activate(model_id: UUID, body: Confirmation):
    return service.activate(str(model_id), body.reviewed_limits)


@app.post("/predict", response_model=PredictionResponse, dependencies=[Depends(authorize)])
def predict(body: NewOrder):
    return service.predict([body.model_dump()])


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orders: list[NewOrder] = Field(min_length=1, max_length=1000)


@app.post("/predict/batch", response_model=PredictionResponse, dependencies=[Depends(authorize)])
def batch(body: Batch):
    ids = [o.order_id for o in body.orders]
    if len(ids) != len(set(ids)):
        raise DomainError("duplicate_id", "Identifiants dupliqués dans le batch")
    return service.predict([o.model_dump() for o in body.orders])


@app.get("/analytics/summary", response_model=Summary, dependencies=[Depends(authorize)])
def analytics():
    return service.summary()


@app.get("/exports/orders.csv", dependencies=[Depends(authorize)])
def export_orders():
    with session() as db:
        rows = service.orders_frame(db).to_dict("records")
    for row in rows:
        row["observed_late"] = (
            int(row["delivered_at"] > row["promised_delivery_at"])
            if row["status"] == "delivered"
            else None
        )
    return Response(
        csv_bytes(rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="orders.csv"'},
    )
