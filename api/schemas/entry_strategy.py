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
    updated_at: datetime


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


class EntryStrategyUploadResponse(BaseModel):
    symbols_processed: int
    created_count: int
    updated_count: int
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


class ApplyRevisionResponse(BaseModel):
    symbol: str
    updated_levels: list[int]
    updated_at: datetime


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


class EntryStrategyListResponse(BaseModel):
    strategies: list[EntryStrategySummarySchema]
