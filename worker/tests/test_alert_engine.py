from sqlalchemy import select

from nms_common.enums import (
    AlertOperator,
    AlertScope,
    AlertSeverity,
    AlertStatus,
    DeviceType,
    MetricType,
    RuleKind,
)
from nms_common.models import Alert, AlertRule, Device

from worker import alert_engine


async def _make_device(db_session, ip="10.10.0.9"):
    device = Device(hostname="srv1", ip_address=ip, device_type=DeviceType.SERVER)
    db_session.add(device)
    await db_session.flush()
    return device


async def test_cpu_alert_opens_after_consecutive_breaches_and_resolves(db_session):
    device = await _make_device(db_session)
    rule = AlertRule(
        name="CPU warning",
        rule_kind=RuleKind.METRIC_THRESHOLD,
        metric_type=MetricType.CPU_USAGE,
        operator=AlertOperator.GT,
        threshold=80,
        severity=AlertSeverity.WARNING,
        scope=AlertScope.GLOBAL,
        consecutive_breaches_to_open=2,
        consecutive_ok_to_resolve=2,
    )
    db_session.add(rule)
    await db_session.flush()

    await alert_engine.evaluate_metric_rules(db_session, device, MetricType.CPU_USAGE, 90.0)
    result = await db_session.execute(select(Alert).where(Alert.device_id == device.id))
    assert result.scalar_one_or_none() is None  # only one breach so far -- not enough to open yet

    await alert_engine.evaluate_metric_rules(db_session, device, MetricType.CPU_USAGE, 92.0)
    result = await db_session.execute(select(Alert).where(Alert.device_id == device.id))
    alert = result.scalar_one()
    assert alert.status == AlertStatus.OPEN
    assert alert.severity == AlertSeverity.WARNING

    await alert_engine.evaluate_metric_rules(db_session, device, MetricType.CPU_USAGE, 50.0)
    await db_session.refresh(alert)
    assert alert.status == AlertStatus.OPEN  # only one OK poll so far

    await alert_engine.evaluate_metric_rules(db_session, device, MetricType.CPU_USAGE, 40.0)
    await db_session.refresh(alert)
    assert alert.status == AlertStatus.RESOLVED


async def test_unreachable_rule_opens_immediately_when_configured_for_one_breach(db_session):
    device = await _make_device(db_session, ip="10.10.0.10")
    rule = AlertRule(
        name="Device unreachable",
        rule_kind=RuleKind.DEVICE_UNREACHABLE,
        severity=AlertSeverity.CRITICAL,
        scope=AlertScope.GLOBAL,
        consecutive_breaches_to_open=1,
        consecutive_ok_to_resolve=1,
    )
    db_session.add(rule)
    await db_session.flush()

    await alert_engine.evaluate_unreachable(db_session, device, reachable=False)
    result = await db_session.execute(select(Alert).where(Alert.device_id == device.id))
    alert = result.scalar_one()
    assert alert.status == AlertStatus.OPEN
    assert alert.severity == AlertSeverity.CRITICAL

    await alert_engine.evaluate_unreachable(db_session, device, reachable=True)
    await db_session.refresh(alert)
    assert alert.status == AlertStatus.RESOLVED
