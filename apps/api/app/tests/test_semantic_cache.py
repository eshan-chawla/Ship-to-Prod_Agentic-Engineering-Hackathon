import logging

import fakeredis

from app.integrations.redis_layer.semantic_cache import SemanticCache


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
    caplog.set_level(logging.INFO)
    cache = make_cache()
    cache.get("supplier_search", "q")
    cache.set("supplier_search", "q", {"x": 1}, ttl_seconds=60)
    cache.get("supplier_search", "q")
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "cache_miss" in messages
    assert "cache_hit" in messages
