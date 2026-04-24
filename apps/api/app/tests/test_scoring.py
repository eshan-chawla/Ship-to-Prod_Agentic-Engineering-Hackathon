from app.services.scoring import (
    ACTION_HOLD_PRICE,
    ACTION_INVESTIGATE,
    ACTION_LAUNCH_PROMO,
    ACTION_LOWER_PRICE,
    ACTION_RAISE_PRICE,
    PRICING_ACTIONS,
    recommend_price,
    score_risk_evidence,
)


# ---------- Supplier risk ----------

def test_supplier_scoring_is_deterministic_and_bounded() -> None:
    evidence = [
        {"title": "Debt pressure", "content": "cash flow concerns and component shortage", "risk_factor": "financial_stress"},
        {"title": "Ransomware precaution", "content": "security patch and data exposure", "risk_factor": "cybersecurity"},
    ]
    result = score_risk_evidence(evidence, criticality="critical")
    assert 0 <= result["score"] <= 100
    assert result["score"] >= 40
    assert "financial_stress" in result["factors"]


def test_supplier_scoring_scores_multiple_factors_from_same_evidence() -> None:
    evidence = [
        {
            "title": "Supplier update",
            "content": "Cash flow pressure, regulatory compliance review, port delay, and tariff risk were all reported.",
            "snippet": "Supplier has multiple risk signals.",
            "risk_factor": "financial_stress",
        }
    ]

    result = score_risk_evidence(evidence, criticality="high")

    assert result["factors"]["financial_stress"] > 0
    assert result["factors"]["legal_regulatory"] > 0
    assert result["factors"]["delivery_disruption"] > 0
    assert result["factors"]["geopolitical"] > 0
    assert "Top contributing factors" in result["explanation"]


def test_supplier_scoring_exposes_per_factor_confidence_and_evidence_ids() -> None:
    evidence = [
        {"id": 101, "title": "Debt and cash flow", "content": "debt servicing and cash flow issues", "risk_factor": "financial_stress"},
        {"id": 102, "title": "Downgrade notice", "content": "Credit downgrade and bankruptcy rumor", "risk_factor": "financial_stress"},
        {"id": 103, "title": "Ransomware", "content": "ransomware incident with data exposure", "risk_factor": "cybersecurity"},
    ]
    result = score_risk_evidence(evidence, criticality="high")

    details = result["factor_details"]
    assert set(details.keys()) == {
        "financial_stress", "legal_regulatory", "delivery_disruption",
        "sentiment", "cybersecurity", "geopolitical",
    }
    # Two hits on financial_stress → confidence ~0.67
    assert details["financial_stress"]["confidence"] == 0.67
    assert set(details["financial_stress"]["evidence_ids"]) == {101, 102}
    assert details["cybersecurity"]["evidence_ids"] == [103]
    # Confidence is bounded
    for factor in details.values():
        assert 0.0 <= factor["confidence"] <= 1.0


def test_supplier_scoring_without_evidence_returns_zero_score() -> None:
    result = score_risk_evidence([], criticality="medium")
    assert result["score"] == 0
    assert all(f["score"] == 0 for f in result["factor_details"].values())
    assert all(f["confidence"] == 0.0 for f in result["factor_details"].values())


# ---------- Pricing ----------

def test_pricing_launch_promo_when_competitors_discount_below_target() -> None:
    result = recommend_price(
        100,
        0.3,
        [
            {"price": 88, "stock_status": "in_stock", "promo_signal": "discount"},
            {"price": 91, "stock_status": "in_stock", "promo_signal": "none"},
        ],
    )
    assert result["action"] == ACTION_LAUNCH_PROMO
    assert result["confidence"] > 0.6
    assert "competitor promo" in result["expected_impact"].lower() or "competitor promo signal" in result["expected_impact"].lower()


def test_pricing_lower_price_when_gap_exists_without_promos() -> None:
    result = recommend_price(
        100,
        0.3,
        [
            {"price": 85, "stock_status": "in_stock", "promo_signal": "none"},
            {"price": 88, "stock_status": "in_stock", "promo_signal": "none"},
        ],
    )
    assert result["action"] == ACTION_LOWER_PRICE
    assert "gap" in result["expected_impact"].lower()


def test_pricing_raise_price_when_competitors_are_far_above_and_margin_healthy() -> None:
    result = recommend_price(
        100,
        0.3,
        [
            {"price": 118, "stock_status": "in_stock", "promo_signal": "none"},
            {"price": 122, "stock_status": "in_stock", "promo_signal": "none"},
        ],
    )
    assert result["action"] == ACTION_RAISE_PRICE
    assert "premium" in result["expected_impact"].lower()


def test_pricing_hold_price_when_gap_is_small() -> None:
    result = recommend_price(
        100,
        0.3,
        [
            {"price": 99, "stock_status": "in_stock", "promo_signal": "none"},
            {"price": 101, "stock_status": "in_stock", "promo_signal": "none"},
        ],
    )
    assert result["action"] == ACTION_HOLD_PRICE
    assert "preserve" in result["expected_impact"].lower()


def test_pricing_investigates_when_observations_are_empty() -> None:
    result = recommend_price(100, 0.3, [])
    assert result["action"] == ACTION_INVESTIGATE
    assert result["confidence"] <= 0.5


def test_pricing_investigates_when_trend_conflicts_with_gap_signal() -> None:
    # gap says LOWER_PRICE, but our historical trend is rising — conflict → INVESTIGATE
    result = recommend_price(
        100,
        0.3,
        [
            {"price": 85, "stock_status": "in_stock", "promo_signal": "none"},
            {"price": 88, "stock_status": "in_stock", "promo_signal": "none"},
        ],
        trend=[90.0, 95.0, 100.0],
    )
    assert result["action"] == ACTION_INVESTIGATE
    assert "Historical trend: up" in result["explanation"]


def test_pricing_action_is_always_one_of_the_enum_values() -> None:
    scenarios = [
        (100, 0.3, []),
        (100, 0.3, [{"price": 85, "stock_status": "in_stock", "promo_signal": "none"}]),
        (100, 0.3, [{"price": 150, "stock_status": "in_stock", "promo_signal": "none"}]),
    ]
    for target, margin, obs in scenarios:
        assert recommend_price(target, margin, obs)["action"] in PRICING_ACTIONS


def test_pricing_returns_all_required_fields() -> None:
    result = recommend_price(
        100,
        0.3,
        [{"price": 99, "stock_status": "in_stock", "promo_signal": "none"}],
    )
    assert set(result.keys()) >= {"action", "confidence", "expected_impact", "explanation"}
    assert 0.0 <= result["confidence"] <= 1.0
