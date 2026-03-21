"""Repository for symbol catalog operations."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import SymbolCatalog


class SymbolCatalogRepository:
    def __init__(self, db: Session):
        self._db = db

    def purge_all(self) -> int:
        """Delete all rows from symbol_catalog. Returns count of deleted rows."""
        deleted = self._db.query(SymbolCatalog).delete()
        self._db.commit()
        return deleted

    def upsert_batch(self, symbols: List[Dict]) -> int:
        """Bulk insert/update symbols. Sets updated_at to now for all records.

        Args:
            symbols: List of dicts with keys: symbol, company_name, series, isin, exchange, cmp

        Returns:
            Number of records inserted/updated.
        """
        count = 0
        now = datetime.utcnow()

        for sym_data in symbols:
            symbol = sym_data["symbol"]
            existing = (
                self._db.query(SymbolCatalog)
                .filter(SymbolCatalog.symbol == symbol)
                .first()
            )

            if existing:
                existing.company_name = sym_data["company_name"]
                existing.series = sym_data["series"]
                existing.isin = sym_data["isin"]
                existing.exchange = sym_data["exchange"]
                existing.cmp = sym_data.get("cmp")
                existing.updated_at = now
            else:
                self._db.add(
                    SymbolCatalog(
                        symbol=symbol,
                        company_name=sym_data["company_name"],
                        series=sym_data["series"],
                        isin=sym_data["isin"],
                        exchange=sym_data["exchange"],
                        cmp=sym_data.get("cmp"),
                        updated_at=now,
                    )
                )
            count += 1

        self._db.commit()
        return count

    def get_count(self) -> int:
        """Return total symbol count."""
        return self._db.query(func.count(SymbolCatalog.symbol)).scalar() or 0

    def get_max_updated_at(self) -> Optional[datetime]:
        """Return max updated_at timestamp."""
        return self._db.query(func.max(SymbolCatalog.updated_at)).scalar()

    def get_all_symbols(self) -> List[str]:
        """Return all symbols."""
        results = self._db.query(SymbolCatalog.symbol).all()
        return [r[0] for r in results]

    def get_symbol_isin_map(self) -> Dict[str, str]:
        """Return dict mapping symbol to ISIN."""
        results = self._db.query(SymbolCatalog.symbol, SymbolCatalog.isin).all()
        return dict(results)

    def symbol_exists(self, symbol: str) -> bool:
        """Check if symbol exists."""
        return (
            self._db.query(func.count(SymbolCatalog.symbol))
            .filter(SymbolCatalog.symbol == symbol)
            .scalar()
            > 0
        )

    def get_all_for_cmp_refresh(self) -> List[Dict]:
        """Return all symbols with their ISIN for CMP refresh."""
        results = self._db.query(
            SymbolCatalog.symbol,
            SymbolCatalog.isin,
            SymbolCatalog.exchange,
            SymbolCatalog.series,
        ).all()
        return [
            {"symbol": r[0], "isin": r[1], "exchange": r[2], "series": r[3]}
            for r in results
        ]

    def update_cmp_batch(self, updates: Dict[str, float]) -> int:
        """Update CMP values for symbols. Returns count of updated records."""
        if not updates:
            return 0
        now = datetime.utcnow()
        count = 0
        for symbol, cmp_value in updates.items():
            result = (
                self._db.query(SymbolCatalog)
                .filter(SymbolCatalog.symbol == symbol)
                .update(
                    {
                        SymbolCatalog.cmp: cmp_value,
                        SymbolCatalog.updated_at: now,
                    }
                )
            )
            if result > 0:
                count += 1
        self._db.commit()
        return count

    def get_cmp_count(self) -> int:
        """Return count of symbols with CMP populated."""
        return (
            self._db.query(func.count(SymbolCatalog.symbol))
            .filter(SymbolCatalog.cmp.isnot(None))
            .scalar()
            or 0
        )

    def get_cmp_for_symbol(self, symbol: str) -> Optional[float]:
        """Get CMP for a single symbol."""
        result = (
            self._db.query(SymbolCatalog.cmp)
            .filter(SymbolCatalog.symbol == symbol)
            .scalar()
        )
        return result

    def get_cmp_for_symbols(self, symbols: List[str]) -> Dict[str, Optional[float]]:
        """Get CMP values for multiple symbols."""
        results = (
            self._db.query(SymbolCatalog.symbol, SymbolCatalog.cmp)
            .filter(SymbolCatalog.symbol.in_(symbols))
            .all()
        )
        return {r[0]: r[1] for r in results}
