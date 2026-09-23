from fastapi import APIRouter

from app.api.routes import (
    alert_rules,
    alerts,
    auth,
    dashboard,
    devices,
    discovery,
    events,
    incidents,
    interfaces,
    locations,
    topology,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(locations.router)
api_router.include_router(devices.router)
api_router.include_router(interfaces.router)
api_router.include_router(discovery.router)
api_router.include_router(alerts.router)
api_router.include_router(alert_rules.router)
api_router.include_router(events.router)
api_router.include_router(topology.router)
api_router.include_router(dashboard.router)
api_router.include_router(incidents.router)
