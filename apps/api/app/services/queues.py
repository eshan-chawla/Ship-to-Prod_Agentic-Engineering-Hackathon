from __future__ import annotations

import json
import uuid
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings

QUEUE_NAME = "scan_jobs"


class ScanQueue:
    def __init__(self, redis_url: str | None = None) -> None:
        self.client = Redis.from_url(redis_url or get_settings().redis_url, decode_responses=True)

    def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        body = {"job_id": job_id, "job_type": job_type, "payload": payload}
        try:
            self.client.rpush(QUEUE_NAME, json.dumps(body))
        except RedisError as exc:
            raise RuntimeError("Unable to enqueue scan job. Is Redis running?") from exc
        return job_id

    def pop_blocking(self, timeout: int = 5) -> dict[str, Any] | None:
        item = self.client.blpop([QUEUE_NAME], timeout=timeout)
        if not item:
            return None
        _, raw = item
        return json.loads(raw)

