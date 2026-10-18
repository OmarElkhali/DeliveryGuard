"""Preserve order-time inputs; never infer them from already mutable legacy rows."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column("orders", sa.Column("initial_snapshot", sa.JSON(none_as_null=True)))
    op.add_column(
        "orders", sa.Column("snapshot_excluded", sa.Boolean, nullable=False, server_default="false")
    )
    op.execute("""
        CREATE FUNCTION guard_initial_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.initial_snapshot::jsonb IS DISTINCT FROM OLD.initial_snapshot::jsonb
               OR (OLD.snapshot_excluded AND NOT NEW.snapshot_excluded) THEN
                RAISE EXCEPTION 'Initial snapshot is immutable; exclusion is irreversible';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER immutable_initial_snapshot BEFORE UPDATE ON orders
        FOR EACH ROW EXECUTE FUNCTION guard_initial_snapshot()
    """)
    # Pre-migration models may have learned revised features/targets. Require a new evaluation.
    op.execute("DELETE FROM active_model")
    op.execute("""
        UPDATE training_runs SET report = (
            report::jsonb || '{"activation_allowed": false,
            "activation_reason": "Legacy evaluation: initial snapshots were not preserved; retrain"}'::jsonb
        )::json WHERE status = 'succeeded'
    """)


def downgrade():
    op.execute("DROP TRIGGER immutable_initial_snapshot ON orders")
    op.execute("DROP FUNCTION guard_initial_snapshot()")
    op.drop_column("orders", "snapshot_excluded")
    op.drop_column("orders", "initial_snapshot")
