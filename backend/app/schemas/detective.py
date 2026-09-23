import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from nms_common.enums import DeviceStatus, DeviceType, RelationshipType

from app.schemas.device import InterfaceOut


class DetectiveMatch(BaseModel):
    device_id: uuid.UUID
    hostname: str
    ip_address: str
    match_type: Literal["device_id", "ip", "hostname", "mac", "serial_number", "ip_history", "mac_history"]
    matched_value: str


class DetectiveSearchResult(BaseModel):
    query: str
    matches: list[DetectiveMatch]


class DeviceIdentity(BaseModel):
    hostname: str
    ip_address: str
    mac_address: str | None
    vendor: str | None
    model: str | None
    device_type: DeviceType
    os: str | None = None  # No OS-fingerprinting source yet -- always None (Unknown) today
    status: DeviceStatus
    first_seen: datetime | None
    last_seen: datetime | None
    serial_number: str | None


class NetworkIdentity(BaseModel):
    """Any field left None here has no real data source yet (see README's SNMPv3 /
    Network Detective notes) -- the frontend renders those as literal "Unknown",
    never a guess."""

    gateway: str | None
    vlan: str | None
    subnet: str | None
    switch_hostname: str | None
    switch_port: str | None
    access_point: str | None
    parent_device_id: uuid.UUID | None
    connected_device_ids: list[uuid.UUID]


class HealthSnapshot(BaseModel):
    availability_pct: float | None
    latency_ms: float | None
    packet_loss_pct: float | None
    cpu_percent: float | None
    memory_percent: float | None
    interfaces: list[InterfaceOut]
    traffic_in_bps: float | None
    traffic_out_bps: float | None


class TimelineEntry(BaseModel):
    time: datetime
    event_type: str
    message: str
    severity: str


class RelationshipNode(BaseModel):
    device_id: uuid.UUID
    hostname: str
    status: DeviceStatus
    relationship_type: RelationshipType | None = None
    interface_name: str | None = None


class InvestigationSummary(BaseModel):
    """Backs the plain-language Investigation Summary -- every field here is
    computed directly from stored events/metrics, never inferred or guessed."""

    current_status: DeviceStatus
    last_outage_start: datetime | None
    last_outage_end: datetime | None
    avg_latency_ms: float | None
    packet_loss_pct: float | None
    ip_changes_24h: int
    mac_changes_24h: int
    connected_through: str | None


class DeviceInvestigation(BaseModel):
    identity: DeviceIdentity
    network_identity: NetworkIdentity
    health: HealthSnapshot
    timeline: list[TimelineEntry]
    ancestors: list[RelationshipNode]
    children: list[RelationshipNode]
    summary: InvestigationSummary
