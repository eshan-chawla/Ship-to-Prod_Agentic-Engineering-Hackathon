"""Back-compat facade composing SemanticCache + AgentMemory.

New code should import SemanticCache / AgentMemory directly from
app.integrations.redis_layer.*. RedisContext remains for existing call sites.
"""
from __future__ import annotations

import json
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.integrations.redis_layer.agent_memory import AgentMemory
from app.integrations.redis_layer.client import build_redis_client
from app.integrations.redis_layer.semantic_cache import SemanticCache


class RedisContext:
    def __init__(self, redis_url: str | None = None, client: Redis | None = None) -> None:
        self.client = client or build_redis_client(redis_url)
        self.cache = SemanticCache(client=self.client)
        self.memory = AgentMemory(client=self.client)

    def get_json(self, key: str) -> Any | None:
        try:
            raw = self.client.get(key)
        except RedisError:
            return None
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        try:
            self.client.setex(key, ttl_seconds, json.dumps(value, default=str))
        except RedisError:
            return

    def semantic_cache_lookup(self, namespace: str, query: str) -> Any | None:
        return self.cache.get(namespace, query)

    def semantic_cache_store(self, namespace: str, query: str, value: Any, ttl_seconds: int = 86400) -> None:
        self.cache.set(namespace, query, value, ttl_seconds=ttl_seconds)

    def append_memory(self, entity_key: str, item: dict[str, Any]) -> None:
        if entity_key.startswith("supplier:"):
            self.memory.record_supplier(int(entity_key.split(":", 1)[1]), item)
        elif entity_key.startswith("product:"):
            self.memory.record_product(int(entity_key.split(":", 1)[1]), item)
        else:
            self.memory._push(f"memory:{entity_key}", item, 20)

    def get_recent_memory(self, entity_key: str, limit: int = 5) -> list[dict[str, Any]]:
        if entity_key.startswith("supplier:"):
            return self.memory.recent_supplier(int(entity_key.split(":", 1)[1]), limit)
        if entity_key.startswith("product:"):
            return self.memory.recent_product(int(entity_key.split(":", 1)[1]), limit)
        return self.memory._read(f"memory:{entity_key}", limit)
