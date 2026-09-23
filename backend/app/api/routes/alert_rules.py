import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.models import AlertRule, User

from app.deps import get_current_user, get_db, require_config_writer
from app.schemas.alert import AlertRuleCreate, AlertRuleOut, AlertRuleUpdate
from app.services.audit import write_audit

router = APIRouter(prefix="/alert-rules", tags=["alert-rules"])


@router.get("/", response_model=list[AlertRuleOut], dependencies=[Depends(get_current_user)])
async def list_alert_rules(db: AsyncSession = Depends(get_db)) -> list[AlertRule]:
    result = await db.execute(select(AlertRule).order_by(AlertRule.name))
    return list(result.scalars().all())


@router.post("/", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    payload: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> AlertRule:
    rule = AlertRule(**payload.model_dump())
    db.add(rule)
    await db.flush()
    await write_audit(db, current_user, "alert_rule.create", "alert_rule", rule.id, {"name": rule.name})
    await db.commit()
    return rule


@router.patch("/{rule_id}", response_model=AlertRuleOut)
async def update_alert_rule(
    rule_id: uuid.UUID,
    payload: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> AlertRule:
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(rule, field, value)
    await write_audit(db, current_user, "alert_rule.update", "alert_rule", rule_id, data)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> None:
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")
    await db.delete(rule)
    await write_audit(db, current_user, "alert_rule.delete", "alert_rule", rule_id)
    await db.commit()
