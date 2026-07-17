from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.document_store import doc_store_client


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for yielding SQLAlchemy AsyncSession.

    Automatically handles rolling back on errors and closing the session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_doc_store() -> Any:
    """Dependency for yielding the active Document Database.

    Returns the JSON file database or MongoDB client instance.
    """
    return doc_store_client.db
