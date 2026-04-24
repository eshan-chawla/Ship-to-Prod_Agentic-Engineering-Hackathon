from datetime import datetime, timezone
from typing import Any
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    website: str
    country: str
    category: str
    criticality: str = Field(default="medium")
    created_at: datetime = Field(default_factory=utc_now)


class SupplierSource(SQLModel, table=True):
    __tablename__ = "supplier_sources"

    id: int | None = Field(default=None, primary_key=True)
    supplier_id: int = Field(index=True, foreign_key="suppliers.id")
    source_type: str
    url: str
    title: str | None = None
    captured_at: datetime = Field(default_factory=utc_now)


class SupplierScan(SQLModel, table=True):
    __tablename__ = "supplier_scans"

    id: int | None = Field(default=None, primary_key=True)
    supplier_id: int = Field(index=True, foreign_key="suppliers.id")
    status: str = Field(default="queued")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    agent_run_id: int | None = Field(default=None, foreign_key="agent_runs.id")


class SupplierRiskScore(SQLModel, table=True):
    __tablename__ = "supplier_risk_scores"

    id: int | None = Field(default=None, primary_key=True)
    supplier_id: int = Field(index=True, foreign_key="suppliers.id")
    scan_id: int = Field(index=True, foreign_key="supplier_scans.id")
    score: int = Field(ge=0, le=100)
    financial_stress: int = Field(default=0)
    legal_regulatory: int = Field(default=0)
    delivery_disruption: int = Field(default=0)
    sentiment: int = Field(default=0)
    cybersecurity: int = Field(default=0)
    geopolitical: int = Field(default=0)
    explanation: str
    created_at: datetime = Field(default_factory=utc_now)


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    brand: str
    category: str
    target_price: float
    target_margin: float
    created_at: datetime = Field(default_factory=utc_now)


class CompetitorUrl(SQLModel, table=True):
    __tablename__ = "competitor_urls"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(index=True, foreign_key="products.id")
    competitor_name: str
    url: str
    created_at: datetime = Field(default_factory=utc_now)


class PriceObservation(SQLModel, table=True):
    __tablename__ = "price_observations"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(index=True, foreign_key="products.id")
    competitor_url_id: int = Field(index=True, foreign_key="competitor_urls.id")
    competitor_name: str
    url: str
    price: float
    stock_status: str
    promo_signal: str
    observed_at: datetime = Field(default_factory=utc_now)
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class PriceRecommendation(SQLModel, table=True):
    __tablename__ = "price_recommendations"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(index=True, foreign_key="products.id")
    action: str
    explanation: str
    confidence: float = Field(default=0.75)
    created_at: datetime = Field(default_factory=utc_now)


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str
    entity_id: int
    severity: str
    title: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: int | None = Field(default=None, primary_key=True)
    run_type: str
    entity_type: str
    entity_id: int
    status: str = Field(default="running")
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    summary: str | None = None
    run_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))


class EvidenceItem(SQLModel, table=True):
    __tablename__ = "evidence_items"

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str
    entity_id: int
    scan_id: int | None = None
    source_url: str
    source_title: str
    content: str
    evidence_type: str
    risk_factor: str | None = None
    captured_at: datetime = Field(default_factory=utc_now)
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    agent_run_id: int | None = Field(default=None, index=True, foreign_key="agent_runs.id")
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
