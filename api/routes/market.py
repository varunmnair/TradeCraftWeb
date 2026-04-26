"""Market data endpoints for app-level CMP and candles."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import get_global_cmp_manager
from core.cmp import CMPManager
from core.services.market_data_service import MarketDataService, get_market_data_service

router = APIRouter(prefix="/market", tags=["market"])
logger = logging.getLogger("tradecraftx.market")


class CmpRequest(BaseModel):
    symbols: list[str]
    exchange: str = "NSE"


class CandlesRequest(BaseModel):
    symbols: list[str]
    days: int = 400


@router.post("/cmp")
def get_cmp(
    request: CmpRequest,
    cmp_manager: CMPManager = Depends(get_global_cmp_manager),
):
    """Get CMP for symbols from in-memory cache. Auto-refreshes stale/missing symbols."""
    symbols_upper = [s.strip().upper() for s in request.symbols]
    exchange = request.exchange.upper()

    prices = cmp_manager.get_cmp_for_symbols(symbols_upper, exchange)
    
    errors = {}
    fetched_prices = {}
    for sym, price in prices.items():
        if price is not None:
            fetched_prices[sym] = price
        else:
            errors[sym] = f"CMP not available for {sym}"

    return {
        "prices": fetched_prices,
        "errors": errors,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "exchange": exchange,
    }


@router.post("/candles")
def get_candles(
    request: CandlesRequest,
    service: MarketDataService = Depends(get_market_data_service),
):
    """Get daily candles for symbols from app-level storage."""
    return service.get_candles(request.symbols, request.days)
