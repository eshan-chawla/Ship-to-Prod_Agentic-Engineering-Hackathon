from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlmodel import Session, func, select
from app.db.session import get_session
from app.models.entities import (
    AgentRun,
    Alert,
    CompetitorUrl,
    EvidenceItem,
    PriceObservation,
    PriceRecommendation,
    Product,
    Supplier,
    SupplierRiskScore,
)
from app.schemas.dto import (
    AgentRunRead,
    AlertRead,
    CompetitorUrlCreate,
    CompetitorUrlRead,
    DashboardRead,
    EvidenceRead,
    JobResponse,
    PriceObservationRead,
    PriceRecommendationRead,
    ProductCreate,
    ProductRead,
    SupplierCreate,
    SupplierRead,
    SupplierRiskRead,
)
from app.services.queues import ScanQueue

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(session: Session = Depends(get_session)) -> DashboardRead:
    suppliers = session.exec(select(func.count(Supplier.id))).one()
    products = session.exec(select(func.count(Product.id))).one()
    open_alerts = session.exec(select(func.count(Alert.id)).where(Alert.acknowledged_at.is_(None))).one()
    agent_runs = session.exec(select(func.count(AgentRun.id))).one()
    latest_risks = session.exec(select(SupplierRiskScore).order_by(desc(SupplierRiskScore.created_at)).limit(5)).all()
    latest_recommendations = session.exec(select(PriceRecommendation).order_by(desc(PriceRecommendation.created_at)).limit(5)).all()
    recent_alerts = session.exec(select(Alert).order_by(desc(Alert.created_at)).limit(5)).all()
    recent_agent_runs = session.exec(select(AgentRun).order_by(desc(AgentRun.started_at)).limit(5)).all()
    return DashboardRead(
        suppliers=suppliers,
        products=products,
        open_alerts=open_alerts,
        agent_runs=agent_runs,
        latest_risks=latest_risks,
        latest_recommendations=latest_recommendations,
        recent_alerts=recent_alerts,
        recent_agent_runs=recent_agent_runs,
    )


@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, session: Session = Depends(get_session)) -> Supplier:
    supplier = Supplier.model_validate(payload)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(session: Session = Depends(get_session)) -> list[Supplier]:
    return session.exec(select(Supplier).order_by(Supplier.name)).all()


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, session: Session = Depends(get_session)) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.post("/suppliers/{supplier_id}/scan", response_model=JobResponse)
def scan_supplier(supplier_id: int, session: Session = Depends(get_session)) -> JobResponse:
    if not session.get(Supplier, supplier_id):
        raise HTTPException(status_code=404, detail="Supplier not found")
    try:
        job_id = ScanQueue().enqueue("supplier_scan", {"supplier_id": supplier_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job_id=job_id, status="queued")


@router.get("/suppliers/{supplier_id}/risk", response_model=SupplierRiskRead | None)
def get_supplier_risk(supplier_id: int, session: Session = Depends(get_session)) -> SupplierRiskScore | None:
    return session.exec(
        select(SupplierRiskScore)
        .where(SupplierRiskScore.supplier_id == supplier_id)
        .order_by(desc(SupplierRiskScore.created_at))
        .limit(1)
    ).first()


@router.get("/suppliers/{supplier_id}/evidence", response_model=list[EvidenceRead])
def get_supplier_evidence(supplier_id: int, session: Session = Depends(get_session)) -> list[EvidenceItem]:
    return session.exec(
        select(EvidenceItem)
        .where(EvidenceItem.entity_type == "supplier", EvidenceItem.entity_id == supplier_id)
        .order_by(desc(EvidenceItem.captured_at))
        .limit(20)
    ).all()


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, session: Session = Depends(get_session)) -> Product:
    product = Product.model_validate(payload)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.get("/products", response_model=list[ProductRead])
def list_products(session: Session = Depends(get_session)) -> list[Product]:
    return session.exec(select(Product).order_by(Product.name)).all()


@router.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, session: Session = Depends(get_session)) -> Product:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/products/{product_id}/competitors", response_model=CompetitorUrlRead, status_code=status.HTTP_201_CREATED)
def add_competitor(product_id: int, payload: CompetitorUrlCreate, session: Session = Depends(get_session)) -> CompetitorUrl:
    if not session.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    competitor = CompetitorUrl(product_id=product_id, **payload.model_dump())
    session.add(competitor)
    session.commit()
    session.refresh(competitor)
    return competitor


@router.get("/products/{product_id}/competitors", response_model=list[CompetitorUrlRead])
def list_competitors(product_id: int, session: Session = Depends(get_session)) -> list[CompetitorUrl]:
    return session.exec(select(CompetitorUrl).where(CompetitorUrl.product_id == product_id)).all()


@router.post("/products/{product_id}/scan-prices", response_model=JobResponse)
def scan_prices(product_id: int, session: Session = Depends(get_session)) -> JobResponse:
    if not session.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        job_id = ScanQueue().enqueue("price_scan", {"product_id": product_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job_id=job_id, status="queued")


@router.get("/products/{product_id}/observations", response_model=list[PriceObservationRead])
def list_price_observations(product_id: int, session: Session = Depends(get_session)) -> list[PriceObservation]:
    return session.exec(
        select(PriceObservation)
        .where(PriceObservation.product_id == product_id)
        .order_by(desc(PriceObservation.observed_at))
        .limit(25)
    ).all()


@router.get("/products/{product_id}/recommendations", response_model=list[PriceRecommendationRead])
def list_recommendations(product_id: int, session: Session = Depends(get_session)) -> list[PriceRecommendation]:
    return session.exec(
        select(PriceRecommendation)
        .where(PriceRecommendation.product_id == product_id)
        .order_by(desc(PriceRecommendation.created_at))
        .limit(10)
    ).all()


@router.get("/products/{product_id}/evidence", response_model=list[EvidenceRead])
def get_product_evidence(product_id: int, session: Session = Depends(get_session)) -> list[EvidenceItem]:
    return session.exec(
        select(EvidenceItem)
        .where(EvidenceItem.entity_type == "product", EvidenceItem.entity_id == product_id)
        .order_by(desc(EvidenceItem.captured_at))
        .limit(20)
    ).all()


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(session: Session = Depends(get_session)) -> list[Alert]:
    return session.exec(select(Alert).order_by(desc(Alert.created_at)).limit(50)).all()


@router.get("/agent-runs", response_model=list[AgentRunRead])
def list_agent_runs(session: Session = Depends(get_session)) -> list[AgentRun]:
    return session.exec(select(AgentRun).order_by(desc(AgentRun.started_at)).limit(50)).all()

