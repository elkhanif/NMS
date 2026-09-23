import uuid
from datetime import datetime

from pydantic import BaseModel

from nms_common.enums import AlertOperator, AlertScope, AlertSeverity, AlertStatus, DeviceType, MetricType, RuleKind

from app.schemas.common import ORMModel


class AlertRuleCreate(BaseModel):
    name: str
    rule_kind: RuleKind = RuleKind.METRIC_THRESHOLD
    metric_type: MetricType | None = None
    operator: AlertOperator | None = None
    threshold: float | None = None
    severity: AlertSeverity = AlertSeverity.WARNING
    scope: AlertScope = AlertScope.GLOBAL
    device_type: DeviceType | None = None
    device_id: uuid.UUID | None = None
    enabled: bool = True
    consecutive_breaches_to_open: int = 2
    consecutive_ok_to_resolve: int = 2


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    threshold: float | None = None
    severity: AlertSeverity | None = None
    enabled: bool | None = None
    consecutive_breaches_to_open: int | None = None
    consecutive_ok_to_resolve: int | None = None


class AlertRuleOut(ORMModel):
    id: uuid.UUID
    name: str
    rule_kind: RuleKind
    metric_type: MetricType | None
    operator: AlertOperator | None
    threshold: float | None
    severity: AlertSeverity
    scope: AlertScope
    device_type: DeviceType | None
    device_id: uuid.UUID | None
    enabled: bool
    consecutive_breaches_to_open: int
    consecutive_ok_to_resolve: int


class AlertOut(ORMModel):
    id: uuid.UUID
    device_id: uuid.UUID
    interface_id: uuid.UUID | None
    alert_rule_id: uuid.UUID | None
    severity: AlertSeverity
    metric: str
    threshold: float | None
    current_value: float | None
    message: str
    status: AlertStatus
    opened_at: datetime
    acknowledged_by_id: uuid.UUID | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
