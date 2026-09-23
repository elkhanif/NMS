import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nms_common.config import get_settings
from nms_common.crypto import hash_password
from nms_common.db import Base, get_db
from nms_common.enums import UserRole
from nms_common.models import User

from app.main import app

settings = get_settings()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Requires a reachable Postgres at settings.database_url (see README: run
    `docker compose up -d postgres` and point DATABASE_URL/SYNC_DATABASE_URL at it,
    or `docker compose run --rm api pytest` to run inside the compose network)."""
    eng = create_async_engine(settings.database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Each test runs inside its own transaction/savepoint that's rolled back after,
    so tests never see each other's data even though they share one schema."""
    connection = await engine.connect()
    trans = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session):
    user = User(email="admin@test.local", hashed_password=hash_password("adminpass123"), role=UserRole.ADMIN)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "adminpass123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]
