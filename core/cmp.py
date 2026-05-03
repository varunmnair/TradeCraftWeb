import logging
import os
import time
from datetime import date, timedelta

import requests


class CMPManager:
    DEFAULT_TTL = 300

    def __init__(
        self,
        broker,
        session_manager,
        market_data_connection_id: int = None,
        ttl: int = DEFAULT_TTL,
    ):
        self.cache = {}
        self.last_updated = 0
        self.ttl = ttl
        self.broker = broker
        self.session_manager = session_manager
        self.market_data_connection_id = market_data_connection_id
        self._pending_symbols = set()

    def _is_cache_valid(self):
        return (time.time() - self.last_updated) < self.ttl

    def _is_stale(self, exchange: str, symbol: str) -> bool:
        key = (exchange.upper(), symbol.upper())
        return key not in self.cache

    def _round_cmp(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 1)

    # ──────────────── Symbol Collection ──────────────── #
    def _collect_symbols(self, holdings, gtts, entry_levels):
        def add_symbol(collection, exchange, symbol):
            # Ensure both exchange and symbol are valid, non-empty strings before adding.
            # This prevents errors from NaN values (floats) in data sources.
            exchange_str = str(exchange or "").strip().upper()
            symbol_str = str(symbol or "").strip().upper()

            if exchange_str and symbol_str and exchange_str != "NAN":
                collection.add((exchange_str, symbol_str.replace("#", "")))
            else:
                logging.debug(
                    f"Skipping invalid symbol data: exchange='{exchange}', symbol='{symbol}'"
                )

        symbols = set()
        for h in holdings:
            if isinstance(h, dict):
                add_symbol(symbols, h.get("exchange"), h.get("tradingsymbol"))
            else:
                add_symbol(
                    symbols,
                    getattr(h, "exchange", None),
                    getattr(h, "tradingsymbol", None),
                )

        # GTT symbols - check both condition and orders for exchange/symbol
        for g in gtts:
            # Try orders array first (has actual exchange/symbol)
            if g.get("orders") and g["orders"][0]:
                order = g["orders"][0]
                add_symbol(symbols, order.get("exchange"), order.get("tradingsymbol"))
            # Fall back to condition (may be None for some GTT types)
            elif g.get("condition"):
                add_symbol(
                    symbols,
                    g["condition"].get("exchange"),
                    g["condition"].get("tradingsymbol"),
                )

        for s in entry_levels:
            add_symbol(symbols, s.get("exchange"), s.get("symbol"))
        logging.debug(f"Collected {len(symbols)} symbols for CMP fetch: {symbols}")
        return list(symbols)

    # ──────────────── Instrument Key Mapping ──────────────── #
    def _get_instrument_key(self, symbol, segment):
        try:
            from core.services.symbol_catalog_service import SymbolCatalogService

            service = SymbolCatalogService()
            isin_map = service.get_symbol_isin_map()

            symbol_clean = str(symbol).replace("-BE", "").strip().upper()
            isin = isin_map.get(symbol_clean)

            if isin:
                return f"{segment}|{isin}"
            else:
                logging.warning(f"Symbol {symbol_clean} not found in symbol catalog.")
        except Exception as e:
            logging.error(f"Error getting instrument key from symbol catalog: {e}")
        return None

    # ──────────────── Quote Fetching ──────────────── #
    def _fetch_quotes(self, token, batch_keys):
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        params = {"instrument_key": ",".join(batch_keys)}
        url = "https://api.upstox.com/v3/market-quote/ltp"
        return requests.get(url, headers=headers, params=params)

    def _fetch_bulk_quote_upstox(self, symbols):
        # Use analytics token from env only
        token = os.environ.get("UPSTOX_ANALYTICS_TOKEN")
        if not token:
            logging.warning("UPSTOX_ANALYTICS_TOKEN not set. Skipping quote fetch.")
            return {}
        instrument_keys = []
        symbol_map = {}

        for exch, sym in symbols:
            segment = exch + "_EQ"
            instrument_key = self._get_instrument_key(sym, segment)
            if instrument_key:
                instrument_keys.append(instrument_key)
                normalized_key = f"{segment}:{sym}"
                symbol_map[normalized_key] = (exch, sym)
                # logging.debug(f"Mapped {normalized_key} -> ({exch}, {sym})")
            else:
                logging.warning(
                    f"Instrument key not found for {sym} in segment {segment}"
                )

        if not instrument_keys:
            logging.warning("No instrument keys found. Skipping quote fetch.")
            return {}

        quote_map = {}
        batch_size = 50

        for i in range(0, len(instrument_keys), batch_size):
            batch_keys = instrument_keys[i : i + batch_size]
            response = self._fetch_quotes(token, batch_keys)

            if response.status_code == 401:
                try:
                    error_data = response.json()
                    error_code = error_data.get("errors", [{}])[0].get("errorCode")
                    if error_code == "UDAPI100050":
                        logging.info(
                            "Invalid Upstox token detected. Regenerating token..."
                        )
                        token = self.session_manager.generate_new_upstox_token()
                        response = self._fetch_quotes(token, batch_keys)
                except Exception as e:
                    logging.error(f"Error while handling token regeneration: {e}")
                    continue

            if response.status_code != 200:
                logging.error(
                    f"Failed to fetch batch quote: {response.status_code} - {response.text}"
                )
                continue

            data = response.json().get("data", {})
            for key, quote in data.items():
                exch, sym = symbol_map.get(key, (None, None))
                if exch and sym:
                    quote_map[(exch, sym)] = quote
                    # logging.debug(f"✅ Added to cache: {sym} ({exch}) -> CMP: {quote.get('last_price')}")

        logging.debug(f"Fetched quotes for {len(quote_map)} symbols")
        return quote_map

    def refresh_for_symbols(self, keys: list[tuple[str, str]]):
        if not keys:
            return
        symbols = [(exch.upper(), sym.upper()) for exch, sym in keys]
        quotes = self._fetch_bulk_quote_upstox(symbols)
        if quotes:
            self.cache.update(quotes)
            self.last_updated = time.time()

    def refresh_cache(self, holdings=None, gtts=None, entry_levels=None):
        if holdings is None or gtts is None or entry_levels is None:
            raise ValueError("holdings, gtts, and entry_levels must be provided")
        symbols = self._collect_symbols(holdings, gtts, entry_levels)
        self.cache = self._fetch_bulk_quote_upstox(symbols)
        self.last_updated = time.time()
        logging.debug(f"CMP cache refreshed with {len(self.cache)} symbols.")

    def get_cmp(self, exchange: str, symbol: str, auto_refresh: bool = True) -> float | None:
        symbol_clean = str(symbol).replace("-BE", "").strip().upper()
        exchange_clean = exchange.upper()
        key = (exchange_clean, symbol_clean)

        if key in self.cache:
            quote = self.cache[key]
            return self._round_cmp(quote.get("last_price"))

        if auto_refresh:
            self._pending_symbols.add(key)
            self.refresh_for_symbols([key])
            self._pending_symbols.discard(key)
            if key in self.cache:
                quote = self.cache[key]
                return self._round_cmp(quote.get("last_price"))

        logging.debug(f"CMP not available for {symbol_clean} after refresh attempt")
        return None

    def get_cmp_for_symbols(
        self, symbols: list[str], exchange: str = "NSE"
    ) -> dict[str, float | None]:
        exchange_clean = exchange.upper()
        keys_needed = set()
        result = {}

        for sym in symbols:
            sym_clean = str(sym).replace("-BE", "").strip().upper()
            key = (exchange_clean, sym_clean)
            if key in self.cache:
                result[sym_clean] = self._round_cmp(self.cache[key].get("last_price"))
            else:
                keys_needed.add(key)
                result[sym_clean] = None

        if keys_needed:
            self._pending_symbols.update(keys_needed)
            self.refresh_for_symbols(list(keys_needed))
            self._pending_symbols.difference_update(keys_needed)

            for sym in symbols:
                sym_clean = str(sym).replace("-BE", "").strip().upper()
                key = (exchange_clean, sym_clean)
                if key in self.cache:
                    result[sym_clean] = self._round_cmp(self.cache[key].get("last_price"))

        return result

    def print_all_cmps(self):
        print("\n📊 Cached CMPs:")
        print(f"{'Symbol':<15} {'Exchange':<10} {'CMP':<10}")
        print("-" * 40)
        for (exchange, symbol), quote in self.cache.items():
            cmp = quote.get("last_price", "N/A")
            print(f"{symbol:<15} {exchange:<10} {cmp:<10}")

    # ──────────────── Historical Data ──────────────── #
    def get_historical_data(
        self, symbol, exchange="NSE", interval="day", to_date=None, from_date=None
    ):
        """
        Fetch historical candle data for a given symbol using the Upstox API.
        - The Upstox API URL format is /to_date/from_date.
        - Fetches last 90 days of data if from_date and to_date are not provided.
        """
        logging.debug(
            f"Getting historical data for {symbol} via CMPManager (Upstox proxy)"
        )

        segment = f"{exchange.upper()}_EQ"
        instrument_key = self._get_instrument_key(symbol, segment)
        if not instrument_key:
            logging.error(f"Could not resolve instrument key for symbol: {symbol}")
            return None

        # Set default dates if not provided
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=90)

        # Defensive check: Ensure `to_date` is not before `from_date`. Swap if necessary.
        if from_date > to_date:
            logging.warning(
                f"from_date {from_date} was after to_date {to_date}. Swapping them."
            )
            from_date, to_date = to_date, from_date

        # The API requires to_date >= from_date.
        end_date_str = to_date.strftime("%Y-%m-%d")
        start_date_str = from_date.strftime("%Y-%m-%d")

        # URL encode the instrument key to handle special characters like '|'
        encoded_instrument_key = requests.utils.quote(instrument_key)
        # Corrected URL format: The API expects /to_date/from_date
        url = f"https://api.upstox.com/v2/historical-candle/{encoded_instrument_key}/{interval}/{end_date_str}/{start_date_str}"
        logging.debug(f"Constructed historical data URL: {url}")

        try:
            connection_id = self.market_data_connection_id
            token = (
                self.session_manager.get_access_token(
                    "upstox", connection_id=connection_id
                )
                if self.session_manager
                else None
            )
            headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

            response = requests.get(url, headers=headers)
            response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)

            data = response.json()
            if data.get("status") != "success":
                logging.error(
                    f"Upstox API returned a non-success status for historical data: {data}"
                )
                return None

            logging.debug(
                f"Successfully fetched historical data for {symbol} via CMPManager"
            )
            return data.get("data", {}).get("candles", [])
        except requests.exceptions.RequestException as e:
            logging.error(
                f"Error fetching historical data from Upstox via CMPManager: {e}"
            )
            raise e  # Re-raise the exception to be caught by the caller
