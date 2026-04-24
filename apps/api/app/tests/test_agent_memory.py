import fakeredis

from app.integrations.redis_layer.agent_memory import AgentMemory


def make_memory() -> AgentMemory:
    return AgentMemory(client=fakeredis.FakeRedis(decode_responses=True))


def test_supplier_memory_write_and_read() -> None:
    memory = make_memory()
    memory.record_supplier(1, {"risk_score": 72, "scan_id": 10})
    memory.record_supplier(1, {"risk_score": 68, "scan_id": 11})
    recent = memory.recent_supplier(1, limit=2)
    assert [r["scan_id"] for r in recent] == [11, 10]


def test_product_memory_write_and_read() -> None:
    memory = make_memory()
    memory.record_product(5, {"recommendation": "hold", "confidence": 0.9})
    recent = memory.recent_product(5)
    assert recent[0]["recommendation"] == "hold"


def test_recent_scan_summary_is_capped_and_ordered() -> None:
    memory = make_memory()
    for i in range(25):
        memory.record_scan_summary({"kind": "supplier_scan", "entity_id": i, "score": i})
    summaries = memory.recent_scans(limit=5)
    assert len(summaries) == 5
    assert [s["entity_id"] for s in summaries] == [24, 23, 22, 21, 20]


def test_missing_entity_returns_empty_list() -> None:
    memory = make_memory()
    assert memory.recent_supplier(999) == []
    assert memory.recent_product(999) == []
    assert memory.recent_scans() == []
