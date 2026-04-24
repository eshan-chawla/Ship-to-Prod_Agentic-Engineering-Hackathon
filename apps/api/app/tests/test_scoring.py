from app.services.scoring import recommend_price, score_risk_evidence


def test_supplier_scoring_is_deterministic_and_bounded() -> None:
    evidence = [
        {"title": "Debt pressure", "content": "cash flow concerns and component shortage", "risk_factor": "financial_stress"},
        {"title": "Ransomware precaution", "content": "security patch and data exposure", "risk_factor": "cybersecurity"},
    ]
    result = score_risk_evidence(evidence, criticality="critical")
    assert 0 <= result["score"] <= 100
    assert result["score"] >= 40
    assert "financial_stress" in result["factors"]


def test_pricing_recommends_promo_when_competitors_discount_below_target() -> None:
    result = recommend_price(
        100,
        0.3,
        [
            {"price": 88, "stock_status": "in_stock", "promo_signal": "discount"},
            {"price": 91, "stock_status": "in_stock", "promo_signal": "none"},
        ],
    )
    assert result["action"] == "launch promo"
    assert result["confidence"] > 0.6

