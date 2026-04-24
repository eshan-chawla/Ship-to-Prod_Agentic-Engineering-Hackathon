from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    name: str
    website: str
    country: str
    category: str
    criticality: str = "medium"


class SupplierRead(SupplierCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FactorDetail(BaseModel):
    score: int
    confidence: float
    evidence_ids: list[int] = Field(default_factory=list)


class SupplierRiskRead(BaseModel):
    id: int
    supplier_id: int
    scan_id: int
    score: int
    financial_stress: int
    legal_regulatory: int
    delivery_disruption: int
    sentiment: int
    cybersecurity: int
    geopolitical: int
    factor_details: dict[str, FactorDetail] = Field(default_factory=dict)
    explanation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str
    brand: str
    category: str
    target_price: float = Field(gt=0)
    target_margin: float = Field(ge=0, le=1)


class ProductRead(ProductCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompetitorUrlCreate(BaseModel):
    competitor_name: str
    url: str


class CompetitorUrlRead(CompetitorUrlCreate):
    id: int
    product_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceObservationRead(BaseModel):
    id: int
    product_id: int
    competitor_url_id: int
    competitor_name: str
    url: str
    price: float
    stock_status: str
    promo_signal: str
    observed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceRecommendationRead(BaseModel):
    id: int
    product_id: int
    action: str
    explanation: str
    expected_impact: str | None = None
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    severity: str
    title: str
    message: str
    created_at: datetime
    acknowledged_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AgentRunRead(BaseModel):
    id: int
    run_type: str
    entity_type: str
    entity_id: int
    status: str
    started_at: datetime
    ended_at: datetime | None
    summary: str | None

    model_config = ConfigDict(from_attributes=True)


class EvidenceRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    scan_id: int | None
    source_url: str
    source_title: str
    content: str
    evidence_type: str
    risk_factor: str | None
    captured_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    job_id: str
    status: str


class DashboardRead(BaseModel):
    suppliers: int
    products: int
    open_alerts: int
    agent_runs: int
    latest_risks: list[SupplierRiskRead]
    latest_recommendations: list[PriceRecommendationRead]
    recent_alerts: list[AlertRead]
    recent_agent_runs: list[AgentRunRead]

