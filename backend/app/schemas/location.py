import uuid

from pydantic import BaseModel

from app.schemas.common import ORMModel


class LocationCreate(BaseModel):
    name: str
    description: str | None = None
    parent_location_id: uuid.UUID | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_location_id: uuid.UUID | None = None


class LocationOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    parent_location_id: uuid.UUID | None
