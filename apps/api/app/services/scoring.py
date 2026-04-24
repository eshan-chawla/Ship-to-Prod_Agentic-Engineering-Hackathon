from __future__ import annotations

import re
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

FACTOR_KEYWORD_WEIGHTS = {
    "financial_stress": {
        "debt": 14,
        "cash flow": 14,
        "downgrade": 16,
        "bankruptcy": 18,
        "insolvency": 18,
        "liquidity": 10,
    },
    "legal_regulatory": {
        "regulatory": 13,
        "compliance": 10,
        "lawsuit": 15,
        "sanction": 18,
        "consent order": 14,
        "recall": 12,
    },
    "delivery_disruption": {
        "delay": 12,
        "shortage": 14,
        "slowdown": 11,
        "strike": 14,
        "shutdown": 15,
        "port": 8,
        "disruption": 10,
    },
    "sentiment": {
        "complaint": 8,
        "complaints": 8,
        "negative": 9,
        "boycott": 12,
        "controversy": 8,
        "labor dispute": 12,
    },
    "cybersecurity": {
        "ransomware": 18,
        "breach": 16,
        "data exposure": 17,
        "cyber": 12,
        "security patch": 11,
    },
    "geopolitical": {
        "tariff": 11,
        "border": 10,
        "war": 16,
        "instability": 15,
        "export control": 14,
        "trade restriction": 14,
    },
}


def score_risk_evidence(evidence: list[dict[str, Any]], criticality: str = "medium") -> dict[str, Any]:
    factor_scores = dict.fromkeys(RISK_FACTORS, 0)
    factor_hits = dict.fromkeys(RISK_FACTORS, 0)
    for item in evidence:
        text = f"{item.get('title', '')} {item.get('content', '')} {item.get('snippet', '')}".lower()
        hinted_factor = item.get("risk_factor") if item.get("risk_factor") in factor_scores else None
        for factor in RISK_FACTORS:
            score = 0
            for keyword, weight in FACTOR_KEYWORD_WEIGHTS[factor].items():
                if keyword_matches(text, keyword):
                    score += weight
            if factor == hinted_factor:
                score += 8
            if score > 0:
                factor_hits[factor] += 1
                factor_scores[factor] = min(100, factor_scores[factor] + min(score, 35))

    criticality_multiplier = {"low": 0.85, "medium": 1.0, "high": 1.15, "critical": 1.3}.get(criticality, 1.0)
    non_zero = [value for value in factor_scores.values() if value > 0] or [0]
    blended = (mean(non_zero) * 0.65) + (max(factor_scores.values()) * 0.35)
    total = int(max(0, min(100, round(blended * criticality_multiplier))))
    ranked_factors = sorted(
        [(factor, score) for factor, score in factor_scores.items() if score > 0],
        key=lambda pair: pair[1],
        reverse=True,
    )
    top_factor = ranked_factors[0][0] if ranked_factors else "sentiment"
    factor_summary = ", ".join(f"{factor.replace('_', ' ')} {score}" for factor, score in ranked_factors[:3])
    explanation = (
        f"Risk score {total}/100 is driven primarily by {top_factor.replace('_', ' ')}. "
        f"Top contributing factors: {factor_summary or 'no material signals'}. "
        f"Scores reflect keyword evidence across all factors, not only the source's primary category."
    )
    return {"score": total, "factors": factor_scores, "factor_hits": factor_hits, "explanation": explanation}


def keyword_matches(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


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
