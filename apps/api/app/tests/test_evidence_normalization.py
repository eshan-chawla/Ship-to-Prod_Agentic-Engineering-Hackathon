from app.integrations.tinyfish import build_supplier_evidence_payload


def test_supplier_evidence_payload_is_concise_and_signal_focused() -> None:
    long_content = " ".join(
        [
            "Generic company boilerplate with no useful signal.",
            "The supplier disclosed cash flow pressure and a regulatory compliance review.",
            "A port delay and component shortage affected two distribution lanes.",
            "The company also mentioned a cybersecurity breach remediation plan.",
        ]
        * 25
    )

    payload = build_supplier_evidence_payload(
        {
            "title": "Supplier risk update",
            "url": "https://example.com/risk",
            "snippet": "Cash flow, compliance, port delay, and breach signals were reported.",
            "risk_factor": None,
            "raw_payload": {"source": "search"},
        },
        {
            "url": "https://example.com/risk",
            "title": "Supplier risk update",
            "content": long_content,
            "raw_payload": {"source": "fetch"},
        },
    )

    assert len(payload["content"]) <= 700
    assert "cash flow" in payload["content"].lower()
    assert "port delay" in payload["content"].lower()
    assert payload["raw_payload"]["full_content_chars"] > len(payload["content"])
