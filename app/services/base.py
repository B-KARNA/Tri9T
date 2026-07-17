from typing import Generic, TypeVar

from app.repositories.base import BaseRepository

T = TypeVar("T")


class BaseService(Generic[T]):
    """Base Service / Use Case layer orchestrator.

    Accepts an abstract repository conforming to BaseRepository contract.
    """

    def __init__(self, repository: BaseRepository[T]):
        self.repository = repository
        # You can also add standard logging references or transaction managers here
