import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nms_common.db import Base
from nms_common.enums import (
    CheckType,
    CredentialType,
    DeviceStatus,
    DeviceType,
    InterfaceStatus,
    RelationshipType,
    UserRole,
)
from nms_common.models.base import CreatedAtMixin, TimestampMixin, UUIDPKMixin


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Location(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String(1000))
    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL")
    )

    devices: Mapped[list["Device"]] = relationship(back_populates="location")


class Device(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "devices"

    hostname: Mapped[str] = mapped_column(String(255), index=True)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, index=True)
    mac_address: Mapped[str | None] = mapped_column(String(17))
    device_type: Mapped[DeviceType] = mapped_column(default=DeviceType.GENERIC, index=True)
    vendor: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL")
    )
    department: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[DeviceStatus] = mapped_column(default=DeviceStatus.UNKNOWN, index=True)
    primary_check_type: Mapped[CheckType] = mapped_column(default=CheckType.ICMP)
    is_monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    location: Mapped[Location | None] = relationship(back_populates="devices")
    checks: Mapped[list["DeviceCheck"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    credentials: Mapped[list["DeviceCredential"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )
    interfaces: Mapped[list["Interface"]] = relationship(back_populates="device", cascade="all, delete-orphan")


class DeviceCheck(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "device_checks"
    __table_args__ = (UniqueConstraint("device_id", "check_type", name="uq_device_check_type"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    check_type: Mapped[CheckType] = mapped_column()
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=5)
    retries: Mapped[int] = mapped_column(Integer, default=1)

    device: Mapped[Device] = relationship(back_populates="checks")


class DeviceCredential(Base, UUIDPKMixin, TimestampMixin):
    """encrypted_payload is Fernet-encrypted JSON (see nms_common.crypto.CredentialCipher).

    Never deserialize/expose this outside the monitoring worker.
    """

    __tablename__ = "device_credentials"
    __table_args__ = (UniqueConstraint("device_id", "credential_type", name="uq_device_credential_type"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    credential_type: Mapped[CredentialType] = mapped_column()
    encrypted_payload: Mapped[bytes] = mapped_column()

    device: Mapped[Device] = relationship(back_populates="credentials")


class Interface(Base, UUIDPKMixin):
    __tablename__ = "interfaces"
    __table_args__ = (UniqueConstraint("device_id", "if_index", name="uq_device_if_index"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    if_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    alias: Mapped[str | None] = mapped_column(String(255))
    oper_status: Mapped[InterfaceStatus] = mapped_column(default=InterfaceStatus.UNKNOWN)
    admin_status: Mapped[InterfaceStatus] = mapped_column(default=InterfaceStatus.UNKNOWN)
    speed_bps: Mapped[int | None] = mapped_column(BigInteger)
    mac_address: Mapped[str | None] = mapped_column(String(17))
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    device: Mapped[Device] = relationship(back_populates="interfaces")


class DeviceRelationship(Base, UUIDPKMixin, CreatedAtMixin):
    """A topology edge between two devices, optionally pinned to specific interfaces."""

    __tablename__ = "device_relationships"
    __table_args__ = (UniqueConstraint("parent_device_id", "child_device_id", name="uq_device_relationship"),)

    parent_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    child_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(default=RelationshipType.DOWNLINK)
    parent_interface_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interfaces.id", ondelete="SET NULL")
    )
    child_interface_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interfaces.id", ondelete="SET NULL")
    )
    discovered: Mapped[bool] = mapped_column(Boolean, default=False)
