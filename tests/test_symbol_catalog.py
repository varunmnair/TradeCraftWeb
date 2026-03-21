"""Tests for symbol catalog repository and service."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from core.services.symbol_catalog_repository import SymbolCatalogRepository
from core.services.symbol_catalog_service import SymbolCatalogService


class TestSymbolCatalogRepository:
    def test_upsert_batch_inserts_new(self, db_session):
        repo = SymbolCatalogRepository(db_session)

        count = repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
            {"symbol": "INFY", "company_name": "Infosys Limited", "series": "EQ", "isin": "INE009A01021", "exchange": "NSE"},
        ])

        assert count == 2

    def test_upsert_batch_updates_existing(self, db_session):
        repo = SymbolCatalogRepository(db_session)

        repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
        ])

        count = repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries Ltd", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
        ])

        assert count == 1
        all_symbols = repo.get_all_symbols()
        assert len(all_symbols) == 1

    def test_purge_all(self, db_session):
        repo = SymbolCatalogRepository(db_session)

        repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
            {"symbol": "INFY", "company_name": "Infosys Limited", "series": "EQ", "isin": "INE009A01021", "exchange": "NSE"},
        ])

        repo.purge_all()

        assert repo.get_count() == 0

    def test_get_count(self, db_session):
        repo = SymbolCatalogRepository(db_session)

        assert repo.get_count() == 0

        repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
            {"symbol": "INFY", "company_name": "Infosys Limited", "series": "EQ", "isin": "INE009A01021", "exchange": "NSE"},
        ])

        assert repo.get_count() == 2

    def test_get_all_symbols(self, db_session):
        repo = SymbolCatalogRepository(db_session)

        repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
            {"symbol": "INFY", "company_name": "Infosys Limited", "series": "EQ", "isin": "INE009A01021", "exchange": "NSE"},
            {"symbol": "TCS", "company_name": "Tata Consultancy Services", "series": "EQ", "isin": "INE467B01029", "exchange": "NSE"},
        ])

        symbols = repo.get_all_symbols()

        assert len(symbols) == 3
        assert "RELIANCE" in symbols
        assert "INFY" in symbols
        assert "TCS" in symbols

    def test_get_symbol_isin_map(self, db_session):
        repo = SymbolCatalogRepository(db_session)

        repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
            {"symbol": "INFY", "company_name": "Infosys Limited", "series": "EQ", "isin": "INE009A01021", "exchange": "NSE"},
        ])

        isin_map = repo.get_symbol_isin_map()

        assert isin_map["RELIANCE"] == "INE002A01018"
        assert isin_map["INFY"] == "INE009A01021"

    def test_get_max_updated_at(self, db_session):
        repo = SymbolCatalogRepository(db_session)

        assert repo.get_max_updated_at() is None

        repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
        ])

        max_updated = repo.get_max_updated_at()
        assert max_updated is not None


class TestSymbolCatalogService:
    def test_import_csv_creates_symbols(self, db_session, tmp_path):
        import csv

        csv_content = (
            "SYMBOL,NAME OF COMPANY,SERIES,ISIN NUMBER\n"
            "RELIANCE,Reliance Industries,EQ,INE002A01018\n"
            "INFY,Infosys Limited,EQ,INE009A01021\n"
        )

        repo = SymbolCatalogRepository(db_session)
        service = SymbolCatalogService(repo)
        result = service.import_csv(csv_content)

        assert result["total_rows"] == 2
        assert result["inserted"] == 2
        assert result["failed"] == 0
        assert len(result["failures"]) == 0

        assert repo.get_count() == 2

    def test_import_csv_handles_duplicates(self, db_session, tmp_path):
        csv_content1 = (
            "SYMBOL,NAME OF COMPANY,SERIES,ISIN NUMBER\n"
            "RELIANCE,Reliance Industries,EQ,INE002A01018\n"
        )

        repo = SymbolCatalogRepository(db_session)
        service = SymbolCatalogService(repo)
        result1 = service.import_csv(csv_content1)
        assert result1["inserted"] == 1

        csv_content2 = (
            "SYMBOL,NAME OF COMPANY,SERIES,ISIN NUMBER\n"
            "RELIANCE,Reliance Industries Ltd,EQ,INE002A01018\n"
            "INFY,Infosys Limited,EQ,INE009A01021\n"
        )

        result2 = service.import_csv(csv_content2)
        assert result2["inserted"] == 2

        assert repo.get_count() == 2

    def test_import_csv_invalid_headers(self, db_session):
        csv_content = "SYMBOL,COMPANY\nRELIANCE,Reliance Industries\n"

        repo = SymbolCatalogRepository(db_session)
        service = SymbolCatalogService(repo)
        result = service.import_csv(csv_content)

        assert "failures" in result
        assert len(result["failures"]) > 0
        assert "Missing columns" in result["failures"][0]["excerpt"]

    def test_get_status(self, db_session):
        repo = SymbolCatalogRepository(db_session)
        repo.upsert_batch([
            {"symbol": "RELIANCE", "company_name": "Reliance Industries", "series": "EQ", "isin": "INE002A01018", "exchange": "NSE"},
        ])

        service = SymbolCatalogService(repo)
        status = service.get_status()

        assert "total_symbols" in status
        assert status["total_symbols"] == 1
        assert "last_updated_at" in status
