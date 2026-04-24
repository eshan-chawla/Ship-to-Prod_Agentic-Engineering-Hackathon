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


# Pricing actions. UPPER_SNAKE_CASE enum so API / UI can branch deterministically.
ACTION_HOLD_PRICE = "HOLD_PRICE"
ACTION_LOWER_PRICE = "LOWER_PRICE"
ACTION_RAISE_PRICE = "RAISE_PRICE"
ACTION_LAUNCH_PROMO = "LAUNCH_PROMO"
ACTION_INVESTIGATE = "INVESTIGATE"

PRICING_ACTIONS = {
    ACTION_HOLD_PRICE,
    ACTION_LOWER_PRICE,
    ACTION_RAISE_PRICE,
    ACTION_LAUNCH_PROMO,
    ACTION_INVESTIGATE,
}


def keyword_matches(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def score_risk_evidence(evidence: list[dict[str, Any]], criticality: str = "medium") -> dict[str, Any]:
    """Deterministic supplier risk score.

    Each `evidence` item is expected to contain:
      - title / content / snippet — text scanned for factor keywords
      - risk_factor — an optional hinted primary factor (adds a small boost)
      - id — optional EvidenceItem.id; recorded in per-factor evidence_ids
    """
    factor_scores: dict[str, int] = dict.fromkeys(RISK_FACTORS, 0)
    factor_hits: dict[str, int] = dict.fromkeys(RISK_FACTORS, 0)
    factor_evidence_ids: dict[str, list[int]] = {factor: [] for factor in RISK_FACTORS}

    for item in evidence:
        text = f"{item.get('title', '')} {item.get('content', '')} {item.get('snippet', '')}".lower()
        hinted_factor = item.get("risk_factor") if item.get("risk_factor") in factor_scores else None
        evidence_id = item.get("id")
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
                if isinstance(evidence_id, int) and evidence_id not in factor_evidence_ids[factor]:
                    factor_evidence_ids[factor].append(evidence_id)

    criticality_multiplier = {"low": 0.85, "medium": 1.0, "high": 1.15, "critical": 1.3}.get(criticality, 1.0)
    non_zero = [value for value in factor_scores.values() if value > 0] or [0]
    blended = (mean(non_zero) * 0.65) + (max(factor_scores.values()) * 0.35)
    total = int(max(0, min(100, round(blended * criticality_multiplier))))

    factor_details: dict[str, dict[str, Any]] = {}
    for factor in RISK_FACTORS:
        hits = factor_hits[factor]
        factor_details[factor] = {
            "score": factor_scores[factor],
            "confidence": round(min(1.0, hits / 3.0), 2),
            "evidence_ids": list(factor_evidence_ids[factor]),
        }

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
    return {
        "score": total,
        "factors": factor_scores,
        "factor_hits": factor_hits,
        "factor_details": factor_details,
        "explanation": explanation,
    }


def _trend_direction(trend: list[float] | None) -> str:
    if not trend or len(trend) < 2:
        return "flat"
    first, last = float(trend[0]), float(trend[-1])
    if first <= 0:
        return "flat"
    delta = (last - first) / first
    if delta > 0.05:
        return "up"
    if delta < -0.05:
        return "down"
    return "flat"


def _impact_line(action: str, *, gap_dollars: float, promo_count: int, margin: float) -> str:
    if action == ACTION_HOLD_PRICE:
        return f"Preserve current margin ~{int(margin * 100)}%; no action needed."
    if action == ACTION_LOWER_PRICE:
        return f"Close the ${abs(gap_dollars):.2f} gap to stabilize conversion and protect share."
    if action == ACTION_RAISE_PRICE:
        return f"Capture ${abs(gap_dollars):.2f} premium; monitor unit velocity for softness."
    if action == ACTION_LAUNCH_PROMO:
        return f"Match {promo_count} competitor promo signal(s); expect short-term volume lift."
    return "Data insufficient or signals conflict; human review recommended before acting."


def recommend_price(
    target_price: float,
    target_margin: float,
    observations: list[dict[str, Any]],
    trend: list[float] | None = None,
) -> dict[str, Any]:
    """Deterministic pricing recommendation.

    Inputs:
      - target_price  — our list price
      - target_margin — our target margin (0..1)
      - observations  — competitor price observations with stock_status + promo_signal
      - trend         — optional chronological list of our recent prices

    Output keys: action (UPPER_SNAKE), confidence (0..1), expected_impact, explanation.
    """
    if not observations:
        return {
            "action": ACTION_INVESTIGATE,
            "confidence": 0.3,
            "expected_impact": _impact_line(ACTION_INVESTIGATE, gap_dollars=0.0, promo_count=0, margin=target_margin),
            "explanation": "No competitor observations were available. Investigate data sources before pricing decisions.",
        }

    active = [obs for obs in observations if obs.get("stock_status") == "in_stock"]
    comparison_set = active or observations
    avg_competitor = mean([float(obs["price"]) for obs in comparison_set])
    promo_count = sum(1 for obs in comparison_set if obs.get("promo_signal") and obs.get("promo_signal") != "none")
    gap = (target_price - avg_competitor) / target_price if target_price else 0.0
    gap_dollars = target_price - avg_competitor
    direction = _trend_direction(trend)

    if gap > 0.08 and promo_count:
        action = ACTION_LAUNCH_PROMO
    elif gap > 0.08:
        action = ACTION_LOWER_PRICE
    elif gap < -0.1 and target_margin >= 0.25:
        action = ACTION_RAISE_PRICE
    else:
        action = ACTION_HOLD_PRICE

    conflict = (action == ACTION_LOWER_PRICE and direction == "up") or (
        action == ACTION_RAISE_PRICE and direction == "down"
    )
    thin_data = len(comparison_set) < 2 and action != ACTION_HOLD_PRICE
    if conflict or thin_data:
        action = ACTION_INVESTIGATE

    confidence = min(0.92, 0.55 + (len(comparison_set) * 0.08))
    if action == ACTION_INVESTIGATE:
        confidence = min(confidence, 0.5)

    trend_clause = f" Historical trend: {direction}." if trend else ""
    explanation = (
        f"Target price ${target_price:.2f} vs average competitor price ${avg_competitor:.2f}. "
        f"{promo_count} competitor promo signals across {len(comparison_set)} usable listings."
        f"{trend_clause}"
    )
    return {
        "action": action,
        "confidence": round(confidence, 2),
        "expected_impact": _impact_line(action, gap_dollars=gap_dollars, promo_count=promo_count, margin=target_margin),
        "explanation": explanation,
    }
