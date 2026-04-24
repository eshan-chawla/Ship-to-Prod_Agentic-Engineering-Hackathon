from __future__ import annotations

import json
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings


class RedisContext:
    def __init__(self, redis_url: str | None = None) -> None:
        self.client = Redis.from_url(redis_url or get_settings().redis_url, decode_responses=True)

    def get_json(self, key: str) -> Any | None:
        try:
            value = self.client.get(key)
        except RedisError:
            return None
        return json.loads(value) if value else None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        try:
            self.client.setex(key, ttl_seconds, json.dumps(value, default=str))
        except RedisError:
            return

    def append_memory(self, entity_key: str, item: dict[str, Any]) -> None:
        try:
            self.client.lpush(f"memory:{entity_key}", json.dumps(item, default=str))
            self.client.ltrim(f"memory:{entity_key}", 0, 19)
        except RedisError:
            return

    def get_recent_memory(self, entity_key: str, limit: int = 5) -> list[dict[str, Any]]:
        try:
            values = self.client.lrange(f"memory:{entity_key}", 0, limit - 1)
        except RedisError:
            return []
        return [json.loads(value) for value in values]

    def semantic_cache_lookup(self, namespace: str, query: str) -> dict[str, Any] | None:
        # Placeholder: replace with embedding similarity lookup backed by Redis vector search.
        return self.get_json(f"semantic:{namespace}:{query.lower()}")

    def semantic_cache_store(self, namespace: str, query: str, value: dict[str, Any]) -> None:
        # Placeholder: store embeddings and metadata when Redis vector indexing is enabled.
        self.set_json(f"semantic:{namespace}:{query.lower()}", value, ttl_seconds=86400)

