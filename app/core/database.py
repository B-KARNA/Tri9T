from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Create async engine for SQLAlchemy 2.0
# SQLite requires some extra query parameters or connect args in certain cases,
# but using aiosqlite, we can keep it standard.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Can set to True in development to see SQL statements
    future=True,
)

# Create the session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Declarative Base for models
class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy database models."""

    pass
