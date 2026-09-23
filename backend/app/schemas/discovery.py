import ipaddress
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from nms_common.config import get_settings
from nms_common.enums import DeviceType, DiscoveryJobStatus

from app.schemas.common import ORMModel

settings = get_settings()


class DiscoveryStartRequest(BaseModel):
    cidr: str
    credential_ref_id: uuid.UUID | None = None
    rate_limit_pps: int = settings.discovery_rate_pps

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        network = ipaddress.ip_network(v, strict=False)
        if network.num_addresses > settings.discovery_max_hosts:
            raise ValueError(
                f"Range too large ({network.num_addresses} hosts); max is "
                f"{settings.discovery_max_hosts}. Use a smaller CIDR to avoid flooding the network."
            )
        return str(network)


class DiscoveryJobOut(ORMModel):
    id: uuid.UUID
    cidr: str
    status: DiscoveryJobStatus
    rate_limit_pps: int
    started_at: datetime | None
    finished_at: datetime | None
    total_hosts: int | None
    found_count: int | None
    error_message: str | None
    created_at: datetime


class DiscoveryResultOut(ORMModel):
    id: uuid.UUID
    discovery_job_id: uuid.UUID
    ip_address: str
    hostname_guess: str | None
    mac_address: str | None
    open_ports: list
    snmp_reachable: bool
    suggested_device_type: DeviceType | None
    imported: bool
    device_id: uuid.UUID | None


class DiscoveryImportRequest(BaseModel):
    result_ids: list[uuid.UUID]
    location_id: uuid.UUID | None = None
    department: str | None = None
