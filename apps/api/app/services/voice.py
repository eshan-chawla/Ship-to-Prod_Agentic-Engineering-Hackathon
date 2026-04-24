"""Voice-assistant data fetchers + concise spoken-text formatters.

Design rule: responses are short enough for a call. Top 3 items, rounded
numbers, short clauses. Each fetcher returns a dict with `spoken` (what Vapi
reads aloud) and `data` (structured backup for clients that want JSON).
"""
from __future__ import annotations

from typing import Any
from sqlalchemy import desc
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.entities import (
    Alert,
    PriceRecommendation,
    Product,
    Supplier,
    SupplierRiskScore,
)
from app.services.scoring import (
    ACTION_INVESTIGATE,
    ACTION_LAUNCH_PROMO,
    ACTION_LOWER_PRICE,
    ACTION_RAISE_PRICE,
)

VOICE_TOP_N = 3


def _friendly_factor(name: str) -> str:
    return name.replace("_", " ")


def _action_phrase(action: str) -> str:
    return {
        "HOLD_PRICE": "hold price",
        "LOWER_PRICE": "lower price",
        "RAISE_PRICE": "raise price",
        ACTION_LAUNCH_PROMO: "launch a promo",
        ACTION_INVESTIGATE: "investigate further",
    }.get(action, action.lower().replace("_", " "))


def high_risk_suppliers(session: Session) -> dict[str, Any]:
    """Suppliers whose latest risk score meets the alert threshold."""
    threshold = get_settings().risk_alert_threshold

    # Latest risk score per supplier
    latest_rows = session.exec(
        select(SupplierRiskScore).order_by(desc(SupplierRiskScore.created_at))
    ).all()
    latest_per_supplier: dict[int, SupplierRiskScore] = {}
    for row in latest_rows:
        latest_per_supplier.setdefault(row.supplier_id, row)

    hits = sorted(
        [row for row in latest_per_supplier.values() if row.score >= threshold],
        key=lambda r: r.score,
        reverse=True,
    )[:VOICE_TOP_N]

    if not hits:
        return {
            "spoken": "No suppliers are above the risk threshold right now. Good news.",
            "count": 0,
            "suppliers": [],
        }

    entries = []
    for row in hits:
        supplier = session.get(Supplier, row.supplier_id)
        if not supplier:
            continue
        top_factor = _top_factor(row)
        entries.append({
            "supplier_id": supplier.id,
            "name": supplier.name,
            "score": row.score,
            "top_factor": top_factor,
        })

    if len(entries) == 1:
        e = entries[0]
        spoken = f"One supplier is above threshold. {e['name']} at {e['score']} out of 100, driven by {_friendly_factor(e['top_factor'])}."
    else:
        head = entries[0]
        rest = ", ".join(f"{e['name']} at {e['score']}" for e in entries[1:])
        spoken = (
            f"{len(entries)} suppliers are above threshold. "
            f"Top is {head['name']} at {head['score']} out of 100, driven by {_friendly_factor(head['top_factor'])}. "
            f"Next: {rest}."
        )
    return {"spoken": spoken, "count": len(entries), "suppliers": entries}


def supplier_summary(session: Session, supplier_id: int) -> dict[str, Any] | None:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        return None

    scores = session.exec(
        select(SupplierRiskScore)
        .where(SupplierRiskScore.supplier_id == supplier_id)
        .order_by(desc(SupplierRiskScore.created_at))
        .limit(2)
    ).all()
    if not scores:
        return {
            "spoken": f"{supplier.name} has not been scanned yet. No risk data available.",
            "supplier_id": supplier.id,
            "score": None,
        }

    latest = scores[0]
    previous = scores[1] if len(scores) > 1 else None
    delta = latest.score - previous.score if previous else None
    top = _top_factor(latest)

    open_alerts = session.exec(
        select(Alert)
        .where(
            Alert.entity_type == "supplier",
            Alert.entity_id == supplier_id,
            Alert.acknowledged_at.is_(None),
        )
    ).all()

    trend_clause = ""
    if delta is not None:
        direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        if direction == "flat":
            trend_clause = " Unchanged from the previous scan."
        else:
            trend_clause = f" That's {direction} {abs(delta)} points from the previous scan."

    factor_clause = f" Top driver: {_friendly_factor(top)}." if top else ""
    alert_clause = f" {len(open_alerts)} open alert{'s' if len(open_alerts) != 1 else ''}." if open_alerts else ""

    spoken = (
        f"{supplier.name} scored {latest.score} out of 100.{trend_clause}{factor_clause}{alert_clause}"
    )
    return {
        "spoken": spoken,
        "supplier_id": supplier.id,
        "name": supplier.name,
        "score": latest.score,
        "previous_score": previous.score if previous else None,
        "top_factor": top,
        "open_alerts": len(open_alerts),
    }


def pricing_recommendations(session: Session) -> dict[str, Any]:
    """Latest recommendation per product."""
    recs = session.exec(
        select(PriceRecommendation).order_by(desc(PriceRecommendation.created_at))
    ).all()
    latest_per_product: dict[int, PriceRecommendation] = {}
    for rec in recs:
        latest_per_product.setdefault(rec.product_id, rec)

    # Priority order: LAUNCH_PROMO / LOWER_PRICE / RAISE_PRICE first, then others
    priority = {
        ACTION_LAUNCH_PROMO: 0,
        ACTION_LOWER_PRICE: 1,
        ACTION_RAISE_PRICE: 2,
        ACTION_INVESTIGATE: 3,
        "HOLD_PRICE": 4,
    }
    sorted_recs = sorted(
        latest_per_product.values(),
        key=lambda r: (priority.get(r.action, 99), -r.confidence),
    )[:VOICE_TOP_N]

    if not sorted_recs:
        return {
            "spoken": "No pricing recommendations yet. Run a price scan to generate one.",
            "count": 0,
            "recommendations": [],
        }

    entries = []
    for rec in sorted_recs:
        product = session.get(Product, rec.product_id)
        if not product:
            continue
        entries.append({
            "product_id": product.id,
            "name": product.name,
            "action": rec.action,
            "action_phrase": _action_phrase(rec.action),
            "confidence": rec.confidence,
        })

    if len(entries) == 1:
        e = entries[0]
        spoken = f"One recommendation. {e['name']}: {e['action_phrase']}. Confidence {int(e['confidence'] * 100)}%."
    else:
        parts = [f"{e['name']}: {e['action_phrase']}" for e in entries]
        spoken = f"{len(entries)} pricing calls today. " + ". ".join(parts) + "."
    return {"spoken": spoken, "count": len(entries), "recommendations": entries}


def _top_factor(score: SupplierRiskScore) -> str:
    values = {
        "financial_stress": score.financial_stress,
        "legal_regulatory": score.legal_regulatory,
        "delivery_disruption": score.delivery_disruption,
        "sentiment": score.sentiment,
        "cybersecurity": score.cybersecurity,
        "geopolitical": score.geopolitical,
    }
    top = max(values, key=values.get)
    return top if values[top] > 0 else ""


def describe_subscription(subscription: dict[str, Any]) -> str:
    entity = subscription.get("entity_type", "item")
    entity_id = subscription.get("entity_id")
    condition = subscription.get("condition", "any signal")
    channel = subscription.get("channel", "voice")
    contact = subscription.get("contact", "on file")
    target = f"{entity} {entity_id}" if entity_id else entity
    return f"Got it. I'll notify {contact} by {channel} when {target} matches: {condition}."
