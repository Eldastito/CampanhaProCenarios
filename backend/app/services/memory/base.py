from abc import ABC, abstractmethod
from typing import Any


class MemoryProvider(ABC):
    @abstractmethod
    def upsert_entity(self, entity_type: str, entity_id: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_relation(
        self,
        source_type: str,
        source_id: str,
        relation_type: str,
        target_type: str,
        target_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def query_context(self, organization_id: str, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError
