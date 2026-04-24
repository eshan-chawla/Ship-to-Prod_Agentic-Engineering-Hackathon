from datetime import datetime, timezone

import fakeredis
from sqlmodel import Session, SQLModel, create_engine

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
    session.add(
        SupplierRiskScore(
            supplier_id=supplier.id,
            scan_id=scan.id,
            score=80,
            financial_stress=40,
            legal_regulatory=10,
            delivery_disruption=30,
            sentiment=0,
            cybersecurity=0,
            geopolitical=0,
            explanation="high",
        )
    )
    session.add(
        EvidenceItem(
            entity_type="supplier",
            entity_id=supplier.id,
            source_url="https://e/1",
            source_title="news",
            content="cash crunch",
            evidence_type="risk_signal",
            risk_factor="financial_stress",
        )
    )
    session.add(
        Alert(
            entity_type="supplier",
            entity_id=supplier.id,
            severity="high",
            title="threshold",
            message="over 80",
        )
    )
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
    session.add(
        PriceRecommendation(product_id=product.id, action="launch promo", explanation="e", confidence=0.8)
    )
    session.add(
        EvidenceItem(
            entity_type="product",
            entity_id=product.id,
            source_url="https://s/1",
            source_title="comp",
            content="$88",
            evidence_type="price_signal",
        )
    )
    session.commit()

    ctx = _ctx()
    ctx.memory.record_product(product.id, {"recommendation": "launch promo", "confidence": 0.8})

    bundle = build_product_context(session, product.id, ctx)
    assert bundle["product"]["name"] == "Sku"
    assert bundle["latest_recommendation"]["action"] == "launch promo"
    assert len(bundle["evidence"]) == 1
    assert bundle["memory"][0]["recommendation"] == "launch promo"


def test_missing_entities_return_none() -> None:
    session = _session()
    ctx = _ctx()
    assert build_supplier_context(session, 999, ctx) is None
    assert build_product_context(session, 999, ctx) is None
