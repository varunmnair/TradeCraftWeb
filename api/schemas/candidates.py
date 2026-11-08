"""Pydantic schemas for the unified entry candidate pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CandidateGenerateRequest(BaseModel):
    apply_risk_management: bool = False


class NormalizedCandidateSchema(BaseModel):
    symbol: str
    exchange: str | None = None
    strategy_type: str
    side: str
    status: str
    status_severity: int = 0
    signal: str | None = None
    cmp: float | None = None
    order_price: float | None = None
    trigger_price: float | None = None
    qty: int
    amount: float
    allocation: float | None = None
    current_holding_qty: float
    current_holding_value: float
    allocation_used_percent: float
    level_or_leg: str
    strategy_reference: str | None = None
    reason_code: str | None = None
    reason_message: str | None = None
    suggested_action: str | None = None
    is_selectable: bool = True
    created_at: datetime | None = None
    additional_details: dict = Field(default_factory=dict)


class SkippedCandidateSchema(BaseModel):
    symbol: str
    exchange: str | None = None
    strategy_type: str
    cmp: float | None = None
    level_or_leg: str | None = None
    reason_code: str
    reason_message: str
    suggested_action: str
    technical_details: str | None = None


class CandidateSummarySchema(BaseModel):
    total: int = 0
    ready: int = 0
    warning: int = 0
    review: int = 0
    skipped: int = 0
    capital_required: float = 0.0


class CandidateGenerateResponse(BaseModel):
    strategy_type: str = "UNIFIED"
    candidates: list[NormalizedCandidateSchema] = Field(default_factory=list)
    skipped: list[SkippedCandidateSchema] = Field(default_factory=list)
    summary: CandidateSummarySchema = Field(default_factory=CandidateSummarySchema)
    generated_at: datetime | None = None


class CandidatePlaceRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, description="Symbols to place orders for")
    apply_risk_management: bool = False


class PlaceOrderResult(BaseModel):
    symbol: str
    strategy_type: str
    qty: int
    order_price: float | None = None
    trigger_price: float | None = None
    amount: float
    status: str
    remarks: str = ""


class CandidatePlaceResponse(BaseModel):
    placed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    results: list[PlaceOrderResult] = Field(default_factory=list)


class CandidateLatestResponse(BaseModel):
    session_id: str
    result: CandidateGenerateResponse | None = None
    generated_at: datetime | None = None
