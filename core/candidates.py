"""Normalized candidate models for the unified entry candidate pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StrategyType(str, Enum):
    MULTI_LEVEL = "MULTI_LEVEL"
    DYNAMIC_AVERAGING = "DYNAMIC_AVERAGING"
    SIP = "SIP"


class CandidateStatus(str, Enum):
    READY = "READY"
    WARNING = "WARNING"
    REVIEW = "REVIEW"
    SKIPPED = "SKIPPED"


class ReasonCode(str, Enum):
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    CONFIGURATION_MISSING = "CONFIGURATION_MISSING"
    PRICE_NOT_IN_RANGE = "PRICE_NOT_IN_RANGE"
    PRICE_TOO_FAR_FROM_PLAN = "PRICE_TOO_FAR_FROM_PLAN"
    ALLOCATION_COMPLETE = "ALLOCATION_COMPLETE"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    TRADE_ALREADY_DONE = "TRADE_ALREADY_DONE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    DA_NOT_ELIGIBLE = "DA_NOT_ELIGIBLE"
    LOW_PROFIT_OPPORTUNITY = "LOW_PROFIT_OPPORTUNITY"
    BROKER_VALIDATION_FAILED = "BROKER_VALIDATION_FAILED"
    THESIS_BREAK = "THESIS_BREAK"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    PRICE_ABOVE_OPPORTUNITY_WINDOW = "PRICE_ABOVE_OPPORTUNITY_WINDOW"
    NO_AVERAGING_CAPACITY = "NO_AVERAGING_CAPACITY"
    PRICE_NOT_READY_FOR_DA = "PRICE_NOT_READY_FOR_DA"
    DA_DISABLED = "DA_DISABLED"
    INVALID_ENTRY_LEVEL_ORDER = "INVALID_ENTRY_LEVEL_ORDER"
    ENTRY_STRATEGY_MISSING = "ENTRY_STRATEGY_MISSING"
    NO_HOLDING = "NO_HOLDING"
    HOLDING_BETWEEN_LEVELS = "HOLDING_BETWEEN_LEVELS"


REASON_MESSAGES: dict[ReasonCode, str] = {
    ReasonCode.DATA_UNAVAILABLE: "CMP is not available. Refresh prices and try again.",
    ReasonCode.CONFIGURATION_MISSING: "Allocation or entry levels are missing. Update the strategy before generating orders.",
    ReasonCode.PRICE_NOT_IN_RANGE: "Current price is above the planned entry range. No entry order is required now.",
    ReasonCode.PRICE_TOO_FAR_FROM_PLAN: "Current price has moved far below the planned entry range. Review and revise entry levels before placing orders.",
    ReasonCode.ALLOCATION_COMPLETE: "Allocated capital for this symbol is already fully deployed.",
    ReasonCode.DUPLICATE_ORDER: "An active order already exists for this symbol and level.",
    ReasonCode.TRADE_ALREADY_DONE: "A buy trade was already completed today. Skipping to avoid duplicate entry.",
    ReasonCode.MANUAL_REVIEW_REQUIRED: "Price has moved significantly below the planned accumulation range. Automation is paused for manual review.",
    ReasonCode.DA_NOT_ELIGIBLE: "Dynamic averaging is not currently eligible for this holding.",
    ReasonCode.LOW_PROFIT_OPPORTUNITY: "Expected net profit is below the configured minimum after estimated charges.",
    ReasonCode.BROKER_VALIDATION_FAILED: "Order does not meet broker or exchange order constraints.",
    ReasonCode.THESIS_BREAK: "Price has moved significantly below the planned accumulation range. Automation is paused for manual review.",
    ReasonCode.SYSTEM_ERROR: "Unable to generate candidate due to an unexpected error.",
    ReasonCode.PRICE_ABOVE_OPPORTUNITY_WINDOW: "Current price is more than the configured opportunity window above the planned entry level.",
    ReasonCode.NO_AVERAGING_CAPACITY: "No meaningful averaging capacity is available at the current entry level.",
    ReasonCode.PRICE_NOT_READY_FOR_DA: "Current price has not fallen enough below average price for Dynamic Averaging.",
    ReasonCode.DA_DISABLED: "Dynamic Averaging is not enabled for this symbol.",
    ReasonCode.INVALID_ENTRY_LEVEL_ORDER: "Entry levels are invalid. Entry prices must be in descending order.",
    ReasonCode.ENTRY_STRATEGY_MISSING: "Entry strategy is missing for this holding.",
    ReasonCode.NO_HOLDING: "No holding found for this symbol.",
    ReasonCode.HOLDING_BETWEEN_LEVELS: "Holding value is between entry tranche levels. MLE activates only at a completed tranche boundary; Dynamic Averaging manages this position for now.",
}


@dataclass
class NormalizedCandidate:
    symbol: str
    exchange: str | None
    strategy_type: StrategyType
    side: str
    status: CandidateStatus
    status_severity: int
    signal: str | None
    cmp: float | None
    order_price: float | None
    trigger_price: float | None
    qty: int
    amount: float
    allocation: float | None
    current_holding_qty: float
    current_holding_value: float
    allocation_used_percent: float
    level_or_leg: str
    strategy_reference: str | None
    reason_code: ReasonCode | None
    reason_message: str | None
    suggested_action: str | None
    is_selectable: bool
    created_at: str
    additional_details: dict = field(default_factory=dict)


@dataclass
class SkippedCandidate:
    symbol: str
    exchange: str | None
    strategy_type: StrategyType
    cmp: float | None
    level_or_leg: str | None
    reason_code: ReasonCode
    reason_message: str
    suggested_action: str
    technical_details: str | None


@dataclass
class CandidateSummary:
    total: int
    ready: int
    warning: int
    review: int
    skipped: int
    capital_required: float


@dataclass
class CandidateResult:
    strategy_type: str
    candidates: list[NormalizedCandidate]
    skipped: list[SkippedCandidate]
    summary: CandidateSummary
