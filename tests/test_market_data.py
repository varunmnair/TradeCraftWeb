"""Tests for market data repository and service."""

from __future__ import annotations

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from core.services.market_data_repository import MarketDataRepository
from core.services.market_data_service import MarketDataService
from core.services.market_data_refresh_service import MarketDataRefreshService
from core.services.symbol_catalog_service import SymbolCatalogService
from db.models import MarketCandleDaily, MarketQuoteDaily, MarketUniverse, OhlcvDaily


class TestMarketDataRepository:
    def test_get_quotes_for_symbols_returns_data_and_missing(self, db_session):
        repo = MarketDataRepository(db_session)

        db_session.add(MarketQuoteDaily(
            symbol="RELIANCE",
            trade_date="2025-03-19",
            cmp=2500.0,
            as_of_ts=None,
            source="test",
        ))
        db_session.commit()

        result = repo.get_quotes_for_symbols(["RELIANCE", "INFY"], "2025-03-19")

        assert result["RELIANCE"] == {"cmp": 2500.0, "as_of_ts": None, "source": "test"}
        assert result["INFY"] is None

    def test_get_quotes_for_symbols_missing_list(self, db_session):
        repo = MarketDataRepository(db_session)

        db_session.add(MarketQuoteDaily(
            symbol="RELIANCE",
            trade_date="2025-03-19",
            cmp=2500.0,
            as_of_ts=None,
            source="test",
        ))
        db_session.commit()

        result = repo.get_quotes_for_symbols(["RELIANCE", "INFY"], "2025-03-19")

        found = [s for s, v in result.items() if v is not None]
        missing = [s for s, v in result.items() if v is None]

        assert "RELIANCE" in found
        assert "INFY" in missing

    def test_upsert_quotes_inserts_new(self, db_session):
        repo = MarketDataRepository(db_session)

        result = repo.upsert_quotes({"TCS": 3500.0}, "2025-03-19", "test")

        assert result == 1
        quote = db_session.query(MarketQuoteDaily).filter(
            MarketQuoteDaily.symbol == "TCS"
        ).first()
        assert quote.cmp == 3500.0
        assert quote.trade_date == "2025-03-19"

    def test_upsert_quotes_updates_existing(self, db_session):
        repo = MarketDataRepository(db_session)

        db_session.add(MarketQuoteDaily(
            symbol="TCS",
            trade_date="2025-03-19",
            cmp=3000.0,
            as_of_ts=None,
            source="test",
        ))
        db_session.commit()

        result = repo.upsert_quotes({"TCS": 3500.0}, "2025-03-19", "test")

        assert result == 1
        quote = db_session.query(MarketQuoteDaily).filter(
            MarketQuoteDaily.symbol == "TCS"
        ).first()
        assert quote.cmp == 3500.0

    def test_get_candles_for_symbols_returns_data(self, db_session):
        repo = MarketDataRepository(db_session)
        
        from datetime import date, timedelta
        today = date.today()
        
        db_session.add(MarketCandleDaily(
            symbol="RELIANCE",
            trade_date=today.strftime("%Y-%m-%d"),
            open=2480.0,
            high=2510.0,
            low=2470.0,
            close=2500.0,
            volume=1000000,
            source="test",
        ))
        db_session.commit()

        result = repo.get_candles_for_symbols(["RELIANCE"], days=400)

        assert "RELIANCE" in result
        assert len(result["RELIANCE"]) == 1
        assert result["RELIANCE"][0]["close"] == 2500.0

    def test_get_candles_for_symbols_missing_symbols(self, db_session):
        repo = MarketDataRepository(db_session)
        
        from datetime import date
        today = date.today()

        db_session.add(MarketCandleDaily(
            symbol="RELIANCE",
            trade_date=today.strftime("%Y-%m-%d"),
            open=2480.0,
            high=2510.0,
            low=2470.0,
            close=2500.0,
            volume=1000000,
            source="test",
        ))
        db_session.commit()

        result = repo.get_candles_for_symbols(["RELIANCE", "INFY"], days=400)

        assert len(result["RELIANCE"]) == 1
        assert len(result["INFY"]) == 0

    def test_set_universe_symbols(self, db_session):
        repo = MarketDataRepository(db_session)

        count = repo.set_universe_symbols(["RELIANCE", "INFY", "TCS"], "NIFTY500")

        assert count == 3
        symbols = repo.get_universe_symbols("NIFTY500")
        assert "RELIANCE" in symbols
        assert "INFY" in symbols
        assert "TCS" in symbols


class TestMarketDataService:
    def test_get_cmp_returns_data_and_missing(self, db_session):
        repo = MarketDataRepository(db_session)
        service = MarketDataService(repo)

        db_session.add(MarketQuoteDaily(
            symbol="RELIANCE",
            trade_date="2025-03-19",
            cmp=2500.0,
            as_of_ts=None,
            source="test",
        ))
        db_session.commit()

        result = service.get_cmp(["RELIANCE", "INFY"], "2025-03-19")

        assert result["trade_date"] == "2025-03-19"
        assert result["data"]["RELIANCE"] == 2500.0
        assert "INFY" in result["missing"]

    def test_get_candles_returns_data_and_missing(self, db_session):
        repo = MarketDataRepository(db_session)
        service = MarketDataService(repo=repo)
        
        from datetime import date
        today = date.today()

        db_session.add(OhlcvDaily(
            symbol="RELIANCE",
            trade_date=today,
            open=2480.0,
            high=2510.0,
            low=2470.0,
            close=2500.0,
            volume=1000000,
        ))
        db_session.commit()

        result = service.get_candles(["RELIANCE", "INFY"], days=400)

        assert "RELIANCE" in result["data"]
        assert "INFY" in result["missing_symbols"]

    def test_get_cmp_handles_empty_symbols(self, db_session):
        repo = MarketDataRepository(db_session)
        service = MarketDataService(repo)

        result = service.get_cmp([], "2025-03-19")

        assert result["data"] == {}
        assert result["missing"] == []

    def test_get_universe_count(self, db_session):
        repo = MarketDataRepository(db_session)
        service = MarketDataService(repo)

        repo.set_universe_symbols(["A", "B", "C"], "NIFTY500")

        count = service.get_universe_count("NIFTY500")

        assert count == 3

    def test_init_universe_from_csv(self, db_session, tmp_path):
        import csv

        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["SYMBOL"])
            writer.writeheader()
            writer.writerow({"SYMBOL": "RELIANCE"})
            writer.writerow({"SYMBOL": "INFY"})
            writer.writerow({"SYMBOL": "TCS"})

        repo = MarketDataRepository(db_session)
        service = MarketDataService(repo)

        result = service.init_universe_from_csv(str(csv_file), "NIFTY500")

        assert result["added"] == 3
        assert result["total"] == 3

    def test_init_universe_from_csv_file_not_found(self, db_session):
        repo = MarketDataRepository(db_session)
        service = MarketDataService(repo)

        result = service.init_universe_from_csv("/nonexistent/file.csv", "NIFTY500")

        assert "error" in result


class TestMarketDataRefreshService:
    def test_get_status_returns_correct_structure(self, db_session):
        from core.services.symbol_catalog_repository import SymbolCatalogRepository

        repo = MarketDataRepository(db_session)
        service = MarketDataService(repo)

        catalog_repo = SymbolCatalogRepository(db_session)
        catalog_repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
            {"symbol": "INFY", "company_name": "Infosys Limited", "series": "EQ", "isin": "INE009A01021", "exchange": "NSE"},
        ])

        db_session.add(MarketQuoteDaily(
            symbol="RELIANCE",
            trade_date=date.today().strftime("%Y-%m-%d"),
            cmp=2500.0,
            as_of_ts=None,
            source="test",
        ))
        db_session.commit()

        catalog_service = SymbolCatalogService(catalog_repo)
        refresh_service = MarketDataRefreshService(repo)
        refresh_service._symbol_catalog_service = catalog_service

        status = refresh_service.get_status()

        assert "symbol_catalog_count" in status
        assert "coverage" in status
        assert "cmp_missing_count" in status["coverage"]
        assert "candles_missing_count" in status["coverage"]

    def test_incremental_candle_fetch_respects_last_date(self, db_session):
        from core.services.market_data_repository import MarketDataRepository

        repo = MarketDataRepository(db_session)

        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        db_session.add(MarketCandleDaily(
            symbol="RELIANCE",
            trade_date=yesterday,
            open=2400.0,
            high=2500.0,
            low=2390.0,
            close=2480.0,
            volume=1000000,
            source="test",
        ))
        db_session.commit()

        last_dates = repo._get_last_candle_dates(["RELIANCE"])

        assert last_dates["RELIANCE"] == date.fromisoformat(yesterday)

    def test_incremental_fetch_starts_from_next_day(self, db_session):
        from core.services.market_data_repository import MarketDataRepository

        repo = MarketDataRepository(db_session)

        last_week = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")

        db_session.add(MarketCandleDaily(
            symbol="RELIANCE",
            trade_date=last_week,
            open=2400.0,
            high=2500.0,
            low=2390.0,
            close=2480.0,
            volume=1000000,
            source="test",
        ))
        db_session.commit()

        last_dates = repo._get_last_candle_dates(["RELIANCE"])
        last_date = last_dates["RELIANCE"]

        from_date = last_date + timedelta(days=1) if last_date else date.today() - timedelta(days=450)

        assert from_date > date.fromisoformat(last_week)

    def test_get_status_with_empty_symbol_catalog(self, db_session):
        from core.services.symbol_catalog_repository import SymbolCatalogRepository

        repo = MarketDataRepository(db_session)
        symbol_repo = SymbolCatalogRepository(db_session)
        symbol_service = SymbolCatalogService(symbol_repo)
        
        refresh_service = MarketDataRefreshService(repo)
        refresh_service._symbol_catalog_service = symbol_service

        status = refresh_service.get_status()

        assert status["symbol_catalog_count"] == 0
        assert status["coverage"]["cmp_missing_count"] == 0
        assert status["coverage"]["candles_missing_count"] == 0