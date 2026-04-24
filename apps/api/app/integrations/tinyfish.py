from __future__ import annotations

import hashlib
import re
import time
from abc import ABC, abstractmethod
from typing import Any
import httpx
import structlog

from app.core.config import Settings, get_settings

log = structlog.get_logger()

RISK_KEYWORDS = {
    "financial_stress": ["debt", "cash flow", "credit", "downgrade", "bankruptcy", "insolvency"],
    "legal_regulatory": ["lawsuit", "regulatory", "compliance", "sanction", "consent order", "recall"],
    "delivery_disruption": ["delay", "shortage", "port", "strike", "shutdown", "slowdown", "disruption"],
    "sentiment": ["complaint", "negative", "boycott", "controversy", "labor dispute"],
    "cybersecurity": ["ransomware", "breach", "data exposure", "cyber", "security patch"],
    "geopolitical": ["tariff", "border", "war", "instability", "export control", "trade restriction"],
}

MAX_EVIDENCE_CHARS = 700


class TinyFishError(RuntimeError):
    def __init__(self, operation: str, message: str, status_code: int | None = None) -> None:
        self.operation = operation
        self.status_code = status_code
        super().__init__(f"TinyFish {operation} failed: {message}")


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
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.tinyfish_api_key:
            raise TinyFishError("configure", "TINYFISH_API_KEY is required for the real provider")
        self.client = client or httpx.Client(timeout=self.settings.tinyfish_timeout_seconds)
        self.headers = {
            "X-API-Key": self.settings.tinyfish_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request_json(
        self,
        operation: str,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempts = self.settings.tinyfish_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                response = self.client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=self.headers,
                    timeout=self.settings.tinyfish_timeout_seconds,
                )
                elapsed_ms = round((time.monotonic() - started) * 1000, 2)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < attempts:
                        log.warning(
                            "tinyfish_retryable_status",
                            operation=operation,
                            status_code=response.status_code,
                            attempt=attempt,
                            elapsed_ms=elapsed_ms,
                        )
                        time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))
                        continue
                response.raise_for_status()
                payload = response.json()
                log.info(
                    "tinyfish_request_succeeded",
                    operation=operation,
                    status_code=response.status_code,
                    attempt=attempt,
                    elapsed_ms=elapsed_ms,
                )
                return payload if isinstance(payload, dict) else {"value": payload}
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                log.warning(
                    "tinyfish_transport_retry",
                    operation=operation,
                    attempt=attempt,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                if attempt < attempts:
                    time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))
                    continue
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                body = exc.response.text[:500]
                log.error(
                    "tinyfish_http_error",
                    operation=operation,
                    status_code=status_code,
                    body=body,
                )
                raise TinyFishError(operation, body or exc.response.reason_phrase, status_code=status_code) from exc
            except ValueError as exc:
                log.error("tinyfish_invalid_json", operation=operation, error=str(exc))
                raise TinyFishError(operation, "response was not valid JSON") from exc

        message = str(last_error) if last_error else "retry budget exhausted"
        log.error("tinyfish_request_failed", operation=operation, attempts=attempts, error=message)
        raise TinyFishError(operation, message)

    def search_web(self, query: str) -> list[dict[str, Any]]:
        payload = self._request_json(
            "search_web",
            "GET",
            self.settings.tinyfish_search_url,
            params={"query": query},
        )
        return normalize_search_results(payload, query)

    def fetch_url(self, url: str) -> dict[str, Any]:
        payload = self._request_json(
            "fetch_url",
            "POST",
            self.settings.tinyfish_fetch_url,
            json_body={"urls": [url], "format": "markdown"},
        )
        return normalize_fetch_response(payload, url)

    def browser_extract(self, url: str, task: str) -> dict[str, Any]:
        payload = self._request_json(
            "browser_extract",
            "POST",
            self.settings.tinyfish_agent_url,
            json_body={
                "url": url,
                "goal": task,
                "browser_profile": "lite",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "price": {"type": "number"},
                        "stock_status": {"type": "string"},
                        "promo_signal": {"type": "string"},
                        "raw_text": {"type": "string"},
                    },
                    "required": ["price", "stock_status", "promo_signal"],
                },
            },
        )
        return normalize_browser_extract_response(payload, url, task)

    def run_agent(self, task: str) -> dict[str, Any]:
        payload = self._request_json(
            "run_agent",
            "POST",
            self.settings.tinyfish_agent_url,
            json_body={"url": "https://www.tinyfish.ai", "goal": task, "browser_profile": "lite"},
        )
        return normalize_agent_response(payload, task)


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
                "raw_payload": {"provider": "mock"},
            }
            for i in range(4)
        ]

    def fetch_url(self, url: str) -> dict[str, Any]:
        seed = self._seed(url)
        return {
            "url": url,
            "title": f"Fetched source {seed % 1000}",
            "content": f"Mock fetched content for {url}. It includes operational signals, market context, and timestamped evidence.",
            "raw_payload": {"provider": "mock"},
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
            "raw_payload": {"provider": "mock"},
        }

    def run_agent(self, task: str) -> dict[str, Any]:
        return {"task": task, "summary": "Mock TinyFish agent completed deterministic analysis."}


def get_tinyfish_provider(settings: Settings | None = None) -> TinyFishProviderInterface:
    settings = settings or get_settings()
    if settings.tinyfish_api_key:
        return TinyFishProvider(settings)
    return MockTinyFishProvider()


def infer_risk_factor(*values: str | None) -> str | None:
    text = " ".join(value or "" for value in values).lower()
    for factor, keywords in RISK_KEYWORDS.items():
        if any(keyword_matches(text, keyword) for keyword in keywords):
            return factor
    return None


def keyword_matches(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def normalize_search_results(payload: dict[str, Any], query: str) -> list[dict[str, Any]]:
    raw_results = payload.get("results") or payload.get("items") or []
    normalized: list[dict[str, Any]] = []
    for index, result in enumerate(raw_results):
        if not isinstance(result, dict):
            continue
        url = result.get("url") or result.get("link")
        if not url:
            continue
        title = result.get("title") or result.get("name") or f"Search result {index + 1}"
        snippet = result.get("snippet") or result.get("description") or result.get("text") or ""
        normalized.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "risk_factor": infer_risk_factor(title, snippet, query),
                "site_name": result.get("site_name"),
                "position": result.get("position", index + 1),
                "raw_payload": result,
            }
        )
    return normalized


def normalize_fetch_response(payload: dict[str, Any], url: str) -> dict[str, Any]:
    errors = payload.get("errors") or []
    if errors and not payload.get("results"):
        raise TinyFishError("fetch_url", f"per-url fetch failure for {url}: {errors}")
    results = payload.get("results") or []
    page = next((item for item in results if isinstance(item, dict) and item.get("url") == url), None)
    if page is None and results and isinstance(results[0], dict):
        page = results[0]
    page = page or payload
    text = page.get("text") or page.get("content") or page.get("markdown") or ""
    title = page.get("title") or page.get("description") or url
    return {
        "url": page.get("url") or url,
        "final_url": page.get("final_url"),
        "title": title,
        "content": stringify_content(text),
        "description": page.get("description"),
        "language": page.get("language"),
        "raw_payload": payload,
    }


def normalize_browser_extract_response(payload: dict[str, Any], url: str, task: str) -> dict[str, Any]:
    extracted = find_structured_payload(payload)
    raw_text = stringify_content(
        extracted.get("raw_text")
        or extracted.get("text")
        or extracted.get("summary")
        or payload.get("summary")
        or payload.get("result")
        or ""
    )
    price = coerce_price(extracted.get("price") or extracted.get("current_price") or raw_text)
    return {
        "url": url,
        "task": task,
        "price": price,
        "stock_status": normalize_stock_status(extracted.get("stock_status") or extracted.get("availability") or raw_text),
        "promo_signal": normalize_promo_signal(extracted.get("promo_signal") or extracted.get("promotion") or raw_text),
        "raw_text": raw_text or f"TinyFish extraction completed for {url}.",
        "raw_payload": payload,
    }


def normalize_agent_response(payload: dict[str, Any], task: str) -> dict[str, Any]:
    structured = find_structured_payload(payload)
    return {
        "task": task,
        "summary": stringify_content(
            structured.get("summary")
            or payload.get("summary")
            or payload.get("result")
            or payload.get("output")
            or "TinyFish agent completed."
        ),
        "raw_payload": payload,
    }


def build_supplier_evidence_payload(result: dict[str, Any], fetched: dict[str, Any]) -> dict[str, Any]:
    title = fetched.get("title") or result.get("title") or "Untitled source"
    full_content = fetched.get("content") or result.get("snippet") or ""
    snippet = result.get("snippet", "")
    content = summarize_evidence_text(title, snippet, full_content)
    risk_factor = result.get("risk_factor") or infer_risk_factor(title, content, snippet)
    return {
        "title": title,
        "content": content,
        "snippet": snippet,
        "risk_factor": risk_factor,
        "url": fetched.get("final_url") or fetched.get("url") or result["url"],
        "raw_payload": {
            "search_result": result.get("raw_payload", result),
            "fetched": fetched.get("raw_payload", fetched),
            "full_content_chars": len(full_content),
        },
    }


def build_product_evidence_payload(competitor_name: str, url: str, extracted: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"{competitor_name} listing",
        "content": extracted.get("raw_text", "Price extraction evidence."),
        "url": url,
        "raw_payload": extracted.get("raw_payload", extracted),
    }


def find_structured_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("data", "result", "results", "output", "structured_output", "extracted_data"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
    return payload


def stringify_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def summarize_evidence_text(title: str, snippet: str, full_content: str) -> str:
    cleaned = clean_text(full_content)
    if not cleaned:
        return clean_text(snippet)[:MAX_EVIDENCE_CHARS]

    sentences = split_sentences(cleaned)
    ranked = sorted(
        enumerate(sentences[:80]),
        key=lambda pair: (sentence_signal_score(pair[1], title, snippet), -pair[0]),
        reverse=True,
    )
    selected: list[str] = []
    for _index, sentence in ranked:
        if sentence_signal_score(sentence, title, snippet) <= 0 and selected:
            continue
        if sentence not in selected:
            selected.append(sentence)
        if len(" ".join(selected)) >= MAX_EVIDENCE_CHARS or len(selected) >= 4:
            break

    if not selected:
        selected = sentences[:3]
    summary = " ".join(selected)
    if snippet and snippet.lower() not in summary.lower():
        summary = f"{clean_text(snippet)} {summary}"
    return truncate_text(summary, MAX_EVIDENCE_CHARS)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def split_sentences(value: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]
    return sentences or ([value] if value else [])


def sentence_signal_score(sentence: str, title: str, snippet: str) -> int:
    text = sentence.lower()
    score = 0
    for keywords in RISK_KEYWORDS.values():
        for keyword in keywords:
            if keyword_matches(text, keyword):
                score += 3 if " " in keyword else 2
    context = f"{title} {snippet}".lower()
    for token in set(re.findall(r"\b[a-z]{5,}\b", context)):
        if token in text:
            score += 1
    return score


def truncate_text(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def coerce_price(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = stringify_content(value)
    match = re.search(r"(?<!\d)(?:\$|USD\s*)?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)", text, flags=re.IGNORECASE)
    if not match:
        raise TinyFishError("browser_extract", "price was not present in TinyFish extraction")
    return float(match.group(1).replace(",", ""))


def normalize_stock_status(value: Any) -> str:
    text = stringify_content(value).lower()
    if "out" in text and "stock" in text:
        return "out_of_stock"
    if "unavailable" in text or "sold out" in text:
        return "out_of_stock"
    if "preorder" in text or "pre-order" in text:
        return "preorder"
    if "stock" in text or "available" in text or "in-store" in text:
        return "in_stock"
    return "unknown"


def normalize_promo_signal(value: Any) -> str:
    text = stringify_content(value).lower()
    if any(token in text for token in ("discount", "sale", "coupon", "promo", "% off", "save ")):
        return "discount"
    if "clearance" in text:
        return "clearance"
    if "bundle" in text:
        return "bundle"
    return "none"
