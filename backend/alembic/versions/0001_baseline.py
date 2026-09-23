"""baseline schema

Creates every table from the nms_common models in one shot (via metadata.create_all)
rather than hand-written op.create_table calls, since this is the very first
migration and the models ARE the source of truth at this point. Subsequent schema
changes should be normal `alembic revision --autogenerate` diffs against this baseline.

Also enables the timescaledb extension and converts `metrics` / `interface_metrics`
into hypertables partitioned on their `time` column.

Revision ID: 0001
Revises:
Create Date: 2026-09-23

"""
import sqlalchemy as sa
from alembic import op

from nms_common.db import Base
from nms_common.models import *  # noqa: F401,F403  (ensures every model is registered)

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb"))

    Base.metadata.create_all(bind=bind)

    bind.execute(sa.text("SELECT create_hypertable('metrics', 'time', if_not_exists => TRUE)"))
    bind.execute(sa.text("SELECT create_hypertable('interface_metrics', 'time', if_not_exists => TRUE)"))


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
