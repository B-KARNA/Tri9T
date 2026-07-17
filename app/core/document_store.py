import json
import os
import uuid
from typing import Any, Dict, List, Optional

import aiofiles
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.logging import logger


# --- Helper classes to mimic MongoDB's motor/pymongo interfaces for JSON File Store ---
class AsyncCursor:
    """Mimics Motor's AsyncCursor for iterating over document query results."""

    def __init__(self, items: List[Dict[str, Any]]):
        self.items = items
        self._index = 0

    def __aiter__(self) -> "AsyncCursor":
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if self._index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self._index]
        self._index += 1
        return item

    async def to_list(self, length: Optional[int] = None) -> List[Dict[str, Any]]:
        """Mimics cursor.to_list(length)."""
        if length is None:
            return self.items
        return self.items[:length]


class InsertOneResult:
    """Mimics PyMongo's InsertOneResult."""

    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id


class UpdateResult:
    """Mimics PyMongo's UpdateResult."""

    def __init__(self, matched_count: int, modified_count: int):
        self.matched_count = matched_count
        self.modified_count = modified_count


class DeleteResult:
    """Mimics PyMongo's DeleteResult."""

    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class JSONCollection:
    """Mimics Motor's AsyncIOMotorCollection."""

    def __init__(self, store: "JSONDocumentStore", name: str):
        self.store = store
        self.name = name

    def _get_items(self) -> List[Dict[str, Any]]:
        if self.name not in self.store._data:
            self.store._data[self.name] = []
        return self.store._data[self.name]

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        items = self._get_items()
        for item in items:
            if all(item.get(k) == v for k, v in query.items()):
                return item
        return None

    def find(self, query: Dict[str, Any]) -> AsyncCursor:
        items = self._get_items()
        matching = []
        for item in items:
            if all(item.get(k) == v for k, v in query.items()):
                matching.append(item)
        return AsyncCursor(matching)

    async def insert_one(self, document: Dict[str, Any]) -> InsertOneResult:
        items = self._get_items()
        doc = dict(document)
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        items.append(doc)
        await self.store._save()
        return InsertOneResult(doc["_id"])

    async def update_one(
        self, query: Dict[str, Any], update: Dict[str, Any]
    ) -> UpdateResult:
        items = self._get_items()
        matched = 0
        modified = 0
        for item in items:
            if all(item.get(k) == v for k, v in query.items()):
                matched = 1
                # Handle standard MongoDB '$set' syntax
                if "$set" in update:
                    for k, v in update["$set"].items():
                        if item.get(k) != v:
                            item[k] = v
                            modified = 1
                else:
                    for k, v in update.items():
                        if item.get(k) != v:
                            item[k] = v
                            modified = 1
                if modified:
                    await self.store._save()
                break
        return UpdateResult(matched, modified)

    async def delete_one(self, query: Dict[str, Any]) -> DeleteResult:
        items = self._get_items()
        deleted = 0
        for i, item in enumerate(items):
            if all(item.get(k) == v for k, v in query.items()):
                items.pop(i)
                deleted = 1
                await self.store._save()
                break
        return DeleteResult(deleted)


class JSONDocumentStore:
    """A thread-safe / async JSON file store mimicking MongoDB client behavior."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._data: Dict[str, List[Dict[str, Any]]] = {}

    async def initialize(self) -> None:
        dir_name = os.path.dirname(self.file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        if not os.path.exists(self.file_path):
            async with aiofiles.open(self.file_path, "w") as f:
                await f.write(json.dumps({}))
            self._data = {}
        else:
            async with aiofiles.open(self.file_path, "r") as f:
                content = await f.read()
                try:
                    self._data = json.loads(content) if content else {}
                except json.JSONDecodeError:
                    self._data = {}
        logger.info("Initialized JSON Document Store", path=self.file_path)

    async def _save(self) -> None:
        async with aiofiles.open(self.file_path, "w") as f:
            await f.write(json.dumps(self._data, indent=2))

    def get_database(self, name: str) -> "JSONDocumentStore":
        # In a JSON file, the database itself is the store instance
        return self

    def __getitem__(self, name: str) -> JSONCollection:
        return JSONCollection(self, name)


# --- Global Document Store Client Provider ---
class DocumentStoreClient:

    def __init__(self) -> None:
        self.client: Any = None
        self.db: Any = None

    async def connect(self) -> None:
        if settings.DOCUMENT_STORE_TYPE == "mongodb":
            logger.info(
                "Connecting to MongoDB",
                url=settings.MONGODB_URL,
                db=settings.MONGODB_DB_NAME,
            )
            self.client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.client[settings.MONGODB_DB_NAME]
        else:
            logger.info(
                "Connecting to local JSON Document Store",
                path=settings.DOCUMENT_STORE_PATH,
            )
            json_store = JSONDocumentStore(settings.DOCUMENT_STORE_PATH)
            await json_store.initialize()
            self.client = json_store
            self.db = json_store.get_database("default")

    async def disconnect(self) -> None:
        if settings.DOCUMENT_STORE_TYPE == "mongodb" and self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")
        else:
            logger.info("Closed JSON Document Store reference")


# Global singleton instance
doc_store_client = DocumentStoreClient()
