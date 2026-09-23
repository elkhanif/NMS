import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nms_common.db import Base
from nms_common.enums import DeviceStatus, IncidentConfidence, IncidentEventRole, IncidentStatus
from nms_common.models.base import TimestampMixin, UUIDPKMixin


class DeviceStateHistory(Base, UUIDPKMixin):
    """Structured, queryable device status transitions -- distinct in purpose from
    Event (the human-readable narrative log used for the Timeline UI as-is): this is
    the numeric/interval-friendly source for uptime %, "last outage window", and the
    correlator's timestamp-proximity math. Always written in the same transaction as
    the corresponding Event (see worker.collectors) so the two can never drift apart.
    """

    __tablename__ = "device_state_history"
    __table_args__ = (Index("ix_device_state_history_device_time", "device_id", "changed_at"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    previous_status: Mapped[DeviceStatus | None] = mapped_column()
    new_status: Mapped[DeviceStatus] = mapped_column()
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    triggering_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )


class Incident(Base, UUIDPKMixin, TimestampMixin):
    """A correlated group of related events (e.g. a switch outage and everything that
    went unreachable behind it). Only ever created by worker.correlator with
    confidence POSSIBLE/SUSPECTED; confidence CONFIRMED is only ever set by a human
    via PATCH /incidents/{id} -- the correlator must never claim root cause on its
    own evidence."""

    __tablename__ = "incidents"

    sequence_number: Mapped[int] = mapped_column(
        Integer, unique=True, server_default=text("nextval('incident_seq')")
    )
    suspected_device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[IncidentStatus] = mapped_column(default=IncidentStatus.OPEN, index=True)
    confidence: Mapped[IncidentConfidence] = mapped_column(default=IncidentConfidence.POSSIBLE)
    title: Mapped[str] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    affected_device_count: Mapped[int] = mapped_column(Integer, default=0)
    root_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)

    suspected_device = relationship("Device")
    incident_events: Mapped[list["IncidentEvent"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentEvent(Base, UUIDPKMixin):
    """Many-to-many join between an Incident and the Events that make it up (trigger,
    affected devices' own down events, and eventual recovery events)."""

    __tablename__ = "incident_events"
    __table_args__ = (UniqueConstraint("incident_id", "event_id", name="uq_incident_event"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[IncidentEventRole] = mapped_column()

    incident: Mapped[Incident] = relationship(back_populates="incident_events")
    event = relationship("Event")
