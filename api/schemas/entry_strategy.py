from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EntryLevelSchema(BaseModel):
    id: int | None = None
    level_no: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    is_active: bool = True


class EntryStrategySummarySchema(BaseModel):
    symbol: str
    allocated: float | None = None
    quality: str | None = None
    exchange: str | None = None
    entry1: float | None = None
    entry2: float | None = None
    entry3: float | None = None
    da_enabled: bool = False
    da_legs: int | None = None
    da_e1_buyback: int | None = None
    da_e2_buyback: int | None = None
    da_e3_buyback: int | None = None
    da_trigger_offset: int | None = None
    levels_count: int
    created_at: datetime
    updated_at: datetime
    swing_eligible: bool | None = None
    swing_avg_volume: float | None = None
    swing_atr_percent: float | None = None
    swing_range_percent: float | None = None
    swing_reasons: list[str] | None = None
    thesis_break_price: float | None = None
    review_status: str | None = None
    last_evaluated_at: datetime | None = None
    last_entry_revision_at: datetime | None = None
    da_eligible: bool | None = None
    da_status: str | None = None
    da_confidence_score: int | None = None
    da_last_evaluated_at: datetime | None = None
    is_holding: bool = False
    holding_entry_level: str | None = None


class EntryStrategyFullSchema(BaseModel):
    id: int
    symbol: str
    allocated: float | None = None
    quality: str | None = None
    exchange: str | None = None
    dynamic_averaging_enabled: bool
    averaging_rules_json: str | None = None
    averaging_rules_summary: str | None = None
    levels: list[EntryLevelSchema]
    created_at: datetime
    updated_at: datetime
    swing_eligible: bool | None = None
    swing_avg_volume: float | None = None
    swing_atr_percent: float | None = None
    swing_range_percent: float | None = None
    swing_reasons: list[str] | None = None
    thesis_break_price: float | None = None
    review_status: str | None = None
    last_evaluated_at: datetime | None = None
    last_entry_revision_at: datetime | None = None
    da_eligible: bool | None = None
    da_status: str | None = None
    da_last_evaluated_at: datetime | None = None
    da_confidence_score: int | None = None
    da_notes: str | None = None
    override_da_enabled: bool | None = None
    override_da_qty_pct: float | None = None
    override_sell_offset: float | None = None
    override_buyback_price: float | None = None
    override_sell_price: float | None = None


class EntryStrategyUploadResponse(BaseModel):
    symbols_processed: int
    created_count: int
    updated_count: int
    deleted_count: int
    errors: list[dict[str, Any]]
    updated_at: datetime


class SuggestedRevision(BaseModel):
    level_no: int
    original_price: float
    suggested_price: float
    rationale: str


class SuggestRevisionResponse(BaseModel):
    symbol: str
    cmp_price: float | None = None
    revised_levels: list[SuggestedRevision]
    swing_eligible: bool | None = None
    review_status: str | None = None
    thesis_break_price: float | None = None
    revision_reason: str | None = None
    style: str | None = None


class ApplyRevisionItem(BaseModel):
    level_no: int
    new_price: float

    @field_validator("new_price")
    @classmethod
    def new_price_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("new_price must be greater than 0")
        return v


class ApplyRevisionRequest(BaseModel):
    levels: list[ApplyRevisionItem]
    thesis_break_price: float | None = None


class ApplyRevisionResponse(BaseModel):
    symbol: str
    updated_levels: list[int]
    updated_at: datetime


class BulkSuggestRevisionRequest(BaseModel):
    symbols: list[str]
    style: str = "balanced"


class BulkSuggestRevisionItem(BaseModel):
    symbol: str
    cmp_price: float | None = None
    revised_levels: list[SuggestedRevision]
    swing_eligible: bool | None = None
    review_status: str | None = None
    thesis_break_price: float | None = None
    revision_reason: str | None = None
    style: str | None = None


class BulkSuggestRevisionResponse(BaseModel):
    suggestions: list[BulkSuggestRevisionItem]


class BulkApplyRevisionItem(BaseModel):
    symbol: str
    levels: list[ApplyRevisionItem]
    thesis_break_price: float | None = None


class BulkApplyRevisionRequest(BaseModel):
    updates: list[BulkApplyRevisionItem]


class BulkApplyRevisionResult(BaseModel):
    symbol: str
    success: bool
    updated_levels: list[int] = []
    updated_at: datetime | None = None
    error: str | None = None


class BulkApplyRevisionResponse(BaseModel):
    results: list[BulkApplyRevisionResult]
    total_updated: int
    total_failed: int


class UploadHistoryItem(BaseModel):
    id: int
    filename: str
    symbols: list[str]
    created_at: datetime


class UploadHistoryResponse(BaseModel):
    uploads: list[UploadHistoryItem]


class VersionItem(BaseModel):
    id: int
    version_no: int
    action: str
    levels: list[EntryLevelSchema]
    changes_summary: str | None = None
    created_at: datetime


class VersionListResponse(BaseModel):
    versions: list[VersionItem]


class RestoreVersionRequest(BaseModel):
    version_id: int


class RestoreVersionResponse(BaseModel):
    symbol: str
    restored_to_version: int
    updated_at: datetime


class EntryStrategyCSVRow(BaseModel):
    symbol: str
    level_no: int
    price: float
    dynamic_averaging_enabled: bool | None = None
    averaging_rules_json: str | None = None

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("level_no")
    @classmethod
    def level_no_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("level_no must be a positive integer")
        return v

    @field_validator("price")
    @classmethod
    def price_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("price must be greater than 0")
        return v


class InlineUpdateRequest(BaseModel):
    allocated: float | None = None
    entry1: float | None = None
    entry2: float | None = None
    entry3: float | None = None


class InlineUpdateResponse(BaseModel):
    symbol: str
    updated_fields: list[str]
    updated_at: datetime


class EntryStrategyListResponse(BaseModel):
    strategies: list[EntryStrategySummarySchema]


class DAEvalResultSchema(BaseModel):
    symbol: str
    da_eligible: bool
    da_status: str | None = None
    da_confidence_score: int | None = None
    da_confidence_label: str | None = None
    da_last_evaluated_at: datetime | None = None
    da_notes: str | None = None
    recommended_sell_trigger: float | None = None
    recommended_sell_limit: float | None = None
    recommended_buyback_price: float | None = None
    recommended_da_qty: int = 0
    recommended_da_qty_pct: int = 0
    expected_sell_value: float | None = None
    expected_buyback_value: float | None = None
    expected_charges: float | None = None
    expected_net_profit: float | None = None
    position_risk_score: int | None = None
    range_high: float | None = None
    range_low: float | None = None
    range_width: float | None = None
    range_pct: float | None = None


class DABulkEvalResponse(BaseModel):
    session_id: str
    results: list[DAEvalResultSchema]


class DAOverrideRequest(BaseModel):
    override_da_enabled: bool | None = None
    override_da_qty_pct: float | None = None
    override_sell_offset: float | None = None
    override_buyback_price: float | None = None
    override_sell_price: float | None = None


class DAConfigSchema(BaseModel):
    minimum_da_net_profit: int = 100
    default_sell_offset: float = 0.01
    minimum_volume_threshold: int = 10000
    da_range_analysis_days: int = 10
    high_confidence_qty_pct: int = 50
    medium_confidence_qty_pct: int = 40
    low_confidence_qty_pct: int = 30
    no_recommendation_min_score: int = 40
    confidence_high_threshold: int = 85
    confidence_medium_threshold: int = 60
    confidence_low_threshold: int = 40
