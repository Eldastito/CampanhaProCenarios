from collections import defaultdict
from typing import Any

from app.services.memory.base import MemoryProvider


class LocalGraphMemoryProvider(MemoryProvider):
    def __init__(self) -> None:
        self.entities: dict[tuple[str, str], dict[str, Any]] = {}
        self.relations: list[dict[str, Any]] = []
        self.index: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def upsert_entity(self, entity_type: str, entity_id: str, payload: dict[str, Any]) -> None:
        self.entities[(entity_type, entity_id)] = payload
        organization_id = str(payload.get("organization_id", "global"))
        self.index[organization_id].append({
            "kind": "entity",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
        })

    def upsert_relation(
        self,
        source_type: str,
        source_id: str,
        relation_type: str,
        target_type: str,
        target_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        relation = {
            "source_type": source_type,
            "source_id": source_id,
            "relation_type": relation_type,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload or {},
        }
        self.relations.append(relation)
        organization_id = str((payload or {}).get("organization_id", "global"))
        self.index[organization_id].append({"kind": "relation", **relation})

    def query_context(self, organization_id: str, query: str) -> list[dict[str, Any]]:
        items = self.index.get(organization_id, [])
        lowered = query.lower()
        return [item for item in items if lowered in str(item).lower()][:20]
