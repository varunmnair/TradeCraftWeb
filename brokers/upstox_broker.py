from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

import requests
import upstox_client
from upstox_client.rest import ApiException

from core.session_manager import SessionManager
from core.utils import get_symbol_from_isin, read_csv, write_csv

from .base_broker import BaseBroker


class UpstoxBroker(BaseBroker):
    """
    Concrete implementation for Upstox broker using upstox-python-sdk v2.
    """

    TOKEN_ERROR = (
        "Upstox token expired or invalid. Please reconnect from Broker Connections."
    )

    def __init__(
        self,
        broker_user_id,
        api_key,
        api_secret,
        redirect_uri,
        code=None,
        access_token=None,
    ):
        super().__init__(broker_user_id)
        self.broker_name = "upstox"
        self.broker_user_id = broker_user_id
        self.configuration = upstox_client.Configuration()
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.session_manager: Optional[SessionManager] = None
        self.connection_id: Optional[int] = None
        self._trades = []
        self.TRANSACTION_TYPE_BUY = "BUY"
        self.TRANSACTION_TYPE_SELL = "SELL"
        self.GTT_TYPE_SINGLE = "single"
        self.GTT_TYPE_OCO = "two-leg"
        self.ORDER_TYPE_LIMIT = "LIMIT"
        self.PRODUCT_CNC = "CNC"
        self.csv_path = "c:\\Users\\nairv1\\OneDrive - Pegasystems Inc\\code\\pycode\\data\\Name-symbol-mapping.csv"

        # API clients will be initialized after login
        self.login_api = None
        self.order_api = None
        self.portfolio_api = None
        self.market_quote_api = None
        self.history_api = None

    def set_session_context(
        self, *, session_manager: SessionManager, connection_id: Optional[int]
    ) -> None:
        self.session_manager = session_manager
        self.connection_id = connection_id

    def _get_access_token(self) -> str:
        from datetime import datetime, timezone
        
        if self.session_manager and self.connection_id:
            bundle = self.session_manager.get_token_bundle(
                "upstox", connection_id=self.connection_id
            )
            if not bundle:
                raise RuntimeError(self.TOKEN_ERROR)
            
            if bundle.expires_at:
                expires_dt = bundle.expires_at
                if isinstance(expires_dt, str):
                    expires_dt = datetime.fromisoformat(expires_dt)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                
                if datetime.now(timezone.utc) >= expires_dt:
                    raise RuntimeError(
                        "Upstox token has expired. Please reconnect from Broker Connections."
                    )
            
            return bundle.access_token
        
        if self.access_token:
            return self.access_token
        raise RuntimeError(self.TOKEN_ERROR)

    def _get_instrument_key(self, symbol, segment):
        try:
            from core.services.symbol_catalog_service import SymbolCatalogService

            service = SymbolCatalogService()
            isin_map = service.get_symbol_isin_map()

            symbol_clean = symbol.replace("-BE", "").strip().upper()
            isin = isin_map.get(symbol_clean)

            if isin:
                return f"{segment}|{isin}"
            else:
                logging.warning(f"Symbol {symbol_clean} not found in symbol catalog.")
        except Exception as e:
            logging.error(f"Error getting instrument key from symbol catalog: {e}")
        return None

    def login(self):
        """
        Authenticate and establish a session with the broker.
        """
        logging.debug(f"Logging in to Upstox for user {self.broker_user_id}")
        try:
            token = self._get_access_token()
            self.configuration.access_token = token
            api_client = upstox_client.ApiClient(self.configuration)

            # Initialize the specific API clients
            self.login_api = upstox_client.LoginApi(api_client)
            self.order_api = upstox_client.OrderApi(api_client)
            self.portfolio_api = upstox_client.PortfolioApi(api_client)
            self.market_quote_api = upstox_client.MarketQuoteApi(api_client)
            self.history_api = upstox_client.HistoryApi(api_client)

            logging.debug(
                f"Successfully logged in to Upstox for user {self.broker_user_id} using existing token."
            )

        except Exception as e:
            logging.debug(f"Error logging in to Upstox: {e}")
            raise

    def logout(self):
        """
        Log out and terminate the session by revoking the access token.
        """
        logging.debug(f"Logging out from Upstox for user {self.broker_user_id}")
        try:
            if self.login_api:
                self.login_api.revoke_access_token("v2")
                logging.debug("Successfully logged out from Upstox (token revoked).")
        except ApiException as e:
            logging.debug(f"Error logging out from Upstox: {e}")

    def get_holdings(self):
        """
        Retrieve the user's current holdings and transform them into a list of dictionaries
        matching the Zerodha format.
        """
        logging.debug("Getting holdings from Upstox")
        try:
            api_response = self.portfolio_api.get_holdings("v2")
            holdings_data = api_response.data
            # logging.debug(f"holdings_data: {holdings_data}")
            holdings = []
            for item in holdings_data:
                holding_dict = {
                    "tradingsymbol": getattr(item, "tradingsymbol", None),
                    "exchange": getattr(item, "exchange", None),
                    "instrument_token": getattr(item, "instrument_token", None),
                    "isin": getattr(item, "isin", None),
                    "product": getattr(item, "product", None),
                    "price": getattr(item, "price", 0),
                    "quantity": getattr(item, "quantity", 0),
                    "used_quantity": getattr(item, "used_quantity", 0),
                    "t1_quantity": getattr(item, "t1_quantity", 0),
                    "realised_quantity": getattr(item, "realised_quantity", 0),
                    "authorised_quantity": getattr(item, "authorised_quantity", 0),
                    "authorised_date": getattr(item, "authorised_date", None),
                    "authorisation": {},
                    "opening_quantity": getattr(item, "opening_quantity", 0),
                    "short_quantity": 0,
                    "collateral_quantity": getattr(item, "collateral_quantity", 0),
                    "collateral_type": getattr(item, "collateral_type", ""),
                    "discrepancy": getattr(item, "discrepancy", False),
                    "average_price": getattr(item, "average_price", 0),
                    "last_price": getattr(item, "last_price", 0),
                    "close_price": getattr(item, "close_price", 0),
                    "pnl": getattr(item, "pnl", 0),
                    "day_change": getattr(item, "day_change", 0),
                    "day_change_percentage": getattr(item, "day_change_percentage", 0),
                    "mtf": {
                        "quantity": 0,
                        "used_quantity": 0,
                        "average_price": 0,
                        "value": 0,
                        "initial_margin": 0,
                    },
                }
                holdings.append(holding_dict)
            # logging.debug(f"Holdings: {holdings}")
            return holdings
        except ApiException as e:
            if getattr(e, "status", None) in (401, 403):
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error getting holdings from Upstox: {e}")
            return []

    def _get_gtt_headers(self):
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_gtt_orders(self):
        """
        Retrieve the user's Good Till Triggered (GTT) orders.
        """
        logging.debug("Getting GTT orders from Upstox")
        try:
            url = "https://api.upstox.com/v3/order/gtt"
            headers = self._get_gtt_headers()
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            gtc_data = response.json().get("data", [])
            # logging.debug(f"gtc_data: {gtc_data}")

            gtt_orders = []
            for g in gtc_data:
                # Find the ENTRY rule and discard others
                entry_rule = None
                if "rules" in g and isinstance(g["rules"], list):
                    for rule in g["rules"]:
                        if rule.get("strategy") == "ENTRY":
                            entry_rule = rule
                            break

                # If no ENTRY rule is found, skip this record
                if not entry_rule:
                    continue

                # Combine original GTC data with the entry rule data
                processed_data = g.copy()
                processed_data.update(entry_rule)

                # Format dates
                def format_timestamp(ts):
                    if not isinstance(ts, int) or ts < 0:
                        return None
                    try:
                        # Assuming timestamp is in microseconds
                        return datetime.fromtimestamp(ts / 1000000).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    except (ValueError, TypeError, OSError):
                        return None

                created_at = format_timestamp(processed_data.get("created_at"))
                expires_at = format_timestamp(processed_data.get("expires_at"))
                # The user's desired format has updated_at. Let's use created_at as a fallback.
                updated_at = format_timestamp(
                    processed_data.get("updated_at", processed_data.get("created_at"))
                )

                # Transform status
                status = processed_data.get("status")
                if status == "SCHEDULED":
                    status = "active"

                # Trim _EQ from exchange
                exchange = processed_data.get("exchange")
                if exchange and exchange.endswith("_EQ"):
                    exchange = exchange[:-3]

                # Build the final nested order dictionary
                order = {
                    "id": processed_data.get("gtt_order_id"),
                    "user_id": self.broker_user_id,
                    "parent_trigger": None,
                    "type": processed_data.get("type", "single"),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "expires_at": expires_at,
                    "status": status,
                    "condition": {
                        "exchange": exchange,
                        "last_price": None,  # Not available from Upstox GTT list API
                        "tradingsymbol": processed_data.get("trading_symbol"),
                        "trigger_values": [processed_data.get("trigger_price")],
                        "instrument_token": processed_data.get("instrument_token"),
                    },
                    "orders": [
                        {
                            "exchange": exchange,
                            "tradingsymbol": processed_data.get("trading_symbol"),
                            "product": "CNC",  # Assuming CNC, as product is not in Upstox GTT response
                            "order_type": "LIMIT",  # Assuming LIMIT, as order_type is not in Upstox GTT response
                            "transaction_type": processed_data.get("transaction_type"),
                            "quantity": processed_data.get("quantity"),
                            "price": processed_data.get(
                                "trigger_price"
                            ),  # price is not in the root, but trigger_price is. Assuming this is what's wanted.
                            "result": None,
                        }
                    ],
                    "meta": {},
                }
                gtt_orders.append(order)

            # logging.debug(f"GTT Orders: {gtt_orders}")
            return gtt_orders

        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code in (401, 403):
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error getting GTT orders from Upstox: {e}")
            return []

    def place_gtt(self, **kwargs):
        """
        Place a single-leg GTT order.
        Handles both Upstox-style and Zerodha-style arguments.
        """
        if (
            "instrument_token" in kwargs
            and "transaction_type" in kwargs
            and "quantity" in kwargs
            and "trigger_price" in kwargs
        ):
            # Upstox-style arguments
            instrument_token = kwargs["instrument_token"]
            transaction_type = kwargs["transaction_type"]
            quantity = kwargs["quantity"]
            trigger_price = kwargs["trigger_price"]
        else:
            # Zerodha-style arguments
            tradingsymbol = kwargs["tradingsymbol"]
            exchange = kwargs["exchange"]
            segment = f"{exchange.upper()}_EQ"
            instrument_token = self._get_instrument_key(tradingsymbol, segment)
            if not instrument_token:
                raise Exception(f"Could not find instrument key for {tradingsymbol}")

            orders = kwargs["orders"]
            transaction_type = orders[0]["transaction_type"]
            quantity = orders[0]["quantity"]
            trigger_values = kwargs["trigger_values"]
            trigger_price = trigger_values[0]

        order_details = {
            "type": "SINGLE",
            "quantity": int(quantity),
            "product": "D",  # Assuming Delivery
            "rules": [
                {
                    "strategy": "ENTRY",
                    "trigger_type": "BELOW",  # This might need to be configurable
                    "trigger_price": round(float(trigger_price)),
                }
            ],
            "instrument_token": instrument_token,
            "transaction_type": transaction_type.upper(),
        }
        return self.place_gtt_order(order_details)

    def place_gtt_order(self, order_details):
        """
        Place a GTT order.
        """
        # logging.debug(f"Placing GTT order in Upstox: {order_details}")
        try:
            url = "https://api.upstox.com/v3/order/gtt/place"
            headers = self._get_gtt_headers()
            response = requests.post(
                url, headers=headers, data=json.dumps(order_details)
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code in (401, 403):
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.error(f"Error placing GTT order in Upstox: {e}")
            if e.response is not None:
                logging.error(f"Response body: {e.response.text}")
            raise

    def modify_gtt(self, order_id, order_details):
        """
        Modify an existing GTT order.
        """
        logging.debug(f"Modifying GTT in Upstox: {order_id}")
        try:
            url = f"https://api.upstox.com/v2/gtt/orders/{order_id}"
            headers = self._get_gtt_headers()
            response = requests.put(
                url, headers=headers, data=json.dumps(order_details)
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code in (401, 403):
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error modifying GTT in Upstox: {e}")
            raise

    def cancel_gtt(self, order_id):
        """
        Cancel a GTT order.
        """
        logging.debug(f"Cancelling GTT in Upstox: {order_id}")
        try:
            url = "https://api.upstox.com/v3/order/gtt/cancel"
            headers = self._get_gtt_headers()
            payload = {"gtt_order_id": order_id}
            response = requests.delete(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code in (401, 403):
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error cancelling GTT in Upstox: {e}")
            raise

    def get_trades(self):
        """
        Retrieve the user's trades from the trade book.
        """
        file_path = f"data/{self.broker_user_id}_trade_book.csv"
        logging.debug(f"Getting trades from {file_path} for Upstox")
        if os.path.exists(file_path):
            self._trades = read_csv(file_path)
        return self._trades

    def trades(self, days: int = 400):
        """
        Retrieve ALL user's trades from the broker's API using /v2/charges/historical-trades
        with pagination support. Fetches all pages until no more data is available.
        
        Args:
            days: Number of days of history to fetch (default: 400)
            
        Returns:
            List of formatted trades matching the internal trade structure
        """
        logging.info(f"Getting trades from Upstox historical-trades API (days={days})")
        
        try:
            # Get access token
            access_token = None
            if hasattr(self, 'session_manager') and self.session_manager:
                access_token = self.session_manager.get_access_token("upstox")
            
            if not access_token:
                logging.error("No access token available for Upstox trades API")
                return []
            
            # Calculate date range based on requested days
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            url = "https://api.upstox.com/v2/charges/historical-trades"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            }
            
            # Log curl command for debugging (first page only)
            curl_cmd = f'curl -H "Authorization: Bearer {access_token}" "{url}?segment=EQ&start_date={start_date}&end_date={end_date}&page_number=1&page_size=100"'
            logging.info(f"CURL for debugging: {curl_cmd}")
            
            # Paginate through all results
            all_upstox_trades = []
            page = 1
            page_size = 100
            max_pages = 100  # Safety limit
            
            while page <= max_pages:
                params = {
                    "segment": "EQ",
                    "start_date": start_date,
                    "end_date": end_date,
                    "page_number": page,
                    "page_size": page_size,
                }
                
                logging.info(f"Fetching trades page {page}...")
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                if response.status_code != 200:
                    logging.error(f"Upstox trades API returned status {response.status_code}: {response.text}")
                    break
                
                data = response.json()
                
                if data.get("status") != "success":
                    error_msg = data.get("errors", [{"message": "Unknown error"}])[0].get("message", "Unknown error")
                    logging.error(f"Upstox trades API error: {error_msg}")
                    break
                
                page_trades = data.get("data", [])
                
                if not page_trades:
                    logging.info(f"No more trades on page {page}, stopping pagination")
                    break
                
                all_upstox_trades.extend(page_trades)
                logging.info(f"Page {page}: {len(page_trades)} trades (total: {len(all_upstox_trades)})")
                
                # If we got fewer than page_size, we've reached the end
                if len(page_trades) < page_size:
                    logging.info(f"Received {len(page_trades)} < {page_size}, reached end of data")
                    break
                
                page += 1
            
            logging.info(f"Upstox API returned {len(all_upstox_trades)} total trades across {page} pages")
            
            # Format trades to match our internal structure
            formatted_trades = []
            for trade in all_upstox_trades:
                trade_date = trade.get("trade_date")
                
                # Parse symbol - remove -EQ suffix if present
                symbol = trade.get("symbol", "")
                if symbol.endswith("-EQ"):
                    symbol = symbol[:-3]
                symbol = symbol.strip().upper()
                
                formatted_trade = {
                    "account_id": self.broker_user_id,
                    "trade_id": trade.get("trade_id"),
                    "order_id": None,  # Not available in this API
                    "exchange": trade.get("exchange", "NSE"),
                    "tradingsymbol": symbol,
                    "instrument_token": trade.get("instrument_token"),
                    "isin": trade.get("isin"),
                    "product": "CNC",  # Assume CNC for historical trades
                    "average_price": trade.get("price", 0),
                    "quantity": trade.get("quantity", 0),
                    "exchange_order_id": None,
                    "transaction_type": trade.get("transaction_type", ""),
                    "fill_timestamp": datetime.strptime(trade_date, "%Y-%m-%d") if trade_date else None,
                    "order_timestamp": None,
                    "exchange_timestamp": datetime.strptime(trade_date, "%Y-%m-%d") if trade_date else None,
                }
                formatted_trades.append(formatted_trade)
            
            logging.info(f"Formatted {len(formatted_trades)} trades")
            return formatted_trades
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error getting trades from Upstox API: {e}")
            return []
        except Exception as e:
            logging.error(f"Error getting trades from Upstox API: {e}")
            return []

    def place_order(self, order_details):
        """
        Place an order with the broker.
        """
        logging.debug(f"Placing order in Upstox: {order_details}")
        try:
            body = upstox_client.PlaceOrderRequest(
                quantity=order_details["quantity"],
                product=order_details["product"],
                validity=order_details["validity"],
                price=order_details.get("price", 0.0),
                instrument_token=order_details["instrument_token"],
                order_type=order_details["order_type"],
                transaction_type=order_details["transaction_type"],
                disclosed_quantity=order_details.get("disclosed_quantity", 0),
                trigger_price=order_details.get("trigger_price", 0.0),
                is_amo=order_details.get("is_amo", False),
            )
            api_response = self.order_api.place_order(body, "v2")
            return api_response.data
        except ApiException as e:
            logging.debug(f"Error placing order in Upstox: {e}")
            raise

    def load_entry_levels(self, file_path):
        """
        Load entry levels from a broker-specific file.
        """
        logging.debug(f"Loading entry levels from {file_path} for Upstox")
        if os.path.exists(file_path):
            return read_csv(file_path)
        return []

    def update_roi_master(self, data):
        """
        Update the ROI master file for the broker.
        """
        file_path = f"data/{self.broker_user_id}_roi_master.csv"
        logging.debug(f"Updating ROI master file for Upstox: {file_path}")
        write_csv(file_path, data)

    def update_trade_book(self, data):
        """
        Update the trade book master file for the broker.
        """
        file_path = f"data/{self.broker_user_id}_trade_book.csv"
        logging.debug(f"Updating trade book for Upstox: {file_path}")
        write_csv(file_path, data)

    def download_historical_trades(self, start_date, end_date):
        """
        Download historical trades from Upstox API.
        """
        logging.debug(
            f"Downloading historical trades for user {self.broker_user_id} from {start_date} to {end_date}"
        )
        all_trades = []
        page_number = 1
        page_size = 500  # As per Upstox API docs, max page size is 500

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        while True:
            url = f"https://api.upstox.com/v2/charges/historical-trades?start_date={start_date}&end_date={end_date}&page_size={page_size}&page_number={page_number}"

            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data.get("status") != "success":
                    logging.error(f"Error from Upstox API: {data.get('errors')}")
                    break

                trades = data.get("data", [])
                if not trades:
                    break

                all_trades.extend(trades)

                meta_data = data.get("meta_data", {})
                total_pages = meta_data.get("page", {}).get("total_pages", 1)

                if page_number >= total_pages:
                    break

                page_number += 1

            except requests.exceptions.RequestException as e:
                logging.error(f"Error downloading historical trades from Upstox: {e}")
                break

        # Transform data
        transformed_trades = []
        for trade in all_trades:
            transformed_trade = {
                "symbol": get_symbol_from_isin(trade.get("isin")),
                "isin": trade.get("isin"),
                "trade_date": trade.get("trade_date"),
                "exchange": trade.get("exchange"),
                "segment": trade.get("segment"),
                "series": trade.get("segment"),  # As per user mapping
                "trade_type": trade.get("transaction_type"),
                "auction": "FALSE",
                "quantity": trade.get("quantity"),
                "price": trade.get("price"),
                "trade_id": trade.get("trade_id"),
                "order_id": "NA",
                "order_execution_time": "NA",
            }
            transformed_trades.append(transformed_trade)

        return transformed_trades

    def get_historical_data(
        self, symbol, interval="day", start_date=None, end_date=None
    ):
        """
        Fetch historical candle data for a given symbol.
        - Fetches last 90 days of data if start_date and end_date are not provided.
        - Caches data locally for performance.
        """
        logging.debug(f"Getting historical data for {symbol}")

        if not self.history_api:
            self.login()

        instrument_key = self._get_instrument_key(symbol, "NSE_EQ")
        if not instrument_key:
            logging.error(f"Could not resolve instrument key for symbol: {symbol}")
            return None

        # Default to last 90 days if dates are not provided
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Format dates as YYYY-MM-DD string
        end_date_str = end_date.strftime("%Y-%m-%d")
        start_date_str = start_date.strftime("%Y-%m-%d")

        try:
            api_response = self.history_api.get_historical_candle_data(
                instrument_key=instrument_key,
                interval=interval,
                to_date=end_date_str,
                from_date=start_date_str,
                api_version="v2",
            )
            logging.debug(f"Successfully fetched historical data for {symbol}")
            return api_response.data.candles
        except ApiException as e:
            logging.error(f"Error fetching historical data from Upstox: {e}")
            return None
