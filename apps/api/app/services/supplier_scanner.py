from __future__ import annotations

from datetime import datetime, timezone
from sqlmodel import Session
from app.core.config import get_settings
from app.integrations.governance import GovernanceRecorder
from app.integrations.redis_context import RedisContext
from app.integrations.tinyfish import TinyFishProviderInterface, build_supplier_evidence_payload, get_tinyfish_provider
from app.models.entities import Alert, EvidenceItem, Supplier, SupplierRiskScore, SupplierScan, SupplierSource
from app.services.scoring import score_risk_evidence


def run_supplier_scan(
    session: Session,
    supplier_id: int,
    provider: TinyFishProviderInterface | None = None,
    redis_context: RedisContext | None = None,
) -> SupplierRiskScore:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise ValueError(f"Supplier {supplier_id} not found")

    settings = get_settings()
    provider = provider or get_tinyfish_provider(settings)
    redis_context = redis_context or RedisContext(settings.redis_url)
    governance = GovernanceRecorder(session)
    run = governance.record_agent_run_start("supplier_scan", "supplier", supplier_id, {"supplier": supplier.name})
    scan = SupplierScan(
        supplier_id=supplier_id,
        status="running",
        started_at=datetime.now(timezone.utc),
        agent_run_id=run.id,
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    try:
        query = f"{supplier.name} {supplier.country} supplier risk news legal financial cyber delivery"
        cache_key = f"tinyfish:search:{query}"
        results = redis_context.get_json(cache_key)
        if not results:
            governance.record_tool_use(run.id, "tinyfish.search_web", {"query": query})
            results = provider.search_web(query)
            redis_context.set_json(cache_key, results, ttl_seconds=3600)

        evidence_payloads = []
        for result in results[:5]:
            source = SupplierSource(
                supplier_id=supplier_id,
                source_type="web",
                url=result["url"],
                title=result.get("title"),
            )
            session.add(source)
            fetched_key = f"tinyfish:fetch:{result['url']}"
            fetched = redis_context.get_json(fetched_key)
            if not fetched:
                governance.record_tool_use(run.id, "tinyfish.fetch_url", {"url": result["url"]})
                fetched = provider.fetch_url(result["url"])
                redis_context.set_json(fetched_key, fetched, ttl_seconds=3600)
            payload = build_supplier_evidence_payload(result, fetched)
            item = EvidenceItem(
                entity_type="supplier",
                entity_id=supplier_id,
                scan_id=scan.id,
                source_url=payload["url"],
                source_title=payload["title"],
                content=payload["content"],
                evidence_type="risk_signal",
                risk_factor=payload["risk_factor"],
                raw_payload=payload["raw_payload"],
            )
            session.add(item)
            session.flush()
            payload["id"] = item.id
            evidence_payloads.append(payload)

        scoring = score_risk_evidence(evidence_payloads, supplier.criticality)
        factors = scoring["factors"]
        risk = SupplierRiskScore(
            supplier_id=supplier_id,
            scan_id=scan.id,
            score=scoring["score"],
            financial_stress=factors["financial_stress"],
            legal_regulatory=factors["legal_regulatory"],
            delivery_disruption=factors["delivery_disruption"],
            sentiment=factors["sentiment"],
            cybersecurity=factors["cybersecurity"],
            geopolitical=factors["geopolitical"],
            factor_details=scoring["factor_details"],
            explanation=scoring["explanation"],
        )
        session.add(risk)
        if risk.score >= settings.risk_alert_threshold:
            session.add(
                Alert(
                    entity_type="supplier",
                    entity_id=supplier_id,
                    severity="high" if risk.score >= 85 else "medium",
                    title=f"{supplier.name} risk threshold crossed",
                    message=f"Risk score reached {risk.score}/100. Review evidence before renewing commitments.",
                )
            )
        scan.status = "completed"
        scan.completed_at = datetime.now(timezone.utc)
        session.add(scan)
        session.commit()
        session.refresh(risk)
        redis_context.memory.record_supplier(supplier_id, {"risk_score": risk.score, "scan_id": scan.id})
        redis_context.memory.record_scan_summary(
            {"kind": "supplier_scan", "entity_id": supplier_id, "score": risk.score, "scan_id": scan.id}
        )
        governance.record_agent_run_end(run.id, "completed", f"Supplier risk score {risk.score}/100")
        session.refresh(risk)
        return risk
    except Exception as exc:
        scan.status = "failed"
        scan.error = str(exc)
        scan.completed_at = datetime.now(timezone.utc)
        session.add(scan)
        session.commit()
        governance.record_agent_run_end(run.id, "failed", str(exc))
        raise
