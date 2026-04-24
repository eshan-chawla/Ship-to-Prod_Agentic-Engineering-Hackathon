import fakeredis
import pytest

from app.services.queues import (
    PRICE_SCAN_QUEUE,
    SUPPLIER_SCAN_QUEUE,
    ScanQueue,
    UnknownJobTypeError,
)


def make_queue() -> ScanQueue:
    return ScanQueue(client=fakeredis.FakeRedis(decode_responses=True))


def test_enqueue_routes_supplier_jobs_to_supplier_queue() -> None:
    queue = make_queue()
    job_id = queue.enqueue("supplier_scan", {"supplier_id": 7})
    assert queue.client.llen(SUPPLIER_SCAN_QUEUE) == 1
    assert queue.client.llen(PRICE_SCAN_QUEUE) == 0
    assert job_id


def test_enqueue_routes_price_jobs_to_price_queue() -> None:
    queue = make_queue()
    queue.enqueue("price_scan", {"product_id": 3})
    assert queue.client.llen(PRICE_SCAN_QUEUE) == 1
    assert queue.client.llen(SUPPLIER_SCAN_QUEUE) == 0


def test_enqueue_rejects_unknown_job_type() -> None:
    queue = make_queue()
    with pytest.raises(UnknownJobTypeError):
        queue.enqueue("banana", {})


def test_dequeue_drains_both_queues() -> None:
    queue = make_queue()
    queue.enqueue("supplier_scan", {"supplier_id": 1})
    queue.enqueue("price_scan", {"product_id": 2})
    first = queue.pop_blocking(timeout=1)
    second = queue.pop_blocking(timeout=1)
    types = sorted([first["job_type"], second["job_type"]])
    assert types == ["price_scan", "supplier_scan"]


def test_dequeue_preserves_fifo_per_queue() -> None:
    queue = make_queue()
    queue.enqueue("supplier_scan", {"supplier_id": 1})
    queue.enqueue("supplier_scan", {"supplier_id": 2})
    a = queue.pop_blocking(timeout=1)
    b = queue.pop_blocking(timeout=1)
    assert a["payload"]["supplier_id"] == 1
    assert b["payload"]["supplier_id"] == 2


def test_pop_returns_none_when_empty() -> None:
    queue = make_queue()
    assert queue.pop_blocking(timeout=1) is None
