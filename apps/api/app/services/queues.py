from __future__ import annotations

import json
import uuid
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.integrations.redis_layer.client import build_redis_client

SUPPLIER_SCAN_QUEUE = "supplier_scan_jobs"
PRICE_SCAN_QUEUE = "price_scan_jobs"

_JOB_TYPE_TO_QUEUE = {
    "supplier_scan": SUPPLIER_SCAN_QUEUE,
    "price_scan": PRICE_SCAN_QUEUE,
}


class UnknownJobTypeError(ValueError):
    pass


class ScanQueue:
    """Dispatches supplier_scan and price_scan jobs to separate Redis lists.

    Workers drain both lists with a single BLPOP call.
    """

    def __init__(self, redis_url: str | None = None, client: Redis | None = None) -> None:
        self.client = client or build_redis_client(redis_url)

    def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        queue_name = _JOB_TYPE_TO_QUEUE.get(job_type)
        if not queue_name:
            raise UnknownJobTypeError(f"Unknown job type: {job_type}")
        job_id = str(uuid.uuid4())
        body = {"job_id": job_id, "job_type": job_type, "payload": payload}
        try:
            self.client.rpush(queue_name, json.dumps(body))
        except RedisError as exc:
            raise RuntimeError("Unable to enqueue scan job. Is Redis running?") from exc
        return job_id

    def pop_blocking(self, timeout: int = 5) -> dict[str, Any] | None:
        item = self.client.blpop([SUPPLIER_SCAN_QUEUE, PRICE_SCAN_QUEUE], timeout=timeout)
        if not item:
            return None
        _, raw = item
        return json.loads(raw)
