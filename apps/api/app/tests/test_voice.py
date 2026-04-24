from __future__ import annotations

import json
from collections.abc import Iterator

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.voice_routes import _redis, router as voice_router
from app.core.config import Settings
from app.db.session import get_session
from app.integrations.redis_context import RedisContext
from app.integrations.vapi import parse_tool_calls, verify_signature
from app.main import app
from app.models.entities import (
    Alert,
    PriceRecommendation,
    Product,
    Supplier,
    SupplierRiskScore,
    SupplierScan,
)
from app.services.voice import (
    describe_subscription,
    high_risk_suppliers,
    pricing_recommendations,
    supplier_summary,
)


@pytest.fixture()
def memory_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def fake_redis_context() -> RedisContext:
    return RedisContext(client=fakeredis.FakeRedis(decode_responses=True))


@pytest.fixture()
def client(memory_session: Session, fake_redis_context: RedisContext) -> Iterator[TestClient]:
    def _session_override() -> Iterator[Session]:
        yield memory_session

    def _redis_override() -> RedisContext:
        return fake_redis_context

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[_redis] = _redis_override
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(_redis, None)


def _seed_two_suppliers(session: Session) -> tuple[Supplier, Supplier]:
    high = Supplier(name="Acme Electronics", website="x", country="US", category="semi", criticality="critical")
    low = Supplier(name="Calm Co", website="x", country="US", category="pkg", criticality="low")
    session.add_all([high, low])
    session.commit()
    session.refresh(high)
    session.refresh(low)
    scan_h = SupplierScan(supplier_id=high.id, status="completed")
    scan_l = SupplierScan(supplier_id=low.id, status="completed")
    session.add_all([scan_h, scan_l])
    session.commit()
    session.refresh(scan_h)
    session.refresh(scan_l)
    session.add(
        SupplierRiskScore(
            supplier_id=high.id, scan_id=scan_h.id, score=82,
            financial_stress=20, legal_regulatory=0, delivery_disruption=53,
            sentiment=0, cybersecurity=42, geopolitical=0,
            explanation="driven by delivery disruption",
        )
    )
    session.add(
        SupplierRiskScore(
            supplier_id=low.id, scan_id=scan_l.id, score=35,
            financial_stress=10, legal_regulatory=0, delivery_disruption=0,
            sentiment=0, cybersecurity=0, geopolitical=0,
            explanation="low signals",
        )
    )
    session.commit()
    return high, low


# ---------- Pure formatter tests ----------

def test_high_risk_suppliers_spoken_mentions_top_supplier(memory_session: Session) -> None:
    high, _low = _seed_two_suppliers(memory_session)
    result = high_risk_suppliers(memory_session)
    assert result["count"] == 1
    assert high.name in result["spoken"]
    assert "82" in result["spoken"]
    assert "delivery disruption" in result["spoken"]


def test_high_risk_suppliers_spoken_says_all_clear_when_nothing_above_threshold(memory_session: Session) -> None:
    low = Supplier(name="Chill Co", website="x", country="US", category="pkg")
    memory_session.add(low)
    memory_session.commit()
    memory_session.refresh(low)
    scan = SupplierScan(supplier_id=low.id, status="completed")
    memory_session.add(scan)
    memory_session.commit()
    memory_session.refresh(scan)
    memory_session.add(
        SupplierRiskScore(
            supplier_id=low.id, scan_id=scan.id, score=20,
            financial_stress=5, legal_regulatory=0, delivery_disruption=0,
            sentiment=0, cybersecurity=0, geopolitical=0,
            explanation="ok",
        )
    )
    memory_session.commit()
    result = high_risk_suppliers(memory_session)
    assert result["count"] == 0
    assert "No suppliers" in result["spoken"]


def test_supplier_summary_mentions_trend_when_two_scores_present(memory_session: Session) -> None:
    high, _ = _seed_two_suppliers(memory_session)
    # Add a second, lower, earlier-read record — but with a later created_at it's treated as latest.
    scan = SupplierScan(supplier_id=high.id, status="completed")
    memory_session.add(scan)
    memory_session.commit()
    memory_session.refresh(scan)
    memory_session.add(
        SupplierRiskScore(
            supplier_id=high.id, scan_id=scan.id, score=88,
            financial_stress=20, legal_regulatory=0, delivery_disruption=60,
            sentiment=0, cybersecurity=40, geopolitical=0,
            explanation="trend up",
        )
    )
    memory_session.commit()
    result = supplier_summary(memory_session, high.id)
    assert "88" in result["spoken"]
    assert "up 6 points" in result["spoken"]


def test_supplier_summary_returns_none_for_missing_supplier(memory_session: Session) -> None:
    assert supplier_summary(memory_session, 999) is None


def test_pricing_recommendations_prioritizes_action_items(memory_session: Session) -> None:
    product_hold = Product(name="Sku-Hold", brand="b", category="c", target_price=100, target_margin=0.3)
    product_promo = Product(name="Sku-Promo", brand="b", category="c", target_price=100, target_margin=0.3)
    memory_session.add_all([product_hold, product_promo])
    memory_session.commit()
    memory_session.refresh(product_hold)
    memory_session.refresh(product_promo)
    memory_session.add_all([
        PriceRecommendation(product_id=product_hold.id, action="HOLD_PRICE", explanation="e", confidence=0.9),
        PriceRecommendation(product_id=product_promo.id, action="LAUNCH_PROMO", explanation="e", confidence=0.8),
    ])
    memory_session.commit()
    result = pricing_recommendations(memory_session)
    # LAUNCH_PROMO should come first in the spoken sentence
    promo_idx = result["spoken"].find("Sku-Promo")
    hold_idx = result["spoken"].find("Sku-Hold")
    assert 0 <= promo_idx < hold_idx
    assert "launch a promo" in result["spoken"]


def test_describe_subscription_uses_all_fields() -> None:
    line = describe_subscription({
        "entity_type": "supplier",
        "entity_id": 7,
        "condition": "risk above 80",
        "channel": "sms",
        "contact": "+14151234567",
    })
    assert "+14151234567" in line
    assert "sms" in line
    assert "supplier 7" in line
    assert "risk above 80" in line


# ---------- HTTP endpoint tests ----------

def test_get_high_risk_suppliers(client: TestClient, memory_session: Session) -> None:
    _seed_two_suppliers(memory_session)
    response = client.get("/voice/high-risk-suppliers")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["count"] == 1
    assert "Acme" in body["spoken"]


def test_get_supplier_summary_200_and_404(client: TestClient, memory_session: Session) -> None:
    high, _ = _seed_two_suppliers(memory_session)
    response = client.get(f"/voice/supplier/{high.id}/summary")
    assert response.status_code == 200
    assert response.json()["data"]["score"] == 82
    assert client.get("/voice/supplier/9999/summary").status_code == 404


def test_get_pricing_recommendations(client: TestClient, memory_session: Session) -> None:
    product = Product(name="P", brand="b", category="c", target_price=10, target_margin=0.3)
    memory_session.add(product)
    memory_session.commit()
    memory_session.refresh(product)
    memory_session.add(PriceRecommendation(product_id=product.id, action="INVESTIGATE", explanation="e", confidence=0.4))
    memory_session.commit()
    body = client.get("/voice/pricing/recommendations").json()
    assert body["data"]["count"] == 1
    assert "investigate" in body["spoken"].lower()


def test_subscribe_alert_persists_to_redis(client: TestClient, fake_redis_context: RedisContext) -> None:
    response = client.post(
        "/voice/subscribe-alert",
        json={
            "entity_type": "supplier",
            "entity_id": 7,
            "condition": "risk score above 80",
            "channel": "sms",
            "contact": "+14151234567",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subscription_id"].startswith("sub_")
    assert "+14151234567" in body["spoken"]
    raw = fake_redis_context.client.lrange("voice:subscriptions", 0, -1)
    assert raw, "subscription was not persisted"
    entry = json.loads(raw[0])
    assert entry["entity_id"] == 7
    assert entry["condition"] == "risk score above 80"


def test_subscribe_alert_rejects_invalid_channel(client: TestClient) -> None:
    response = client.post(
        "/voice/subscribe-alert",
        json={"entity_type": "supplier", "condition": "risk", "channel": "carrier_pigeon", "contact": "a@b"},
    )
    assert response.status_code == 422


# ---------- Vapi envelope tests ----------

def test_parse_tool_calls_handles_both_envelope_shapes() -> None:
    # Flat top-level shape
    flat = {"toolCalls": [{"id": "c1", "function": {"name": "high_risk_suppliers", "arguments": "{}"}}]}
    calls = parse_tool_calls(flat)
    assert len(calls) == 1 and calls[0].name == "high_risk_suppliers"

    # Nested `message` envelope with JSON-string args
    nested = {
        "message": {
            "toolCalls": [
                {"id": "c2", "function": {"name": "supplier_summary", "arguments": '{"supplier_id": 5}'}},
            ],
        },
    }
    calls = parse_tool_calls(nested)
    assert calls[0].name == "supplier_summary"
    assert calls[0].arguments == {"supplier_id": 5}


def test_verify_signature_mock_mode_accepts_everything() -> None:
    settings = Settings(vapi_mock_mode=True, vapi_webhook_secret="sekret")
    assert verify_signature(None, b"anything", settings) is True


def test_verify_signature_production_mode_enforces_hmac() -> None:
    import hmac
    settings = Settings(vapi_mock_mode=False, vapi_webhook_secret="sekret")
    body = b'{"hi": 1}'
    good = hmac.new(b"sekret", body, "sha256").hexdigest()
    assert verify_signature(good, body, settings) is True
    assert verify_signature(f"sha256={good}", body, settings) is True
    assert verify_signature("deadbeef", body, settings) is False
    assert verify_signature(None, body, settings) is False


def test_webhook_dispatches_supplier_summary(client: TestClient, memory_session: Session) -> None:
    high, _ = _seed_two_suppliers(memory_session)
    payload = {
        "message": {
            "toolCalls": [
                {"id": "call_1", "function": {"name": "supplier_summary", "arguments": json.dumps({"supplier_id": high.id})}},
            ],
        },
    }
    response = client.post("/voice/webhook", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["toolCallId"] == "call_1"
    assert high.name in body["results"][0]["result"]


def test_webhook_reports_unknown_tool(client: TestClient) -> None:
    payload = {"toolCalls": [{"id": "c", "function": {"name": "make_coffee", "arguments": "{}"}}]}
    response = client.post("/voice/webhook", json=payload)
    assert response.status_code == 200
    assert "Unknown tool" in response.json()["results"][0]["result"]


def test_webhook_empty_payload_returns_empty_results(client: TestClient) -> None:
    response = client.post("/voice/webhook", json={})
    assert response.status_code == 200
    assert response.json() == {"results": []}
