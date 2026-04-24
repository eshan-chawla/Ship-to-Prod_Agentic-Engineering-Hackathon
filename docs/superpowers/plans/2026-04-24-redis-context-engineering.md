# Redis Context Engineering Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current thin `RedisContext` + single-queue `ScanQueue` into a proper context-engineering layer with (a) semantic cache with TTL/logging, (b) structured agent memory per supplier/product and recent scan summaries, (c) a retrieval context builder that assembles compact LLM/scoring context, and (d) dedicated Redis lists for supplier/price scan jobs, plus tests.

**Architecture:**
- Split `apps/api/app/integrations/redis_context.py` into focused modules under `apps/api/app/integrations/redis/`: `client.py` (connection), `semantic_cache.py`, `agent_memory.py`. Keep `redis_context.py` as a thin facade re-exporting a `RedisContext` that composes those pieces (backward-compatible with existing call sites).
- Add `apps/api/app/services/context_builder.py` that reads evidence, recent recommendations, and open alerts from Postgres and merges them with recent Redis memory/cache into a compact `ContextBundle`.
- Refactor `apps/api/app/services/queues.py` so `ScanQueue.enqueue()` routes `supplier_scan` jobs to `supplier_scan_jobs` and `price_scan` jobs to `price_scan_jobs` lists, and `pop_blocking()` reads from both.
- All Redis classes accept an injected `Redis` client for testing; `fakeredis` powers unit tests.

**Tech Stack:** Python 3.14, FastAPI, `redis` 5.2.1 client, `fakeredis` 2.35 for tests, `structlog` for hit/miss logging, SQLModel for DB reads in the retrieval builder.

---

### Task 1: Add fakeredis to requirements

**Files:**
- Modify: `apps/api/requirements.txt`

- [ ] **Step 1: Append fakeredis**

```
fakeredis==2.35.1
```

- [ ] **Step 2: Confirm pip sees it**

Run: `cd apps/api && .venv/bin/pip install -r requirements.txt && .venv/bin/python -c "import fakeredis; print(fakeredis.__version__)"`
Expected: prints `2.35.1`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/requirements.txt
git commit -m "chore: add fakeredis for redis unit tests"
```

---

### Task 2: Semantic cache abstraction

**Files:**
- Create: `apps/api/app/integrations/redis/__init__.py`
- Create: `apps/api/app/integrations/redis/client.py`
- Create: `apps/api/app/integrations/redis/semantic_cache.py`
- Test: `apps/api/app/tests/test_semantic_cache.py`

- [ ] **Step 1: Write failing test `test_semantic_cache.py`**

```python
import fakeredis
from app.integrations.redis.semantic_cache import SemanticCache


def make_cache() -> SemanticCache:
    return SemanticCache(client=fakeredis.FakeRedis(decode_responses=True))


def test_cache_miss_returns_none() -> None:
    cache = make_cache()
    assert cache.get("supplier_search", "Acme Co NEWS") is None


def test_cache_hit_after_set_roundtrips_value() -> None:
    cache = make_cache()
    cache.set("supplier_search", "Acme Co NEWS", {"results": [1, 2, 3]}, ttl_seconds=60)
    assert cache.get("supplier_search", "Acme Co NEWS") == {"results": [1, 2, 3]}


def test_cache_key_normalizes_query_whitespace_and_case() -> None:
    cache = make_cache()
    cache.set("supplier_search", "Acme Co NEWS", {"results": ["hit"]}, ttl_seconds=60)
    assert cache.get("supplier_search", "  acme   co  news ") == {"results": ["hit"]}


def test_cache_ttl_is_applied() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    cache = SemanticCache(client=client)
    cache.set("price_extract", "https://shop.example/product", {"price": 10}, ttl_seconds=42)
    key = cache._key("price_extract", "https://shop.example/product")
    assert 0 < client.ttl(key) <= 42


def test_hit_and_miss_are_logged(caplog) -> None:
    import logging
    caplog.set_level(logging.INFO)
    cache = make_cache()
    cache.get("supplier_search", "q")  # miss
    cache.set("supplier_search", "q", {"x": 1}, ttl_seconds=60)
    cache.get("supplier_search", "q")  # hit
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "cache_miss" in messages
    assert "cache_hit" in messages
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_semantic_cache.py -v`
Expected: FAIL (`ModuleNotFoundError: app.integrations.redis.semantic_cache`).

- [ ] **Step 3: Create empty package init**

`apps/api/app/integrations/redis/__init__.py`:
```python
```

- [ ] **Step 4: Create shared client factory**

`apps/api/app/integrations/redis/client.py`:
```python
from __future__ import annotations

from redis import Redis
from app.core.config import get_settings


def build_redis_client(redis_url: str | None = None) -> Redis:
    return Redis.from_url(redis_url or get_settings().redis_url, decode_responses=True)
```

- [ ] **Step 5: Implement SemanticCache**

`apps/api/app/integrations/redis/semantic_cache.py`:
```python
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.integrations.redis.client import build_redis_client

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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_semantic_cache.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/integrations/redis/ apps/api/app/tests/test_semantic_cache.py
git commit -m "feat(redis): semantic cache with TTL and hit/miss logging"
```

---

### Task 3: Agent memory (supplier, product, recent scans)

**Files:**
- Create: `apps/api/app/integrations/redis/agent_memory.py`
- Test: `apps/api/app/tests/test_agent_memory.py`

- [ ] **Step 1: Write failing test `test_agent_memory.py`**

```python
import fakeredis
from app.integrations.redis.agent_memory import AgentMemory


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_agent_memory.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement AgentMemory**

`apps/api/app/integrations/redis/agent_memory.py`:
```python
from __future__ import annotations

import json
import logging
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.integrations.redis.client import build_redis_client

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_agent_memory.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/integrations/redis/agent_memory.py apps/api/app/tests/test_agent_memory.py
git commit -m "feat(redis): structured agent memory for suppliers, products, scans"
```

---

### Task 4: Refactor RedisContext facade (backward-compatible)

**Files:**
- Modify: `apps/api/app/integrations/redis_context.py`
- Modify: `apps/api/app/services/supplier_scanner.py`
- Modify: `apps/api/app/services/pricing_scanner.py`

- [ ] **Step 1: Replace redis_context.py with facade**

Full new contents of `apps/api/app/integrations/redis_context.py`:
```python
"""Back-compat facade composing SemanticCache + AgentMemory.

New code should import SemanticCache / AgentMemory directly from
app.integrations.redis.*. RedisContext remains for existing call sites.
"""
from __future__ import annotations

from typing import Any
from redis import Redis
from app.integrations.redis.agent_memory import AgentMemory
from app.integrations.redis.client import build_redis_client
from app.integrations.redis.semantic_cache import SemanticCache


class RedisContext:
    def __init__(self, redis_url: str | None = None, client: Redis | None = None) -> None:
        self.client = client or build_redis_client(redis_url)
        self.cache = SemanticCache(client=self.client)
        self.memory = AgentMemory(client=self.client)

    # --- cache helpers (legacy key-value API, now delegates through cache namespace) ---
    def get_json(self, key: str) -> Any | None:
        raw = self.client.get(key)
        if raw is None:
            return None
        import json
        return json.loads(raw)

    def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        import json
        self.client.setex(key, ttl_seconds, json.dumps(value, default=str))

    # --- semantic cache (preferred going forward) ---
    def semantic_cache_lookup(self, namespace: str, query: str) -> Any | None:
        return self.cache.get(namespace, query)

    def semantic_cache_store(self, namespace: str, query: str, value: Any, ttl_seconds: int = 86400) -> None:
        self.cache.set(namespace, query, value, ttl_seconds=ttl_seconds)

    # --- legacy memory API, now routes through AgentMemory ---
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
```

- [ ] **Step 2: Record a scan summary when supplier scan completes**

In `apps/api/app/services/supplier_scanner.py`, replace the existing line:
```python
redis_context.append_memory(f"supplier:{supplier_id}", {"risk_score": risk.score, "scan_id": scan.id})
```
with:
```python
redis_context.memory.record_supplier(supplier_id, {"risk_score": risk.score, "scan_id": scan.id})
redis_context.memory.record_scan_summary(
    {"kind": "supplier_scan", "entity_id": supplier_id, "score": risk.score, "scan_id": scan.id}
)
```

- [ ] **Step 3: Same for price scanner**

In `apps/api/app/services/pricing_scanner.py`, replace:
```python
redis_context.append_memory(f"product:{product_id}", {"recommendation": recommendation.action})
```
with:
```python
redis_context.memory.record_product(product_id, {"recommendation": recommendation.action, "confidence": recommendation.confidence})
redis_context.memory.record_scan_summary(
    {"kind": "price_scan", "entity_id": product_id, "action": recommendation.action}
)
```

- [ ] **Step 4: Run entire test suite**

Run: `cd apps/api && .venv/bin/pytest -q`
Expected: all tests pass (semantic_cache + agent_memory + existing health/scoring/tinyfish).

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/integrations/redis_context.py apps/api/app/services/supplier_scanner.py apps/api/app/services/pricing_scanner.py
git commit -m "refactor: route RedisContext through SemanticCache + AgentMemory"
```

---

### Task 5: Retrieval context builder

**Files:**
- Create: `apps/api/app/services/context_builder.py`
- Test: `apps/api/app/tests/test_context_builder.py`

- [ ] **Step 1: Write failing test `test_context_builder.py`**

```python
from datetime import datetime, timezone
import fakeredis
from sqlmodel import Session, SQLModel, create_engine

from app.integrations.redis.agent_memory import AgentMemory
from app.integrations.redis_context import RedisContext
from app.models.entities import (
    Alert,
    EvidenceItem,
    PriceRecommendation,
    Product,
    Supplier,
    SupplierRiskScore,
    SupplierScan,
)
from app.services.context_builder import build_product_context, build_supplier_context


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _ctx() -> RedisContext:
    return RedisContext(client=fakeredis.FakeRedis(decode_responses=True))


def test_supplier_context_gathers_evidence_risk_alerts_and_memory() -> None:
    session = _session()
    supplier = Supplier(name="Acme", website="x", country="US", category="c")
    session.add(supplier)
    session.commit()
    scan = SupplierScan(supplier_id=supplier.id, status="completed", started_at=datetime.now(timezone.utc))
    session.add(scan)
    session.commit()
    session.add(SupplierRiskScore(
        supplier_id=supplier.id, scan_id=scan.id, score=80,
        financial_stress=40, legal_regulatory=10, delivery_disruption=30,
        sentiment=0, cybersecurity=0, geopolitical=0, explanation="high",
    ))
    session.add(EvidenceItem(
        entity_type="supplier", entity_id=supplier.id, source_url="https://e/1",
        source_title="news", content="cash crunch", evidence_type="risk_signal",
        risk_factor="financial_stress",
    ))
    session.add(Alert(
        entity_type="supplier", entity_id=supplier.id,
        severity="high", title="threshold", message="over 80",
    ))
    session.commit()

    ctx = _ctx()
    ctx.memory.record_supplier(supplier.id, {"risk_score": 80, "scan_id": scan.id})

    bundle = build_supplier_context(session, supplier.id, ctx)
    assert bundle["supplier"]["name"] == "Acme"
    assert bundle["latest_risk"]["score"] == 80
    assert len(bundle["evidence"]) == 1
    assert len(bundle["alerts"]) == 1
    assert bundle["memory"][0]["risk_score"] == 80


def test_product_context_gathers_recommendations_evidence_and_memory() -> None:
    session = _session()
    product = Product(name="Sku", brand="b", category="c", target_price=100, target_margin=0.3)
    session.add(product)
    session.commit()
    session.add(PriceRecommendation(product_id=product.id, action="launch promo", explanation="e", confidence=0.8))
    session.add(EvidenceItem(
        entity_type="product", entity_id=product.id, source_url="https://s/1",
        source_title="comp", content="$88", evidence_type="price_signal",
    ))
    session.commit()

    ctx = _ctx()
    ctx.memory.record_product(product.id, {"recommendation": "launch promo", "confidence": 0.8})

    bundle = build_product_context(session, product.id, ctx)
    assert bundle["product"]["name"] == "Sku"
    assert bundle["latest_recommendation"]["action"] == "launch promo"
    assert len(bundle["evidence"]) == 1
    assert bundle["memory"][0]["recommendation"] == "launch promo"


def test_missing_entities_return_none_for_entity() -> None:
    session = _session()
    ctx = _ctx()
    assert build_supplier_context(session, 999, ctx) is None
    assert build_product_context(session, 999, ctx) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_context_builder.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement context_builder.py**

`apps/api/app/services/context_builder.py`:
```python
from __future__ import annotations

from typing import Any
from sqlalchemy import desc
from sqlmodel import Session, select
from app.integrations.redis_context import RedisContext
from app.models.entities import (
    Alert,
    EvidenceItem,
    PriceRecommendation,
    Product,
    Supplier,
    SupplierRiskScore,
)


def _evidence_dict(item: EvidenceItem) -> dict[str, Any]:
    return {
        "source_url": item.source_url,
        "source_title": item.source_title,
        "content": item.content,
        "evidence_type": item.evidence_type,
        "risk_factor": item.risk_factor,
        "captured_at": item.captured_at.isoformat() if item.captured_at else None,
    }


def _alert_dict(alert: Alert) -> dict[str, Any]:
    return {
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def build_supplier_context(
    session: Session,
    supplier_id: int,
    redis_context: RedisContext,
    *,
    evidence_limit: int = 5,
    alert_limit: int = 5,
    memory_limit: int = 5,
) -> dict[str, Any] | None:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        return None
    latest_risk = session.exec(
        select(SupplierRiskScore)
        .where(SupplierRiskScore.supplier_id == supplier_id)
        .order_by(desc(SupplierRiskScore.created_at))
        .limit(1)
    ).first()
    evidence = session.exec(
        select(EvidenceItem)
        .where(EvidenceItem.entity_type == "supplier", EvidenceItem.entity_id == supplier_id)
        .order_by(desc(EvidenceItem.captured_at))
        .limit(evidence_limit)
    ).all()
    alerts = session.exec(
        select(Alert)
        .where(Alert.entity_type == "supplier", Alert.entity_id == supplier_id)
        .order_by(desc(Alert.created_at))
        .limit(alert_limit)
    ).all()
    return {
        "supplier": {"id": supplier.id, "name": supplier.name, "country": supplier.country, "criticality": supplier.criticality},
        "latest_risk": {
            "score": latest_risk.score,
            "explanation": latest_risk.explanation,
        } if latest_risk else None,
        "evidence": [_evidence_dict(e) for e in evidence],
        "alerts": [_alert_dict(a) for a in alerts],
        "memory": redis_context.memory.recent_supplier(supplier_id, memory_limit),
        "recent_scans": redis_context.memory.recent_scans(limit=10),
    }


def build_product_context(
    session: Session,
    product_id: int,
    redis_context: RedisContext,
    *,
    evidence_limit: int = 5,
    memory_limit: int = 5,
) -> dict[str, Any] | None:
    product = session.get(Product, product_id)
    if not product:
        return None
    latest_rec = session.exec(
        select(PriceRecommendation)
        .where(PriceRecommendation.product_id == product_id)
        .order_by(desc(PriceRecommendation.created_at))
        .limit(1)
    ).first()
    evidence = session.exec(
        select(EvidenceItem)
        .where(EvidenceItem.entity_type == "product", EvidenceItem.entity_id == product_id)
        .order_by(desc(EvidenceItem.captured_at))
        .limit(evidence_limit)
    ).all()
    return {
        "product": {
            "id": product.id, "name": product.name, "brand": product.brand,
            "target_price": product.target_price, "target_margin": product.target_margin,
        },
        "latest_recommendation": {
            "action": latest_rec.action,
            "explanation": latest_rec.explanation,
            "confidence": latest_rec.confidence,
        } if latest_rec else None,
        "evidence": [_evidence_dict(e) for e in evidence],
        "memory": redis_context.memory.recent_product(product_id, memory_limit),
        "recent_scans": redis_context.memory.recent_scans(limit=10),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_context_builder.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/context_builder.py apps/api/app/tests/test_context_builder.py
git commit -m "feat(context): retrieval builder for supplier/product LLM context"
```

---

### Task 6: Split scan-jobs into supplier and price lists

**Files:**
- Modify: `apps/api/app/services/queues.py`
- Test: `apps/api/app/tests/test_queues.py`

- [ ] **Step 1: Write failing test `test_queues.py`**

```python
import fakeredis
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
    import pytest
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_queues.py -v`
Expected: FAIL (symbols don't exist yet).

- [ ] **Step 3: Replace queues.py**

Full new contents of `apps/api/app/services/queues.py`:
```python
from __future__ import annotations

import json
import uuid
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.integrations.redis.client import build_redis_client

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
```

- [ ] **Step 4: Run test**

Run: `cd apps/api && .venv/bin/pytest app/tests/test_queues.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Run full test suite to catch regressions**

Run: `cd apps/api && .venv/bin/pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/queues.py apps/api/app/tests/test_queues.py
git commit -m "feat(queues): split supplier_scan_jobs and price_scan_jobs lists"
```

---

### Task 7: Documentation

**Files:**
- Create: `docs/context-engineering.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Write docs/context-engineering.md**

Full contents:
````markdown
# Redis Context Engineering

The AI Market Intelligence OS uses Redis as the agent's short-term context
layer alongside Postgres (durable evidence) and TinyFish (fresh signal).
Three primitives sit on top of a single Redis connection:

| Primitive | Class | Keys | Purpose |
|-----------|-------|------|---------|
| Semantic cache | `SemanticCache` | `semcache:<namespace>:<sha256(normalized_query)>` | Skip repeated TinyFish calls for near-identical queries |
| Agent memory | `AgentMemory` | `memory:supplier:<id>`, `memory:product:<id>`, `memory:scans:recent` | Short-term per-entity and global scan history |
| Job queues | `ScanQueue` | `supplier_scan_jobs`, `price_scan_jobs` | Work handoff from API to worker |

## Semantic cache

`SemanticCache.get(namespace, query)` / `.set(namespace, query, value, ttl_seconds)`:

- Queries are normalized (trim, collapse whitespace, lowercase) before hashing — so
  `"Acme Co NEWS"` and `"  acme   co  news "` share a cache entry.
- Keys embed an SHA-256 digest truncated to 24 chars. Namespaces isolate usage
  (e.g. `supplier_search`, `tinyfish_fetch`, `price_extract`).
- TTL is per entry; 15 min for volatile price extracts, 1 h for search results,
  24 h for fetched pages. `SETEX` is atomic so there is no write window.
- Hit and miss are emitted via `logging.INFO` events `cache_hit` / `cache_miss`
  carrying the namespace and key; redis errors surface as `cache_error` warnings.

Legacy `RedisContext.semantic_cache_lookup` / `..._store` forwards to this class.
A future swap-in of Redis Vector Search only needs to override `_key()` to embed
query vectors — call sites stay identical.

## Agent memory

`AgentMemory` wraps three capped LPUSH/LTRIM lists. They carry compact JSON
summaries, not the full evidence — evidence lives in Postgres.

- `record_supplier(supplier_id, entry)` → `memory:supplier:<id>` (cap 20)
- `record_product(product_id, entry)` → `memory:product:<id>` (cap 20)
- `record_scan_summary(entry)` → `memory:scans:recent` (cap 50)

Typical supplier entry: `{"risk_score": 72, "scan_id": 10}`.
Typical product entry: `{"recommendation": "launch promo", "confidence": 0.8}`.
Typical scan-summary entry: `{"kind": "supplier_scan", "entity_id": 7, "score": 72}`.

Writes use a pipeline (`LPUSH` + `LTRIM`) so the cap is enforced atomically.
Reads tolerate missing keys and return an empty list.

## Retrieval context builder

`app.services.context_builder` composes a compact bundle for LLM prompts or
deterministic scoring:

```python
bundle = build_supplier_context(session, supplier_id, redis_context)
# {
#   "supplier":   {"id": 7, "name": "...", "criticality": "high"},
#   "latest_risk":{"score": 80, "explanation": "..."},
#   "evidence":   [ ...last 5 rows... ],
#   "alerts":     [ ...open/recent alerts... ],
#   "memory":     [ ...last 5 supplier memory entries... ],
#   "recent_scans":[ ...last 10 scan summaries... ],
# }
```

`build_product_context` mirrors this for products, returning the latest
recommendation in place of `latest_risk` and `alerts`.

The shape is stable and sized for a single LLM call (≈ 2-3 kB).

## Job queues

Supplier and price scans run on separate Redis lists so a pile of price scans
never blocks supplier work and per-queue depth is observable (`LLEN`).

- `supplier_scan_jobs` — bodies like `{"job_id", "job_type": "supplier_scan", "payload": {"supplier_id": N}}`
- `price_scan_jobs` — `{"job_id", "job_type": "price_scan", "payload": {"product_id": N}}`

The worker uses a single `BLPOP [supplier_scan_jobs, price_scan_jobs]` so it
still blocks efficiently while draining both queues. Unknown job types raise
`UnknownJobTypeError` at enqueue time.

Streams (`XADD` / consumer groups) are a drop-in upgrade for later: the job
body format already carries a stable `job_id` and is easy to port.

## Tests

- `apps/api/app/tests/test_semantic_cache.py` — cache hit, miss, normalization, TTL, log output
- `apps/api/app/tests/test_agent_memory.py` — per-entity write/read, cap, missing keys
- `apps/api/app/tests/test_context_builder.py` — supplier & product bundles, missing entities
- `apps/api/app/tests/test_queues.py` — routing, unknown job, multi-queue drain, FIFO

All tests use `fakeredis` so no Redis server is required in CI.
````

- [ ] **Step 2: Update architecture.md bullet to mention new structure**

In `docs/architecture.md`, replace the bullet:
```
- Redis context engineering provides web result caching, short-term memory, semantic-cache placeholder methods, and queueing.
```
with:
```
- Redis context engineering provides a semantic cache (TTL + hit/miss logging), structured agent memory (per-supplier, per-product, recent scans), a retrieval context builder that assembles compact LLM/scoring input, and dedicated job queues (`supplier_scan_jobs`, `price_scan_jobs`). See [context-engineering.md](./context-engineering.md).
```

Also replace the mermaid line:
```
  API --> Queue[Redis scan_jobs list]
```
with:
```
  API --> Queue[supplier_scan_jobs + price_scan_jobs]
```

- [ ] **Step 3: Commit**

```bash
git add docs/context-engineering.md docs/architecture.md
git commit -m "docs: describe redis context engineering layer"
```

---

## Self-Review

**Spec coverage:**
- Semantic cache abstraction (norm key, TTL, hit/miss log) → Task 2
- Agent memory (supplier, product, recent scan summaries) → Task 3
- Retrieval context builder (evidence, recs, alerts, compact object) → Task 5
- Redis streams/lists for `supplier_scan_jobs` and `price_scan_jobs` → Task 6 (lists; streams noted as future upgrade in docs)
- Tests for cache hit/miss, memory write/read, job enqueue/dequeue → Tasks 2, 3, 6
- Update `docs/context-engineering.md` → Task 7

**Type consistency:** `AgentMemory.record_supplier/record_product/record_scan_summary` and `recent_supplier/recent_product/recent_scans` are used consistently in Tasks 3, 4, 5, 7. `SemanticCache.get/set` + `_key` consistent. `ScanQueue.enqueue/pop_blocking` consistent with existing worker call site.

No placeholders; every step contains either full code or a precise edit.
