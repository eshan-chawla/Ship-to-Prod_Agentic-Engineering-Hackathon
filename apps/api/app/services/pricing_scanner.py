from __future__ import annotations

from sqlmodel import Session, select
from app.core.config import get_settings
from app.integrations.governance import GovernanceRecorder
from app.integrations.redis_context import RedisContext
from app.integrations.tinyfish import TinyFishProviderInterface, get_tinyfish_provider
from app.models.entities import CompetitorUrl, EvidenceItem, PriceObservation, PriceRecommendation, Product
from app.services.scoring import recommend_price


def run_price_scan(
    session: Session,
    product_id: int,
    provider: TinyFishProviderInterface | None = None,
    redis_context: RedisContext | None = None,
) -> PriceRecommendation:
    product = session.get(Product, product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    settings = get_settings()
    provider = provider or get_tinyfish_provider(settings)
    redis_context = redis_context or RedisContext(settings.redis_url)
    governance = GovernanceRecorder(session)
    run = governance.record_agent_run_start("price_scan", "product", product_id, {"product": product.name})
    competitors = session.exec(select(CompetitorUrl).where(CompetitorUrl.product_id == product_id)).all()
    observations: list[dict] = []

    try:
        for competitor in competitors:
            cache_key = f"tinyfish:extract:{competitor.url}:price"
            extracted = redis_context.get_json(cache_key)
            if not extracted:
                governance.record_tool_use(run.id, "tinyfish.browser_extract", {"url": competitor.url})
                extracted = provider.browser_extract(
                    competitor.url,
                    "Extract current price, stock status, and promotion or discount signals.",
                )
                redis_context.set_json(cache_key, extracted, ttl_seconds=900)
            observation = PriceObservation(
                product_id=product_id,
                competitor_url_id=competitor.id,
                competitor_name=competitor.competitor_name,
                url=competitor.url,
                price=float(extracted["price"]),
                stock_status=extracted.get("stock_status", "unknown"),
                promo_signal=extracted.get("promo_signal", "none"),
                raw_payload=extracted,
            )
            session.add(observation)
            observations.append(
                {
                    "price": observation.price,
                    "stock_status": observation.stock_status,
                    "promo_signal": observation.promo_signal,
                }
            )
            session.add(
                EvidenceItem(
                    entity_type="product",
                    entity_id=product_id,
                    source_url=competitor.url,
                    source_title=f"{competitor.competitor_name} listing",
                    content=extracted.get("raw_text", "Price extraction evidence."),
                    evidence_type="price_signal",
                    raw_payload=extracted,
                )
            )

        rec = recommend_price(product.target_price, product.target_margin, observations)
        recommendation = PriceRecommendation(
            product_id=product_id,
            action=rec["action"],
            explanation=rec["explanation"],
            confidence=rec["confidence"],
        )
        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)
        redis_context.append_memory(f"product:{product_id}", {"recommendation": recommendation.action})
        governance.record_agent_run_end(run.id, "completed", f"Pricing recommendation: {recommendation.action}")
        session.refresh(recommendation)
        return recommendation
    except Exception as exc:
        session.rollback()
        governance.record_agent_run_end(run.id, "failed", str(exc))
        raise
