from typing import Any, Generic, List, Optional, Type, TypeVar

from app.repositories.base import BaseRepository

T = TypeVar("T")


class DocumentRepository(BaseRepository[T], Generic[T]):
    """Base repository implementation for NoSQL/Document databases.

    Compatible with both real MongoDB collections (via motor) and the mock
    JSON store.
    """

    def __init__(self, db: Any, collection_name: str, model: Type[T]):
        self.db = db
        self.collection = db[collection_name]
        self.model = model

    async def get_by_id(self, id: Any) -> Optional[T]:
        doc = await self.collection.find_one({"_id": str(id)})
        if doc:
            return self._map_to_model(doc)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        cursor = self.collection.find({})

        # Check if cursor is Motor cursor or local AsyncCursor
        if hasattr(cursor, "skip") and hasattr(cursor, "limit"):
            cursor = cursor.skip(skip).limit(limit)
            docs = await cursor.to_list(length=limit)
        else:
            docs = await cursor.to_list()
            docs = docs[skip : skip + limit]

        return [self._map_to_model(doc) for doc in docs]

    async def create(self, entity: T) -> T:
        doc = (
            entity.model_dump(by_alias=True)
            if hasattr(entity, "model_dump")
            else dict(entity)
        )

        # Map 'id' attribute to '_id' for mongo compatibility
        if "_id" not in doc:
            if "id" in doc and doc["id"] is not None:
                doc["_id"] = str(doc.pop("id"))
            elif hasattr(entity, "id") and getattr(entity, "id") is not None:
                doc["_id"] = str(getattr(entity, "id"))

        result = await self.collection.insert_one(doc)

        if hasattr(entity, "id"):
            try:
                setattr(entity, "id", result.inserted_id)
            except AttributeError:
                # Entity might be immutable Pydantic model
                pass

        return entity

    async def update(self, id: Any, entity: T) -> Optional[T]:
        doc = (
            entity.model_dump(by_alias=True, exclude_unset=True)
            if hasattr(entity, "model_dump")
            else dict(entity)
        )
        doc.pop("_id", None)
        doc.pop("id", None)

        result = await self.collection.update_one({"_id": str(id)}, {"$set": doc})
        if result.matched_count > 0:
            return await self.get_by_id(id)
        return None

    async def delete(self, id: Any) -> bool:
        result = await self.collection.delete_one({"_id": str(id)})
        return result.deleted_count > 0

    def _map_to_model(self, doc: dict) -> T:
        # Convert _id key back to id field for Pydantic mapping compatibility
        data = dict(doc)
        if "_id" in data and "id" not in data:
            data["id"] = data.pop("_id")
        return self.model(**data)
