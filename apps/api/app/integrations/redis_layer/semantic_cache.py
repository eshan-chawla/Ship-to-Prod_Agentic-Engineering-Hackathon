from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.integrations.redis_layer.client import build_redis_client

log = logging.getLogger(__name__)

_WHITESPACE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    return _WHITESPACE.sub(" ", query.strip().lower())


class SemanticCache:
    """Keyed cache with TTL and hit/miss logging.

    Normalizes queries (trim, collapse whitespace, lowercase) and hashes them
    into the cache key so semantically equivalent queries collide.
    """

    def __init__(self, client: Redis | None = None, redis_url: str | None = None) -> None:
        self.client = client or build_redis_client(redis_url)

    def _key(self, namespace: str, query: str) -> str:
        digest = hashlib.sha256(normalize_query(query).encode("utf-8")).hexdigest()[:24]
        return f"semcache:{namespace}:{digest}"

    def get(self, namespace: str, query: str) -> Any | None:
        key = self._key(namespace, query)
        try:
            raw = self.client.get(key)
        except RedisError as exc:
            log.warning("cache_error op=get namespace=%s error=%s", namespace, exc)
            return None
        if raw is None:
            log.info("cache_miss namespace=%s key=%s", namespace, key)
            return None
        log.info("cache_hit namespace=%s key=%s", namespace, key)
        return json.loads(raw)

    def set(self, namespace: str, query: str, value: Any, ttl_seconds: int) -> None:
        key = self._key(namespace, query)
        try:
            self.client.setex(key, ttl_seconds, json.dumps(value, default=str))
        except RedisError as exc:
            log.warning("cache_error op=set namespace=%s error=%s", namespace, exc)
