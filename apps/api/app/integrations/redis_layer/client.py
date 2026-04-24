from __future__ import annotations

from redis import Redis
from app.core.config import get_settings


def build_redis_client(redis_url: str | None = None) -> Redis:
    return Redis.from_url(redis_url or get_settings().redis_url, decode_responses=True)
