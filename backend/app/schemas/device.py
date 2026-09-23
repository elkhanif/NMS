import ipaddress
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from nms_common.enums import AddressSource, CheckType, CredentialType, DeviceStatus, DeviceType, InterfaceStatus

from app.schemas.common import ORMModel


class DeviceCreate(BaseModel):
    hostname: str
    ip_address: str
    mac_address: str | None = None
    device_type: DeviceType = DeviceType.GENERIC
    vendor: str | None = None
    model: str | None = None
    location_id: uuid.UUID | None = None
    department: str | None = None
    primary_check_type: CheckType = CheckType.ICMP
    serial_number: str | None = None
    default_gateway_ip: str | None = None

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        ipaddress.ip_address(v)  # raises ValueError if invalid
        return v


class DeviceUpdate(BaseModel):
    hostname: str | None = None
    mac_address: str | None = None
    device_type: DeviceType | None = None
    vendor: str | None = None
    model: str | None = None
    location_id: uuid.UUID | None = None
    department: str | None = None
    primary_check_type: CheckType | None = None
    is_monitored: bool | None = None
    serial_number: str | None = None
    default_gateway_ip: str | None = None


class DeviceOut(ORMModel):
    id: uuid.UUID
    hostname: str
    ip_address: str
    mac_address: str | None
    device_type: DeviceType
    vendor: str | None
    model: str | None
    location_id: uuid.UUID | None
    department: str | None
    status: DeviceStatus
    primary_check_type: CheckType
    is_monitored: bool
    last_seen: datetime | None
    created_at: datetime
    has_snmp_credential: bool = False
    serial_number: str | None = None
    default_gateway_ip: str | None = None


class DeviceCheckIn(BaseModel):
    check_type: CheckType
    enabled: bool = True
    config: dict = Field(default_factory=dict)
    interval_seconds: int = 60
    timeout_seconds: int = 5
    retries: int = 1


class DeviceCheckOut(ORMModel):
    id: uuid.UUID
    check_type: CheckType
    enabled: bool
    config: dict
    interval_seconds: int
    timeout_seconds: int
    retries: int


class InterfaceOut(ORMModel):
    id: uuid.UUID
    if_index: int
    name: str
    alias: str | None
    oper_status: InterfaceStatus
    admin_status: InterfaceStatus
    speed_bps: int | None
    mac_address: str | None
    last_change_at: datetime | None


class LatestMetricOut(BaseModel):
    metric_type: str
    value: float
    unit: str | None
    time: datetime


class DeviceDetailOut(DeviceOut):
    checks: list[DeviceCheckOut] = []
    interfaces: list[InterfaceOut] = []
    latest_metrics: list[LatestMetricOut] = []


class BulkCheckIn(BaseModel):
    """Applies the same monitoring check (type, interval, timeout, retries, config)
    to many devices in one call, so an operator doesn't have to open each device
    individually just to set up the same ICMP/TCP/HTTP/SNMP check everywhere."""

    device_ids: list[uuid.UUID]
    check_type: CheckType
    enabled: bool = True
    config: dict = Field(default_factory=dict)
    interval_seconds: int = 60
    timeout_seconds: int = 5
    retries: int = 1


class DeviceCredentialIn(BaseModel):
    """Write-only: payload is the raw secret (e.g. SNMP community string, HTTP basic
    creds). It is encrypted server-side and never echoed back in any response."""

    credential_type: CredentialType
    payload: dict


class BulkCredentialIn(BaseModel):
    """Applies the same SNMP credential to many devices in one call, so an operator
    doesn't have to open each device individually just to set the same community
    string (or the same SNMPv3 user) everywhere."""

    device_ids: list[uuid.UUID]
    credential_type: CredentialType
    payload: dict


class DeviceCredentialOut(ORMModel):
    """Metadata only -- deliberately excludes the encrypted payload."""

    id: uuid.UUID
    credential_type: CredentialType
    created_at: datetime
    updated_at: datetime


class DeviceAddressOut(ORMModel):
    id: uuid.UUID
    ip_address: str
    mac_address: str | None
    source: AddressSource
    is_current: bool
    first_seen_at: datetime
    last_seen_at: datetime
