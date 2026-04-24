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
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "country": supplier.country,
            "criticality": supplier.criticality,
        },
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
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "target_price": product.target_price,
            "target_margin": product.target_margin,
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
