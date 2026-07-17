from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, TypeVar

T = TypeVar("T")


class BaseRepository(Generic[T], ABC):
    """Abstract Base Class defining the contract for all repositories.

    This ensures database-agnostic use in service layers.
    """

    @abstractmethod
    async def get_by_id(self, id: Any) -> Optional[T]:
        """Retrieve an entity by its identifier."""
        pass

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Retrieve a list of entities with pagination."""
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create and store a new entity."""
        pass

    @abstractmethod
    async def update(self, id: Any, entity: T) -> Optional[T]:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete(self, id: Any) -> bool:
        """Delete an entity by its identifier."""
        pass
