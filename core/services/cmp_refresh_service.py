"""CMP refresh service using Upstox market quotes API."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from core.session_manager import SessionManager

LOGGER = logging.getLogger("tradecraftx.cmp_refresh")

BATCH_SIZE = 20
SLEEP_BETWEEN_BATCHES = 2
MAX_FAILURES = 100


class CMPRefreshService:
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        connection_id: Optional[int] = None,
    ):
        self._session_manager = session_manager
        self._connection_id = connection_id

    def refresh(
        self,
        session_manager: SessionManager,
        connection_id: int,
    ) -> Dict[str, Any]:
        LOGGER.info("=== Starting CMP refresh ===")

        from core.services.symbol_catalog_repository import SymbolCatalogRepository
        from db.database import SessionLocal

        db = SessionLocal()
        try:
            repo = SymbolCatalogRepository(db)
            symbols_data = repo.get_all_for_cmp_refresh()
        finally:
            db.close()

        if not symbols_data:
            LOGGER.warning("No symbols in symbol catalog")
            return {
                "operation": "cmp_refresh",
                "total": 0,
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "failures": [],
            }

        LOGGER.info(f"Found {len(symbols_data)} symbols in catalog")

        SUPPORTED_SEGMENTS = {"NSE_EQ", "BSE_EQ"}

        instrument_keys_map = {}
        skipped_segments = {}
        sample_keys = []
        for item in symbols_data:
            exchange = (item.get("exchange") or "NSE").upper()
            series = (item.get("series") or "EQ").upper()
            segment = f"{exchange}_{series}"
            isin = item.get("isin", "")
            if isin:
                if segment not in SUPPORTED_SEGMENTS:
                    skipped_segments[segment] = skipped_segments.get(segment, 0) + 1
                    continue
                key = f"{segment}|{isin}"
                instrument_keys_map[key] = item["symbol"]
                if len(sample_keys) < 5:
                    sample_keys.append((key, item["symbol"], isin))

        skipped_count = sum(skipped_segments.values())
        if skipped_segments:
            LOGGER.warning(f"Skipped unsupported segments: {skipped_segments}")

        LOGGER.info(f"Built {len(instrument_keys_map)} instrument keys (skipped {skipped_count} unsupported segments)")
        LOGGER.info(f"Sample keys: {sample_keys}")

        total = len(symbols_data)
        token = session_manager.get_access_token("upstox", connection_id=connection_id)
        if not token:
            LOGGER.error("UPSTOX_NOT_CONNECTED: No access token found")
            return {
                "operation": "cmp_refresh",
                "total": total,
                "processed": 0,
                "succeeded": 0,
                "failed": total,
                "skipped": skipped_count,
                "failures": [
                    {"symbol": s["symbol"], "excerpt": "No access token"}
                    for s in symbols_data[:MAX_FAILURES]
                ],
            }

        succeeded = 0
        failed = 0
        failures: List[Dict] = []

        keys_list = list(instrument_keys_map.keys())

        for i in range(0, len(keys_list), BATCH_SIZE):
            batch_keys = keys_list[i : i + BATCH_SIZE]
            batch_start = i
            batch_end = min(i + BATCH_SIZE, len(keys_list))
            LOGGER.info(
                f"Processing batch {batch_start + 1}-{batch_end} of {len(keys_list)}"
            )

            batch_result = self._fetch_batch(batch_keys, instrument_keys_map, token)

            if batch_result["updates"]:
                from db.database import SessionLocal

                db = SessionLocal()
                try:
                    repo = SymbolCatalogRepository(db)
                    repo.update_cmp_batch(batch_result["updates"])
                    db.commit()
                except Exception as e:
                    db.rollback()
                    LOGGER.error(f"DB error during CMP update: {e}")
                finally:
                    db.close()
                succeeded += len(batch_result["updates"])

            failed += len(batch_result["failures"])
            failures.extend(batch_result["failures"])

            LOGGER.info(
                f"Batch complete: +{len(batch_result['updates'])} succeeded, +{len(batch_result['failures'])} failed"
            )

            if i + BATCH_SIZE < len(keys_list):
                time.sleep(SLEEP_BETWEEN_BATCHES)

        LOGGER.info(
            f"=== CMP refresh complete: {succeeded}/{total} succeeded, {failed} failed, {skipped_count} skipped ==="
        )

        return {
            "operation": "cmp_refresh",
            "total": total,
            "processed": succeeded + failed,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped_count,
            "failures": failures[:MAX_FAILURES],
        }

    def _fetch_batch(
        self,
        keys: List[str],
        symbol_map: Dict[str, str],
        token: str,
    ) -> Dict[str, Any]:
        import requests

        url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={quote(','.join(keys), safe='')}"

        updates: Dict[str, float] = {}
        batch_failures: List[Dict] = []

        try:
            response = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=30,
            )

            LOGGER.info(f"Upstox API response status: {response.status_code}")
            LOGGER.info(f"Requested {len(symbol_map)} symbols")
            if response.status_code != 200:
                LOGGER.warning(f"Upstox API error response: {response.text[:500]}")

            if response.status_code == 200:
                data = response.json()

                if data.get("status") != "success":
                    LOGGER.warning(f"Upstox API returned error status: {data}")
                    for key in symbol_map:
                        batch_failures.append(
                            {
                                "symbol": symbol_map[key],
                                "excerpt": f"API error: {data.get('errors', [{}])[0].get('message', 'Unknown error')}",
                            }
                        )
                    return {"updates": updates, "failures": batch_failures}

                quotes_data = data.get("data", {})

                LOGGER.info(
                    f"API returned {len(quotes_data)} quotes for {len(symbol_map)} requested"
                )

                found_instrument_tokens = set()
                matched_count = 0
                unmatched_instrument_tokens = []
                for key, quote_info in quotes_data.items():
                    instrument_token = quote_info.get("instrument_token")
                    if not instrument_token:
                        LOGGER.debug(f"No instrument_token in quote for {key}")
                        continue

                    symbol = symbol_map.get(instrument_token)
                    if not symbol:
                        unmatched_instrument_tokens.append((key, instrument_token))
                        continue

                    found_instrument_tokens.add(instrument_token)
                    matched_count += 1

                    last_price = quote_info.get("last_price")
                    if last_price is not None:
                        try:
                            updates[symbol] = float(last_price)
                        except (ValueError, TypeError):
                            batch_failures.append(
                                {
                                    "symbol": symbol,
                                    "excerpt": f"Invalid price value: {last_price}",
                                }
                            )
                    else:
                        batch_failures.append(
                            {
                                "symbol": symbol,
                                "excerpt": "No last_price in response",
                            }
                        )

                LOGGER.info(
                    f"Matched {matched_count} quotes, {len(unmatched_instrument_tokens)} unmatched in response"
                )
                LOGGER.info(f"Sample requested tokens: {list(symbol_map.keys())[:3]}")
                if unmatched_instrument_tokens[:3]:
                    LOGGER.info(
                        f"Sample unmatched in response: {unmatched_instrument_tokens[:3]}"
                    )

                missing_tokens = set(keys) - found_instrument_tokens
                for token_key in missing_tokens:
                    symbol = symbol_map.get(token_key)
                    if symbol:
                        batch_failures.append(
                            {
                                "symbol": symbol,
                                "excerpt": f"Symbol not in API response (token: {token_key})",
                            }
                        )

                if missing_tokens:
                    LOGGER.warning(f"Missing tokens sample: {list(missing_tokens)[:5]}")

            elif response.status_code == 401:
                LOGGER.error("Upstox API returned 401 Unauthorized")
                for key in keys:
                    symbol = symbol_map.get(key, key)
                    batch_failures.append(
                        {
                            "symbol": symbol,
                            "excerpt": "Unauthorized - reconnect broker",
                        }
                    )
            else:
                LOGGER.warning(f"Upstox API returned {response.status_code}")
                for key in keys:
                    symbol = symbol_map.get(key, key)
                    batch_failures.append(
                        {
                            "symbol": symbol,
                            "excerpt": f"API error: {response.status_code}",
                        }
                    )

        except requests.RequestException as e:
            LOGGER.error(f"Request failed: {e}")
            for key in keys:
                symbol = symbol_map.get(key, key)
                batch_failures.append(
                    {
                        "symbol": symbol,
                        "excerpt": f"Request failed: {type(e).__name__}",
                    }
                )
        except Exception as e:
            LOGGER.exception(f"Unexpected error in batch fetch: {e}")
            for key in keys:
                symbol = symbol_map.get(key, key)
                batch_failures.append(
                    {
                        "symbol": symbol,
                        "excerpt": f"Error: {type(e).__name__}",
                    }
                )

        return {"updates": updates, "failures": batch_failures}
