from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Any
import httpx

from app.core.config import Settings, get_settings


class TinyFishProviderInterface(ABC):
    @abstractmethod
    def search_web(self, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_url(self, url: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def browser_extract(self, url: str, task: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def run_agent(self, task: str) -> dict[str, Any]:
        raise NotImplementedError


class TinyFishProvider(TinyFishProviderInterface):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = httpx.Client(
            base_url=self.settings.tinyfish_base_url,
            headers={"Authorization": f"Bearer {self.settings.tinyfish_api_key}"},
            timeout=20,
        )

    def search_web(self, query: str) -> list[dict[str, Any]]:
        response = self.client.post("/search", json={"query": query})
        response.raise_for_status()
        return response.json().get("results", [])

    def fetch_url(self, url: str) -> dict[str, Any]:
        response = self.client.post("/fetch", json={"url": url})
        response.raise_for_status()
        return response.json()

    def browser_extract(self, url: str, task: str) -> dict[str, Any]:
        response = self.client.post("/browser/extract", json={"url": url, "task": task})
        response.raise_for_status()
        return response.json()

    def run_agent(self, task: str) -> dict[str, Any]:
        response = self.client.post("/agent/run", json={"task": task})
        response.raise_for_status()
        return response.json()


class MockTinyFishProvider(TinyFishProviderInterface):
    risk_terms = {
        "financial_stress": ["debt pressure", "cash flow concerns", "credit downgrade"],
        "legal_regulatory": ["regulatory review", "import compliance", "consent order"],
        "delivery_disruption": ["port delay", "factory slowdown", "component shortage"],
        "sentiment": ["customer complaints", "negative press", "labor dispute"],
        "cybersecurity": ["ransomware precaution", "data exposure", "security patch"],
        "geopolitical": ["tariff risk", "border inspection", "regional instability"],
    }

    def _seed(self, value: str) -> int:
        return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)

    def search_web(self, query: str) -> list[dict[str, Any]]:
        seed = self._seed(query)
        factors = list(self.risk_terms.keys())
        return [
            {
                "title": f"{query} signal brief {i + 1}",
                "url": f"https://mock.tinyfish.local/evidence/{seed % 997}/{i + 1}",
                "snippet": f"Mock source reports {self.risk_terms[factors[(seed + i) % len(factors)]][0]} related to {query}.",
                "risk_factor": factors[(seed + i) % len(factors)],
            }
            for i in range(4)
        ]

    def fetch_url(self, url: str) -> dict[str, Any]:
        seed = self._seed(url)
        return {
            "url": url,
            "title": f"Fetched source {seed % 1000}",
            "content": f"Mock fetched content for {url}. It includes operational signals, market context, and timestamped evidence.",
        }

    def browser_extract(self, url: str, task: str) -> dict[str, Any]:
        seed = self._seed(url + task)
        price = round(25 + (seed % 9000) / 100, 2)
        promo = "discount" if seed % 3 == 0 else "none"
        stock = "out_of_stock" if seed % 11 == 0 else "in_stock"
        return {
            "url": url,
            "task": task,
            "price": price,
            "stock_status": stock,
            "promo_signal": promo,
            "raw_text": f"Mock extraction found price {price}, stock {stock}, promo {promo}.",
        }

    def run_agent(self, task: str) -> dict[str, Any]:
        return {"task": task, "summary": "Mock TinyFish agent completed deterministic analysis."}


def get_tinyfish_provider(settings: Settings | None = None) -> TinyFishProviderInterface:
    settings = settings or get_settings()
    if settings.tinyfish_api_key:
        return TinyFishProvider(settings)
    return MockTinyFishProvider()

