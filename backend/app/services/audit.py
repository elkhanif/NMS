import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.models import AuditLog, User


async def write_audit(
    db: AsyncSession,
    user: User | None,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip_address=ip_address,
        )
    )
    await db.flush()
