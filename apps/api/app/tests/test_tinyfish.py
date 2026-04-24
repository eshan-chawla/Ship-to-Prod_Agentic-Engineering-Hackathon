import httpx
import pytest

from app.core.config import Settings
from app.integrations.tinyfish import (
    MockTinyFishProvider,
    TinyFishError,
    TinyFishProvider,
    get_tinyfish_provider,
)


def make_settings(**overrides: object) -> Settings:
    values = {
        "tinyfish_api_key": "test-key",
        "tinyfish_search_url": "https://api.search.tinyfish.ai",
        "tinyfish_fetch_url": "https://api.fetch.tinyfish.ai",
        "tinyfish_agent_url": "https://agent.tinyfish.ai/v1/automation/run",
        "tinyfish_timeout_seconds": 1,
        "tinyfish_max_retries": 1,
    }
    values.update(overrides)
    return Settings(**values)


def test_get_tinyfish_provider_uses_mock_without_key() -> None:
    provider = get_tinyfish_provider(make_settings(tinyfish_api_key=None))
    assert isinstance(provider, MockTinyFishProvider)


def test_search_web_calls_real_search_endpoint_and_normalizes_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "api.search.tinyfish.ai"
        assert request.headers["X-API-Key"] == "test-key"
        assert request.url.params["query"] == "supplier cyber risk"
        return httpx.Response(
            200,
            json={
                "query": "supplier cyber risk",
                "results": [
                    {
                        "position": 1,
                        "site_name": "News",
                        "title": "Supplier reports ransomware event",
                        "snippet": "Security patch and data exposure under review",
                        "url": "https://example.com/risk",
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TinyFishProvider(make_settings(), client=client)
    results = provider.search_web("supplier cyber risk")

    assert results[0]["url"] == "https://example.com/risk"
    assert results[0]["risk_factor"] == "cybersecurity"
    assert results[0]["raw_payload"]["site_name"] == "News"


def test_fetch_url_posts_urls_and_normalizes_page_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.host == "api.fetch.tinyfish.ai"
        assert request.headers["X-API-Key"] == "test-key"
        assert request.read() == b'{"urls":["https://example.com/page"],"format":"markdown"}'
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com/page",
                        "final_url": "https://example.com/page",
                        "title": "Supplier update",
                        "text": "# Supplier update\n\nPort delay reported.",
                    }
                ],
                "errors": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TinyFishProvider(make_settings(), client=client)
    page = provider.fetch_url("https://example.com/page")

    assert page["title"] == "Supplier update"
    assert "Port delay" in page["content"]
    assert page["raw_payload"]["errors"] == []


def test_browser_extract_uses_agent_run_and_normalizes_price_signal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert request.method == "POST"
        assert request.url.host == "agent.tinyfish.ai"
        assert '"goal":"Extract current price' in body
        assert '"output_schema"' in body
        return httpx.Response(
            200,
            json={
                "run_id": "run_123",
                "status": "completed",
                "result": {
                    "price": "$119.99",
                    "stock_status": "In stock",
                    "promo_signal": "Sale: save 10%",
                    "raw_text": "Product is in stock for $119.99 with sale pricing.",
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TinyFishProvider(make_settings(), client=client)
    extracted = provider.browser_extract(
        "https://shop.example/product",
        "Extract current price, stock status, and promotion or discount signals.",
    )

    assert extracted["price"] == 119.99
    assert extracted["stock_status"] == "in_stock"
    assert extracted["promo_signal"] == "discount"


def test_retry_on_retryable_status_then_success() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        return httpx.Response(200, json={"results": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TinyFishProvider(make_settings(tinyfish_max_retries=1), client=client)

    assert provider.search_web("test") == []
    assert calls == 2


def test_timeout_retries_are_reported_as_tinyfish_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connect timed out")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TinyFishProvider(make_settings(tinyfish_max_retries=1), client=client)

    with pytest.raises(TinyFishError) as exc:
        provider.search_web("test")

    assert "connect timed out" in str(exc.value)

