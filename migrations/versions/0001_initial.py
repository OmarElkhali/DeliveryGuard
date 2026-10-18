"""DeliveryGuard v0.1 persistent schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(128), primary_key=True),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("promised_delivery_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("carrier", sa.String(128)),
        sa.Column("destination_zone", sa.String(128)),
        sa.Column("product_category", sa.String(128)),
        sa.Column("weight_kg", sa.Float),
        sa.Column("order_amount", sa.Float),
        sa.CheckConstraint("status IN ('open', 'delivered', 'cancelled')", name="status_valid"),
        sa.CheckConstraint("promised_delivery_at >= ordered_at", name="promise_valid"),
        sa.CheckConstraint(
            "(status = 'delivered') = (delivered_at IS NOT NULL)", name="outcome_valid"
        ),
        sa.CheckConstraint("delivered_at >= ordered_at", name="delivery_valid"),
        sa.CheckConstraint("weight_kg >= 0 AND order_amount >= 0", name="nonnegative"),
    )
    op.create_index("ix_orders_ordered_at", "orders", ["ordered_at"])
    op.create_table(
        "imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fingerprint", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report", sa.JSON, nullable=False),
    )
    op.create_table(
        "training_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("report", sa.JSON, nullable=False),
    )
    op.create_index("ix_training_runs_status", "training_runs", ["status"])
    op.create_table(
        "active_model",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("training_runs.id"), nullable=False),
        sa.Column("confirmed", sa.Boolean, nullable=False),
        sa.CheckConstraint("id = 1", name="single_active"),
    )


def downgrade():
    for table in ["active_model", "training_runs", "imports", "orders"]:
        op.drop_table(table)
