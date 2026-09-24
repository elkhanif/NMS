import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.cors import ALLOWED_ORIGINS
from app.ws.manager import manager
from app.ws.redis_listener import listen


@asynccontextmanager
async def lifespan(app: FastAPI):
    listener_task = asyncio.create_task(listen(manager))
    try:
        yield
    finally:
        listener_task.cancel()


app = FastAPI(
    title="Network Monitoring System API",
    description="Mini NMS: device inventory, monitoring configuration, metrics, alerts, events, and topology.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
