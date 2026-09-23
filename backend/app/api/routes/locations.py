import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.models import Location, User

from app.deps import get_db, get_current_user, require_config_writer
from app.schemas.location import LocationCreate, LocationOut, LocationUpdate
from app.services.audit import write_audit

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/", response_model=list[LocationOut], dependencies=[Depends(get_current_user)])
async def list_locations(db: AsyncSession = Depends(get_db)) -> list[Location]:
    result = await db.execute(select(Location).order_by(Location.name))
    return list(result.scalars().all())


@router.post("/", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> Location:
    location = Location(**payload.model_dump())
    db.add(location)
    await db.flush()
    await write_audit(db, current_user, "location.create", "location", location.id)
    await db.commit()
    return location


@router.patch("/{location_id}", response_model=LocationOut)
async def update_location(
    location_id: uuid.UUID,
    payload: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> Location:
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, field, value)
    await write_audit(db, current_user, "location.update", "location", location_id)
    await db.commit()
    await db.refresh(location)
    return location


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> None:
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    await db.delete(location)
    await write_audit(db, current_user, "location.delete", "location", location_id)
    await db.commit()
