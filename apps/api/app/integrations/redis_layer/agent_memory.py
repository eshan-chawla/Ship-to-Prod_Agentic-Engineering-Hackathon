from __future__ import annotations

import json
import logging
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.integrations.redis_layer.client import build_redis_client

log = logging.getLogger(__name__)

SUPPLIER_MEMORY_LIMIT = 20
PRODUCT_MEMORY_LIMIT = 20
SCAN_SUMMARY_LIMIT = 50


class AgentMemory:
    """Per-supplier, per-product, and global recent-scan memory lists."""

    def __init__(self, client: Redis | None = None, redis_url: str | None = None) -> None:
        self.client = client or build_redis_client(redis_url)

    def _push(self, key: str, item: dict[str, Any], cap: int) -> None:
        try:
            pipe = self.client.pipeline()
            pipe.lpush(key, json.dumps(item, default=str))
            pipe.ltrim(key, 0, cap - 1)
            pipe.execute()
        except RedisError as exc:
            log.warning("memory_error op=push key=%s error=%s", key, exc)

    def _read(self, key: str, limit: int) -> list[dict[str, Any]]:
        try:
            raw = self.client.lrange(key, 0, limit - 1)
        except RedisError as exc:
            log.warning("memory_error op=read key=%s error=%s", key, exc)
            return []
        return [json.loads(item) for item in raw]

    def record_supplier(self, supplier_id: int, entry: dict[str, Any]) -> None:
        self._push(f"memory:supplier:{supplier_id}", entry, SUPPLIER_MEMORY_LIMIT)

    def recent_supplier(self, supplier_id: int, limit: int = 5) -> list[dict[str, Any]]:
        return self._read(f"memory:supplier:{supplier_id}", limit)

    def record_product(self, product_id: int, entry: dict[str, Any]) -> None:
        self._push(f"memory:product:{product_id}", entry, PRODUCT_MEMORY_LIMIT)

    def recent_product(self, product_id: int, limit: int = 5) -> list[dict[str, Any]]:
        return self._read(f"memory:product:{product_id}", limit)

    def record_scan_summary(self, entry: dict[str, Any]) -> None:
        self._push("memory:scans:recent", entry, SCAN_SUMMARY_LIMIT)

    def recent_scans(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._read("memory:scans:recent", limit)
