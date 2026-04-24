from __future__ import annotations

from sqlmodel import Session, delete
from app.db.session import create_db_and_tables, engine
from app.models.entities import (
    AgentRun,
    Alert,
    AuditLog,
    CompetitorUrl,
    EvidenceItem,
    PriceObservation,
    PriceRecommendation,
    Product,
    Supplier,
    SupplierRiskScore,
    SupplierScan,
    SupplierSource,
    User,
)


def reset_tables(session: Session) -> None:
    for model in [
        AuditLog,
        EvidenceItem,
        Alert,
        PriceRecommendation,
        PriceObservation,
        CompetitorUrl,
        Product,
        SupplierRiskScore,
        SupplierScan,
        SupplierSource,
        Supplier,
        AgentRun,
        User,
    ]:
        session.exec(delete(model))
    session.commit()


def seed() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        reset_tables(session)
        session.add(User(email="demo@market-os.local", password_hash="dev-only-not-for-production"))

        suppliers = [
            Supplier(name="Nippon Precision Components", website="https://example.com/nippon", country="Japan", category="Semiconductors", criticality="critical"),
            Supplier(name="Atlas Cold Chain Logistics", website="https://example.com/atlas", country="Mexico", category="Logistics", criticality="high"),
            Supplier(name="Baltic Packaging Works", website="https://example.com/baltic", country="Poland", category="Packaging", criticality="medium"),
        ]
        session.add_all(suppliers)
        session.commit()
        for supplier in suppliers:
            session.refresh(supplier)

        products = [
            Product(name="Smart Thermostat Pro", brand="Northstar", category="Connected Home", target_price=129.0, target_margin=0.34),
            Product(name="TrailBlend 12 Pack", brand="Granite Foods", category="Grocery", target_price=18.5, target_margin=0.27),
            Product(name="AirSeal Storage Bin", brand="HomeGrid", category="Storage", target_price=42.0, target_margin=0.31),
        ]
        session.add_all(products)
        session.commit()
        for product in products:
            session.refresh(product)

        competitors = [
            CompetitorUrl(product_id=products[0].id, competitor_name="RetailHub", url="https://retail.example/smart-thermostat"),
            CompetitorUrl(product_id=products[0].id, competitor_name="DepotMart", url="https://depot.example/thermostat-pro"),
            CompetitorUrl(product_id=products[1].id, competitor_name="MegaGrocer", url="https://grocery.example/trailblend-12"),
            CompetitorUrl(product_id=products[2].id, competitor_name="HouseShop", url="https://home.example/airseal-bin"),
        ]
        session.add_all(competitors)
        session.commit()
        for competitor in competitors:
            session.refresh(competitor)

        run1 = AgentRun(run_type="supplier_scan", entity_type="supplier", entity_id=suppliers[0].id, status="completed", summary="Supplier risk score 82/100")
        run2 = AgentRun(run_type="price_scan", entity_type="product", entity_id=products[0].id, status="completed", summary="Pricing recommendation: launch promo")
        session.add_all([run1, run2])
        session.commit()
        session.refresh(run1)
        session.refresh(run2)

        scan = SupplierScan(supplier_id=suppliers[0].id, status="completed", agent_run_id=run1.id)
        session.add(scan)
        session.commit()
        session.refresh(scan)

        session.add_all(
            [
                SupplierSource(supplier_id=suppliers[0].id, source_type="web", url="https://mock.tinyfish.local/evidence/semis-1", title="Port delays hit component shipments"),
                EvidenceItem(
                    entity_type="supplier",
                    entity_id=suppliers[0].id,
                    scan_id=scan.id,
                    source_url="https://mock.tinyfish.local/evidence/semis-1",
                    source_title="Port delays hit component shipments",
                    content="Mock evidence cites port delay, component shortage, and cash flow concerns.",
                    evidence_type="risk_signal",
                    risk_factor="delivery_disruption",
                    raw_payload={"provider": "mock"},
                ),
                EvidenceItem(
                    entity_type="supplier",
                    entity_id=suppliers[0].id,
                    scan_id=scan.id,
                    source_url="https://mock.tinyfish.local/evidence/semis-2",
                    source_title="Security patch required across supplier portal",
                    content="Mock evidence cites security patch urgency and data exposure concerns.",
                    evidence_type="risk_signal",
                    risk_factor="cybersecurity",
                    raw_payload={"provider": "mock"},
                ),
                SupplierRiskScore(
                    supplier_id=suppliers[0].id,
                    scan_id=scan.id,
                    score=82,
                    financial_stress=29,
                    legal_regulatory=0,
                    delivery_disruption=53,
                    sentiment=0,
                    cybersecurity=42,
                    geopolitical=0,
                    explanation="Risk score 82/100 is driven by delivery disruption and cybersecurity evidence in mock sources.",
                ),
                Alert(
                    entity_type="supplier",
                    entity_id=suppliers[0].id,
                    severity="high",
                    title="Critical supplier risk threshold crossed",
                    message="Nippon Precision Components reached 82/100 after mock evidence review.",
                ),
            ]
        )

        session.add_all(
            [
                PriceObservation(product_id=products[0].id, competitor_url_id=competitors[0].id, competitor_name="RetailHub", url=competitors[0].url, price=119.99, stock_status="in_stock", promo_signal="discount", raw_payload={"provider": "mock"}),
                PriceObservation(product_id=products[0].id, competitor_url_id=competitors[1].id, competitor_name="DepotMart", url=competitors[1].url, price=124.5, stock_status="in_stock", promo_signal="none", raw_payload={"provider": "mock"}),
                PriceRecommendation(product_id=products[0].id, action="launch promo", confidence=0.82, explanation="Target price $129.00 is above average in-stock competitor price $122.25 and one competitor is discounting."),
                EvidenceItem(entity_type="product", entity_id=products[0].id, source_url=competitors[0].url, source_title="RetailHub listing", content="Mock extraction found $119.99 with discount signal.", evidence_type="price_signal", raw_payload={"provider": "mock"}),
                Alert(entity_type="product", entity_id=products[0].id, severity="medium", title="Promo pressure detected", message="RetailHub is discounting Smart Thermostat Pro below target price."),
                AuditLog(agent_run_id=run1.id, event_type="tool_use", message="Used tinyfish.search_web", payload={"provider": "mock"}),
                AuditLog(agent_run_id=run2.id, event_type="tool_use", message="Used tinyfish.browser_extract", payload={"provider": "mock"}),
            ]
        )
        session.commit()


if __name__ == "__main__":
    seed()
    print("Seeded AI Market Intelligence OS demo data.")

