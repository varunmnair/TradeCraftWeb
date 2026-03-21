"""Market data endpoints for app-level CMP and candles."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.services.market_data_service import MarketDataService, get_market_data_service

router = APIRouter(prefix="/market", tags=["market"])


class CmpRequest(BaseModel):
    symbols: List[str]
    trade_date: Optional[str] = None


class CandlesRequest(BaseModel):
    symbols: List[str]
    days: int = 400


@router.post("/cmp")
def get_cmp(
    request: CmpRequest,
    service: MarketDataService = Depends(get_market_data_service),
):
    """Get CMP for symbols from app-level storage."""
    return service.get_cmp(request.symbols, request.trade_date)


@router.post("/candles")
def get_candles(
    request: CandlesRequest,
    service: MarketDataService = Depends(get_market_data_service),
):
    """Get daily candles for symbols from app-level storage."""
    return service.get_candles(request.symbols, request.days)
