import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from nms_common.db import Base
from nms_common.enums import MetricType

# Metric and InterfaceMetric are converted into TimescaleDB hypertables by the
# baseline Alembic migration (SELECT create_hypertable(...)). Timescale requires the
# partitioning column ("time") to be part of every unique/primary key, so these tables
# intentionally have no single-column primary key -- `id` is just an indexed identifier.


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_device_type_time", "device_id", "metric_type", "time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    metric_type: Mapped[MetricType] = mapped_column(primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))


class InterfaceMetric(Base):
    __tablename__ = "interface_metrics"
    __table_args__ = (
        Index("ix_ifmetrics_interface_time", "interface_id", "time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    interface_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interfaces.id", ondelete="CASCADE"), primary_key=True
    )
    in_octets: Mapped[int | None] = mapped_column(BigInteger)
    out_octets: Mapped[int | None] = mapped_column(BigInteger)
    in_bps: Mapped[float | None] = mapped_column(Float)
    out_bps: Mapped[float | None] = mapped_column(Float)
    errors_in: Mapped[int | None] = mapped_column(BigInteger)
    errors_out: Mapped[int | None] = mapped_column(BigInteger)
    discards_in: Mapped[int | None] = mapped_column(BigInteger)
    discards_out: Mapped[int | None] = mapped_column(BigInteger)
