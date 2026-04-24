# Redis Context Engineering

The AI Market Intelligence OS uses Redis as the agent's short-term context
layer alongside Postgres (durable evidence) and TinyFish (fresh signal).
Three primitives sit on top of a single Redis connection:

| Primitive        | Class           | Keys                                                               | Purpose                                                    |
| ---------------- | --------------- | ------------------------------------------------------------------ | ---------------------------------------------------------- |
| Semantic cache   | `SemanticCache` | `semcache:<namespace>:<sha256(normalized_query)>`                  | Skip repeated TinyFish calls for near-identical queries    |
| Agent memory     | `AgentMemory`   | `memory:supplier:<id>`, `memory:product:<id>`, `memory:scans:recent` | Short-term per-entity and global scan history             |
| Job queues       | `ScanQueue`     | `supplier_scan_jobs`, `price_scan_jobs`                            | Work handoff from API to worker                            |

All three modules live under [apps/api/app/integrations/redis_layer/](../apps/api/app/integrations/redis_layer/) and share a single connection factory, `build_redis_client()`. A thin backward-compatible [RedisContext](../apps/api/app/integrations/redis_context.py) facade composes all three for existing call sites.

## Semantic cache

`SemanticCache.get(namespace, query)` / `.set(namespace, query, value, ttl_seconds)`:

- Queries are normalized (trim, collapse whitespace, lowercase) before hashing — so
  `"Acme Co NEWS"` and `"  acme   co  news "` share a cache entry.
- Keys embed an SHA-256 digest truncated to 24 chars. Namespaces isolate usage
  (e.g. `supplier_search`, `tinyfish_fetch`, `price_extract`).
- TTL is per entry; typical values are 15 min for volatile price extracts, 1 h for
  search results, 24 h for fetched pages. `SETEX` is atomic so there is no write window.
- Hit and miss are emitted at `logging.INFO` as `cache_hit` / `cache_miss` events
  carrying the namespace and key; Redis errors surface as `cache_error` warnings.

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

Writes use a pipeline (`LPUSH` + `LTRIM`) so the cap is enforced in one round-trip.
Reads tolerate missing keys and return an empty list.

Scanners record both per-entity memory *and* a global scan summary on completion,
so the recent-scans stream is observable even when callers only know the entity id.

## Retrieval context builder

[apps/api/app/services/context_builder.py](../apps/api/app/services/context_builder.py) composes a compact bundle for LLM prompts or deterministic scoring:

```python
bundle = build_supplier_context(session, supplier_id, redis_context)
# {
#   "supplier":     {"id": 7, "name": "...", "criticality": "high"},
#   "latest_risk":  {"score": 80, "explanation": "..."},
#   "evidence":     [ ...last 5 rows... ],
#   "alerts":       [ ...recent alerts... ],
#   "memory":       [ ...last 5 supplier memory entries... ],
#   "recent_scans": [ ...last 10 scan summaries... ],
# }
```

`build_product_context` mirrors this for products, returning the latest
recommendation in place of `latest_risk` and `alerts`.

The shape is stable and sized for a single LLM call (≈ 2-3 kB for typical tenants).
Limits on evidence/alert/memory counts are keyword args so callers can widen the
window when summarizing longer horizons.

## Job queues

Supplier and price scans run on separate Redis lists so a pile of price scans
never blocks supplier work and per-queue depth is observable (`LLEN`).

- `supplier_scan_jobs` — bodies like `{"job_id", "job_type": "supplier_scan", "payload": {"supplier_id": N}}`
- `price_scan_jobs`    — `{"job_id", "job_type": "price_scan",    "payload": {"product_id":  N}}`

The worker uses a single `BLPOP [supplier_scan_jobs, price_scan_jobs]` so it
still blocks efficiently while draining both queues. Unknown job types raise
`UnknownJobTypeError` at enqueue time so a typo fails loudly at the API boundary
rather than silently sitting in a queue no worker reads.

Streams (`XADD` / consumer groups) are a drop-in upgrade for later: the job
body format already carries a stable `job_id` and is easy to port when we need
consumer-group semantics, per-message acks, or dead-letter handling.

## Tests

- [app/tests/test_semantic_cache.py](../apps/api/app/tests/test_semantic_cache.py) — cache hit, miss, query normalization, TTL, hit/miss log output
- [app/tests/test_agent_memory.py](../apps/api/app/tests/test_agent_memory.py) — per-entity write/read, 50-item cap, missing keys
- [app/tests/test_context_builder.py](../apps/api/app/tests/test_context_builder.py) — supplier & product bundles, missing entities
- [app/tests/test_queues.py](../apps/api/app/tests/test_queues.py) — routing, unknown job, multi-queue drain, FIFO, empty-pop

All tests use `fakeredis` so no Redis server is required in CI. Run:

```bash
cd apps/api && .venv/bin/pytest -q
```
