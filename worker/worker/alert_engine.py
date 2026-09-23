import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import AlertOperator, AlertScope, AlertStatus, MetricType, RuleKind
from nms_common.models import Alert, AlertRule, Device

from worker import state


def _compare(value: float, operator: AlertOperator, threshold: float) -> bool:
    return {
        AlertOperator.GT: value > threshold,
        AlertOperator.GTE: value >= threshold,
        AlertOperator.LT: value < threshold,
        AlertOperator.LTE: value <= threshold,
        AlertOperator.EQ: value == threshold,
    }.get(operator, False)


async def _applicable_rules(
    db: AsyncSession, device: Device, rule_kind: RuleKind, metric_type: MetricType | None = None
) -> list[AlertRule]:
    conditions = [AlertRule.enabled.is_(True), AlertRule.rule_kind == rule_kind]
    if metric_type is not None:
        conditions.append(AlertRule.metric_type == metric_type)
    scope_condition = or_(
        AlertRule.scope == AlertScope.GLOBAL,
        and_(AlertRule.scope == AlertScope.DEVICE_TYPE, AlertRule.device_type == device.device_type),
        and_(AlertRule.scope == AlertScope.DEVICE, AlertRule.device_id == device.id),
    )
    result = await db.execute(select(AlertRule).where(*conditions, scope_condition))
    return list(result.scalars().all())


async def _get_open_alert(
    db: AsyncSession, device_id: uuid.UUID, rule_id: uuid.UUID, interface_id: uuid.UUID | None
) -> Alert | None:
    conditions = [
        Alert.device_id == device_id,
        Alert.alert_rule_id == rule_id,
        Alert.status != AlertStatus.RESOLVED,
    ]
    if interface_id is not None:
        conditions.append(Alert.interface_id == interface_id)
    result = await db.execute(select(Alert).where(*conditions).order_by(Alert.opened_at.desc()).limit(1))
    return result.scalar_one_or_none()


async def _open_or_update_alert(
    db: AsyncSession,
    device: Device,
    rule: AlertRule,
    metric_label: str,
    value: float,
    message: str,
    interface_id: uuid.UUID | None = None,
) -> None:
    existing = await _get_open_alert(db, device.id, rule.id, interface_id)
    if existing is not None:
        existing.current_value = value
        return
    db.add(
        Alert(
            device_id=device.id,
            interface_id=interface_id,
            alert_rule_id=rule.id,
            severity=rule.severity,
            metric=metric_label,
            threshold=rule.threshold,
            current_value=value,
            message=message,
            status=AlertStatus.OPEN,
            opened_at=datetime.now(timezone.utc),
        )
    )


async def _auto_resolve(
    db: AsyncSession, device_id: uuid.UUID, rule_id: uuid.UUID, interface_id: uuid.UUID | None = None
) -> None:
    alert = await _get_open_alert(db, device_id, rule_id, interface_id)
    if alert is not None:
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)


async def evaluate_metric_rules(db: AsyncSession, device: Device, metric_type: MetricType, value: float) -> None:
    for rule in await _applicable_rules(db, device, RuleKind.METRIC_THRESHOLD, metric_type):
        if rule.operator is None or rule.threshold is None:
            continue
        key = (device.id, rule.id)
        if _compare(value, rule.operator, rule.threshold):
            if state.record_breach(key) >= rule.consecutive_breaches_to_open:
                await _open_or_update_alert(
                    db,
                    device,
                    rule,
                    metric_type.value,
                    value,
                    f"{metric_type.value} {rule.operator.value} {rule.threshold} on {device.hostname} "
                    f"(current: {value:.1f})",
                )
        else:
            if state.record_ok(key) >= rule.consecutive_ok_to_resolve:
                await _auto_resolve(db, device.id, rule.id)


async def evaluate_unreachable(db: AsyncSession, device: Device, reachable: bool) -> None:
    for rule in await _applicable_rules(db, device, RuleKind.DEVICE_UNREACHABLE):
        key = (device.id, rule.id)
        if not reachable:
            if state.record_breach(key) >= rule.consecutive_breaches_to_open:
                await _open_or_update_alert(
                    db, device, rule, "AVAILABILITY", 0.0, f"{device.hostname} ({device.ip_address}) is unreachable"
                )
        else:
            if state.record_ok(key) >= rule.consecutive_ok_to_resolve:
                await _auto_resolve(db, device.id, rule.id)


async def evaluate_interface_down(
    db: AsyncSession, device: Device, interface_id: uuid.UUID, interface_name: str, is_down: bool
) -> None:
    for rule in await _applicable_rules(db, device, RuleKind.INTERFACE_DOWN):
        key = (device.id, rule.id, interface_id)
        if is_down:
            if state.record_breach(key) >= rule.consecutive_breaches_to_open:
                await _open_or_update_alert(
                    db,
                    device,
                    rule,
                    "INTERFACE_STATUS",
                    0.0,
                    f"Interface {interface_name} on {device.hostname} is down",
                    interface_id=interface_id,
                )
        else:
            if state.record_ok(key) >= rule.consecutive_ok_to_resolve:
                await _auto_resolve(db, device.id, rule.id, interface_id)
