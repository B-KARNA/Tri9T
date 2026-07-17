from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository

T = TypeVar("T")


class SQLAlchemyRepository(BaseRepository[T], Generic[T]):
    """Base repository implementation for SQLAlchemy 2.0."""

    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def get_by_id(self, id: Any) -> Optional[T]:
        return await self.session.get(self.model, id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update(self, id: Any, entity: T) -> Optional[T]:
        db_entity = await self.get_by_id(id)
        if not db_entity:
            return None

        # Copy non-internal attributes from the updated entity
        # target models should have their fields updated accordingly
        for key, val in entity.__dict__.items():
            if not key.startswith("_") and key != "id":
                setattr(db_entity, key, val)

        await self.session.commit()
        await self.session.refresh(db_entity)
        return db_entity

    async def delete(self, id: Any) -> bool:
        db_entity = await self.get_by_id(id)
        if not db_entity:
            return False
        await self.session.delete(db_entity)
        await self.session.commit()
        return True
