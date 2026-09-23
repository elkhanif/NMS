from datetime import datetime

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_devices: int
    online: int
    warning: int
    critical: int
    offline: int
    unknown: int
    overall_availability_pct: float
    active_alerts: int
    active_critical_alerts: int
    avg_latency_ms: float | None
    avg_packet_loss_pct: float | None
    total_inbound_bps: float | None
    total_outbound_bps: float | None
    worker_last_heartbeat_at: datetime | None


class ChartPoint(BaseModel):
    time: datetime
    value: float


class ChartSeries(BaseModel):
    label: str
    points: list[ChartPoint]


class DeviceStatusDistribution(BaseModel):
    status: str
    count: int
