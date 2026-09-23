import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nms_common.db import Base
from nms_common.enums import (
    AlertOperator,
    AlertScope,
    AlertSeverity,
    AlertStatus,
    DeviceType,
    EventSeverity,
    EventType,
    MetricType,
    RuleKind,
)
from nms_common.models.base import CreatedAtMixin, TimestampMixin, UUIDPKMixin


class AlertRule(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "alert_rules"

    name: Mapped[str] = mapped_column(String(255))
    rule_kind: Mapped[RuleKind] = mapped_column(default=RuleKind.METRIC_THRESHOLD)
    metric_type: Mapped[MetricType | None] = mapped_column()
    operator: Mapped[AlertOperator | None] = mapped_column()
    threshold: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[AlertSeverity] = mapped_column(default=AlertSeverity.WARNING)
    scope: Mapped[AlertScope] = mapped_column(default=AlertScope.GLOBAL)
    device_type: Mapped[DeviceType | None] = mapped_column()
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    consecutive_breaches_to_open: Mapped[int] = mapped_column(default=2)
    consecutive_ok_to_resolve: Mapped[int] = mapped_column(default=2)


class Alert(Base, UUIDPKMixin):
    __tablename__ = "alerts"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    interface_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interfaces.id", ondelete="CASCADE")
    )
    alert_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="SET NULL")
    )
    severity: Mapped[AlertSeverity] = mapped_column(index=True)
    metric: Mapped[str] = mapped_column(String(64))
    threshold: Mapped[float | None] = mapped_column(Float)
    current_value: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str] = mapped_column(String(1000))
    status: Mapped[AlertStatus] = mapped_column(default=AlertStatus.OPEN, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    device = relationship("Device")
    interface = relationship("Interface")
    acknowledged_by = relationship("User")


class Event(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "events"

    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    interface_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interfaces.id", ondelete="CASCADE")
    )
    event_type: Mapped[EventType] = mapped_column(index=True)
    severity: Mapped[EventSeverity] = mapped_column(default=EventSeverity.INFO)
    message: Mapped[str] = mapped_column(String(1000))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    device = relationship("Device")
    interface = relationship("Interface")
