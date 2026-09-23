import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nms_common.db import Base
from nms_common.enums import CheckType, DeviceType, DiscoveryJobStatus, MonitoringJobStatus
from nms_common.models.base import CreatedAtMixin, UUIDPKMixin


class MonitoringJob(Base, UUIDPKMixin):
    __tablename__ = "monitoring_jobs"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    check_type: Mapped[CheckType] = mapped_column()
    status: Mapped[MonitoringJobStatus] = mapped_column(default=MonitoringJobStatus.PENDING)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(1000))


class DiscoveryJob(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "discovery_jobs"

    cidr: Mapped[str] = mapped_column(String(64))
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[DiscoveryJobStatus] = mapped_column(default=DiscoveryJobStatus.PENDING, index=True)
    rate_limit_pps: Mapped[int] = mapped_column(Integer, default=20)
    credential_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_hosts: Mapped[int | None] = mapped_column(Integer)
    found_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(String(1000))

    results: Mapped[list["DiscoveryResult"]] = relationship(back_populates="discovery_job", cascade="all, delete-orphan")


class DiscoveryResult(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "discovery_results"

    discovery_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_jobs.id", ondelete="CASCADE"), index=True
    )
    ip_address: Mapped[str] = mapped_column(String(45))
    hostname_guess: Mapped[str | None] = mapped_column(String(255))
    mac_address: Mapped[str | None] = mapped_column(String(17))
    open_ports: Mapped[list] = mapped_column(JSONB, default=list)
    snmp_reachable: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_device_type: Mapped[DeviceType | None] = mapped_column()
    imported: Mapped[bool] = mapped_column(Boolean, default=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL")
    )

    discovery_job: Mapped[DiscoveryJob] = relationship(back_populates="results")


class AuditLog(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(255), index=True)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45))


class WorkerHeartbeat(Base, UUIDPKMixin):
    __tablename__ = "worker_heartbeats"

    worker_name: Mapped[str] = mapped_column(String(255), unique=True)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_devices: Mapped[int] = mapped_column(Integer, default=0)
    active_polls: Mapped[int] = mapped_column(Integer, default=0)
