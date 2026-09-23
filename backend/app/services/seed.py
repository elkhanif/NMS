"""Idempotent startup seed: creates the initial admin user and default alert rules
if they don't already exist. Run via `python -m app.services.seed` (see entrypoint.sh).
"""
import asyncio

from sqlalchemy import select

from nms_common.config import get_settings
from nms_common.crypto import hash_password
from nms_common.db import new_session
from nms_common.enums import AlertOperator, AlertScope, AlertSeverity, MetricType, RuleKind, UserRole
from nms_common.models import AlertRule, User

DEFAULT_ALERT_RULES = [
    dict(
        name="Device unreachable",
        rule_kind=RuleKind.DEVICE_UNREACHABLE,
        severity=AlertSeverity.CRITICAL,
        consecutive_breaches_to_open=1,
        consecutive_ok_to_resolve=1,
    ),
    dict(
        name="Interface down",
        rule_kind=RuleKind.INTERFACE_DOWN,
        severity=AlertSeverity.WARNING,
        consecutive_breaches_to_open=1,
        consecutive_ok_to_resolve=1,
    ),
    dict(
        name="Packet loss warning",
        rule_kind=RuleKind.METRIC_THRESHOLD,
        metric_type=MetricType.PACKET_LOSS,
        operator=AlertOperator.GT,
        threshold=10,
        severity=AlertSeverity.WARNING,
    ),
    dict(
        name="Packet loss critical",
        rule_kind=RuleKind.METRIC_THRESHOLD,
        metric_type=MetricType.PACKET_LOSS,
        operator=AlertOperator.GT,
        threshold=30,
        severity=AlertSeverity.CRITICAL,
    ),
    dict(
        name="CPU usage warning",
        rule_kind=RuleKind.METRIC_THRESHOLD,
        metric_type=MetricType.CPU_USAGE,
        operator=AlertOperator.GT,
        threshold=80,
        severity=AlertSeverity.WARNING,
    ),
    dict(
        name="CPU usage critical",
        rule_kind=RuleKind.METRIC_THRESHOLD,
        metric_type=MetricType.CPU_USAGE,
        operator=AlertOperator.GT,
        threshold=95,
        severity=AlertSeverity.CRITICAL,
    ),
    dict(
        name="Memory usage warning",
        rule_kind=RuleKind.METRIC_THRESHOLD,
        metric_type=MetricType.MEMORY_USAGE,
        operator=AlertOperator.GT,
        threshold=85,
        severity=AlertSeverity.WARNING,
    ),
]


async def seed() -> None:
    settings = get_settings()
    async with new_session() as db:
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None:
            db.add(
                User(
                    email=settings.initial_admin_email,
                    hashed_password=hash_password(settings.initial_admin_password),
                    full_name="Administrator",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )
            print(f"Seeded initial admin user: {settings.initial_admin_email}")

        result = await db.execute(select(AlertRule).limit(1))
        if result.scalar_one_or_none() is None:
            for rule in DEFAULT_ALERT_RULES:
                db.add(AlertRule(scope=AlertScope.GLOBAL, **rule))
            print(f"Seeded {len(DEFAULT_ALERT_RULES)} default alert rules")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
