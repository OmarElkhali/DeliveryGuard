from datetime import UTC, datetime
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from deliveryguard.config import settings


def now():
    return datetime.now(UTC)


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'delivered', 'cancelled')", name="status_valid"),
        CheckConstraint("promised_delivery_at >= ordered_at", name="promise_valid"),
        CheckConstraint(
            "(status = 'delivered') = (delivered_at IS NOT NULL)", name="outcome_valid"
        ),
        CheckConstraint("delivered_at >= ordered_at", name="delivery_valid"),
        CheckConstraint("weight_kg >= 0 AND order_amount >= 0", name="nonnegative"),
    )
    order_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    promised_delivery_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    carrier: Mapped[str | None] = mapped_column(String(128))
    destination_zone: Mapped[str | None] = mapped_column(String(128))
    product_category: Mapped[str | None] = mapped_column(String(128))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    order_amount: Mapped[float | None] = mapped_column(Float)


class Import(Base):
    __tablename__ = "imports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    report: Mapped[dict] = mapped_column(JSON)


class Run(Base):
    __tablename__ = "training_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)


class ActiveModel(Base):
    __tablename__ = "active_model"
    __table_args__ = (CheckConstraint("id = 1", name="single_active"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("training_runs.id"))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)


@lru_cache
def engine():
    return create_engine(
        settings().database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"options": "-c timezone=UTC"},
    )


def session():
    return Session(engine())
