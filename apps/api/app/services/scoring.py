from __future__ import annotations

from statistics import mean
from typing import Any

RISK_FACTORS = [
    "financial_stress",
    "legal_regulatory",
    "delivery_disruption",
    "sentiment",
    "cybersecurity",
    "geopolitical",
]

KEYWORD_WEIGHTS = {
    "debt": 15,
    "cash flow": 14,
    "downgrade": 16,
    "regulatory": 13,
    "compliance": 10,
    "lawsuit": 15,
    "delay": 12,
    "shortage": 14,
    "slowdown": 11,
    "complaints": 8,
    "negative": 9,
    "labor dispute": 12,
    "ransomware": 18,
    "data exposure": 17,
    "security": 8,
    "tariff": 11,
    "border": 10,
    "instability": 15,
}


def score_risk_evidence(evidence: list[dict[str, Any]], criticality: str = "medium") -> dict[str, Any]:
    factor_scores = dict.fromkeys(RISK_FACTORS, 0)
    for item in evidence:
        text = f"{item.get('title', '')} {item.get('content', '')} {item.get('snippet', '')}".lower()
        factor = item.get("risk_factor") if item.get("risk_factor") in factor_scores else "sentiment"
        score = 5
        for keyword, weight in KEYWORD_WEIGHTS.items():
            if keyword in text:
                score += weight
        factor_scores[factor] = min(100, factor_scores[factor] + score)

    criticality_multiplier = {"low": 0.85, "medium": 1.0, "high": 1.15, "critical": 1.3}.get(criticality, 1.0)
    non_zero = [value for value in factor_scores.values() if value > 0] or [0]
    blended = (mean(non_zero) * 0.65) + (max(factor_scores.values()) * 0.35)
    total = int(max(0, min(100, round(blended * criticality_multiplier))))
    top_factor = max(factor_scores, key=lambda key: factor_scores[key])
    explanation = (
        f"Risk score {total}/100 is driven primarily by {top_factor.replace('_', ' ')}. "
        f"The deterministic MVP formula blends average factor intensity, highest factor severity, and supplier criticality."
    )
    return {"score": total, "factors": factor_scores, "explanation": explanation}


def recommend_price(target_price: float, target_margin: float, observations: list[dict[str, Any]]) -> dict[str, Any]:
    if not observations:
        return {
            "action": "hold price",
            "confidence": 0.45,
            "explanation": "No competitor observations were available, so the safest MVP recommendation is to hold price.",
        }

    active = [obs for obs in observations if obs.get("stock_status") == "in_stock"]
    comparison_set = active or observations
    avg_competitor = mean([float(obs["price"]) for obs in comparison_set])
    promo_count = sum(1 for obs in comparison_set if obs.get("promo_signal") != "none")
    gap = (target_price - avg_competitor) / target_price

    if gap > 0.08 and promo_count:
        action = "launch promo"
    elif gap > 0.08:
        action = "lower price"
    elif gap < -0.1 and target_margin >= 0.25:
        action = "raise price"
    else:
        action = "hold price"

    explanation = (
        f"Target price ${target_price:.2f} compared with average competitor price ${avg_competitor:.2f}. "
        f"{promo_count} competitor promo signals were observed across {len(comparison_set)} usable listings."
    )
    confidence = min(0.92, 0.55 + (len(comparison_set) * 0.08))
    return {"action": action, "confidence": round(confidence, 2), "explanation": explanation}

