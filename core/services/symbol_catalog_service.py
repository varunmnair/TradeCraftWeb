"""Service for symbol catalog operations."""

from __future__ import annotations

import csv
import logging
from contextlib import contextmanager
from typing import Dict, Generator, List, Optional

from sqlalchemy.orm import Session

from core.services.symbol_catalog_repository import SymbolCatalogRepository

LOGGER = logging.getLogger("tradecraftx.symbol_catalog_service")

MAX_FAILURES = 50


class SymbolCatalogService:
    def __init__(self, db_or_repo: Optional[Session | SymbolCatalogRepository] = None):
        if db_or_repo is None:
            self._db = None
            self._repo = None
        elif isinstance(db_or_repo, SymbolCatalogRepository):
            self._db = None
            self._repo = db_or_repo
        else:
            self._db = db_or_repo
            self._repo = None

    @contextmanager
    def _repo_context(self) -> Generator[SymbolCatalogRepository, None, None]:
        if self._repo is not None:
            yield self._repo
        elif self._db is not None:
            yield SymbolCatalogRepository(self._db)
        else:
            from db.database import SessionLocal

            db = SessionLocal()
            try:
                yield SymbolCatalogRepository(db)
            finally:
                db.close()

    def import_csv(self, csv_content: str, replace: bool = True) -> Dict:
        """Parse and import symbol catalog from CSV content.

        Args:
            csv_content: Raw CSV string content
            replace: If True, purge existing data before import

        Returns:
            Dict with operation results including total_rows, inserted, failed, failures
        """
        with self._repo_context() as repo:
            lines = csv_content.strip().split("\n")
            if not lines:
                return {
                    "operation": "symbol_catalog_import",
                    "total_rows": 0,
                    "inserted": 0,
                    "failed": 0,
                    "failures": [
                        {"row": 0, "symbol": "", "excerpt": "Empty CSV content"}
                    ],
                }

            reader = csv.DictReader(lines)
            headers = reader.fieldnames or []

            expected_headers = {"SYMBOL", "NAME OF COMPANY", "SERIES", "ISIN NUMBER"}
            actual_headers = {h.strip().upper() for h in headers if h}

            missing = expected_headers - actual_headers
            if missing:
                return {
                    "operation": "symbol_catalog_import",
                    "total_rows": 0,
                    "inserted": 0,
                    "failed": 0,
                    "failures": [
                        {
                            "row": 0,
                            "symbol": "",
                            "excerpt": f"Missing columns: {missing}",
                        }
                    ],
                }

            normalized_headers = {h.strip().upper(): h for h in headers if h}
            LOGGER.info(f"Detected CSV headers: {list(normalized_headers.keys())}")

            parsed_rows: List[Dict] = []
            failures: List[Dict] = []
            seen_symbols: Dict[str, int] = {}
            total_rows = 0

            for i, row in enumerate(reader, start=2):
                total_rows += 1

                raw_symbol = row.get(
                    normalized_headers.get("SYMBOL", "SYMBOL"), ""
                ).strip()
                if not raw_symbol:
                    failures.append(
                        {
                            "row": i,
                            "symbol": "",
                            "excerpt": "Missing SYMBOL",
                        }
                    )
                    continue

                symbol = raw_symbol.upper()

                if symbol in seen_symbols:
                    failures.append(
                        {
                            "row": i,
                            "symbol": symbol,
                            "excerpt": f"Duplicate SYMBOL (first seen at row {seen_symbols[symbol]})",
                        }
                    )
                    continue

                seen_symbols[symbol] = i

                company_name = row.get(
                    normalized_headers.get("NAME OF COMPANY", "NAME OF COMPANY"), ""
                ).strip()
                if not company_name:
                    failures.append(
                        {
                            "row": i,
                            "symbol": symbol,
                            "excerpt": "Missing company name",
                        }
                    )
                    continue

                series = (
                    row.get(normalized_headers.get("SERIES", "SERIES"), "")
                    .strip()
                    .upper()
                )
                if not series:
                    failures.append(
                        {
                            "row": i,
                            "symbol": symbol,
                            "excerpt": "Missing SERIES",
                        }
                    )
                    continue

                isin = (
                    row.get(normalized_headers.get("ISIN NUMBER", "ISIN NUMBER"), "")
                    .strip()
                    .upper()
                )
                if not isin:
                    failures.append(
                        {
                            "row": i,
                            "symbol": symbol,
                            "excerpt": "Missing ISIN",
                        }
                    )
                    continue

                exchange = (
                    row.get(normalized_headers.get("EXCHANGE", "EXCHANGE"), "")
                    .strip()
                    .upper()
                )
                if not exchange:
                    exchange = "NSE"

                parsed_rows.append(
                    {
                        "symbol": symbol,
                        "company_name": company_name,
                        "series": series,
                        "isin": isin,
                        "exchange": exchange,
                        "cmp": None,
                    }
                )

            LOGGER.info(
                f"Symbol catalog import: {total_rows} rows parsed, {len(parsed_rows)} valid, {len(failures)} failed"
            )

            if failures:
                LOGGER.warning(f"First 5 failures: {failures[:5]}")

            if replace:
                deleted = repo.purge_all()
                LOGGER.info(f"Purged {deleted} existing symbols")

            inserted = 0
            if parsed_rows:
                inserted = repo.upsert_batch(parsed_rows)
                LOGGER.info(f"Inserted/updated {inserted} symbols")

            all_failures = failures[:MAX_FAILURES]

            return {
                "operation": "symbol_catalog_import",
                "total_rows": total_rows,
                "inserted": inserted,
                "failed": len(failures),
                "failures": all_failures,
            }

    def get_status(self) -> Dict:
        """Get symbol catalog status.

        Returns:
            Dict with total_symbols and last_updated_at
        """
        with self._repo_context() as repo:
            total_symbols = repo.get_count()
            last_updated = repo.get_max_updated_at()

            return {
                "total_symbols": total_symbols,
                "last_updated_at": last_updated.isoformat() if last_updated else None,
            }

    def get_all_symbols(self) -> List[str]:
        """Get all symbols from catalog."""
        with self._repo_context() as repo:
            return repo.get_all_symbols()

    def get_symbol_isin_map(self) -> Dict[str, str]:
        """Get mapping of symbol to ISIN."""
        with self._repo_context() as repo:
            return repo.get_symbol_isin_map()
