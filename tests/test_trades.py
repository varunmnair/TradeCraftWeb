"""Tests for trades service and readiness."""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from core.services.trades_repository import TradesRepository
from core.services.trades_service import TradesService
from db.models import MarketCandleDaily, MarketQuoteDaily, MarketUniverse, UserTrade


class TestTradesRepository:
    def test_upsert_trades_inserts_new(self, db_session):
        repo = TradesRepository(db_session)

        trades = [{
            "user_id": 1,
            "broker": "upstox",
            "symbol": "RELIANCE",
            "isin": "INE002A01018",
            "trade_date": "2025-03-19",
            "exchange": "NSE",
            "segment": "EQ",
            "series": "EQ",
            "side": "BUY",
            "quantity": 10,
            "price": 2500.0,
            "trade_id": "T001",
            "order_id": "O001",
            "order_execution_time": "2025-03-19T10:00:00",
            "source": "upstox_api",
        }]

        count = repo.upsert_trades(trades)

        assert count == 1
        saved = db_session.query(UserTrade).filter(
            UserTrade.user_id == 1,
            UserTrade.trade_id == "T001"
        ).first()
        assert saved is not None
        assert saved.symbol == "RELIANCE"

    def test_upsert_trades_de_duplicates(self, db_session):
        repo = TradesRepository(db_session)

        trade = {
            "user_id": 1,
            "broker": "upstox",
            "symbol": "RELIANCE",
            "isin": "INE002A01018",
            "trade_date": "2025-03-19",
            "exchange": "NSE",
            "segment": "EQ",
            "series": "EQ",
            "side": "BUY",
            "quantity": 10,
            "price": 2500.0,
            "trade_id": "T001",
            "order_id": "O001",
            "order_execution_time": "2025-03-19T10:00:00",
            "source": "upstox_api",
        }

        repo.upsert_trades([trade])
        repo.upsert_trades([trade])

        count = db_session.query(UserTrade).filter(
            UserTrade.user_id == 1,
            UserTrade.trade_id == "T001"
        ).count()

        assert count == 1

    def test_get_trade_count(self, db_session):
        repo = TradesRepository(db_session)

        db_session.add(UserTrade(
            user_id=1,
            broker="upstox",
            symbol="RELIANCE",
            trade_date="2025-03-19",
            side="BUY",
            quantity=10,
            price=2500.0,
            trade_id="T001",
            source="upstox_api",
        ))
        db_session.commit()

        count = repo.get_trade_count(1, "upstox")

        assert count == 1

    def test_get_trade_count_with_date_filter(self, db_session):
        repo = TradesRepository(db_session)

        db_session.add(UserTrade(
            user_id=1,
            broker="upstox",
            symbol="RELIANCE",
            trade_date=(date.today() - timedelta(days=500)).strftime("%Y-%m-%d"),
            side="BUY",
            quantity=10,
            price=2500.0,
            trade_id="T001",
            source="upstox_api",
        ))
        db_session.commit()

        from_date = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        count = repo.get_trade_count(1, "upstox", from_date)

        assert count == 0


class TestTradesService:
    def test_readiness_with_missing_trades(self, db_session):
        repo = TradesRepository(db_session)
        from core.services.market_data_repository import MarketDataRepository
        market_repo = MarketDataRepository(db_session)

        db_session.add(MarketQuoteDaily(
            symbol="RELIANCE",
            trade_date=date.today().strftime("%Y-%m-%d"),
            cmp=2500.0,
            as_of_ts=None,
            source="test",
        ))
        db_session.commit()

        service = TradesService(repo, market_repo)
        readiness = service.get_readiness(
            user_id=1,
            broker="upstox",
            holdings_symbols=["RELIANCE"],
        )

        assert readiness["trades_ready"] is False
        assert readiness["blocking_reason"] == "TRADES_SYNC_REQUIRED"
        assert "RELIANCE" in readiness["missing"]["trades"]

    def test_readiness_with_missing_market_data(self, db_session):
        repo = TradesRepository(db_session)
        from core.services.market_data_repository import MarketDataRepository
        market_repo = MarketDataRepository(db_session)

        db_session.add(UserTrade(
            user_id=1,
            broker="upstox",
            symbol="RELIANCE",
            trade_date="2025-03-19",
            side="BUY",
            quantity=10,
            price=2500.0,
            trade_id="T001",
            source="upstox_api",
        ))
        db_session.commit()

        service = TradesService(repo, market_repo)
        readiness = service.get_readiness(
            user_id=1,
            broker="upstox",
            holdings_symbols=["RELIANCE"],
        )

        assert readiness["trades_ready"] is True
        assert readiness["market_data_ready"] is False
        assert readiness["blocking_reason"] == "MARKET_DATA_MISSING"

    def test_readiness_zerodha_requires_upload(self, db_session):
        repo = TradesRepository(db_session)
        from core.services.market_data_repository import MarketDataRepository
        market_repo = MarketDataRepository(db_session)

        service = TradesService(repo, market_repo)
        readiness = service.get_readiness(
            user_id=1,
            broker="zerodha",
            holdings_symbols=["RELIANCE"],
        )

        assert readiness["broker"] == "zerodha"
        assert readiness["trades_ready"] is False
        assert readiness["blocking_reason"] == "TRADEBOOK_NOT_UPLOADED"

    def test_upload_zerodha_tradebook_valid_csv(self, db_session):
        repo = TradesRepository(db_session)
        service = TradesService(repo)

        csv_content = """symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time
RELIANCE,INE002A01018,2025-03-19,NSE,EQ,EQ,BUY,false,10,2500,T001,O001,2025-03-19 10:00:00
INFY,INE009A01021,2025-03-19,NSE,EQ,EQ,BUY,false,20,1500,T002,O002,2025-03-19 11:00:00"""

        result = service.upload_zerodha_tradebook(1, csv_content)

        assert result["rows_ingested"] == 2
        assert result["symbols_covered"] == 2
        assert len(result["errors"]) == 0

    def test_upload_zerodha_tradebook_missing_headers(self, db_session):
        repo = TradesRepository(db_session)
        service = TradesService(repo)

        csv_content = """symbol,quantity,price
RELIANCE,10,2500"""

        result = service.upload_zerodha_tradebook(1, csv_content)

        assert result["rows_ingested"] == 0
        assert "Missing columns" in result["errors"][0]