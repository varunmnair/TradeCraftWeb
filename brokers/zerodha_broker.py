from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from kiteconnect import KiteConnect
from core.session_manager import SessionManager
from core.utils import read_csv, write_csv
import os
import logging

if TYPE_CHECKING:
    from core.session_manager import SessionManager


class ZerodhaBroker:
    TOKEN_ERROR = "Zerodha session expired. Please reconnect Zerodha."

    def __init__(self, user_id, api_key, access_token=None):
        super().__init__()
        self.broker_name = "zerodha"
        self.user_id = user_id
        self.api_key = api_key
        self.access_token = access_token
        self.session_manager: Optional[SessionManager] = None
        self.connection_id: Optional[int] = None
        self.kite: Optional[KiteConnect] = None
        self._trades = []
        self.TRANSACTION_TYPE_BUY = 'BUY'
        self.TRANSACTION_TYPE_SELL = 'SELL'
        self.GTT_TYPE_SINGLE = 'single'
        self.GTT_TYPE_OCO = 'two-leg'
        self.ORDER_TYPE_LIMIT = 'LIMIT'
        self.PRODUCT_CNC = 'CNC'

    def set_session_context(self, *, session_manager: SessionManager, connection_id: Optional[int]) -> None:
        self.session_manager = session_manager
        self.connection_id = connection_id

    def _get_access_token(self) -> str:
        if self.session_manager and self.connection_id:
            token = self.session_manager.get_access_token("zerodha", connection_id=self.connection_id)
            if not token:
                raise RuntimeError(self.TOKEN_ERROR)
            return token
        if self.access_token:
            return self.access_token
        raise RuntimeError(self.TOKEN_ERROR)

    def _ensure_kite(self) -> KiteConnect:
        if self.kite is None:
            self.kite = KiteConnect(api_key=self.api_key)
            token = self._get_access_token()
            self.kite.set_access_token(token)
        return self.kite

    def login(self):
        logging.debug(f"Logging in to Zerodha for user {self.user_id}")
        try:
            kite = self._ensure_kite()
            profile = kite.profile()
            logging.debug(f"Successfully logged in as {profile.get('user_name', 'unknown')}")
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error logging in to Zerodha: {e}")
            raise

    def logout(self):
        logging.debug(f"Logging out from Zerodha for user {self.user_id}")
        try:
            kite = self._ensure_kite()
            kite.invalidate_access_token()
            self.kite = None
            logging.debug("Successfully logged out from Zerodha.")
        except Exception as e:
            logging.debug(f"Error logging out from Zerodha: {e}")

    def get_holdings(self):
        logging.debug("Getting holdings from Zerodha")
        try:
            kite = self._ensure_kite()
            holdings = kite.holdings()
            normalized = []
            for h in holdings:
                normalized.append({
                    'tradingsymbol': h.get('tradingsymbol'),
                    'exchange': h.get('exchange'),
                    'instrument_token': h.get('instrument_token'),
                    'isin': h.get('isin'),
                    'product': h.get('product'),
                    'price': h.get('price', 0),
                    'quantity': h.get('quantity', 0),
                    'average_price': h.get('average_price', 0),
                    'last_price': h.get('last_price', 0),
                    'pnl': h.get('pnl', 0),
                    'day_change': h.get('day_change', 0),
                    'day_change_percentage': h.get('day_change_percentage', 0),
                })
            return normalized
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error getting holdings from Zerodha: {e}")
            return []

    def get_gtt_orders(self):
        logging.debug("Getting GTT orders from Zerodha")
        try:
            kite = self._ensure_kite()
            logging.info(f"Fetching GTTs from Zerodha for user {self.user_id}")
            gtts = kite.get_gtts()
            logging.info(f"Zerodha raw GTTs: {gtts}")
            normalized = []
            for g in gtts:
                # Log the raw GTT data to debug
                trigger_id = g.get('trigger_id') or g.get('id')
                logging.info(f"Processing GTT: trigger_id={trigger_id}, status={g.get('status')}")
                normalized.append({
                    'id': trigger_id,
                    'user_id': self.user_id,
                    'type': g.get('type'),
                    'created_at': g.get('created_at'),
                    'updated_at': g.get('updated_at'),
                    'expires_at': g.get('expires_at'),
                    'status': g.get('status'),
                    'condition': {
                        'exchange': g.get('exchange'),
                        'last_price': g.get('last_price'),
                        'tradingsymbol': g.get('tradingsymbol'),
                        'trigger_values': g.get('trigger_values'),
                    },
                    'orders': g.get('orders', []),
                })
            return normalized
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error getting GTT orders from Zerodha: {e}")
            return []

    def get_trades(self):
        file_path = f"data/{self.user_id}_trade_book.csv"
        logging.debug(f"Getting trades from {file_path} for Zerodha")
        if os.path.exists(file_path):
            self._trades = read_csv(file_path)
        logging.debug(f"Trades: {self._trades}")
        return self._trades

    def trades(self):
        logging.debug("Getting trades from Zerodha API")
        try:
            kite = self._ensure_kite()
            trades = kite.trades()
            normalized = []
            for t in trades:
                normalized.append({
                    'trade_id': t.get('trade_id'),
                    'order_id': t.get('order_id'),
                    'exchange': t.get('exchange'),
                    'tradingsymbol': t.get('tradingsymbol'),
                    'product': t.get('product'),
                    'average_price': t.get('average_price'),
                    'quantity': t.get('quantity'),
                    'transaction_type': t.get('transaction_type'),
                })
            return normalized
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error getting trades from Zerodha API: {e}")
            return []

    def place_order(self, order_details):
        logging.debug(f"Placing order in Zerodha: {order_details}")
        try:
            kite = self._ensure_kite()
            return kite.place_order(
                variety=order_details.get('variety', 'regular'),
                exchange=order_details['exchange'],
                tradingsymbol=order_details['tradingsymbol'],
                transaction_type=order_details['transaction_type'],
                quantity=order_details['quantity'],
                product=order_details['product'],
                order_type=order_details.get('order_type', 'LIMIT'),
                price=order_details.get('price'),
                trigger_price=order_details.get('trigger_price')
            )
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error placing order in Zerodha: {e}")
            raise

    def place_gtt(self, **kwargs):
        logging.debug(f"Placing GTT in Zerodha: {kwargs}")
        try:
            kite = self._ensure_kite()
            
            # Safely extract values with defaults
            last_price = kwargs.get('last_price') or kwargs.get('ltp') 
            if last_price is None:
                trigger_vals = kwargs.get('trigger_values', [])
                if trigger_vals:
                    last_price = trigger_vals[0]
            last_price = float(last_price) if last_price else 0.0
            
            trigger_price = kwargs.get('trigger_price')
            if trigger_price is None:
                trigger_vals = kwargs.get('trigger_values', [])
                trigger_price = trigger_vals[0] if trigger_vals else None
            trigger_price = float(trigger_price) if trigger_price else 0.0
            
            # Build order dict safely
            orders = kwargs.get('orders', [])
            order = orders[0] if orders else {}
            quantity = int(order.get('quantity', 0) or 0)
            price = float(order.get('price', 0) or 0)
            
            logging.debug(f"GTT params - last_price: {last_price}, trigger_price: {trigger_price}, quantity: {quantity}, price: {price}")
            
            return kite.place_gtt(
                trigger_type=kwargs.get('trigger_type', 'two-leg'),
                tradingsymbol=kwargs.get('tradingsymbol'),
                exchange=kwargs.get('exchange'),
                trigger_values=[trigger_price],
                last_price=last_price,
                orders=[{
                    "exchange": kwargs.get('exchange'),
                    "tradingsymbol": kwargs.get('tradingsymbol'),
                    "transaction_type": order.get('transaction_type', 'BUY'),
                    "quantity": quantity,
                    "order_type": order.get('order_type', 'LIMIT'),
                    "product": order.get('product', 'CNC'),
                    "price": price,
                }],
            )
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error placing GTT in Zerodha: {e}")
            raise

    def modify_gtt(self, gtt_order):
        logging.debug(f"Modifying GTT in Zerodha: {gtt_order}")
        try:
            kite = self._ensure_kite()
            return kite.modify_gtt(
                trigger_id=gtt_order['trigger_id'],
                tradingsymbol=gtt_order['tradingsymbol'],
                exchange=gtt_order['exchange'],
                trigger_values=gtt_order['trigger_values'],
                last_price=gtt_order['last_price'],
                orders=gtt_order['orders']
            )
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error modifying GTT in Zerodha: {e}")
            raise

    def cancel_gtt(self, order_id):
        logging.debug(f"Cancelling GTT in Zerodha: {order_id}")
        try:
            kite = self._ensure_kite()
            return kite.delete_gtt(trigger_id=order_id)
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Access token" in error_msg or "Invalid" in error_msg:
                self.kite = None
                raise RuntimeError(self.TOKEN_ERROR) from e
            logging.debug(f"Error cancelling GTT in Zerodha: {e}")
            raise

    def load_entry_levels(self, file_path):
        logging.debug(f"Loading entry levels from {file_path} for Zerodha")
        if os.path.exists(file_path):
            return read_csv(file_path)
        return []

    def update_roi_master(self, data):
        file_path = f"data/{self.user_id}_roi_master.csv"
        logging.debug(f"Updating ROI master file for Zerodha: {file_path}")
        write_csv(file_path, data)

    def update_trade_book(self, data):
        file_path = f"data/{self.user_id}_trade_book.csv"
        logging.debug(f"Updating trade book for Zerodha: {file_path}")
        write_csv(file_path, data)

    def download_historical_trades(self, start_date, end_date):
        logging.info("Downloading historical trades is not implemented for Zerodha yet.")
        return []

    def get_historical_data(self, symbol, interval, start_date, end_date):
        logging.warning("get_historical_data is not supported directly by ZerodhaBroker.")
        return None
