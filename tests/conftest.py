import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.core.database import Base
from app.core.document_store import doc_store_client
from app.main import app

# Define test database credentials
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_sql_app.db"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Test document database file path
TEST_DOCUMENT_STORE_PATH = "./data/test_document_db.json"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Initializes schema and settings override before testing and tears down after."""
    # Ensure test environment config
    settings.ENVIRONMENT = "test"
    settings.DATABASE_URL = TEST_DATABASE_URL
    settings.DOCUMENT_STORE_TYPE = "json"
    settings.DOCUMENT_STORE_PATH = TEST_DOCUMENT_STORE_PATH

    # Initialize SQL database tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize document store client
    await doc_store_client.connect()

    yield

    # Disconnect store
    await doc_store_client.disconnect()

    # Drop database tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Clean up generated databases
    db_file = "./test_sql_app.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass

    if os.path.exists(TEST_DOCUMENT_STORE_PATH):
        try:
            os.remove(TEST_DOCUMENT_STORE_PATH)
        except OSError:
            pass


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a transaction-wrapped test database session."""
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yields an AsyncClient configured to run against the app with overridden DB session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
